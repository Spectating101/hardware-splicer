from src.engines.requirements_intake import (
    build_capability_matrix,
    evaluate_requirements,
    run_lane_checks,
    template_for_lane,
)


def test_power_budget_ok():
    req = template_for_lane("power")
    req["meta"]["project_name"] = "Demo"
    req["manufacturing"]["fab"]["name"] = "JLCPCB"
    req["board"]["layers"] = 2
    req["risk_and_validation"]["what_good_looks_like"] = "Powers on and passes smoke test."
    req["manufacturing"]["dnp_policy"] = "explicit"

    req["power"]["rails"] = [
        {"name": "3V3", "voltage_v": 3.3, "max_current_a": 1.0, "notes": ""},
    ]
    req["power"]["sources"] = [
        {"name": "VIN", "voltage_v": 5.0, "max_current_a": 2.0, "notes": ""},
    ]
    req["power"]["loads"] = [
        {"name": "MCU", "rail": "3V3", "current_a": 0.2, "notes": ""},
        {"name": "Sensor", "rail": "3V3", "current_a": 0.3, "notes": ""},
    ]

    readiness = evaluate_requirements(req)
    lane_checks = run_lane_checks(req)
    assert lane_checks["checks"]["power_budget"]["status"] == "ok"
    assert lane_checks["checks"]["power_budget"]["rails"]["3V3"]["total_load_a"] == 0.5
    assert readiness["readiness_level"] == "manufacturable"

    caps = build_capability_matrix(req, readiness=readiness, lane_checks=lane_checks)
    assert caps["capabilities"]["power_budget_check"]["status"] == "reliable"


def test_regulator_headroom_and_thermal_checks():
    req = template_for_lane("power")
    req["meta"]["project_name"] = "Demo"
    req["manufacturing"]["fab"]["name"] = "JLCPCB"
    req["board"]["layers"] = 2
    req["risk_and_validation"]["what_good_looks_like"] = "Powers on."
    req["manufacturing"]["dnp_policy"] = "explicit"
    req["board"]["environment"]["ambient_c"] = 40

    req["power"]["regulators"] = [
        {
            "name": "U1",
            "type": "LDO",
            "vin_min_v": 3.5,
            "vin_max_v": 5.0,
            "vout_v": 3.3,
            "iout_est_a": 0.3,
            "dropout_v": 0.3,
            "theta_ja_c_per_w": 60,
            "max_junction_c": 125,
        }
    ]

    lane_checks = run_lane_checks(req)
    assert lane_checks["checks"]["regulators"]["status"] in ("ok", "issues_found")
    assert lane_checks["checks"]["regulators"]["regulators"][0]["name"] == "U1"


def test_derating_resistor_flags_over_utilization():
    req = template_for_lane("generic")
    req["meta"]["project_name"] = "Demo"
    req["manufacturing"]["fab"]["name"] = "JLCPCB"
    req["board"]["layers"] = 2
    req["risk_and_validation"]["what_good_looks_like"] = "Works."
    req["manufacturing"]["dnp_policy"] = "explicit"
    req["meta"]["design_intent"] = "professional"

    req["bom"] = [
        {"ref": "R1", "type": "resistor", "power_rating_w": 0.125, "power_diss_w": 0.1},
    ]
    lane_checks = run_lane_checks(req)
    assert lane_checks["checks"]["derating"]["status"] == "issues_found"


def test_interfaces_i2c_requires_pullups():
    req = template_for_lane("generic")
    req["meta"]["project_name"] = "Demo"
    req["manufacturing"]["fab"]["name"] = "JLCPCB"
    req["board"]["layers"] = 2
    req["risk_and_validation"]["what_good_looks_like"] = "Works."
    req["manufacturing"]["dnp_policy"] = "explicit"

    req["interfaces"] = [
        {"name": "I2C bus", "type": "I2C", "voltage_v": 3.3, "pullups_present": False, "cable_length_cm": 10},
    ]
    lane_checks = run_lane_checks(req)
    assert lane_checks["checks"]["interfaces"]["status"] == "issues_found"


def test_quality_grade_drops_with_missing_inputs():
    req = template_for_lane("generic")
    # Intentionally omit most readiness fields.
    lane_checks = run_lane_checks(req)
    assert lane_checks["quality"]["grade"] in ("D", "E", "F")

def test_power_budget_missing_currents_blocks_manufacturable():
    req = template_for_lane("power")
    req["meta"]["project_name"] = "Demo"
    req["manufacturing"]["fab"]["name"] = "JLCPCB"
    req["board"]["layers"] = 2
    req["risk_and_validation"]["what_good_looks_like"] = "Powers on."
    req["manufacturing"]["dnp_policy"] = "explicit"

    req["power"]["rails"] = [{"name": "3V3", "voltage_v": 3.3, "max_current_a": 1.0, "notes": ""}]
    req["power"]["loads"] = [{"name": "MCU", "rail": "3V3", "current_a": None, "notes": ""}]

    readiness = evaluate_requirements(req)
    assert readiness["readiness_level"] == "reviewable"
    assert "power.loads[].current_a" in readiness["blockers"]

    lane_checks = run_lane_checks(req)
    assert lane_checks["checks"]["power_budget"]["status"] == "needs_input"


def test_power_budget_over_limit_is_issue():
    req = template_for_lane("power")
    req["meta"]["project_name"] = "Demo"
    req["manufacturing"]["fab"]["name"] = "JLCPCB"
    req["board"]["layers"] = 2
    req["risk_and_validation"]["what_good_looks_like"] = "Powers on."
    req["manufacturing"]["dnp_policy"] = "explicit"

    req["power"]["rails"] = [{"name": "5V", "voltage_v": 5.0, "max_current_a": 0.5, "notes": ""}]
    req["power"]["loads"] = [{"name": "Load", "rail": "5V", "current_a": 0.9, "notes": ""}]

    lane_checks = run_lane_checks(req)
    assert lane_checks["checks"]["power_budget"]["status"] == "issues_found"
    assert lane_checks["checks"]["power_budget"]["rails"]["5V"]["status"] == "over_limit"
