from __future__ import annotations

import json
import os
from typing import Any
from urllib import request

import boto3


class BedrockClient:
    """Wrapper minimal pour appeler un modèle AWS Bedrock en mode texte.

    Supporte deux modes d’authentification :
    - AWS standard via boto3 (access_key / secret / session token)
    - endpoint proxy mutualisé via JWT/Bearer token (cas partagé, sans credentials AWS classiques)
    """

    def __init__(self, region_name: str | None = None, model_id: str | None = None):
        self.region_name = region_name or os.getenv("AWS_REGION", "eu-west-3")
        self.model_id = model_id or os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0")
        self.bearer_token = os.getenv("AWS_BEARER_TOKEN_BEDROCK")
        self.endpoint_url = os.getenv("BEDROCK_ENDPOINT_URL")

        if not self.endpoint_url and self.bearer_token:
            self.endpoint_url = f"https://bedrock-runtime.{self.region_name}.amazonaws.com"

        self.use_bearer_proxy = bool(self.bearer_token and self.endpoint_url)

        access_key = os.getenv("AWS_ACCESS_KEY_ID")
        secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        session_token = os.getenv("AWS_SESSION_TOKEN")

        if access_key and secret_key:
            client_kwargs: dict[str, Any] = {"region_name": self.region_name}
            client_kwargs["aws_access_key_id"] = access_key
            client_kwargs["aws_secret_access_key"] = secret_key
            if session_token:
                client_kwargs["aws_session_token"] = session_token
            self.client = boto3.client("bedrock-runtime", **client_kwargs)
            self.use_bearer_proxy = False
            return

        if os.getenv("AWS_PROFILE"):
            self.client = boto3.client("bedrock-runtime", region_name=self.region_name)
            return

        if self.use_bearer_proxy:
            self.client = None
            return

        raise RuntimeError(
            "Aucune authentification AWS valide n’a été trouvée. "
            "Configure AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY, ou un profil AWS, "
            "ou un token Bearer via AWS_BEARER_TOKEN_BEDROCK. L’endpoint AWS par défaut est "
            "https://bedrock-runtime.<region>.amazonaws.com."
        )

    def _extract_text(self, data: dict[str, Any]) -> str:
        if isinstance(data, dict):
            if "content" in data:
                content = data["content"]
                if isinstance(content, list):
                    text_blocks = []
                    for item in content:
                        if isinstance(item, dict):
                            if "text" in item:
                                text_blocks.append(str(item["text"]))
                            elif "content" in item:
                                nested = self._extract_text(item)
                                if nested:
                                    text_blocks.append(nested)
                    if text_blocks:
                        return "\n".join(text_blocks)

            for key in ("text", "output_text", "completion"):
                value = data.get(key)
                if isinstance(value, str) and value:
                    return value

            if "output" in data:
                nested = self._extract_text(data["output"])
                if nested:
                    return nested

        return ""

    def _invoke_with_bearer(self, body: dict[str, Any]) -> str:
        if not self.bearer_token:
            raise RuntimeError("Le mode Bearer nécessite AWS_BEARER_TOKEN_BEDROCK.")

        endpoint = (self.endpoint_url or f"https://bedrock-runtime.{self.region_name}.amazonaws.com").rstrip("/")
        url = f"{endpoint}/model/{self.model_id}:invoke"
        payload = json.dumps(body).encode("utf-8")

        req = request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.bearer_token}",
            },
            method="POST",
        )

        with request.urlopen(req, timeout=60) as response:
            raw = response.read()

        data = json.loads(raw.decode("utf-8"))
        return self._extract_text(data)

    def invoke(self, prompt: str) -> str:
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": prompt}]}
            ],
        }

        if self.use_bearer_proxy:
            return self._invoke_with_bearer(body)

        response = self.client.invoke_model(modelId=self.model_id, body=json.dumps(body))
        payload = response["body"].read()
        data = json.loads(payload)
        return self._extract_text(data)
