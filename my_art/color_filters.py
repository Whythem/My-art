"""Aides d'affichage pour le contraste et le daltonisme."""

from io import BytesIO

import numpy as np
from PIL import Image
from daltonize import daltonize as daltonize_library

OPTIONS = {
    "Normal": "normal",
    "Élevé (high contrast)": "high",
    "Doux (low contrast)": "low",
    "Protanopie — aide rouge–vert": "protanopia",
    "Deutéranopie — aide rouge–vert": "deuteranopia",
    "Tritanopie — aide bleu–jaune": "tritanopia",
}
DALTONIZE_TYPES = {
    "protanopia": "p",
    "deuteranopia": "d",
    "tritanopia": "t",
}

# Kept as the public set of color-aid modes used by the interface.
SIMULATION = DALTONIZE_TYPES


def color_aid_image(source, kind: str, strength: float = 0.6) -> bytes:
    """Return a PNG with daltonize's correction applied in memory."""
    if kind not in DALTONIZE_TYPES or not 0 <= strength <= 1:
        raise ValueError("Filtre inconnu ou intensité hors de l’intervalle 0–1.")

    image_source = BytesIO(source) if isinstance(source, bytes) else source
    with Image.open(image_source) as image:
        rgba = image.convert("RGBA")
        rgb = np.asarray(rgba.convert("RGB"), dtype=np.float32)
        linear_rgb = daltonize_library.gamma_correction(rgb)
        corrected = daltonize_library.daltonize(linear_rgb, DALTONIZE_TYPES[kind])
        corrected = daltonize_library.array_to_img(corrected)
        corrected_rgb = np.asarray(corrected, dtype=np.float32)
        blended = np.clip(rgb * (1 - strength) + corrected_rgb * strength, 0, 255).astype(np.uint8)
        output = Image.fromarray(blended, mode="RGB")
        output.putalpha(rgba.getchannel("A"))
        buffer = BytesIO()
        output.save(buffer, format="PNG")
        return buffer.getvalue()


def filter_markup(kind: str, strength: float = 0.6) -> str:
    """HTML/CSS constant et coefficients validés ; aucune image modifiée sur disque."""
    if kind not in OPTIONS.values():
        raise ValueError("Filtre inconnu.")
    effect = {"normal": "none", "high": "contrast(1.6)", "low": "contrast(0.75)"}.get(kind, "none")
    # Conteneurs dédiés : le logo, les icônes et les textes restent inchangés.
    return ('<style>div[class*="st-key-artwork_image_"] [data-testid="stImage"] img '
                  f'{{filter: {effect};}}</style>')
