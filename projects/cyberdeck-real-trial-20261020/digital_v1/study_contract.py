"""Deterministic Fielddeck engineering calculations and bounded study goals.

No CAD or plotting imports: the backend and verifier can independently recompute
every reported number from retained design, geometry, BOM and requirement bytes.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

SCHEMA = 'hardware_splicer.fielddeck_calculations.v2'
DEFAULT_REQUIREMENTS = {
    'minimum_work_runtime_h': 2.5,
    'minimum_supply_margin_a': .3,
    'maximum_case_width_mm': 320,
    'maximum_case_depth_mm': 300,
    'maximum_case_height_mm': 75,
    'printer_bed_x_mm': 220,
    'printer_bed_y_mm': 220,
    'pi_work_current_a': 1.0,
    'keyboard_current_a': .1,
}
BOUNDS = {
    'minimum_work_runtime_h': (.1, 24),
    'minimum_supply_margin_a': (0, 2),
    'maximum_case_width_mm': (100, 1000),
    'maximum_case_depth_mm': (100, 1000),
    'maximum_case_height_mm': (20, 500),
    'printer_bed_x_mm': (100, 1000),
    'printer_bed_y_mm': (100, 1000),
    'pi_work_current_a': (.4, 2.5),
    'keyboard_current_a': (.02, .5),
}


def number(value, label, minimum=0, maximum=1e9):
    try:
        finite = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError(f'{label} must be a finite number.')
    if not minimum <= value <= maximum:
        raise ValueError(f'{label} must be between {minimum} and {maximum}.')
    return float(value)


def validate_requirements(values=None, *, design=None):
    if values is not None and not isinstance(values, dict):
        raise ValueError('Study requirements must be an object.')
    defaults = dict(DEFAULT_REQUIREMENTS)
    if design is not None:
        defaults.update(design.get('engineering_requirements', {}))
        assumptions = design['engineering_assumptions']
        defaults['pi_work_current_a'] = assumptions['pi_current_a']['work']
        defaults['keyboard_current_a'] = assumptions['keyboard_current_a']['normal_allocation']
    values = values or {}
    if set(values) - set(BOUNDS) or set(defaults) - set(BOUNDS):
        raise ValueError('Unknown Fielddeck requirement.')
    result = {**defaults, **values}
    return {k: number(result[k], k, *bounds) for k, bounds in BOUNDS.items()}


def load_requirements(root):
    root = Path(root)
    design = json.loads((root / 'design.json').read_text())
    path = root / 'requirements.json'
    return validate_requirements(json.loads(path.read_text()) if path.is_file() else None, design=design)


def input_hashes(root):
    root = Path(root)
    names = ['design.json', 'bom.json', 'cad/geometry_report.json', 'study_contract.py', 'engineering.py']
    if (root / 'requirements.json').exists():
        names.append('requirements.json')
    result = {}
    for name in names:
        path = root / name
        if path.is_symlink() or not path.is_file():
            raise ValueError('Missing or unsafe calculation input: ' + name)
        result[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def calculate(design, geometry, bom, requirements=None):
    req = validate_requirements(requirements, design=design)
    a = design['engineering_assumptions']
    ids = [row['id'] for row in bom['items']]
    identities = [(row['manufacturer'], row['mpn']) for row in bom['items']
                  if row.get('manufacturer') and row.get('mpn')]
    if len(ids) != len(set(ids)) or len(identities) != len(set(identities)):
        raise ValueError('Duplicate BOM identifier or selected commercial module.')
    voltage = number(a['supply_voltage_v'], 'supply voltage', 4, 6)
    limit = number(design['power_bank']['rated_5v_current_a'], 'bank current', .1, 10)
    capacity_ah = number(design['power_bank']['capacity_mah'], 'cell capacity mAh', 100, 100000) / 1000
    cell_v = number(a['power_bank_cell_voltage_v'], 'cell voltage', 2.5, 4.5)
    efficiency = [number(v, 'conversion efficiency', .1, 1) for v in a['conversion_efficiency_range']]
    usable_fraction = [number(v, 'usable capacity fraction', .1, 1) for v in a['usable_capacity_fraction_range']]
    if len(efficiency) != 2 or len(usable_fraction) != 2 or efficiency != sorted(efficiency) or usable_fraction != sorted(usable_fraction):
        raise ValueError('Efficiency and usable-capacity ranges must be ordered two-item ranges.')
    energy = capacity_ah * cell_v
    usable = [energy * efficiency[i] * usable_fraction[i] for i in (0, 1)]
    fan_a = number(a['fan_current_a'], 'fan current', 0, 1)
    display_published = number(a['display_w']['published'], 'published display power', .01, 30)
    display_allocated = number(a['display_w']['allocated'], 'allocated display power', display_published, 30)
    pi_light = number(a['pi_current_a']['light'], 'light Pi current', .1, 3)
    pi_stress = number(a['pi_current_a']['stress'], 'stress Pi current', .1, 3)
    keyboard_high = number(a['keyboard_current_a']['usb2_high_power_sensitivity'], 'keyboard sensitivity', .02, 1.2)
    scenarios = []
    for name, pi, display, keys in [
        ('light', pi_light, display_published, req['keyboard_current_a']),
        ('work', req['pi_work_current_a'], display_published, req['keyboard_current_a']),
        ('stress_allocation', pi_stress, display_allocated, req['keyboard_current_a']),
        ('high_power_keyboard_sensitivity', pi_stress, display_allocated, keyboard_high),
    ]:
        current = pi + display / voltage + keys + fan_a
        scenarios.append({'name': name, 'pi_current_a': pi, 'display_w': display, 'keyboard_a': keys,
                          'usb_current_a': round(keys + fan_a, 6), 'current_a': round(current, 6),
                          'power_w': round(voltage * current, 6), 'current_headroom_a': round(limit - current, 6),
                          'runtime_h': [round(e / (voltage * current), 6) for e in usable]})
    work = scenarios[1]
    stress = scenarios[2]
    operating = scenarios[:3]
    peak = max(operating, key=lambda row: row['power_w'])
    minimum_margin = min(row['current_headroom_a'] for row in operating)
    density = number(design['print']['density_g_cm3'], 'PETG density', .1, 10)
    volume = sum(number(p['volume_mm3'], 'part volume', 0) for p in geometry['parts'] if p['printable'])
    post = a['display_support']
    fixed_section = {'outer_diameter_mm': 10, 'tool_bore_diameter_mm': 6,
                     'cantilever_length_mm': 49.54, 'post_count': 4}
    if any(post.get(key) != expected for key, expected in fixed_section.items()):
        raise ValueError('Display-support dimensions must match the fixed authored geometry.')
    outer = number(post['outer_diameter_mm'], 'post outer diameter', 1, 50)
    inner = number(post['tool_bore_diameter_mm'], 'post bore diameter', 0, outer - .01)
    length = number(post['cantilever_length_mm'], 'post length', 1, 500)
    inertia = math.pi / 64 * (outer ** 4 - inner ** 4)
    panel_kg = number(post['panel_mass_kg'], 'panel mass', .01, 2)
    lateral_g = number(post['lateral_acceleration_g'], 'acceleration scenario', .1, 10)
    count = number(post['post_count'], 'post count', 1, 100)
    force = panel_kg * 9.80665 * lateral_g / count
    modulus = number(a['petg_elastic_modulus_mpa'], 'PETG modulus', 1, 10000)
    allowable = number(a['petg_design_allowable_mpa'], 'PETG stress allowance', .1, 100)
    bending_stress = force * length * outer / (2 * inertia)
    deflection = force * length ** 3 / (3 * modulus * inertia)
    cooling = a['cooling']
    fractions = [number(v, 'delivered airflow fraction', .01, 1) for v in cooling['delivered_flow_fraction']]
    flow = number(cooling['fan_free_air_m3_h'], 'fan free-air flow', .01, 100)
    rho = number(cooling['air_density_kg_m3'], 'air density', .1, 10)
    cp = number(cooling['air_specific_heat_j_kg_k'], 'air specific heat', 1, 10000)
    heat = peak['power_w']  # Conservative total electrical input as cavity heat.
    air_rise = [heat / (rho * cp * (flow / 3600) * fraction) for fraction in fractions]
    cable = a['power_cable']
    conductor_r = number(cable['conductor_resistance_ohm_m'], 'cable conductor resistance', 0, 10)
    cable_length = number(cable['length_m'], 'power cable length', .01, 10)
    contacts = [number(v, 'loop contact resistance', 0, 2) for v in cable['contact_resistance_range_ohm']]
    resistances = [2 * cable_length * conductor_r + value for value in contacts]
    retail = sum(number(row['price_usd'], 'BOM price', 0) for row in bom['items'] if row['price_basis'] == 'observed retail')
    allowance_cost = sum(number(row['price_usd'], 'BOM price', 0) for row in bom['items'] if row['price_basis'] != 'observed retail')
    case = design['case_mm']
    case_dimensions = {key: number(case[key], 'case ' + key, 1, 2000) for key in ('width', 'depth', 'height')}
    constraints = []

    def check(identifier, label, actual, bound, unit, minimum=True):
        constraints.append({'id': identifier, 'label': label, 'actual': actual, 'limit': bound,
                            'unit': unit, 'passed': actual >= bound if minimum else actual <= bound})

    check('work_runtime', 'Conservative work-runtime scenario', work['runtime_h'][0], req['minimum_work_runtime_h'], 'h')
    check('supply_current_margin', 'Smallest ordinary-operation single-port current margin', minimum_margin, req['minimum_supply_margin_a'], 'A')
    check('sensitivity_supply_limit', 'Largest modelled current including keyboard sensitivity', max(row['current_a'] for row in scenarios), limit, 'A', False)
    usb_limit = number(a['pi_usb_aggregate_limit_a'], 'Pi aggregate USB current limit', .1, 3)
    check('usb_current_limit', 'Largest modelled USB load', max(s['usb_current_a'] for s in scenarios), usb_limit, 'A', False)
    for key in case_dimensions:
        check('case_' + key, 'Nominal enclosure ' + key, case_dimensions[key], req['maximum_case_' + key + '_mm'], 'mm', False)
    for axis, index in (('x', 0), ('y', 1)):
        extent = max(p['print_dimensions_mm'][index] for p in geometry['parts'] if p['printable'])
        check('print_bed_' + axis, 'Largest printed-part ' + axis + ' span', extent, req['printer_bed_' + axis + '_mm'], 'mm', False)
    check('display_post_bending', 'Ideal display-post bending stress', bending_stress, allowable, 'MPa', False)
    return {
        'schema_version': SCHEMA, 'case_id': 'fielddeck-7', 'calculation_type': 'first_order_scenarios_not_physical_simulation',
        'requirements': req, 'requirements_met': all(row['passed'] for row in constraints), 'constraints': constraints,
        'metrics': {'work_runtime_lower_h': work['runtime_h'][0], 'work_runtime_upper_h': work['runtime_h'][1],
                    'stress_current_margin_a': stress['current_headroom_a'],
                    'minimum_supply_current_margin_a': minimum_margin,
                    'planning_cost_usd': round(retail + allowance_cost, 2),
                    'solid_petg_mass_g': round(volume / 1000 * density, 3),
                    **{'case_' + k + '_mm': v for k, v in case_dimensions.items()}},
        'effective_assumptions': {'pi_work_current_a': req['pi_work_current_a'], 'keyboard_current_a': req['keyboard_current_a'],
                                  'source': 'Design defaults with explicit study-requirement overrides.'},
        'battery_nominal_cell_energy_wh': energy, 'usable_output_energy_wh': usable,
        'battery_basis': f'{capacity_ah:g}Ah × {cell_v:g}V cell nominal; conversion {efficiency}; usable capacity {usable_fraction}. Not capacity at USB voltage.',
        'load_scenarios': scenarios, 'bank_single_port_limit_a': limit, 'supply_voltage_v': voltage,
        'pi_usb_aggregate_limit_a': number(a['pi_usb_aggregate_limit_a'], 'Pi USB current limit', .1, 3),
        'power_cable_loop_resistance_ohm': resistances,
        'stress_cable_drop_v': [stress['current_a'] * r for r in resistances],
        'stress_pi_voltage_if_bank_exactly_5v': [voltage - stress['current_a'] * r for r in resistances],
        'largest_ordinary_scenario': peak['name'],
        'peak_cable_drop_v': [peak['current_a'] * r for r in resistances],
        'peak_pi_voltage_if_bank_nominal': [voltage - peak['current_a'] * r for r in resistances],
        'voltage_caveat': 'Single-port current headroom does not establish input-voltage stability; bank regulation and actual contact resistance are unmeasured.',
        'gpio_extension_copper_drop_v': display_allocated / voltage * 2 * a['gpio_extension_length_m'] * a['gpio_conductor_resistance_ohm_m'],
        'custom_solid_volume_cm3': volume / 1000, 'custom_100_percent_solid_petg_mass_g': volume / 1000 * density,
        'mass_note': '100% solid CAD mass bound; actual sliced mass, supports and printing time not computed.',
        'post_lateral_2g_check': {'panel_mass_assumption_kg': panel_kg, 'lateral_acceleration_g': lateral_g,
            'load_per_post_n': force, 'length_mm': length, 'section_second_moment_mm4': inertia,
            'elastic_modulus_assumption_mpa': modulus, 'allowable_stress_assumption_mpa': allowable,
            'bending_stress_mpa': bending_stress, 'tip_deflection_mm': deflection,
            'scope': 'Ideal equal-share cantilevers; excludes roots, layer anisotropy, fasteners, joints and glass; no drop rating.'},
        'cooling_sensitivity': {'heat_assumption_w': heat, 'fan_free_air_m3_h': flow, 'delivered_fraction': fractions,
            'bulk_air_rise_c': air_rise, 'scope': 'Air-energy balance, not CFD, junction temperature or a predicted fan/system operating point.'},
        'cost_usd': {'observed_retail_subtotal': round(retail, 2), 'explicit_allowance_subtotal': round(allowance_cost, 2),
                     'planning_total': round(retail + allowance_cost, 2), 'scope': bom['pricing_scope']},
        'open_digital_fit_items': ['bank ports/button and built-in cable not dimensioned',
            'keyboard underside/pad retention and cable bend not manufacturer CAD',
            'display lug thread/engagement nominal only', 'GPIO extension contact current rating/retention unverified',
            'flexible cable bends/routing not solid-interference verified'],
        'thermal_acceptance_established': False, 'physical_validation_performed': False,
    }


def validate_calculation_record(root):
    root = Path(root)
    try:
        saved = json.loads((root / 'analysis/calculations.json').read_text())
        expected = calculate(json.loads((root / 'design.json').read_text()),
                             json.loads((root / 'cad/geometry_report.json').read_text()),
                             json.loads((root / 'bom.json').read_text()), load_requirements(root))
        expected['input_sha256'] = input_hashes(root)
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError('Missing or invalid engineering calculation inputs.') from exc
    if saved != expected:
        raise ValueError('Saved calculations differ from the retained inputs; regenerate engineering.py.')
    return saved
