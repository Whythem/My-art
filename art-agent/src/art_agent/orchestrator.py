from __future__ import annotations

from pathlib import Path

from art_agent.config import settings
from art_agent.llm.bedrock_client import BedrockClient
from art_agent.tools.audio_tool import AudioTool
from art_agent.tools.image_analyzer import ImageAnalyzer
from art_agent.tools.rag_tool import RagTool
from art_agent.types import RagContext, TaskType, WorkflowResult


class ArtAgentOrchestrator:
    """Orchestre les différents outils pour produire un artefact enrichi."""

    def __init__(self, rag_dir: str | Path | None = None, output_dir: str | Path | None = None):
        self.rag_dir = Path(rag_dir or settings.rag_dir)
        self.output_dir = Path(output_dir or settings.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.image_analyzer = ImageAnalyzer()
        self.rag_tool = RagTool(self.rag_dir)
        self.audio_tool = AudioTool(self.output_dir)
        self.bedrock_client = BedrockClient(region_name=settings.aws_region, model_id=settings.bedrock_model_id)

    def run(self, image_path: str | Path, task: TaskType) -> WorkflowResult:
        image_analysis = self.image_analyzer.analyze(image_path)
        rag_context = self._build_rag_context(image_analysis, task)
        prompt = self._build_prompt(image_analysis, rag_context, task)
        llm_output = self.bedrock_client.invoke(prompt)

        output_path = self._persist_output(task, llm_output, image_analysis.image_path)

        return WorkflowResult(
            task=task,
            image_path=image_analysis.image_path,
            output_path=output_path,
            content=llm_output,
            metadata={
                "width": image_analysis.width or 0,
                "height": image_analysis.height or 0,
                "dominant_colors": ", ".join(image_analysis.dominant_colors),
                "rag_sources": len(rag_context.source_documents),
            },
        )

    def _build_rag_context(self, image_analysis, task: TaskType) -> RagContext:
        docs = self.rag_tool.load_documents()
        query = (
            "Renseigne-moi sur le contexte artistique, la description sensible, et le ton à adopter "
            f"pour une {task} adaptée à cette image."
        )
        summary = self.rag_tool.build_context(query)
        return RagContext(source_documents=docs, summary=summary)

    def _build_prompt(self, image_analysis, rag_context: RagContext, task: TaskType) -> str:
        if task == "audio-description":
            return (
                "Tu es un assistant d'accessibilité artistique. "
                "Tu dois rédiger une audiodescription concise et élégante pour une œuvre d'art. "
                "Utilise le contexte visuel et le contexte RAG donné. "
                "Respecte les principes de narration immersive mais accessible.\n\n"
                f"IMAGE:\n{image_analysis.description}\n\n"
                f"CONTEXT RAG:\n{rag_context.summary}\n\n"
                "RÉPONSE attendue : un texte d'audiodescription structuré, agréable à écouter, de 120 à 220 mots."
            )

        return (
            "Tu es un assistant de création sonore pour des œuvres d'art. "
            "Tu dois proposer un prompt ou une description de fond sonore qui accompagne l'image de manière cohérente. "
            "Prends en compte les couleurs, la composition, le sentiment et le contexte RAG.\n\n"
            f"IMAGE:\n{image_analysis.description}\n\n"
            f"CONTEXT RAG:\n{rag_context.summary}\n\n"
            "RÉPONSE attendue : un texte de direction artistique pour un fond sonore, avec ambiance, instruments, rythme et émotion."
        )

    def _persist_output(self, task: TaskType, content: str, image_path: str | Path) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        image_name = Path(image_path).stem
        suffix = "audiodescription" if task == "audio-description" else "background_sound"
        output_path = self.output_dir / f"{image_name}_{suffix}.md"
        output_path.write_text(content, encoding="utf-8")
        return output_path
