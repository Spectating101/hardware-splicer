from src.api.v1 import main as main_module
from src.intelligence.repair_lane_packs import RepairLanePacks


def test_repair_lane_packs_list_and_match():
    packs = RepairLanePacks()

    listed = packs.list_packs()
    assert listed["pilot_lane_ids"] == ["controller_input", "battery_charging", "small_motor_usb"]
    assert len(listed["packs"]) == 3

    match = packs.match("Xbox controller stick drift after cleaning")
    assert match["matched"] is True
    assert match["recommended_lane_id"] == "controller_input"


def test_repair_lane_packs_api():
    packs = RepairLanePacks()
    user = {"user_id": "user-1"}

    listed = main_module.repair_lane_packs_list(current_user=user, packs=packs)
    assert listed["metadata"]["user_id"] == "user-1"
    assert listed["lane_packs"]["packs"]

    one = main_module.repair_lane_packs_get("battery_charging", current_user=user, packs=packs)
    assert one["lane_pack"]["label"] == "Battery and charging gadgets"

    match = main_module.repair_lane_packs_match(
        {"text": "USB fan will not spin unless connector is wiggled"},
        current_user=user,
        packs=packs,
    )
    assert match["match"]["recommended_lane_id"] == "small_motor_usb"
