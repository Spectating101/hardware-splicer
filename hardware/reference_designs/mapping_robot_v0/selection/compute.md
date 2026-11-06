# On-board computer and IMU (Build 1, test 1)

Searched Ruten 2026-11-06 (read-only, 8 requests): `Raspberry Pi 4 4GB`, `樹莓派4 4GB`, `Raspberry Pi 5 4GB`, `GY-521 MPU6050`.

| Candidate | Listing | Sold | Why not / why |
|---|---|---|---|
| **Raspberry Pi 4 Model B 4 GB** | [22640800216898](https://www.ruten.com.tw/item/22640800216898/) NT$3,171 | 0 | **Chosen.** Single-variant listing (most Pi listings are multi-variant ranges); 3.0 A recommended supply against the Pi 5's 5.0 A, which matters for the 60 minute target; ROS 2 Jazzy is Tier 1 on Ubuntu 24.04 arm64 until May 2029. Seller says delivery takes about seven days, so it probably ships from abroad. |
| Raspberry Pi 5 4 GB | e.g. [22525874462232](https://www.ruten.com.tw/item/22525874462232/) NT$4,140-5,600 | 0 | **Alternative.** Faster, but needs a 5 A supply and draws more; listings are variant ranges. |
| **GY-521 (MPU-6050)** | [21438233309457](https://www.ruten.com.tw/item/21438233309457/) NT$85 | 634 | **Chosen.** Most-sold domestic IMU board; seller publishes chip, 3-5 V supply with regulator, I2C, 2.54 mm pitch. Seller warns that an equivalent board from another factory may be shipped. |

Open on the bench: the Pi's current under SLAM and Nav2 (1.4 A assumed), board dimensions from the drawings, the IMU board
actually received.
