from __future__ import annotations

from pathlib import Path


class AudioTool:
    """Contrat pour les outils audio génératifs ou de synthèse."""

    def __init__(self, output_dir: str | Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_background_sound(self, prompt: str, output_name: str = "background_sound.txt") -> Path:
        file_path = self.output_dir / output_name
        file_path.write_text(
            f"PROMPT SONORE\n{prompt}\n\n"
            "Ce fichier est un placeholder de génération audio. "
            "Dans une vraie implémentation, il pourrait être envoyé à un moteur de synthèse sonore.",
            encoding="utf-8",
        )
        return file_path

    def generate_audio_description(self, prompt: str, output_name: str = "audio_description.txt") -> Path:
        file_path = self.output_dir / output_name
        file_path.write_text(prompt, encoding="utf-8")
        return file_path
