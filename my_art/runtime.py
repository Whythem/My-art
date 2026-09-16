"""Assemblage du musée et stockage des résultats, communs à la CLI et à l'UI."""

from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4

from .bedrock import BedrockModel
from .config import Settings
from .corpus import DirectContextProvider
from .paths import ROOT
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
