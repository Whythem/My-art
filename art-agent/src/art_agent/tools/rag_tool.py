from __future__ import annotations

from pathlib import Path


class RagTool:
    """Charge un ensemble de documents texte en local pour servir de contexte."""

    def __init__(self, rag_dir: str | Path):
        self.rag_dir = Path(rag_dir)

    def load_documents(self) -> list[str]:
        if not self.rag_dir.exists():
            return []

        docs: list[str] = []
        for file_path in sorted(self.rag_dir.rglob("*")):
            if file_path.is_file() and file_path.suffix.lower() in {".txt", ".md", ".json"}:
                try:
                    docs.append(file_path.read_text(encoding="utf-8"))
                except Exception:
                    continue
        return docs

    def build_context(self, query: str) -> str:
        documents = self.load_documents()
        if not documents:
            return (
                "Aucun document RAG disponible. Le système utilisera uniquement l'analyse de l'image "
                "et la consigne métier fournie pour produire une réponse."
            )

        text = "\n\n---\n\n".join(documents)
        return f"Contexte RAG disponible :\n\n{text}\n\nQuestion de contexte : {query}"
