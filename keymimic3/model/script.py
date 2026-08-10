"""Script = metadata (name, loop, humanize) + an ordered list of top-level Blocks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .block import Block

SCRIPT_FORMAT_VERSION = 1


@dataclass
class Script:
    version: int = SCRIPT_FORMAT_VERSION
    thread_name: str = "Macro"
    loop: bool = True
    humanize: int = 0
    blocks: List[Block] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "thread_name": self.thread_name,
            "loop": self.loop,
            "humanize": self.humanize,
            "blocks": [b.to_dict() for b in self.blocks],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Script":
        return cls(
            version=d.get("version", SCRIPT_FORMAT_VERSION),
            thread_name=d.get("thread_name", "Macro"),
            loop=d.get("loop", True),
            humanize=d.get("humanize", 0),
            blocks=[Block.from_dict(b) for b in d.get("blocks", [])],
        )

    @classmethod
    def empty(cls, thread_name: str = "Macro") -> "Script":
        return cls(thread_name=thread_name, blocks=[])


class ScriptValidationError(ValueError):
    pass


def validate_script(script: Script) -> None:
    """
    Raise ScriptValidationError if the script cannot be started.

    An empty block (no steps) is not an error - it simply does nothing when run.
    """
    if not script.blocks:
        raise ScriptValidationError("Script has no blocks.")
    _validate_blocks(script.blocks)


def _validate_blocks(blocks: List[Block]) -> None:
    for block in blocks:
        if block.kind == "repeat":
            if block.count < 1:
                raise ScriptValidationError(
                    f"Repeat block must run at least once (got {block.count})."
                )
            _validate_blocks(block.children)
