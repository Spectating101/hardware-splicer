# P049 · Assembled SO-101 follower arm

This study reuses the exact joint origins and limits from The Robot Studio's SO-101 model. A cold transfer follows an empty-tool trajectory from a common pick position to a station, using five positioning joints and a fixed tool orientation. The gripper actuator is outside this test.

A 425 mm station X coordinate missed the target by up to **25.07 mm** and **38.24°**. Moving the station to 200 mm brought the numerical position residual below 0.001 mm and orientation residual below 0.001° throughout the revised path. Injecting just **1.5° of shoulder-pan zero error** produced a 4.79 mm position error on that same revised path. That sensitivity is what matters for a shop deciding whether to pay for a calibrated arm. The study omits gripping, collisions, payload dynamics and real servo repeatability.

[Pose trace](cold-transfer.csv) · [Results](results.json) · [Inputs](../cases.json) · [Kinematic model](so101.urdf) · [Kinematic helper](cell.py) · [Upstream license](LICENSE-SO101) · [Pinned joint model](https://github.com/TheRobotStudio/SO-ARM100/blob/a758567c3978dfeefe282ede0500085a48fe8f78/Simulation/SO101/so101_new_calib.urdf)
