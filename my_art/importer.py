"""Import reproductible d'un dossier art_gallery vers le catalogue local."""

from pathlib import Path

from PIL import Image

from .corpus import Catalog, within
from .schemas import Artwork


def import_artwork(source: Path, data_dir: Path) -> str:
    source = source.resolve()
    metadata = source / "metadata.json"
    artwork = Artwork.model_validate_json(metadata.read_text(encoding="utf-8-sig"))
    catalog = Catalog(data_dir)
    images = {v.file for v in artwork.views.values()}
    if artwork.image:
        images.add(artwork.image)
    files = [(metadata, catalog.artwork_dir(artwork.id) / "metadata.json")]
    for filename in sorted(images):
        path = within(source, source / filename)
        if path.stat().st_size > 20 * 1024 * 1024:
            raise ValueError("Image supérieure à 20 Mio.")
        with Image.open(path) as image:
            if image.format not in {"PNG", "JPEG", "WEBP"}:
                raise ValueError("Format d'image non pris en charge.")
            image.verify()
        target = within(catalog.artwork_dir(artwork.id), catalog.artwork_dir(artwork.id) / filename)
        files.append((path, target))
    documents = sorted(p for p in source.iterdir() if p.suffix.lower() in {".txt", ".md", ".pdf"})
    if not documents:
        raise ValueError("Aucun document TXT, Markdown ou PDF dans le dossier source.")
    for path in documents:
        path = within(source, path)
        if path.suffix.lower() in {".txt", ".md"}:
            path.read_text(encoding="utf-8-sig")  # Refuser les fichiers qui ne sont pas UTF-8.
        target = within(data_dir, data_dir / "documents" / artwork.id / path.name)
        files.append((path, target))
    # Vérifier les conflits avant toute écriture. Un second import identique est sans effet.
    contents = [(target, path.read_bytes()) for path, target in files]
    for target, content in contents:
        if target.exists() and target.read_bytes() != content:
            raise ValueError(f"Import refusé : fichier déjà présent et différent ({target.name}).")
    for target, content in contents:
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_bytes(content)
    return artwork.id
