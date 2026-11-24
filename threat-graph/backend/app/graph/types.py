from dataclasses import dataclass, field
from typing import Any


@dataclass
class GraphNode:
    key: str
    type: str
    label: str
    properties: dict[str, Any] = field(default_factory=dict)
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = self.key.split(":", 1)[-1]


@dataclass
class GraphEdge:
    source: str
    target: str
    relationship: str
    provenance: str = "observed"
    confidence: float = 0.5
    strength: float = 0.5
    properties: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.source}|{self.relationship}|{self.target}|{self.provenance}"
