from __future__ import annotations

from pathlib import Path

import typer

from art_agent.orchestrator import ArtAgentOrchestrator
from art_agent.types import TaskType

app = typer.Typer(add_completion=False, help="Agent IA pour enrichir des œuvres d'art.")


@app.command()
def generate(
    image_path: str = typer.Option(..., "--image-path", help="Chemin vers l'image à traiter."),
    task: TaskType = typer.Option("audio-description", "--task", help="Type de sortie : audio-description ou background-sound."),
    rag_dir: str = typer.Option("./data/rag", "--rag-dir", help="Dossier contenant les documents du RAG."),
    output_dir: str = typer.Option("./outputs", "--output-dir", help="Dossier de sortie des artefacts produits."),
):
    """Génère une audiodescription ou un fond sonore à partir d'une image."""
    orchestrator = ArtAgentOrchestrator(rag_dir=rag_dir, output_dir=output_dir)
    result = orchestrator.run(image_path=image_path, task=task)

    typer.echo(f"Task: {result.task}")
    typer.echo(f"Image: {result.image_path}")
    typer.echo(f"Output: {result.output_path}")
    typer.echo("\n--- Contenu généré ---")
    typer.echo(result.content)


@app.command()
def version():
    from art_agent import __version__

    typer.echo(__version__)


if __name__ == "__main__":
    app()
