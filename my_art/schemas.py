from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Artwork(StrictModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")
    title: str = Field(min_length=1, max_length=200)
    artist: str = Field(min_length=1, max_length=200)
    image: str | None = None
    image_alt: str = Field(default="", max_length=1000)
    demo: bool = False


class Evidence(StrictModel):
    source_id: str = Field(min_length=1, max_length=80)
    quote: str = Field(min_length=10, max_length=1200)


class Step(StrictModel):
    title: str = Field(min_length=1, max_length=150)
    text: str = Field(min_length=1, max_length=2000)
    basis: Literal["document", "observation"]
    evidence: list[Evidence] = Field(max_length=6)
    visual_focus: Literal["none", "overview", "foreground", "background", "detail"]
    visual_target: str = Field(max_length=500)


class Visit(StrictModel):
    status: Literal["answered", "insufficient_sources"]
    steps: list[Step] = Field(max_length=4)


# Schéma volontairement simple pour le sous-ensemble JSON Schema de Nova.
VISIT_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["answered", "insufficient_sources"]},
        "steps": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "text": {"type": "string"},
                "basis": {"type": "string", "enum": ["document", "observation"]},
                "evidence": {"type": "array", "items": {
                    "type": "object", "properties": {
                        "source_id": {"type": "string"}, "quote": {"type": "string"}},
                    "required": ["source_id", "quote"]}},
                "visual_focus": {"type": "string", "enum": [
                    "none", "overview", "foreground", "background", "detail"]},
                "visual_target": {"type": "string"},
            },
            "required": ["title", "text", "basis", "evidence", "visual_focus", "visual_target"],
        }},
    },
    "required": ["status", "steps"],
}
