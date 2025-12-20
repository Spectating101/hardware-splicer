"""
Lightweight ArUco marker locator to aid future robot/bench calibration.
Uses OpenCV's built-in ArUco support to find markers and return their pixel coords.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import cv2
import numpy as np


@dataclass
class ArucoMarker:
    marker_id: int
    corners: List[Tuple[float, float]]  # four (x, y) corners
    center: Tuple[float, float]


def detect_markers(image_bgr: np.ndarray, dictionary: str = "DICT_4X4_50") -> List[ArucoMarker]:
    """
    Detect ArUco markers in a BGR image.
    Returns a list of ArucoMarker with pixel coordinates.
    """
    if image_bgr is None:
        return []

    dict_map = {
        "DICT_4X4_50": cv2.aruco.DICT_4X4_50,
        "DICT_5X5_50": cv2.aruco.DICT_5X5_50,
        "DICT_6X6_50": cv2.aruco.DICT_6X6_50,
        "DICT_7X7_50": cv2.aruco.DICT_7X7_50,
    }
    dict_id = dict_map.get(dictionary, cv2.aruco.DICT_4X4_50)
    aruco_dict = cv2.aruco.getPredefinedDictionary(dict_id)
    parameters = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)

    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    corners, ids, _ = detector.detectMarkers(gray)
    markers: List[ArucoMarker] = []
    if ids is None:
        return markers

    for marker_id, pts in zip(ids.flatten(), corners):
        pts_list = [(float(x), float(y)) for x, y in pts.reshape(-1, 2)]
        cx = sum(p[0] for p in pts_list) / 4.0
        cy = sum(p[1] for p in pts_list) / 4.0
        markers.append(ArucoMarker(marker_id=int(marker_id), corners=pts_list, center=(cx, cy)))
    return markers
