"""
Data model for the block-based script editor.

A `Script` has two independent, parallel tracks - `keyboard_blocks` and
`mouse_blocks` - each an ordered list of top-level `Block`s that runs on its
own executor, both started together (see `execution.executor`). A `Block` is
a small tagged union (kept flat on purpose, rather than a class hierarchy)
with three kinds:

- "block": keyboard-only, an ordered list of `Step`s (press/release/sleep/
  log/wait_with_keys). Only ever lives in `keyboard_blocks`. Holding two
  keys "at once" is expressed by ordering, e.g. press A, wait, press B,
  wait, release B, wait, release A.
- "mouse_path": mouse-only, a single block holding every recorded mouse
  sample (moves and button down/up) as a list of typed points, so a whole
  gesture-with-clicks stays one card instead of dozens of tiny ones. Only
  ever lives in `mouse_blocks`.
- "repeat": a container that re-runs its `children` blocks `count` times.
  Belongs to whichever track it's placed in - all of its children must be
  that same track's kind (repeats may nest).
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field, asdict
from typing import List, Optional

STEP_TYPES = ("press", "release", "sleep", "log", "wait_with_keys")
MOUSE_POINT_KINDS = ("move", "left_down", "left_up", "right_down", "right_up")

BLOCK_KINDS = ("block", "repeat", "mouse_path")


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def _clean(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}


@dataclass
class Step:
    """A keyboard-track action. Lives only inside a "block"-kind Block."""

    type: str
    key: Optional[str] = None
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
    """
    One sample on the mouse track: either an absolute cursor position to
    move to, or a button down/up event (fired wherever the cursor currently
    is). Absolute coordinates (not relative deltas) are used deliberately -
    Windows applies pointer-acceleration curves to relative SendInput
    moves, which made played-back movement drift from where it was
    recorded; absolute moves land exactly on the recorded pixel every time.
    """

    kind: str = "move"  # one of MOUSE_POINT_KINDS
    x: int = 0
    y: int = 0
    dt: float = 0.0  # delay before this point fires, relative to the previous one

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
    collapsed: bool = True
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
            collapsed=d.get("collapsed", True),
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
        """Deep copy with a fresh id for itself and every nested descendant
        (not just direct children) - otherwise duplicating a Repeat-of-Repeats
        would leave duplicate ids alive deeper in the tree."""
        cloned = Block.from_dict(self.to_dict())
        _reassign_ids(cloned)
        return cloned

    # -- presentation helpers ------------------------------------------------

    @property
    def dominant_type(self) -> str:
        """Rough category used to pick the block's auto color tag."""
        if self.kind == "repeat":
            return "repeat"
        if self.kind == "mouse_path":
            return "mouse"
        counts = {"keyboard": 0, "sleep": 0, "log": 0, "wait": 0}
        for step in self.steps:
            if step.type in ("press", "release"):
                counts["keyboard"] += 1
            elif step.type == "sleep":
                counts["sleep"] += 1
            elif step.type == "log":
                counts["log"] += 1
            elif step.type == "wait_with_keys":
                counts["wait"] += 1
        best = max(counts, key=lambda k: counts[k])
        return best if counts[best] > 0 else "empty"

    def estimated_duration(self) -> float:
        """
        Rough total seconds this block takes to run, used to size its card
        on the timeline. Only counts explicit waits (sleep, a press's hold
        duration, wait_with_keys, the dt between mouse points) - instantaneous
        single actions don't meaningfully add to it.
        """
        if self.kind == "mouse_path":
            return sum(p.dt for p in self.points)
        if self.kind == "repeat":
            inner = sum(child.estimated_duration() for child in self.children)
            return inner * max(self.count, 1)
        total = 0.0
        for step in self.steps:
            if step.type == "sleep":
                total += step.duration or 0.0
            elif step.type == "press" and step.duration:
                total += step.duration
            elif step.type == "wait_with_keys":
                total += step.duration or 0.0
        return total

    def leading_wait(self) -> float:
        """
        The explicit recorded pause before this block's first real action, if
        any - a "block"'s first step being a sleep, or a "mouse_path"'s first
        point's dt. Used purely for rendering: the timeline shows this as its
        own small "Sleep" segment ahead of the block instead of folding it
        invisibly into the block's own height.
        """
        if self.kind == "block" and self.steps and self.steps[0].type == "sleep":
            return self.steps[0].duration or 0.0
        if self.kind == "mouse_path" and self.points:
            return self.points[0].dt or 0.0
        return 0.0

    def active_duration(self) -> float:
        """estimated_duration() minus the leading_wait() already carved out
        as its own timeline segment, so the two don't double-count."""
        return max(0.0, self.estimated_duration() - self.leading_wait())

    def summary(self) -> str:
        """Short one-line description shown on a collapsed card."""
        if self.kind == "repeat":
            return f"Repeat x{self.count} ({len(self.children)} block(s))"
        if self.kind == "mouse_path":
            total_dt = sum(p.dt for p in self.points)
            moves = sum(1 for p in self.points if p.kind == "move")
            clicks = len(self.points) - moves
            click_part = f", {clicks} click event(s)" if clicks else ""
            return f"Mouse Path: {moves} move(s){click_part}, {total_dt:.1f}s"
        if not self.steps:
            return "Empty block"
        return " / ".join(s.to_text() for s in self.steps[:3]) + (
            " ..." if len(self.steps) > 3 else ""
        )

    def display_label(self) -> str:
        """What a card shows: the user's own note if set, else the auto-summary."""
        return self.label.strip() if self.label.strip() else self.summary()


def _reassign_ids(block: Block) -> None:
    """Give `block` and every descendant nested inside it (recursively, through
    any depth of Repeat-in-Repeat) a fresh id, in place."""
    block.id = new_id()
    if block.kind == "repeat":
        for child in block.children:
            _reassign_ids(child)


def block_track(block: Block) -> str:
    """
    Which track this (sub)tree is tied to: "keyboard", "mouse", or "any" for
    an empty Repeat that hasn't picked up any content yet. Used to stop a
    block from being dragged/pasted into the wrong track's list - "block"
    kind can only ever run on the keyboard track, "mouse_path" only on the
    mouse track, and a Repeat inherits whatever its children are.
    """
    if block.kind == "block":
        return "keyboard"
    if block.kind == "mouse_path":
        return "mouse"
    if block.kind == "repeat":
        tracks = {block_track(c) for c in block.children} - {"any"}
        if len(tracks) > 1:
            return "conflict"  # shouldn't happen in well-formed data
        return next(iter(tracks), "any")
    return "any"


def block_fits_track(block: Block, track: str) -> bool:
    """True if `block` (and everything nested inside it) may live on `track`."""
    found = block_track(block)
    return found in (track, "any")
