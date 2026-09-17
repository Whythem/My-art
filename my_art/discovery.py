"""Détection locale des originaux et des vues pédagogiques."""

from hashlib import sha256
import json
from pathlib import Path

from .schemas import Artwork, PreparedView

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
VIEW_ALIASES = {
    "foreground": {"firstplan", "premierplan", "foreground"},
    "midground": {"secondplan", "secondplan", "second_plan", "midground"},
    "background": {"arriereplan", "arriere_plan", "background"},
    "detail": {"detail"},
}


def _key(value: str) -> str:
    return value.lower().replace("-", "").replace("_", "")


def _images(folder: Path) -> list[Path]:
    return sorted(path for path in folder.iterdir()
                  if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES)


def _view_kind(path: Path) -> str | None:
    stem = _key(path.stem)
    for kind, aliases in VIEW_ALIASES.items():
        if stem in {_key(alias) for alias in aliases}:
            return kind
    return None


def discover_images(artwork: Artwork, folder: Path) -> Artwork:
    """Complète une notice en mémoire à partir de conventions de fichiers."""
    images = _images(folder) if folder.is_dir() else []
    view_paths = {path for path in images if _view_kind(path) is not None}
    candidates = [path for path in images if path not in view_paths]

    image = artwork.image
    if image is None:
        named = [path for path in candidates if _key(path.stem) == _key(artwork.id)]
        originals = [path for path in candidates if _key(path.stem) == "original"]
        if len(named) == 1:
            image = named[0].name
        elif not named and len(originals) == 1:
            image = originals[0].name
        elif not named and not originals and len(candidates) == 1:
            image = candidates[0].name

    views = dict(artwork.views)
    for kind in VIEW_ALIASES:
        if kind in views:
            continue
        matches = [path for path in view_paths if _view_kind(path) == kind]
        if len(matches) == 1:
            views[kind] = PreparedView(
                file=matches[0].name,
                label={
                    "foreground": "Premier plan",
                    "midground": "Second plan",
                    "background": "Arrière-plan",
                    "detail": "Détail",
                }[kind],
                description=f"Vue pédagogique préparée : {matches[0].stem}.",
            )

    from .view_cache import cached_views
    resolved = artwork.model_copy(update={"image": image, "views": views})
    views.update(cached_views(resolved, folder))
    return resolved.model_copy(update={"views": views})


def catalog_snapshot(data_dir: Path) -> str:
    """Retourne une empreinte stable des notices, images et documents du catalogue."""
    root = data_dir.resolve()
    records = []
    for scope in ("artworks", "documents"):
        directory = root / scope
        if not directory.exists():
            continue
        for path in sorted(path for path in directory.rglob("*") if path.is_file()):
            stat = path.stat()
            records.append((path.relative_to(root).as_posix(), stat.st_size,
                            stat.st_mtime_ns))
    return sha256(json.dumps(records, separators=(",", ":")).encode()).hexdigest()
