"""Installation locale des corpus fictifs versionnés pour les essais."""

from pathlib import Path
import shutil

from .paths import ROOT


def init_demo(target: Path) -> None:
    if target.exists() and any(target.iterdir()):
        raise ValueError("Le dossier de données n'est pas vide. Aucun fichier n'a été remplacé.")
    shutil.copytree(ROOT / "examples" / "museum", target, dirs_exist_ok=True)
