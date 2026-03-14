from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class SourceMeta:
    source_id: str
    source_tag: str
    fetched_at: str


class Parser(Protocol):
    def parse(self, payload: str): ...
