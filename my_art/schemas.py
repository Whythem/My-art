from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PreparedView(StrictModel):
    file: str = Field(min_length=1, max_length=250)
    label: str = Field(min_length=1, max_length=150)
    description: str = Field(min_length=1, max_length=1000)


class Artwork(StrictModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")
    title: str = Field(min_length=1, max_length=200)
    artist: str = Field(min_length=1, max_length=200)
    image: str | None = None
    image_alt: str = Field(default="", max_length=1000)
    demo: bool = False
    views: dict[Literal["foreground", "midground", "background", "detail"], PreparedView] = Field(default_factory=dict)


class Evidence(StrictModel):
    source_id: str = Field(min_length=1, max_length=80)
    quote: str = Field(min_length=10, max_length=1200)


class Step(StrictModel):
    title: str = Field(min_length=1, max_length=150)
    text: str = Field(min_length=1, max_length=2000)
    basis: Literal["document", "observation"]
    evidence: list[Evidence] = Field(max_length=6)
    visual_focus: Literal["none", "overview", "foreground", "midground", "background", "detail"]
    visual_target: str = Field(max_length=500)


class Visit(StrictModel):
    status: Literal["answered", "insufficient_sources"]
    steps: list[Step] = Field(max_length=4)


# Même contrat côté modèle et validation locale, sans références JSON imbriquées.
def _visit_schema() -> dict:
    schema = Visit.model_json_schema()
    definitions = schema.pop("$defs", {})

    def inline(value):
        if isinstance(value, list):
            return [inline(item) for item in value]
        if not isinstance(value, dict):
            return value
        if "$ref" in value:
            return inline(definitions[value["$ref"].rsplit("/", 1)[-1]])
        return {key: ({name: inline(prop) for name, prop in item.items()}
                     if key == "properties" else inline(item))
                for key, item in value.items() if key != "title"}

    return inline(schema)


VISIT_SCHEMA = _visit_schema()
