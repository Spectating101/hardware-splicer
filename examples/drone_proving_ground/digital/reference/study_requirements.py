"""Bounded, explicit requirements for the registered digital drone case.

This parser deliberately supports a small documented vocabulary. It does not
pretend to redesign arbitrary hardware or translate gust force into wind speed.
"""
from __future__ import annotations

import math
import re

DEFAULTS = {'payload_mass_g': 0.0, 'gust_scale': 1.0, 'max_mass_g': 250.0}
BOUNDS = {'payload_mass_g': (0, 50), 'gust_scale': (0, 3), 'max_mass_g': (150, 500)}
OPTIONAL = {'min_hover_endurance_min': 'endurance', 'min_thrust_to_weight': 'minimum_thrust_to_weight'}


def validate(value=None):
    value = {} if value is None else value
    if not isinstance(value, dict) or set(value) - (set(DEFAULTS) | set(OPTIONAL)):
        raise ValueError('Requirements support payload_mass_g, gust_scale, max_mass_g, '
                         'min_hover_endurance_min and min_thrust_to_weight only.')
    result = dict(DEFAULTS)
    for key, number in value.items():
        if isinstance(number, bool) or not isinstance(number, (int, float)):
            raise ValueError(f'{key} must be a number.')
        low, high = BOUNDS.get(key, (0, math.inf))
        if not math.isfinite(number) or not low <= number <= high:
            raise ValueError(f'{key} must be between {low} and {high}.')
        result[key] = float(number)
    return result


def resolve(current, change_request='', overrides=None):
    result = validate(current)
    text = str(change_request or '').strip().lower().rstrip('.!?').strip()
    if len(text) > 200:
        raise ValueError('Keep the change request under 200 characters.')
    if text:
        match = re.fullmatch(r'(add|remove|set)\s+(\d+(?:\.\d+)?)\s*(?:g|grams?)\s+(?:(?:of\s+)?payload)', text)
        set_match = re.fullmatch(r'set\s+payload\s+to\s+(\d+(?:\.\d+)?)\s*(?:g|grams?)', text)
        if set_match:
            result['payload_mass_g'] = float(set_match[1])
        elif match:
            action, number = match[1], float(match[2])
            result['payload_mass_g'] = (number if action == 'set' else
                                        result['payload_mass_g'] + (number if action == 'add' else -number))
        else:
            raise ValueError('Supported changes: "Add 10 g of payload", "Remove 5 g of payload", '
                             'or "Set payload to 10 g". Use the fields for gust force and mass limit.')
    if overrides:
        validate(overrides)
        if text and 'payload_mass_g' in overrides:
            raise ValueError('Use either a payload change request or payload_mass_g, not both.')
        result.update(overrides)
    return validate(result)


def configure(config, requirements):
    import copy
    config = copy.deepcopy(config)
    requirements = validate(requirements)
    config['requirements'] = requirements
    config['assumptions']['gust_force_n'] = [x * requirements['gust_scale'] for x in config['assumptions']['gust_force_n']]
    return config


def verdict_basis(requirements):
    return 'mass_budget_only' if not set(requirements).intersection(OPTIONAL) else 'mass_budget_and_declared_performance'


def constraints(model, requirements, assessment=None):
    requirements = validate(requirements)
    mass = model['mass_kg'] * 1000
    limit = requirements['max_mass_g']
    result = [
        {'id': 'nominal_mass', 'label': 'Nominal mass', 'actual': mass, 'limit': limit,
         'kind': 'mass_budget', 'unit': 'g', 'margin': limit - mass, 'margin_g': limit - mass, 'passed': mass <= limit},
        {'id': 'mass_uncertainty', 'label': 'Mass with 5 g uncertainty', 'actual': mass + 5,
         'kind': 'mass_budget', 'limit': limit, 'unit': 'g', 'margin': limit - mass - 5,
         'margin_g': limit - mass - 5, 'passed': mass + 5 <= limit},
        {'id': 'inertia_approximation', 'label': 'Relative omitted products of inertia',
         'actual': model['inertia_off_diagonal_relative_max'], 'limit': .05, 'unit': '',
         'margin': .05 - model['inertia_off_diagonal_relative_max'],
         'passed': model['inertia_off_diagonal_relative_max'] < .05},
    ]
    for check in result:
        check['verdict_basis'] = verdict_basis(requirements)
        if check.get('kind') == 'mass_budget':
            check['mass_budget'] = check['passed']
    assessments = assessment if isinstance(assessment, list) else [assessment] if assessment else []
    metrics = {'min_hover_endurance_min': ('estimated_hover_endurance_min', 'min'),
               'min_thrust_to_weight': ('thrust_to_weight_at_min_voltage', '')}
    for key, kind in OPTIONAL.items():
        if key not in requirements:
            continue
        metric, unit = metrics[key]
        values = [a.get('metrics', {}).get(metric) for a in assessments]
        evaluated = bool(values) and all(v is not None and math.isfinite(v) for v in values)
        actual = min(values) if evaluated else None
        result.append({'id': key, 'kind': kind, 'label': key, 'actual': actual,
                       'limit': requirements[key], 'unit': unit,
                       'margin': actual-requirements[key] if evaluated else None,
                       'passed': actual >= requirements[key] if evaluated else None,
                       'status': 'evaluated' if evaluated else 'not_evaluated',
                       'verdict_basis': verdict_basis(requirements)})
    return result
