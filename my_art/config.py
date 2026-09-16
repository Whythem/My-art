from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv

from .paths import ROOT
MODELS = {
    "eu.amazon.nova-pro-v1:0": True,
    "eu.amazon.nova-lite-v1:0": True,
    "eu.amazon.nova-2-lite-v1:0": True,
    "eu.amazon.nova-micro-v1:0": False,
}


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    region: str = "eu-west-3"
    model_id: str = "eu.amazon.nova-pro-v1:0"
    max_context_chars: int = 40_000
    max_output_tokens: int = 3_000

    def __post_init__(self):
        if self.model_id not in MODELS:
            raise ValueError("Modèle non pris en charge par ce POC. Choisir un modèle Nova configuré.")

    @classmethod
    def from_env(cls):
        load_dotenv(ROOT / ".env", override=False)
        directory = Path(os.getenv("MUSEUM_DATA_DIR") or "data")
        return cls(
            data_dir=(directory if directory.is_absolute() else ROOT / directory).resolve(),
            region=os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "eu-west-3",
            model_id=os.getenv("BEDROCK_MODEL_ID") or "eu.amazon.nova-pro-v1:0",
        )
