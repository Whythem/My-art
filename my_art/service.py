"""Orchestration bornée : contexte -> modèle -> validation -> résultat."""

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Literal

from pydantic import ValidationError

from .config import MODELS, Settings
from .corpus import Catalog, Context, ContextProvider
from .bedrock import VisitModel
from .schemas import Artwork, Visit

CAPABILITIES = {"document_context": True, "visual_analysis": True,
                "embeddings": False, "image_generation": False,
                "speech_synthesis": False, "speech_transcription": False}


@dataclass
class Prepared:
    artwork: Artwork
    context: Context
    prompt: str
    image: bytes | None
    mode: str
    level: str

    def preview(self):
        return {"artwork": self.artwork.model_dump(), "context": self.context.as_dict(),
                "mode": self.mode, "level": self.level, "prompt": self.prompt,
                "image_attached": self.image is not None,
                "image_sha256": sha256(self.image).hexdigest() if self.image else None,
                "image_bytes": len(self.image) if self.image else 0}


class MuseumService:
    def __init__(self, settings: Settings, context_provider: ContextProvider, model: VisitModel):
        self.settings = settings
        self.catalog = Catalog(settings.data_dir)
        self.context_provider = context_provider
        self.model = model

    def prepare(self, artwork_id: str, question: str = "", mode: Literal["ask", "visit"] = "ask",
                level: Literal["simple", "detaille"] = "simple", include_image: bool = True) -> Prepared:
        if mode not in {"ask", "visit"} or level not in {"simple", "detaille"}:
            raise ValueError("Mode ou niveau inconnu.")
        if mode == "ask" and not question.strip():
            raise ValueError("Saisissez une question.")
        if len(question) > 2000:
            raise ValueError("Question trop longue (maximum 2000 caractères).")
        artwork = self.catalog.get(artwork_id)
        context = self.context_provider.retrieve(artwork_id, question)
        image = None
        if include_image and artwork.image:
            if not MODELS[self.settings.model_id]:
                raise ValueError("Nova Micro n'accepte pas d'image : désactivez l'analyse visuelle.")
            image = self.catalog.image_bytes(artwork)
        prompt = json.dumps({
            "task": "Répondre à la question" if mode == "ask" else "Créer une visite guidée courte",
            "language": "français", "level": level,
            "style": "Phrases courtes, vocabulaire courant, une idée par étape."
                     if level == "simple" else "Expliquer les termes et développer sans inventer.",
            "question": question.strip(), "artwork": artwork.model_dump(),
            "image_attached": image is not None,
            "documents": context.as_dict(),
        }, ensure_ascii=False)
        return Prepared(artwork, context, prompt, image, mode, level)

    def run(self, prepared: Prepared) -> dict:
        result = prepared.preview()
        result.update(model=self.settings.model_id, region=self.settings.region,
                      capabilities={**CAPABILITIES,
                                    "visual_analysis": MODELS[self.settings.model_id]},
                      calls=0, usage={})
        if not prepared.context.sources:
            result["visit"] = {"status": "insufficient_sources", "steps": []}
            result["message"] = "Aucun document exploitable pour cette œuvre. Ajoutez une notice."
            return result
        completion = self.model.complete(prepared.prompt, prepared.image)
        visit = self._validate(completion.payload, prepared)
        result.update(visit=visit.model_dump(), calls=1, usage=completion.usage,
                      request_id=completion.request_id,
                      message="Proposition IA : références vérifiées, contenu à relire."
                      if visit.status == "answered" else "La documentation ne permet pas de répondre.")
        return result

    @staticmethod
    def _validate(payload: dict, prepared: Prepared) -> Visit:
        try:
            visit = Visit.model_validate(payload)
        except ValidationError:
            raise ValueError("Réponse au format invalide. Aucun contenu généré n'est affiché.") from None
        if visit.status == "insufficient_sources":
            if visit.steps:
                raise ValueError("Réponse incohérente : refus documentaire accompagné d'affirmations.")
            return visit
        if not visit.steps:
            raise ValueError("Le modèle a renvoyé une réponse vide.")
        sources = {s.id: s for s in prepared.context.sources}
        normalize = lambda text: " ".join(text.split())
        for step in visit.steps:
            if step.basis == "document" and not step.evidence:
                raise ValueError("Affirmation documentaire sans source : réponse rejetée.")
            if step.basis == "observation" and prepared.image is None:
                raise ValueError("Observation visuelle sans image fournie : réponse rejetée.")
            if (step.visual_focus == "none") != (step.visual_target == ""):
                raise ValueError("Cible visuelle incohérente : réponse rejetée.")
            for evidence in step.evidence:
                source = sources.get(evidence.source_id)
                if source is None or normalize(evidence.quote) not in normalize(source.text):
                    raise ValueError("Référence ou citation non retrouvée dans le corpus : réponse rejetée.")
        return visit
