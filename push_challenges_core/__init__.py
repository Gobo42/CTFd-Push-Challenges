"""Pure, CTFd-independent challenge import primitives."""

from .errors import Diagnostic, ManifestValidationError
from .model import ChallengeSpec, FlagSpec, HintSpec, Manifest, SolutionSpec

__all__ = [
    "ChallengeSpec",
    "Diagnostic",
    "FlagSpec",
    "HintSpec",
    "Manifest",
    "ManifestValidationError",
    "SolutionSpec",
]
