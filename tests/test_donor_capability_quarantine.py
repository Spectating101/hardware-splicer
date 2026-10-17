from __future__ import annotations

from hardware_splicer.donor_capability_quarantine import quarantine_policy_for_role
from hardware_splicer.salvage_resource_graph import project_salvage_resource_graph


def test_battery_and_mains_roles_are_explicitly_quarantined():
    battery = quarantine_policy_for_role("battery_pack")
    assert battery["quarantine_id"] == "salvage.quarantine.battery_pack"
    assert battery["architecture_use_allowed"] is False
    assert battery["energized_testing_allowed"] is False
    assert battery["truth_contract"]["agent_can_release_quarantine"] is False

    mains = quarantine_policy_for_role("mains_supply")
    assert mains["quarantine_id"] == "salvage.quarantine.mains_or_high_energy_power"
    assert mains["architecture_use_allowed"] is False
    assert mains["energized_testing_allowed"] is False


def test_verified_contract_does_not_override_quarantine():
    graph = project_salvage_resource_graph(
        project_id="quarantine-test",
        donors=[
            {
                "donor_id": "donor:laptop:battery",
                "label": "Laptop battery pack",
                "contract_state": "verified",
                "capabilities": [{"role": "battery_pack", "grade": "person_measurement"}],
                "missing_facts": [],
            }
        ],
    )
    donor = graph["resources"][0]
    capability = donor["capabilities"][0]
    assert capability["architecture_usable"] is False
    assert capability["quarantine"]["architecture_use_allowed"] is False
    assert donor["usable_for_architecture"] is False
    assert donor["verified_for_ready"] is False
    assert donor["quarantined_capabilities"][0]["role"] == "battery_pack"
    assert graph["truth_contract"]["agent_can_release_quarantine"] is False


def test_safe_capability_on_same_donor_can_remain_useful_while_high_energy_role_is_quarantined():
    graph = project_salvage_resource_graph(
        project_id="mixed-quarantine-test",
        donors=[
            {
                "donor_id": "donor:appliance:mixed",
                "label": "Mixed low/high energy donor",
                "contract_state": "verified",
                "capabilities": [
                    {"role": "momentary_button", "grade": "person_measurement"},
                    {"role": "mains_circuit", "grade": "person_measurement"},
                ],
                "missing_facts": [],
            }
        ],
    )
    donor = graph["resources"][0]
    by_role = {row["role"]: row for row in donor["capabilities"]}
    assert by_role["momentary_button"]["architecture_usable"] is True
    assert "quarantine" not in by_role["momentary_button"]
    assert by_role["mains_circuit"]["architecture_usable"] is False
    assert donor["usable_for_architecture"] is True
    assert donor["verified_for_ready"] is True
