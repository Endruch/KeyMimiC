"""
Data model for the block-based script editor.

A `Script` is an ordered list of top-level `Block`s. A `Block` is a small
tagged union (kept flat on purpose, rather than a class hierarchy) with three
kinds:

- "block": an ordered list of `Step`s (press/release/click/move/sleep/...).
  Parallel key holds are expressed by ordering, e.g. press A, wait, press B,
  wait, release B, wait, release A.
- "repeat": a container that re-runs its `children` blocks `count` times.
  Children may themselves be repeat/mouse_path/block, so repeats can nest.
- "mouse_path": a single block holding every recorded mouse-move sample as a
  list of relative (dx, dy, dt) points, so a whole gesture stays one card in
  the editor instead of dozens of separate move steps.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field, asdict
from typing import List, Optional

STEP_TYPES = (
    "press", "release", "click", "right_click",
    "move", "move_to", "sleep", "log", "wait_with_keys",
)

BLOCK_KINDS = ("block", "repeat", "mouse_path")

# Rough categorisation used for the auto color-tag of a block.
_KEYBOARD_STEPS = {"press", "release"}
_MOUSE_STEPS = {"click", "right_click", "move", "move_to"}


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def _clean(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}


@dataclass
class Step:
    type: str
    key: Optional[str] = None
    dx: Optional[int] = None
    dy: Optional[int] = None
    x: Optional[int] = None
    y: Optional[int] = None
    duration: Optional[float] = None
    variation: Optional[float] = None
    message: Optional[str] = None
    taps: Optional[List[dict]] = None  # wait_with_keys: [{"key": .., "interval": ..}, ...]

    def to_dict(self) -> dict:
        return _clean(asdict(self))

    @classmethod
    def from_dict(cls, d: dict) -> "Step":
        return cls(**d)

    def to_text(self) -> str:
        """Render this step as one line of the block's mini text editor."""
        t = self.type
        if t in ("press", "release"):
            line = f"{t} {self.key}"
            if t == "press" and self.duration is not None:
                line += f" {self.duration}"
            return line
        if t in ("click", "right_click"):
            return t
        if t == "move":
            return f"move {self.dx} {self.dy}"
        if t == "move_to":
            return f"move_to {self.x} {self.y}"
        if t == "sleep":
            line = f"sleep {self.duration}"
            if self.variation:
                line += f" {self.variation}"
            return line
        if t == "log":
            return f"log {self.message}"
        if t == "wait_with_keys":
            parts = [f"wait_with_keys {self.duration}"]
            for tap in self.taps or []:
                parts.append(f"{tap['key']} {tap['interval']}")
            return " ".join(parts)
        return f"# unknown step: {t}"

    @classmethod
    def from_text(cls, line: str) -> "Step":
        """Parse one line of the block's mini text editor into a Step."""
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            raise ValueError("empty or comment line")

        tokens = re.findall(r'"[^"]*"|\'[^\']*\'|\S+', stripped)
        name = tokens[0].lower()
        args = tokens[1:]

        if name not in STEP_TYPES:
            raise ValueError(f"Unknown step type: {name!r}")

        if name == "press":
            if not args:
                raise ValueError("press requires a key name")
            duration = float(args[1]) if len(args) > 1 else None
            return cls(type="press", key=args[0], duration=duration)
        if name == "release":
            if not args:
                raise ValueError("release requires a key name")
            return cls(type="release", key=args[0])
        if name in ("click", "right_click"):
            return cls(type=name)
        if name == "move":
            if len(args) < 2:
                raise ValueError("move requires dx dy")
            return cls(type="move", dx=int(float(args[0])), dy=int(float(args[1])))
        if name == "move_to":
            if len(args) < 2:
                raise ValueError("move_to requires x y")
            return cls(type="move_to", x=int(float(args[0])), y=int(float(args[1])))
        if name == "sleep":
            if not args:
                raise ValueError("sleep requires a duration")
            variation = float(args[1]) if len(args) > 1 else None
            return cls(type="sleep", duration=float(args[0]), variation=variation)
        if name == "log":
            message = " ".join(a.strip("\"'") for a in args) if args else ""
            return cls(type="log", message=message)
        if name == "wait_with_keys":
            if not args:
                raise ValueError("wait_with_keys requires a duration")
            duration = float(args[0])
            taps = []
            rest = args[1:]
            for i in range(0, len(rest) - 1, 2):
                taps.append({"key": rest[i], "interval": float(rest[i + 1])})
            return cls(type="wait_with_keys", duration=duration, taps=taps)

        raise ValueError(f"Unhandled step type: {name!r}")


