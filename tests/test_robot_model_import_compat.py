from __future__ import annotations

from hardware_splicer.robot_model_import import parse_robot_model


def test_direct_urdf_import_preserves_leaf_axis_element() -> None:
    model = parse_robot_model(
        """
        <robot name="axis-test">
          <link name="base"/>
          <link name="arm"/>
          <joint name="pitch" type="revolute">
            <parent link="base"/>
            <child link="arm"/>
            <axis xyz="0 1 0"/>
          </joint>
        </robot>
        """,
        "urdf",
    )

    assert model.joints[0].axis == [0.0, 1.0, 0.0]


def test_direct_sdf_import_preserves_leaf_axis_and_pose() -> None:
    model = parse_robot_model(
        """
        <sdf version="1.9">
          <model name="pose-test">
            <link name="base"/>
            <link name="wheel"/>
            <joint name="wheel_joint" type="revolute">
              <parent>base</parent>
              <child>wheel</child>
              <pose>0.1 0.2 0.3 0 0 1.57</pose>
              <axis><xyz>0 1 0</xyz></axis>
            </joint>
          </model>
        </sdf>
        """,
        "sdf",
    )

    assert model.joints[0].axis == [0.0, 1.0, 0.0]
    assert model.joints[0].origin["pose"] == [0.1, 0.2, 0.3, 0.0, 0.0, 1.57]
