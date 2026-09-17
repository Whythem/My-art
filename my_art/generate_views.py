"""Test d'édition d'un tableau via OpenAI Images, sans RAG ni orchestrateur."""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI
from PIL import Image, UnidentifiedImageError


from .paths import ROOT
MAX_INPUT_BYTES = 20 * 1024 * 1024
FORMATS = {"PNG": ("png", "image/png"), "JPEG": ("jpg", "image/jpeg"),
           "WEBP": ("webp", "image/webp")}
VIEWS = ("premier_plan", "arriere_plan", "detail")

BASE_PROMPT = """Crée une vue pédagogique modifiée pour un musée à partir de
l'image fournie. Cette image est le tableau à éditer, pas une inspiration pour
une nouvelle peinture. Préserve autant que possible les couleurs, les textures,
les traits, les visages et les proportions des éléments conservés. Conserve le
cadrage global et la position des éléments. Ne complète aucune partie cachée.
Ne crée aucun personnage, objet, décor ou détail supplémentaire. Ne rajoute pas
de texte, de légende ou de signature. Remplace les régions exclues par un gris
clair uni, sans texture, au lieu de reconstruire ce qui se trouve derrière.
Si les plans sont ambigus, reste conservateur : n'invente pas de séparation.
"""


def build_prompts(detail: str) -> dict[str, str]:
    return {
        "premier_plan": BASE_PROMPT + "\nConserve uniquement les éléments visibles "
        "du premier plan. Masque les autres plans avec le gris clair uni.",
        "arriere_plan": BASE_PROMPT + "\nConserve uniquement les portions déjà "
        "visibles de l'arrière-plan. Remplace le premier plan par du gris clair "
        "uni, y compris les trous ainsi laissés. Ne reconstitue jamais le décor "
        "caché derrière les personnages ou objets."
    }


def read_image(path: Path) -> tuple[bytes, dict]:
    if not path.is_file():
        raise ValueError(f"Image introuvable : {path}")
    if path.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError("Pour ce test, l'image doit faire au maximum 20 Mio.")
    content = path.read_bytes()
    try:
        with Image.open(io.BytesIO(content)) as img:
            if img.format not in FORMATS:
                raise ValueError("Formats acceptés : PNG, JPEG et WEBP.")
            if getattr(img, "n_frames", 1) != 1:
                raise ValueError("Fournir une image fixe, sans animation.")
            extension, mime = FORMATS[img.format]
            metadata = {"width": img.width, "height": img.height,
                        "extension": extension, "mime": mime}
            img.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("Image illisible, corrompue ou trop grande.") from exc
    return content, metadata


