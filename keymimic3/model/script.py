"""
Script = metadata (name, loop, humanize) + two independent, parallel tracks:
`keyboard_blocks` and `mouse_blocks`. Both tracks start together when the
script runs and each proceeds through its own blocks at its own pace (see
execution.executor) - real recorded gaps within a track keep the two in
sync without needing any separate per-block timestamp.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .block import Block

SCRIPT_FORMAT_VERSION = 2


@dataclass
class Script:
    version: int = SCRIPT_FORMAT_VERSION
    thread_name: str = "Macro"
    loop: bool = True
    humanize: int = 0
    keyboard_blocks: List[Block] = field(default_factory=list)
    mouse_blocks: List[Block] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "thread_name": self.thread_name,
            "loop": self.loop,
            "humanize": self.humanize,
            "keyboard_blocks": [b.to_dict() for b in self.keyboard_blocks],
            "mouse_blocks": [b.to_dict() for b in self.mouse_blocks],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Script":
        return cls(
            version=d.get("version", SCRIPT_FORMAT_VERSION),
            thread_name=d.get("thread_name", "Macro"),
            loop=d.get("loop", True),
            humanize=d.get("humanize", 0),
            keyboard_blocks=[Block.from_dict(b) for b in d.get("keyboard_blocks", [])],
            mouse_blocks=[Block.from_dict(b) for b in d.get("mouse_blocks", [])],
        )

    @classmethod
    def empty(cls, thread_name: str = "Macro") -> "Script":
        return cls(thread_name=thread_name, keyboard_blocks=[], mouse_blocks=[])


class ScriptValidationError(ValueError):
    pass


def validate_script(script: Script) -> None:
    """
    Raise ScriptValidationError if the script cannot be started.

    An empty block (no steps/points) is not an error - it simply does
    nothing when run. Only one of the two tracks needs content.
    """
    if not script.keyboard_blocks and not script.mouse_blocks:
        raise ScriptValidationError("Script is empty (no keyboard or mouse blocks).")
    _validate_blocks(script.keyboard_blocks)
    _validate_blocks(script.mouse_blocks)


def _validate_blocks(blocks: List[Block]) -> None:
    for block in blocks:
        if block.kind == "repeat":
            if block.count < 1:
                raise ScriptValidationError(
                    f"Repeat block must run at least once (got {block.count})."
                )
            _validate_blocks(block.children)
