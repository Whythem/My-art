from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    aws_region: str = os.getenv("AWS_REGION", "eu-west-1")
    aws_profile: str | None = os.getenv("AWS_PROFILE")
    aws_access_key_id: str | None = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str | None = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_session_token: str | None = os.getenv("AWS_SESSION_TOKEN")
    aws_bearer_token_bedrock: str | None = os.getenv("AWS_BEARER_TOKEN_BEDROCK")
    bedrock_endpoint_url: str | None = os.getenv("BEDROCK_ENDPOINT_URL")
    bedrock_model_id: str = os.getenv(
        "BEDROCK_MODEL_ID",
        "google.gemma-3-27b-it",
    )
    rag_dir: str = os.getenv("RAG_DIR", "./data/rag")
    output_dir: str = os.getenv("OUTPUT_DIR", "./outputs")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    @property
    def rag_path(self) -> Path:
        return Path(self.rag_dir).resolve()

    @property
    def output_path(self) -> Path:
        return Path(self.output_dir).resolve()


settings = Settings()
