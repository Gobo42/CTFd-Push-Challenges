"""Pure, CTFd-independent challenge import primitives."""

from .errors import Diagnostic, ManifestValidationError
from .model import (
    BonusSpec,
    BonusTierSpec,
    ChallengeSpec,
    DynamicScoringSpec,
    FlagSpec,
    HintSpec,
    Manifest,
    SolutionSpec,
)

__all__ = [
    "BonusSpec",
    "BonusTierSpec",
    "ChallengeSpec",
    "Diagnostic",
    "DynamicScoringSpec",
    "FlagSpec",
    "HintSpec",
    "Manifest",
    "ManifestValidationError",
    "SolutionSpec",
]
