"""Canonical immutable manifest model."""

from dataclasses import dataclass
from typing import Literal

ChallengeState = Literal["hidden", "visible", "locked"]
ChallengeType = Literal["standard"]
FlagLogic = Literal["any", "all"]
FlagType = Literal["static", "regex"]
FlagData = Literal["case_sensitive", "case_insensitive"]
SolutionAction = Literal["preserve", "upsert", "clear"]
SolutionState = Literal["hidden", "visible", "solved"]


@dataclass(frozen=True)
class FlagSpec:
    type: FlagType
    content: str
    data: FlagData


@dataclass(frozen=True)
class HintSpec:
    title: str
    content: str
    cost: int
    required_hints: tuple[str, ...]


@dataclass(frozen=True)
class SolutionSpec:
    action: SolutionAction
    content: str | None = None
    state: SolutionState | None = None


@dataclass(frozen=True)
class ChallengeSpec:
    name: str
    description: str
    value: int
    category: str
    state: ChallengeState
    type: ChallengeType
    logic: FlagLogic
    max_attempts: int
    attribution: str
    connection_info: str
    tags: tuple[str, ...]
    next: str | None
    solution: SolutionSpec
    flags: tuple[FlagSpec, ...]
    hints: tuple[HintSpec, ...]


@dataclass(frozen=True)
class Manifest:
    warnings: tuple["Diagnostic", ...]
    challenges: tuple[ChallengeSpec, ...]
    format: Literal["push-challenges"] = "push-challenges"
    version: Literal[1] = 1


from .errors import Diagnostic  # noqa: E402
