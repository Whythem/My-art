"""Adaptateur AWS Bedrock Converse ; client créé lors de la première demande."""

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Protocol

import boto3
from botocore.config import Config
from botocore.exceptions import (BotoCoreError, ClientError, NoCredentialsError,
                                 PartialCredentialsError, ProxyConnectionError,
                                 EndpointConnectionError, SSLError, ReadTimeoutError,
                                 ConnectTimeoutError, ProfileNotFound, TokenRetrievalError)

from .config import Settings
from .schemas import VISIT_SCHEMA

# Consigne commune appliquée automatiquement aux questions et aux visites.
SYSTEM = Path(__file__).with_name("master_prompt.txt").read_text(encoding="utf-8")


@dataclass
class Completion:
    payload: dict
    usage: dict
    request_id: str | None = None


class VisitModel(Protocol):
    """Point de remplacement futur par un autre fournisseur de génération textuelle."""
    def complete(self, prompt: str, image: bytes | None) -> Completion: ...


class ModelError(RuntimeError):
    pass


class BedrockModel:
    def __init__(self, settings: Settings, client=None):
        self.settings = settings
        self._client = client

    def complete(self, prompt: str, image: bytes | None) -> Completion:
        content = [{"text": prompt}]
        if image:
            content.append({"image": {"format": "jpeg", "source": {"bytes": image}}})
        try:
            if self._client is None:
                # Authentification par clé Bedrock ou chaîne AWS standard (profil, SSO, IAM).
                if os.environ.get("AWS_BEARER_TOKEN_BEDROCK"):
                    # Une clé Bedrock suffit : éviter la recherche EC2 sur un poste local.
                    os.environ.setdefault("AWS_EC2_METADATA_DISABLED", "true")
                self._client = boto3.client(
                    "bedrock-runtime", region_name=self.settings.region,
                    config=Config(read_timeout=180, connect_timeout=10,
                                  retries={"total_max_attempts": 1}),
                )
            response = self._client.converse(
                modelId=self.settings.model_id,
                system=[{"text": SYSTEM}],
                messages=[{"role": "user", "content": content}],
                inferenceConfig={"maxTokens": self.settings.max_output_tokens, "temperature": 0},
                toolConfig={"tools": [{"toolSpec": {
                    "name": "present_visit",
                    "description": "Transmettre une proposition de visite documentée pour validation.",
                    "inputSchema": {"json": VISIT_SCHEMA},
                }}], "toolChoice": {"tool": {"name": "present_visit"}}},
            )
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "Unknown")
            messages = {
                "AccessDeniedException": "Accès Bedrock refusé : vérifier les droits et le profil d'inférence EU.",
                "UnrecognizedClientException": "Identifiants AWS invalides ou expirés.",
                "ExpiredTokenException": "Identifiants AWS expirés : renouveler la clé ou la session SSO.",
                "ThrottlingException": "Limite de débit Bedrock atteinte. Réessayez plus tard.",
                "ValidationException": "Bedrock refuse la requête : vérifier région, modèle et formats.",
                "ResourceNotFoundException": "Modèle ou profil d'inférence indisponible dans cette région.",
            }
            raise ModelError(messages.get(code, "Erreur du service Bedrock. Vérifiez votre compte AWS.")) from None
        except BotoCoreError as exc:
            messages = {
                NoCredentialsError: "Aucun identifiant AWS trouvé. Renseignez AWS_BEARER_TOKEN_BEDROCK dans .env ou configurez un profil AWS.",
                PartialCredentialsError: "Identifiants IAM incomplets : vérifier la configuration locale AWS.",
                ProfileNotFound: "Le profil AWS configuré est introuvable sur ce poste.",
                TokenRetrievalError: "Impossible de récupérer le jeton AWS : renouveler la session SSO ou la clé Bedrock.",
                ProxyConnectionError: "Connexion au proxy impossible. Vérifiez le proxy et le VPN du poste.",
                EndpointConnectionError: "Serveur Bedrock inaccessible. Vérifiez la connexion, le VPN et la région AWS.",
                SSLError: "Le certificat TLS AWS n'est pas reconnu. Vérifiez le certificat du proxy et AWS_CA_BUNDLE ; conservez la vérification TLS.",
                ConnectTimeoutError: "Délai de connexion à Bedrock dépassé. Vérifiez le réseau et le proxy.",
                ReadTimeoutError: "Bedrock n'a pas répondu dans le délai prévu. L'appel peut avoir été facturé ; vérifiez l'usage avant de relancer.",
            }
            message = next((text for kind, text in messages.items() if isinstance(exc, kind)),
                           "Erreur locale du SDK AWS. Vérifiez la configuration de l'authentification et du réseau.")
            # Le type est utile au diagnostic ; le message brut peut contenir des secrets.
            raise ModelError(f"{message} ({type(exc).__name__})") from None
        blocks = response.get("output", {}).get("message", {}).get("content", [])
        tools = [block["toolUse"] for block in blocks if "toolUse" in block]
        if (response.get("stopReason") != "tool_use" or len(tools) != 1
                or tools[0].get("name") != "present_visit"
                or not isinstance(tools[0].get("input"), dict)):
            raise ModelError("Réponse Bedrock incomplète ou non structurée. Rien n'a été publié.")
        return Completion(tools[0]["input"], response.get("usage", {}),
                          response.get("ResponseMetadata", {}).get("RequestId"))
