import json
from unittest.mock import patch

from art_agent.llm.bedrock_client import BedrockClient


def test_bedrock_client_uses_bearer_token_when_no_aws_credentials(monkeypatch):
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "shared-token")
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    monkeypatch.delenv("AWS_SESSION_TOKEN", raising=False)
    monkeypatch.setenv("AWS_REGION", "eu-west-1")
    monkeypatch.setenv("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0")

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps({"content": [{"type": "text", "text": "ok"}]}).encode("utf-8")

    with patch("urllib.request.urlopen", return_value=FakeResponse()) as mock_urlopen:
        client = BedrockClient()
        result = client.invoke("bonjour")

    assert result == "ok"
    assert client.bearer_token == "shared-token"
    assert mock_urlopen.called
