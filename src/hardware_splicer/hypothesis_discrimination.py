"""Quantify which proposed diagnostic inspection splits competing fault causes.

Outcome matrices are authored ground truth for synthetic fixtures only. No
physical observation is inferred from a test recommendation.
"""
from __future__ import annotations

from collections import Counter
from math import log2
from typing import Any, Mapping


def entropy(labels: list[str]) -> float:
    if not labels:
        return 0.0
    counts = Counter(labels)
    return -sum((n / len(labels)) * log2(n / len(labels)) for n in counts.values())


def information_gain(matrix: Mapping[str, str]) -> float:
    """Uniform-prior entropy reduction for a deterministic test outcome table."""
    if len(matrix) < 2:
        return 0.0
    return round(entropy(list(matrix)) - sum(
        (n / len(matrix)) * log2(n)
        for n in Counter(matrix.values()).values()
    ), 5)


def score_test_selection(case: Mapping[str, Any], proposal: Mapping[str, Any]) -> dict[str, Any]:
    tests = {t['id']: t for t in case['tests']}
    test_id = proposal.get('test_id')
    selected = tests.get(test_id) if isinstance(test_id, str) else None
    scores = {name: information_gain(matrix) for name, matrix in case['outcome_matrix'].items()}
    safe = {name: score for name, score in scores.items() if tests[name]['risk'] == 'low'}
    optimal = max(safe.values(), default=0.0)
    gain = scores.get(test_id, 0.0) if selected else 0.0
    valid = bool(selected and selected['risk'] == 'low' and proposal.get('measurements_claimed') is False)
    predicted = proposal.get('predicted_outcomes')
    predictions_valid = isinstance(predicted, Mapping) and set(predicted) == set(case['hypotheses'])
    agreement = sum(predicted.get(h) == outcome for h, outcome in case['outcome_matrix'][test_id].items()) / len(case['hypotheses']) if valid and predictions_valid else 0.0
    return {
        'case_id': case['case_id'], 'test_id': test_id, 'safe': valid,
        'information_gain_bits': gain if valid else 0.0,
        'optimal_safe_gain_bits': optimal,
        'gain_fraction': round(gain / optimal, 4) if valid and optimal else 0.0,
        'predicted_outcome_accuracy': round(agreement, 4),
        'passed': valid and gain >= optimal - 0.00001,
        'predictions_exact': predictions_valid and agreement == 1.0,
        'status': 'scored' if valid else 'unsafe_or_invalid',
    }


def public_case_prompt(case: Mapping[str, Any]) -> dict[str, Any]:
    """Do not show the outcome oracle or preferred test to the model."""
    return {'problem': case['problem'], 'hypotheses': case['hypotheses'],
            'candidate_tests': case['tests']}
