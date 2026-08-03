from __future__ import annotations

import pytest

from hardware_splicer.robot_model_import import (
    RobotModelImportError,
    parse_robot_model,
    topology_from_robot_model,
)
from hardware_splicer.robot_topology import RobotGenre


URDF = """
<robot name="two_link_arm">
  <link name="base_link"/>
  <link name="arm_link">
    <inertial><origin xyz="0 0 0.1"/><mass value="0.5"/></inertial>
    <visual><geometry><mesh filename="package://arm/arm.stl"/></geometry></visual>
    <collision><geometry><box size="0.1 0.1 0.3"/></geometry></collision>
  </link>
  <joint name="shoulder_joint" type="revolute">
    <parent link="base_link"/>
    <child link="arm_link"/>
    <origin xyz="0 0 0.1" rpy="0 0 0"/>
    <axis xyz="0 1 0"/>
    <limit lower="-1.2" upper="1.2" effort="4" velocity="2"/>
  </joint>
  <transmission name="shoulder_transmission">
    <joint name="shoulder_joint"/>
    <actuator name="shoulder_motor"><mechanicalReduction>2</mechanicalReduction></actuator>
  </transmission>
</robot>
"""


SDF = """
<sdf version="1.9">
  <model name="simple_rover">
    <link name="base_link"/>
    <link name="left_wheel"/>
    <joint name="left_wheel_joint" type="revolute">
      <parent>base_link</parent>
      <child>left_wheel</child>
      <axis><xyz>0 1 0</xyz><limit><lower>-3.14</lower><upper>3.14</upper></limit></axis>
    </joint>
  </model>
</sdf>
"""


MJCF = """
<mujoco model="simple_leg">
  <worldbody>
    <body name="base">
      <body name="upper_leg">
        <joint name="hip" type="hinge" axis="0 1 0" range="-1 1"/>
        <body name="lower_leg">
          <joint name="knee" type="hinge" axis="0 1 0" range="-1.5 0"/>
        </body>
      </body>
    </body>
  </worldbody>
  <actuator>
    <motor name="hip_motor" joint="hip"/>
    <motor name="knee_motor" joint="knee"/>
  </actuator>
</mujoco>
"""


def test_urdf_import_preserves_links_joint_limits_and_transmission() -> None:
    model = parse_robot_model(URDF, "urdf")

    assert model.name == "two_link_arm"
    assert len(model.links) == 2
    assert model.links[1].mass_kg == 0.5
    assert model.links[1].visual_refs == ["mesh:package://arm/arm.stl"]
    assert len(model.joints) == 1
    assert model.joints[0].axis == [0.0, 1.0, 0.0]
    assert model.joints[0].limits == {
        "lower": -1.2,
        "upper": 1.2,
        "effort": 4.0,
        "velocity": 2.0,
    }
    assert model.actuators[0].joint_id == "shoulder_joint"
    assert model.actuators[0].reduction == 2.0

    topology = topology_from_robot_model(model)
    assert topology.robot_genre in {RobotGenre.GENERIC, RobotGenre.SERIAL_MANIPULATOR}
    assert topology.root_link_id == "base_link"
    assert topology.joints[0].limits["effort"] == 4.0
    assert topology.actuators[0].actuator_id == "shoulder_motor"
    assert topology.actuators[0].joint_ids == ["shoulder_joint"]
    assert topology.metadata["motion_authorized"] is False


def test_sdf_import_preserves_wheel_relationship_and_infers_rover() -> None:
    model = parse_robot_model(SDF, "sdf")
    topology = topology_from_robot_model(model)

    assert model.joints[0].parent_link_id == "base_link"
    assert model.joints[0].child_link_id == "left_wheel"
    assert model.joints[0].limits["lower"] == -3.14
    assert topology.robot_genre == RobotGenre.ROVER
    assert topology.root_link_id == "base_link"


def test_mjcf_import_preserves_body_chain_and_actuators() -> None:
    model = parse_robot_model(MJCF, "mjcf")
    topology = topology_from_robot_model(model)

    assert {row.link_id for row in model.links} >= {"world", "base", "upper_leg", "lower_leg"}
    assert {row.joint_id for row in model.joints} >= {"hip", "knee"}
    assert {row.actuator_id for row in model.actuators} == {"hip_motor", "knee_motor"}
    actuator_joint_map = {row.actuator_id: row.joint_ids for row in topology.actuators}
    assert actuator_joint_map["hip_motor"] == ["hip"]
    assert actuator_joint_map["knee_motor"] == ["knee"]
    assert topology.metadata["source_model_format"] == "mjcf"
    assert topology.metadata["calibration_verified"] is False


def test_robot_model_import_rejects_dtd_and_oversized_input() -> None:
    with pytest.raises(RobotModelImportError, match="DTD"):
        parse_robot_model('<!DOCTYPE robot [<!ENTITY x "bad">]><robot name="x"/>', "urdf")

    with pytest.raises(RobotModelImportError, match="maximum"):
        parse_robot_model(" " * (5 * 1024 * 1024 + 1), "urdf")
