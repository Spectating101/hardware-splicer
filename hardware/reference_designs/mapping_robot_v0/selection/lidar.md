# LiDAR (Build 1, test 1)

Searched Ruten 2026-11-06 (read-only, 10 requests): `LD06 光達`, `LD19 雷射雷達`, `YDLIDAR X2`, `RPLIDAR C1`,
`小米 掃地機 雷射頭 LDS`.

| Candidate | Best listing | Sold | Why not / why |
|---|---|---|---|
| **Slamtec RPLIDAR C1** | [22403646891274](https://www.ruten.com.tw/item/22403646891274/) NT$2,700 | 5 | **Chosen.** 12 m range, manufacturer datasheet with power, interface, pinout and mass; the motor needs no control line; official SDK and ROS 2 driver (`sllidar_ros2`) name the C1. |
| YDLIDAR X2L | [22228755677610](https://www.ruten.com.tw/item/22228755677610/) NT$1,990 | 2 | **Alternative.** Cheaper, 8 m (meets ≥ 6 m), vendor datasheet and ROS driver exist; not sourced in this pass. |
| LDROBOT LD19 (D300 kit) / LD06 | [22247757888864](https://www.ruten.com.tw/item/22247757888864/) NT$3,800 | 3 | Dearer; LD06 listing has no sales. |
| Xiaomi LDS spare | e.g. [22508773748036](https://www.ruten.com.tw/item/22508773748036/) NT$576 | 0 | Cheapest, but titles name the "雷射頭…電機馬達", i.e. possibly only the spin motor, and the pinout is disputed between sources. It belongs to Build 2's donor work. |

Requirement check (`REQUIREMENTS.md`): range 12 m ≥ 6 m; documented protocol with an open decoder: yes. Supply 5 V at up to
0.26 A comes from the 5 V rail, so the buck converter must cover it. Its UART is 3.3 V, matching an ESP32 or a Pi directly.

Open on the bench: body dimensions (datasheet drawing only), actual current at 10 Hz.
