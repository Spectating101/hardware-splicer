"""Adversarial transformation tests; real OCC, GLB and browser in CI."""
import copy
import pytest
from hardware_splicer.teardown_cad_showcase import resolve_positions,safe_vec

def scene():
    spec={"schema_version":"assembly_spec.v0.1",
          "instances":[
              {"id":"tray","transform":{"translate_mm":[0,0,0]}},
              {"id":"panel","place_relative_to":{"ref":"tray","parent_frame":"back_top_seat",
                "frame":"front_bottom_seat","axis":"z","side":"positive","offset_mm":0,"lock":"frame"}},
              {"id":"housing","transform":{"translate_mm":[160,130,228]}}],
          "not_built_yet":[{"item":"bracket"}]}
    frames={"schema_version":"connector_metadata.v0.1","components":[
      {"id":"tray","frames":[{"id":"back_top_seat","origin_mm":[225,230,14],"verified":True}]},
      {"id":"panel","frames":[{"id":"front_bottom_seat","origin_mm":[225,0,0],"verified":True}]}]}
    return spec,frames

def test_real_constraint_frame_resolves_to_assembly_not_a_row():
    spec,connectors=scene()
    x=resolve_positions(spec,connectors,{"tray","panel","housing"})
    assert x=={"tray":[0.,0.,0.],"panel":[0.,230.,14.],"housing":[160.,130.,228.]}

@pytest.mark.parametrize("bad",[
  "duplicate","unverified","missing_frame","drift","unsupported_rotation",
  "bad_transform","wrong_inventory","cycle",
])
def test_reject_unqualified_assembly_placement(bad):
    spec,connectors=scene()
    if bad=="duplicate":spec["instances"].append(copy.deepcopy(spec["instances"][0]))
    elif bad=="unverified":connectors["components"][0]["frames"][0]["verified"]=False
    elif bad=="missing_frame":spec["instances"][1]["place_relative_to"]["frame"]="invented"
    elif bad=="drift":spec["instances"][1]["place_relative_to"]["offset_mm"]=10
    elif bad=="unsupported_rotation":spec["instances"][0]["transform"]["rotate_deg"]=[0,0,45]
    elif bad=="bad_transform":spec["instances"][0]["transform"]["translate_mm"]=[0,float("nan"),0]
    elif bad=="wrong_inventory":spec["instances"].pop()
    elif bad=="cycle":
        spec["instances"][0].pop("transform")
        spec["instances"][0]["place_relative_to"]={"ref":"panel","parent_frame":"back_top_seat",
          "frame":"front_bottom_seat","axis":"z","side":"positive","offset_mm":0,"lock":"frame"}
    with pytest.raises((ValueError,KeyError)):
        resolve_positions(spec,connectors,{"tray","panel","housing"})

def test_no_infinite_or_nonsense_world_vectors():
    for invalid in ([1,2], [0,0,True], [0,float("inf"),0], [0,0,100001]):
        with pytest.raises(ValueError):
            safe_vec(invalid)
