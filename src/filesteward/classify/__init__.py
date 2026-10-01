"""Deterministic disposition rules and independent adversarial challenge."""

from filesteward.classify.challenge import AdversarialChallenge, ChallengeResult
from filesteward.classify.gates import GateResults, ProvisionalDisposition
from filesteward.classify.rules import (
    CacheContract,
    evaluate_gates,
    is_managed,
    match_contract,
    nominate,
    resolve_directory_disposition,
)

__all__ = [
    "AdversarialChallenge",
    "CacheContract",
    "ChallengeResult",
    "GateResults",
    "ProvisionalDisposition",
    "evaluate_gates",
    "is_managed",
    "match_contract",
    "nominate",
    "resolve_directory_disposition",
]