@dataclass
class MousePathPoint:
    dx: int
    dy: int
    dt: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "MousePathPoint":
        return cls(**d)


@dataclass
class Block:
    id: str = field(default_factory=new_id)
    kind: str = "block"
    enabled: bool = True
    collapsed: bool = False
    color: Optional[str] = None
    label: str = ""
    steps: List[Step] = field(default_factory=list)
    count: int = 2
    children: List["Block"] = field(default_factory=list)
    points: List[MousePathPoint] = field(default_factory=list)

    # -- constructors -----------------------------------------------------

    @staticmethod
    def new_block(steps: Optional[List[Step]] = None) -> "Block":
        return Block(kind="block", steps=list(steps or []))

    @staticmethod
    def new_repeat(count: int = 2, children: Optional[List["Block"]] = None) -> "Block":
        return Block(kind="repeat", count=count, children=list(children or []))

    @staticmethod
    def new_mouse_path(points: Optional[List[MousePathPoint]] = None) -> "Block":
        return Block(kind="mouse_path", points=list(points or []))

    # -- serialization ------------------------------------------------------

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "kind": self.kind,
            "enabled": self.enabled,
            "collapsed": self.collapsed,
            "color": self.color,
            "label": self.label,
        }
        if self.kind == "block":
            d["steps"] = [s.to_dict() for s in self.steps]
        elif self.kind == "repeat":
            d["count"] = self.count
            d["children"] = [c.to_dict() for c in self.children]
        elif self.kind == "mouse_path":
            d["points"] = [p.to_dict() for p in self.points]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Block":
        block = cls(
            id=d.get("id") or new_id(),
            kind=d.get("kind", "block"),
            enabled=d.get("enabled", True),
            collapsed=d.get("collapsed", False),
            color=d.get("color"),
            label=d.get("label", ""),
        )
        if block.kind == "block":
            block.steps = [Step.from_dict(s) for s in d.get("steps", [])]
        elif block.kind == "repeat":
            block.count = d.get("count", 2)
            block.children = [Block.from_dict(c) for c in d.get("children", [])]
        elif block.kind == "mouse_path":
            block.points = [MousePathPoint.from_dict(p) for p in d.get("points", [])]
        return block

    def clone(self) -> "Block":
        """Deep copy with a fresh id (and fresh ids for nested children)."""
        cloned = Block.from_dict(self.to_dict())
        cloned.id = new_id()
        if cloned.kind == "repeat":
            for child in cloned.children:
                child.id = new_id()
        return cloned

    # -- presentation helpers ------------------------------------------------

    @property
    def dominant_type(self) -> str:
        """Rough category used to pick the block's auto color tag."""
        if self.kind == "repeat":
            return "repeat"
        if self.kind == "mouse_path":
            return "mouse"
        counts = {"keyboard": 0, "mouse": 0, "sleep": 0, "log": 0, "wait": 0}
        for step in self.steps:
            if step.type in _KEYBOARD_STEPS:
                counts["keyboard"] += 1
            elif step.type in _MOUSE_STEPS:
                counts["mouse"] += 1
            elif step.type == "sleep":
                counts["sleep"] += 1
            elif step.type == "log":
                counts["log"] += 1
            elif step.type == "wait_with_keys":
                counts["wait"] += 1
        best = max(counts, key=lambda k: counts[k])
        return best if counts[best] > 0 else "empty"

    def summary(self) -> str:
        """Short one-line description shown on a collapsed card."""
        if self.kind == "repeat":
            return f"Repeat x{self.count} ({len(self.children)} block(s))"
        if self.kind == "mouse_path":
            total_dt = sum(p.dt for p in self.points)
            return f"Mouse Path: {len(self.points)} point(s), {total_dt:.1f}s"
        if not self.steps:
            return "Empty block"
        return " / ".join(s.to_text() for s in self.steps[:3]) + (
            " ..." if len(self.steps) > 3 else ""
        )
