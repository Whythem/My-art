from __future__ import annotations

from pathlib import Path

from PIL import Image

from art_agent.types import ImageAnalysis


class ImageAnalyzer:
    """Analyse basique d'une image pour fournir un premier contexte visuel."""

    def analyze(self, image_path: str | Path) -> ImageAnalysis:
        path = Path(image_path)
        with Image.open(path) as img:
            width, height = img.size
            dominant_colors = self._extract_dominant_colors(img)

        description = (
            f"Image détectée : {path.name}. "
            f"Dimensions {width}x{height}. "
            f"Palette dominante : {', '.join(dominant_colors) if dominant_colors else 'non détectée'}."
        )

        return ImageAnalysis(
            image_path=path,
            width=width,
            height=height,
            dominant_colors=dominant_colors,
            description=description,
        )

    def _extract_dominant_colors(self, img: Image.Image, max_colors: int = 5) -> list[str]:
        try:
            resized = img.convert("RGB").resize((32, 32))
            pixels = list(resized.getdata())
            colors = []
            for r, g, b in pixels:
                colors.append(f"#{r:02x}{g:02x}{b:02x}")
            unique = sorted(set(colors))
            return unique[:max_colors]
        except Exception:
            return []
