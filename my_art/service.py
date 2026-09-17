"""Orchestration bornée : contexte -> modèle -> validation -> résultat."""

from dataclasses import dataclass
from hashlib import sha256
import json
import unicodedata
from typing import Literal

from pydantic import ValidationError

from .config import MODELS, Settings
from .corpus import Catalog, Context, ContextProvider, with_uploads
from .bedrock import VisitModel
from .schemas import Artwork, Visit
from .visuals import ImageProvider, MockImageProvider, VisualRequest

CAPABILITIES = {"document_context": True, "visual_analysis": True,
                "embeddings": False, "image_generation": False,
                "speech_synthesis": False, "speech_transcription": False,
                "mock_image_generation": True}


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
    def __init__(self, settings: Settings, context_provider: ContextProvider, model: VisitModel,
                 image_provider: ImageProvider | None = None):
        self.settings = settings
        self.catalog = Catalog(settings.data_dir)
        self.context_provider = context_provider
        self.model = model
        self.image_provider = image_provider or MockImageProvider(self.catalog)

    def prepare(self, artwork_id: str, question: str = "", mode: Literal["ask", "visit"] = "ask",
                level: Literal["simple", "detaille"] = "simple", include_image: bool = True,
                documents: list[tuple[str, bytes]] | None = None) -> Prepared:
        if mode not in {"ask", "visit"} or level not in {"simple", "detaille"}:
            raise ValueError("Mode ou niveau inconnu.")
        if mode == "ask" and not question.strip():
            raise ValueError("Saisissez une question.")
        if len(question) > 2000:
            raise ValueError("Question trop longue (maximum 2000 caractères).")
        artwork = self.catalog.get(artwork_id)
        context = self.context_provider.retrieve(artwork_id, question)
        if documents:
            context = with_uploads(context, artwork_id, documents, self.settings.max_context_chars)
        image = None
        if include_image and artwork.image:
            if not MODELS[self.settings.model_id]:
                raise ValueError("Nova Micro n'accepte pas d'image : désactivez l'analyse visuelle.")
            image = self.catalog.image_bytes(artwork)
        prompt = json.dumps({
            "task": "Répondre à la question" if mode == "ask" else "Créer une visite guidée en exactement trois parties",
            "language": "français", "level": level,
            "style": "Phrases courtes, vocabulaire courant et concret, une idée par phrase. "
                     "Expliquer les mots difficiles. 40 à 80 mots par partie. Ton adulte et respectueux."
                     if level == "simple" else "Développer chaque partie sur 150 à 250 mots si les sources le permettent. "
                     "Expliquer composition, contexte, technique et interprétations documentées sans inventer.",
            "visit_structure": [
                {"visual_focus": "overview", "subject": "Présentation générale : peintre, date de création et informations sur l’œuvre. Signaler les informations absentes."},
                {"visual_focus": "foreground", "subject": "Premier plan uniquement : éléments, positions et explications documentées."},
                {"visual_focus": "midground", "subject": "Second plan uniquement : éléments, positions et explications documentées."},
            ] if mode == "visit" else None,
            "question": question.strip(), "artwork": artwork.model_dump(),
            "image_attached": image is not None,
            "response_contract": {
                "document_step": "evidence obligatoire: source_id exact et quote copiee mot a mot depuis documents",
                "observation_step": "evidence doit etre une liste vide; decrire uniquement ce qui est visible dans image",
                "when_uncertain": "renvoyer status=insufficient_sources et steps=[]",
            },
            "available_visuals": {focus: view.model_dump(exclude={"file"})
                                  for focus, view in artwork.views.items()},
            "documents": context.as_dict(),
        }, ensure_ascii=False)
        return Prepared(artwork, context, prompt, image, mode, level)

    def run(self, prepared: Prepared) -> dict:
        result = prepared.preview()
        result.update(model=self.settings.model_id, region=self.settings.region,
                      capabilities={**CAPABILITIES,
                                    "visual_analysis": MODELS[self.settings.model_id]},
                      calls=0, usage={}, visual_calls=[])
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
        for index, step in enumerate(visit.steps):
            if step.visual_focus not in {"none", "overview"}:
                visual = self.image_provider.generate(VisualRequest(
                    prepared.artwork.id, step.visual_focus, step.visual_target))
                result["visit"]["steps"][index]["visual"] = visual
                result["visual_calls"].append(visual)
        return result

    @staticmethod
    def _validate(payload: dict, prepared: Prepared) -> Visit:
        try:
            visit = Visit.model_validate(payload)
        except ValidationError as exc:
            # Ne jamais inclure les valeurs du modèle dans le message de diagnostic.
            known = {"status", "steps", "title", "text", "basis", "evidence",
                     "source_id", "quote", "visual_focus", "visual_target"}
            details = []
            for error in exc.errors(include_input=False, include_url=False)[:5]:
                location = ".".join(str(part) if isinstance(part, int) or part in known
                                    else "champ_inconnu" for part in error["loc"])
                details.append(f"{location}: {error['type']}")
            raise ValueError("Réponse au format invalide : " + "; ".join(details)
                             + ". Aucun contenu généré n'est affiché.") from None
        if visit.status == "insufficient_sources":
            if visit.steps:
                raise ValueError("Réponse incohérente : refus documentaire accompagné d'affirmations.")
            return visit
        if not visit.steps:
            raise ValueError("Le modèle a renvoyé une réponse vide.")
        if prepared.mode == "visit" and [step.visual_focus for step in visit.steps] != ["overview", "foreground", "midground"]:
            raise ValueError("La visite doit contenir trois parties : présentation générale, premier plan, second plan.")
        sources = {s.id: s for s in prepared.context.sources}
        def normalize(text: str) -> str:
            text = unicodedata.normalize("NFKC", text)
            text = (text.replace("’", "'").replace("‘", "'")
                .replace("“", '"').replace("”", '"')
                .replace("–", "-").replace("—", "-"))
            return " ".join(text.split()).strip("\"'")
        for step in visit.steps:
            if step.basis == "document" and not step.evidence:
                raise ValueError("Affirmation documentaire sans source : réponse rejetée.")
            if step.basis == "observation" and step.evidence:
                raise ValueError("Une observation visuelle ne doit pas contenir de citations documentaires.")
            if step.basis == "observation" and prepared.image is None:
                raise ValueError("Observation visuelle sans image fournie : réponse rejetée.")
            # Ces libellés pilotent l'affichage, sans ajouter d'affirmation sur l'œuvre.
            if step.visual_focus == "none":
                step.visual_target = ""
            elif not step.visual_target:
                step.visual_target = {
                    "overview": "Vue d'ensemble", "foreground": "Premier plan",
                    "midground": "Second plan", "background": "Arrière-plan",
                    "detail": "Détail non précisé",
                }[step.visual_focus]
            for evidence in step.evidence:
                source = sources.get(evidence.source_id)
                quote = normalize(evidence.quote)
                if source is None or quote not in normalize(source.text):
                    matches = [candidate for candidate in sources.values()
                               if quote in normalize(candidate.text)]
                    if len(matches) == 1:
                        # Le hash source_id est résolu par une citation exacte et unique.
                        evidence.source_id = matches[0].id
                        continue
                    raise ValueError("Référence ou citation non retrouvée dans le corpus : réponse rejetée.")
        return visit
