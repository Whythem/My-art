import argparse
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys
from uuid import uuid4

from .bedrock import BedrockModel, ModelError
from .config import MODELS, ROOT, Settings
from .corpus import Catalog, DirectContextProvider
from .service import MuseumService


def make_service(settings: Settings) -> MuseumService:
    return MuseumService(settings, DirectContextProvider(settings.data_dir, settings.max_context_chars),
                         BedrockModel(settings))


def save_result(result: dict, output: Path | None = None) -> Path:
    parent = output or ROOT / "output" / "museum"
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    folder = parent / run_id
    folder.mkdir(parents=True, exist_ok=False)
    path = folder / "result.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def init_demo(target: Path) -> None:
    if target.exists() and any(target.iterdir()):
        raise ValueError("Le dossier de données n'est pas vide. Aucun fichier n'a été remplacé.")
    shutil.copytree(ROOT / "examples" / "museum", target, dirs_exist_ok=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Musée documentaire local sur Bedrock.")
    parser.add_argument("--data-dir", type=Path, help="Remplacer le dossier administrateur.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-demo", help="Copier deux œuvres fictives dans un dossier vide, sans réseau.")
    sub.add_parser("list", help="Lister les œuvres locales, sans réseau.")
    for name in ("ask", "visit"):
        command = sub.add_parser(name)
        command.add_argument("artwork_id")
        if name == "ask":
            command.add_argument("question")
        command.add_argument("--level", choices=("simple", "detaille"), default="simple")
        command.add_argument("--model", choices=tuple(MODELS))
        command.add_argument("--text-only", action="store_true")
        command.add_argument("--dry-run", action="store_true", help="Aperçu local, aucun appel Bedrock.")
    args = parser.parse_args(argv)
    try:
        settings = Settings.from_env()
        if args.data_dir:
            settings = replace(settings, data_dir=args.data_dir.resolve())
        if args.command == "init-demo":
            init_demo(settings.data_dir)
            print(f"Deux œuvres fictives installées dans {settings.data_dir}.")
            return 0
        if args.command == "list":
            artworks = Catalog(settings.data_dir).list()
            for art in artworks:
                print(f"{art.id} — {art.title}" + (" [DÉMONSTRATION FICTIVE]" if art.demo else ""))
            if not artworks:
                print("Catalogue vide. Ajouter des œuvres ou lancer : python -m my_art init-demo")
            return 0
        if args.model:
            settings = replace(settings, model_id=args.model)
        service = make_service(settings)
        prepared = service.prepare(args.artwork_id, getattr(args, "question", ""),
                                   args.command, args.level, not args.text_only)
        if args.dry_run:
            result = {**prepared.preview(), "status": "dry_run", "calls": 0,
                      "model": settings.model_id, "region": settings.region}
            print(f"Aperçu : {len(prepared.context.sources)} passages ; "
                  f"image jointe : {'oui' if prepared.image else 'non'} ; aucun appel API.")
        else:
            print(f"Modèle : {settings.model_id}. Au maximum un appel Bedrock facturable.", flush=True)
            result = service.run(prepared)
            print(result["message"])
            sources = {s.id: s for s in prepared.context.sources}
            for step in result["visit"]["steps"]:
                print(f"\n{step['title']}\n{step['text']}")
                for evidence in step["evidence"]:
                    source = sources[evidence["source_id"]]
                    print(f"  Source : {source.document}, {source.location}\n  « {evidence['quote']} »")
                if step["visual_focus"] != "none":
                    print(f"  Suggestion visuelle (non générée) : {step['visual_target']}")
        print(f"Résultat local : {save_result(result)}")
        return 0
    except (ValueError, ModelError, OSError) as exc:
        message = str(exc) if isinstance(exc, (ValueError, ModelError)) else "Erreur de lecture ou d'écriture locale."
        print(f"Erreur : {message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
