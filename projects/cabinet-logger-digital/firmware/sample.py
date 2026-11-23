def read_channels(sensor):
    """GJSON uses degrees Celsius, relative humidity percent and pascals."""
    try:
        return {
            "T": sensor.temperature,
            "H": sensor.relative_humidity,
            "P": sensor.pressure * 100,
        }
    except (OSError, RuntimeError, ValueError):
        return {"error": "sensor_error"}
