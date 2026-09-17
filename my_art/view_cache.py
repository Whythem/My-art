"""Simulation persistante de la préparation des plans, sans service externe."""

from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from uuid import uuid4

from .schemas import PreparedView

CACHE_DIR = ".generated_views"
GENERATOR_VERSION = "mock-original-copy-v1"
PROMPTS = {
    "foreground": "Isoler les éléments visibles du premier plan, sans reconstruire les zones cachées.",
    "midground": "Isoler les éléments visibles du second plan, sans reconstruire les zones cachées.",
}
LABELS = {"foreground": "Premier plan", "midground": "Second plan"}
NOTICE = "Simulation uniquement : copie de l’original, les plans ne sont pas réellement séparés."


def _identity(folder, artwork):
    from .corpus import within
    if not artwork.image:
        return None
    source = within(folder, folder / artwork.image)
    if not source.is_file() or source.stat().st_size > 20 * 1024 * 1024:
        return None
    return sha256(source.read_bytes()).hexdigest()


def _key(source_hash, focus):
    return sha256(json.dumps([source_hash, GENERATOR_VERSION, focus, PROMPTS[focus]],
                             ensure_ascii=False).encode()).hexdigest()


def _cached(folder, source_hash, focus):
    from .corpus import within
    key = _key(source_hash, focus)
    record_path = within(folder, folder / CACHE_DIR / f"{key}.json")
    image_path = within(folder, folder / CACHE_DIR / f"{key}.jpg")
    if not record_path.is_file() or not image_path.is_file():
        return None
    if record_path.stat().st_size > 64_000 or image_path.stat().st_size > 20 * 1024 * 1024:
        return None
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
        if (not isinstance(record, dict) or record.get("key") != key
                or record.get("sha256") != sha256(image_path.read_bytes()).hexdigest()):
            return None
        return PreparedView(file=f"{CACHE_DIR}/{key}.jpg", label=LABELS[focus], description=NOTICE)
    except (ValueError, OSError):
        return None


def cached_views(artwork, folder):
    """Lecture seule ; les fichiers fournis par l’utilisateur gardent la priorité."""
    missing = [focus for focus in PROMPTS if focus not in artwork.views]
    if not missing or not (folder / CACHE_DIR).is_dir():
        return {}
    source_hash = _identity(folder, artwork)
    if source_hash is None:
        return {}
    return {focus: view for focus in missing
            if (view := _cached(folder, source_hash, focus)) is not None}


@contextmanager
def _generation_lock(path):
    """Verrou interprocessus libéré par l’OS même après un arrêt brutal."""
    with path.open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        acquired = False
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError:
            pass
        try:
            yield acquired
        finally:
            if acquired:
                handle.seek(0)
                if os.name == "nt":
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _atomic_write(path, data):
    temporary = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_bytes(data)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


class SimulatedImageGenerator:
    """Point d’injection pour simuler un appel modèle ; aucune segmentation réelle."""

    def generate(self, original: bytes, focus: str, prompt: str) -> bytes:
        return original


def ensure_artwork_views(catalog, artwork_id, generator=None):
    """Prépare une fois les deux plans absents et renvoie les événements de cache."""
    from .corpus import within
    from .visuals import asset_path
    artwork = catalog.get(artwork_id)
    folder = catalog.artwork_dir(artwork_id)
    events = []
    needed = []
    for focus in PROMPTS:
        view = artwork.views.get(focus)
        if view is not None:
            try:
                asset_path(catalog, artwork_id, view.file)
                status = "cache_hit" if view.file.startswith(f"{CACHE_DIR}/") else "provided"
            except (ValueError, OSError):
                # Une vue fournie explicitement n’est jamais écrasée.
                status = "unavailable"
            events.append({"focus": focus, "status": status, "file": view.file,
                           "simulated_calls": 0, "external_api_calls": 0})
        else:
            needed.append(focus)
    if not needed:
        return events
    source_hash = _identity(folder, artwork)
    if source_hash is None:
        return events + [{"focus": focus, "status": "unavailable", "file": None,
                          "simulated_calls": 0, "external_api_calls": 0} for focus in needed]
    cache = within(folder, folder / CACHE_DIR)
    cache.mkdir(exist_ok=True)
    with _generation_lock(within(folder, cache / "generation.lock")) as acquired:
        if not acquired:
            return events + [{"focus": focus, "status": "pending", "file": None,
                              "simulated_calls": 0, "external_api_calls": 0} for focus in needed]
        original = None
        for focus in needed:
            existing = _cached(folder, source_hash, focus)
            if existing:
                events.append({"focus": focus, "status": "cache_hit", "file": existing.file,
                               "simulated_calls": 0, "external_api_calls": 0})
                continue
            if original is None:
                original = catalog.image_bytes(artwork)
                if _identity(folder, artwork) != source_hash:
                    raise ValueError("L’original a changé pendant la préparation. Réessayez.")
            key = _key(source_hash, focus)
            content = (generator or SimulatedImageGenerator()).generate(original, focus, PROMPTS[focus])
            image_path = within(folder, cache / f"{key}.jpg")
            _atomic_write(image_path, content)
            asset_path(catalog, artwork_id, f"{CACHE_DIR}/{key}.jpg")
            record = {"key": key, "source_sha256": source_hash, "sha256": sha256(content).hexdigest(),
                      "generator": GENERATOR_VERSION, "prompt": PROMPTS[focus], "focus": focus,
                      "created_at": datetime.now(timezone.utc).isoformat(),
                      "request_id": "mock-" + uuid4().hex, "simulated": True,
                      "placeholder": True, "notice": NOTICE, "external_api_calls": 0}
            # Le manifeste n’est publié qu’une fois l’image valide et complète.
            _atomic_write(within(folder, cache / f"{key}.json"), json.dumps(
                record, ensure_ascii=False, indent=2).encode("utf-8"))
            events.append({"focus": focus, "status": "generated", "file": f"{CACHE_DIR}/{key}.jpg",
                           "simulated_calls": 1, "external_api_calls": 0})
    return events
