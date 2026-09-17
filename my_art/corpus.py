"""Contexte documentaire intégral, borné et isolé par œuvre ; pas d'embeddings."""

from dataclasses import asdict, dataclass
from hashlib import sha256
import io
import json
from pathlib import Path
import re
from typing import Protocol

from PIL import Image, ImageOps, UnidentifiedImageError
from pypdf import PdfReader

from .schemas import Artwork
from .discovery import discover_images


def within(root: Path, path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError("Un chemin sort du dossier autorisé de l'œuvre.")
    return resolved


@dataclass(frozen=True)
class Source:
    id: str
    document: str
    location: str
    text: str


@dataclass(frozen=True)
class Context:
    sources: list[Source]
    version: str

    def as_dict(self):
        return {"version": self.version, "sources": [asdict(s) for s in self.sources]}


class ContextProvider(Protocol):
    """Point de remplacement futur par une recherche textuelle ou vectorielle."""
    def retrieve(self, artwork_id: str, question: str) -> Context: ...


class Catalog:
    def __init__(self, data_dir: Path):
        self.root = data_dir.resolve()

    def artwork_dir(self, artwork_id: str) -> Path:
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", artwork_id):
            raise ValueError("Identifiant d'œuvre invalide.")
        return within(self.root, self.root / "artworks" / artwork_id)

    def get(self, artwork_id: str) -> Artwork:
        folder = self.artwork_dir(artwork_id)
        path = within(folder, folder / "metadata.json")
        if not path.is_file():
            if not folder.is_dir():
                raise ValueError(f"Dossier absent pour l'œuvre {artwork_id}.")
            artwork = Artwork(id=artwork_id, title=artwork_id.replace("-", " ").replace("_", " ").title(),
                              artist="Artiste non renseigné")
            return discover_images(artwork, folder)
        if path.stat().st_size > 64_000:
            raise ValueError("Notice trop volumineuse.")
        try:
            artwork = Artwork.model_validate_json(path.read_text(encoding="utf-8-sig"))
        except ValueError as exc:
            raise ValueError(f"Notice metadata.json invalide pour {artwork_id}.") from exc
        if artwork.id != artwork_id:
            raise ValueError("L'identifiant de la notice ne correspond pas au dossier.")
        return discover_images(artwork, folder)

    def list(self) -> list[Artwork]:
        directory = within(self.root, self.root / "artworks")
        if not directory.exists():
            return []
        return [self.get(p.name) for p in sorted(directory.iterdir()) if p.is_dir() and p.name != "documents"]

    def image_bytes(self, artwork: Artwork) -> bytes | None:
        if not artwork.image:
            return None
        folder = self.artwork_dir(artwork.id)
        path = within(folder, folder / artwork.image)
        if not path.is_file() or path.stat().st_size > 20 * 1024 * 1024:
            raise ValueError("Image absente ou supérieure à 20 Mio.")
        try:
            with Image.open(path) as original:
                if original.format not in {"PNG", "JPEG", "WEBP"}:
                    raise ValueError("L'image doit être un PNG, JPEG ou WEBP.")
                if getattr(original, "n_frames", 1) != 1:
                    raise ValueError("Fournir une image fixe.")
                image = ImageOps.exif_transpose(original).convert("RGB")
                image.thumbnail((1600, 1600))
                buffer = io.BytesIO()
                image.save(buffer, format="JPEG", quality=90)
                data = buffer.getvalue()
        except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
            raise ValueError("Image illisible ou trop grande.") from exc
        if len(data) > 3_500_000:
            raise ValueError("Image trop volumineuse après préparation pour Bedrock.")
        return data


class DirectContextProvider:
    def __init__(self, data_dir: Path, max_chars: int = 40_000):
        self.root = data_dir.resolve()
        self.max_chars = max_chars

    def retrieve(self, artwork_id: str, question: str = "") -> Context:
        Catalog(self.root).artwork_dir(artwork_id)  # Valider l'identifiant avant tout accès.
        folders = [within(self.root, self.root / "documents" / artwork_id),
                   within(self.root, self.root / "artworks" / "documents" / artwork_id),
                   within(self.root, self.root / "artworks" / artwork_id / "documents")]
        sources = []
        total = 0
        file_count = 0
        for folder in folders:
            if not folder.exists():
                continue
            paths = sorted(folder.rglob("*"))
            files = [within(folder, p) for p in paths if p.is_file()]
            file_count += len(files)
            if file_count > 30:
                raise ValueError("Maximum 30 fichiers par œuvre dans ce POC.")
            for path in files:
                if path.suffix.lower() not in {".md", ".txt", ".pdf"}:
                    raise ValueError(f"Format documentaire non pris en charge : {path.name}")
                if path.stat().st_size > 10 * 1024 * 1024:
                    raise ValueError(f"Document supérieur à 10 Mio : {path.name}")
                if path.suffix.lower() == ".pdf":
                    units = self._pdf_pages(path)
                else:
                    try:
                        units = [("texte", path.read_text(encoding="utf-8-sig"))]
                    except UnicodeError as exc:
                        raise ValueError(f"Document non encodé en UTF-8 : {path.name}") from exc
                for location, text in units:
                    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
                    for paragraph_index, paragraph in enumerate(paragraphs, 1):
                        # Les blocs très longs sont découpés sans perdre de texte.
                        for start in range(0, len(paragraph), 3000):
                            passage = paragraph[start:start + 3000]
                            total += len(passage)
                            if total > self.max_chars:
                                raise ValueError(
                                    f"Corpus trop long (limite {self.max_chars} caractères). "
                                    "Réduisez le corpus avant le test ; aucune troncature automatique.")
                            name = path.relative_to(self.root).as_posix()
                            locator = f"{location}, paragraphe {paragraph_index}, bloc {start // 3000 + 1}"
                            identity = json.dumps([artwork_id, name, locator, passage], ensure_ascii=False)
                            sid = "s-" + sha256(identity.encode()).hexdigest()[:20]
                            sources.append(Source(sid, name, locator, passage))
            if len(sources) > 150:
                raise ValueError("Trop de passages (maximum 150). Regroupez les documents.")
        version = sha256(json.dumps([asdict(s) for s in sources], ensure_ascii=False,
                                    sort_keys=True).encode()).hexdigest()
        return Context(sources, version)

    @staticmethod
    def _pdf_pages(path: Path):
        try:
            reader = PdfReader(path)
            if reader.is_encrypted or len(reader.pages) > 50:
                raise ValueError("PDF chiffré ou supérieur à 50 pages.")
            pages = [(f"page {i}", page.extract_text() or "")
                     for i, page in enumerate(reader.pages, 1)]
            if any(not text.strip() for _, text in pages):
                raise ValueError("PDF avec une page sans texte extractible : fournir une version "
                                 "texte ou OCR vérifiée. Aucune page n'est ignorée silencieusement.")
            return pages
        except Exception as exc:
            raise ValueError(f"Impossible d'extraire complètement le PDF {path.name}. "
                             "Vérifiez le texte, le chiffrement et la limite de 50 pages.") from exc


def with_uploads(context: Context, artwork_id: str, documents: list[tuple[str, bytes]],
                 max_chars: int = 40_000) -> Context:
    """Ajoute des TXT en mémoire, sans écrire de fichier ni partager entre œuvres."""
    if len(documents) > 10:
        raise ValueError("Maximum 10 documents personnels par demande.")
    sources = list(context.sources)
    total = sum(len(source.text) for source in sources)
    for index, (name, data) in enumerate(documents, 1):
        name = name.replace("\\", "/").rsplit("/", 1)[-1]
        if not name.lower().endswith(".txt") or len(data) > 1_000_000:
            raise ValueError("Les documents personnels doivent être des TXT de moins de 1 Mo.")
        try:
            text = data.decode("utf-8-sig")
        except UnicodeError as exc:
            raise ValueError("Les documents personnels doivent être encodés en UTF-8.") from exc
        if not text.strip() or "\x00" in text:
            raise ValueError("Document personnel vide ou non textuel.")
        for paragraph_index, paragraph in enumerate(re.split(r"\n\s*\n", text), 1):
            paragraph = paragraph.strip()
            for start in range(0, len(paragraph), 3000):
                passage = paragraph[start:start + 3000]
                total += len(passage)
                if total > max_chars:
                    raise ValueError(f"Corpus trop long (limite {max_chars} caractères), documents personnels inclus.")
                location = f"texte, paragraphe {paragraph_index}, bloc {start // 3000 + 1}"
                identity = json.dumps([artwork_id, index, name, location, passage], ensure_ascii=False)
                sources.append(Source("u-" + sha256(identity.encode()).hexdigest()[:20],
                                      f"Ajout personnel {index} : {name}", location, passage))
    if total > max_chars or len(sources) > 150:
        raise ValueError("Contexte trop volumineux : maximum 150 passages et limite de caractères dépassée.")
    version = sha256(json.dumps([asdict(s) for s in sources], ensure_ascii=False,
                                sort_keys=True).encode()).hexdigest()
    return Context(sources, version)
