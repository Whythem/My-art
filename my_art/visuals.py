"""Contrat de génération d'images et fournisseur simulé, sans réseau."""

from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Literal, Protocol
from uuid import uuid4

from PIL import Image, UnidentifiedImageError

from .corpus import Catalog, within


@dataclass(frozen=True)
class VisualRequest:
    artwork_id: str
    focus: Literal["foreground", "midground", "background", "detail"]
    target: str


class ImageProvider(Protocol):
    def generate(self, request: VisualRequest) -> dict: ...


def asset_path(catalog: Catalog, artwork_id: str, filename: str) -> Path:
    folder = catalog.artwork_dir(artwork_id)
    path = within(folder, folder / filename)
    if not path.is_file() or path.stat().st_size > 20 * 1024 * 1024:
        raise ValueError("Vue préparée absente ou trop volumineuse.")
    try:
        with Image.open(path) as image:
            if image.format not in {"PNG", "JPEG", "WEBP"}:
                raise ValueError("Format de vue non pris en charge.")
            image.verify()
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise ValueError("Vue préparée illisible.") from exc
    return path


class MockImageProvider:
    """Simule la réponse d'un service d'édition avec les fichiers fournis par l'admin.

    Le texte target est journalisé, jamais exécuté ni utilisé comme chemin.
    Une vue préparée peut couvrir une zone plus large que le détail demandé.
    """
    def __init__(self, catalog: Catalog):
        self.catalog = catalog

    def generate(self, request: VisualRequest) -> dict:
        response = {
            "request_id": "mock-" + uuid4().hex,
            "provider": "local_prepared_images", "simulated": True,
            "external_api_calls": 0, "request": asdict(request),
            "status": "unavailable", "file": None,
        }
        artwork = self.catalog.get(request.artwork_id)
        view = artwork.views.get(request.focus)
        if view is None:
            response["message"] = "Aucune vue préparée pour cette demande. Consulter l'original."
            return response
        try:
            path = asset_path(self.catalog, artwork.id, view.file)
            fingerprint = sha256(path.read_bytes()).hexdigest()
        except (ValueError, OSError):
            response["message"] = "La vue préparée n'est pas exploitable. Consulter l'original."
            return response
        response.update(status="ready", file=view.file, label=view.label,
                        description=view.description, sha256=fingerprint,
                        cache_hit=True, simulated_calls=0,
                        message="Image réutilisée depuis le disque : aucun nouvel appel de génération.")
        return response
