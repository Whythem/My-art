from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


TaskType = Literal["audio-description", "background-sound"]


@dataclass
class ImageAnalysis:
    image_path: Path
    width: int | None = None
    height: int | None = None
    dominant_colors: list[str] = field(default_factory=list)
    description: str = ""
    art_context: str = ""


@dataclass
class RagContext:
    source_documents: list[str] = field(default_factory=list)
    summary: str = ""


@dataclass
class WorkflowResult:
    task: TaskType
    image_path: Path
    output_path: Path
    content: str
    metadata: dict[str, str | int | float | bool] = field(default_factory=dict)