def decode_png(response) -> bytes:
    if not response.data or not response.data[0].b64_json:
        raise ValueError("L'API n'a renvoyé aucune image encodée en base64.")
    try:
        content = base64.b64decode(response.data[0].b64_json, validate=True)
        with Image.open(io.BytesIO(content)) as img:
            if img.format != "PNG":
                raise ValueError("Le résultat n'est pas au format PNG demandé.")
            img.verify()
    except (ValueError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("L'API a renvoyé une image PNG invalide.") from exc
    return content


def describe_error(exc: Exception) -> str:
    # Ne pas enregistrer le corps brut d'une erreur HTTP ni une clé éventuelle.
    if isinstance(exc, APITimeoutError):
        return ("Délai API dépassé. La requête peut avoir été traitée et facturée. "
                "Vérifiez votre usage avant de relancer.")
    if isinstance(exc, APIStatusError):
        messages = {
            400: "Requête refusée : vérifiez les paramètres, l'image et la consigne.",
            401: "Clé API invalide ou expirée. Vérifiez votre fichier .env.",
            403: "Accès refusé : vérifiez les permissions du projet et du modèle.",
            404: "Modèle indisponible : vérifiez OPENAI_IMAGE_MODEL et vos accès.",
            429: "Quota, crédits ou limite de débit atteints. Vérifiez le compte API.",
        }
        return messages.get(exc.status_code, f"Erreur du service API (HTTP {exc.status_code}).")
    if isinstance(exc, APIConnectionError):
        return "Connexion API interrompue. Vérifiez le réseau et l'usage avant de relancer."
    if isinstance(exc, ValueError):
        return str(exc)
    if isinstance(exc, OSError):
        return "Échec d'accès aux fichiers : vérifiez les permissions et l'espace disponible."
    return f"Erreur inattendue ({type(exc).__name__})."


def save_manifest(folder: Path, manifest: dict) -> None:
    target = folder / "manifest.json"
    temporary = folder / "manifest.tmp"
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(target)


def generate(client, source: bytes, metadata: dict, folder: Path, manifest: dict) -> bool:
    """Un appel par vue ; chaque appel reçoit exactement l'original."""
    manifest["status"] = "running"
    save_manifest(folder, manifest)
    for view in manifest["views"]:
        print(f"Génération : {view['name']}…", flush=True)
        view["status"] = "running"
        save_manifest(folder, manifest)
        try:
            response = client.images.edit(
                model=manifest["model"],
                image=(f"original.{metadata['extension']}", source, metadata["mime"]),
                prompt=view["prompt"],
                n=1,
                size=manifest["size"],
                quality=manifest["quality"],
                output_format="png",
            )
            content = decode_png(response)
            filename = f"{view['name']}.png"
            (folder / filename).write_bytes(content)
            view.update(status="generated_unreviewed", file=filename)
            if response.usage is not None:
                view["usage"] = response.usage.model_dump(mode="json")
        except (APIStatusError, APIConnectionError, ValueError, OSError) as exc:
            message = describe_error(exc)
            view.update(status="failed", error=message)
            manifest["status"] = "failed"
            save_manifest(folder, manifest)
            print(message, file=sys.stderr)
            return False
        save_manifest(folder, manifest)
    manifest["status"] = "completed_unreviewed"
    save_manifest(folder, manifest)
    return True


def main(argv: list[str] | None = None) -> int:
    load_dotenv(ROOT / ".env", override=False)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, help="Chemin du tableau PNG, JPEG ou WEBP.")
    parser.add_argument("--output", type=Path, default=ROOT / "output" / "imagegen")
    parser.add_argument("--views", nargs="+", choices=VIEWS, default=list(VIEWS))
    parser.add_argument("--detail", default="le sujet principal du tableau",
                        help="Élément à isoler pour la vue detail.")
    parser.add_argument("--model", default=os.getenv("OPENAI_IMAGE_MODEL") or "gpt-image-2")
    parser.add_argument("--quality", choices=("low", "medium", "high", "auto"), default="medium")
    parser.add_argument("--size", choices=("auto", "1024x1024", "1536x1024", "1024x1536"),
                        default="auto")
    parser.add_argument("--dry-run", action="store_true",
                        help="Préparer les consignes sans clé API, réseau ni facturation.")
    args = parser.parse_args(argv)
    if not args.detail.strip():
        parser.error("--detail ne doit pas être vide.")
    if not args.dry_run and not os.getenv("OPENAI_API_KEY", "").strip():
        parser.error("OPENAI_API_KEY manque. Renseignez .env ou utilisez --dry-run.")
    try:
        source, metadata = read_image(args.image)
        prompts = build_prompts(args.detail.strip())
        names = list(dict.fromkeys(args.views))
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
        folder = args.output.resolve() / run_id
        folder.mkdir(parents=True, exist_ok=False)
        original_name = f"original.{metadata['extension']}"
        (folder / original_name).write_bytes(source)
        manifest = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "dry_run" if args.dry_run else "pending",
            "original": original_name,
            "original_sha256": hashlib.sha256(source).hexdigest(),
            "input": metadata,
            "model": args.model, "quality": args.quality, "size": args.size,
            "notice": "Vues pédagogiques modifiées par IA ; validation humaine requise. "
                      "Les consignes ne garantissent pas la fidélité des pixels.",
            "views": [{"name": name, "prompt": prompts[name], "status": "pending"}
                      for name in names],
        }
        save_manifest(folder, manifest)
        print(f"Dossier : {folder}", flush=True)
        if args.dry_run:
            print(f"Simulation : {len(names)} consignes préparées, aucun appel API.")
            return 0
        print(f"{len(names)} appel(s) API payant(s), modèle {args.model}, qualité {args.quality}.",
              flush=True)
        # Pas de relance automatique d'une génération potentiellement facturable.
        with OpenAI(timeout=600.0, max_retries=0) as client:
            success = generate(client, source, metadata, folder, manifest)
        if not success:
            return 1
        print("Images enregistrées. Comparez-les à l'original avant utilisation.")
        return 0
    except (ValueError, OSError) as exc:
        print(describe_error(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nInterrompu. Consultez le manifest et l'usage API avant de relancer.", file=sys.stderr)
        sys.exit(130)
