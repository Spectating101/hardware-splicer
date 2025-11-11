"""
Per-class confidence thresholds for Circuit.AI

This module defines confidence thresholds for different component classes
to reduce false positives, especially for common components like resistors and capacitors.
"""

# Per-class confidence thresholds
# Higher thresholds for common components to reduce false positives
CONFIDENCE_THRESHOLDS = {
    # Common passive components - higher threshold to reduce false positives
    "resistor": 0.35,
    "capacitor": 0.35,
    "inductor": 0.30,
    
    # Active components - moderate threshold
    "diode": 0.30,
    "transistor": 0.25,
    "ic": 0.25,
    
    # Mechanical components - lower threshold as they're more distinct
    "connector": 0.20,
    "switch": 0.20,
    "led": 0.30,
    "crystal": 0.25,
    
    # Power components
    "relay": 0.25,
    "transformer": 0.25,
    "fuse": 0.20,
    "potentiometer": 0.25,
    
    # Sensors and special components
    "thermistor": 0.25,
    "varistor": 0.25,
    "photodiode": 0.25,
    "phototransistor": 0.25,
    "optoisolator": 0.25,
    
    # ICs and processors
    "voltage_regulator": 0.25,
    "oscillator": 0.25,
    "filter": 0.25,
    "amplifier": 0.25,
    "comparator": 0.25,
    "multiplexer": 0.25,
    "demultiplexer": 0.25,
    "encoder": 0.25,
    "decoder": 0.25,
    "counter": 0.25,
    "flip_flop": 0.25,
    "memory": 0.25,
    "microcontroller": 0.25,
    "microprocessor": 0.25,
    "dsp": 0.25,
    "fpga": 0.25,
    "cpld": 0.25,
    "adc": 0.25,
    "dac": 0.25,
    "timer": 0.25,
    "watchdog": 0.25,
    
    # Communication interfaces
    "uart": 0.25,
    "spi": 0.25,
    "i2c": 0.25,
    "can": 0.25,
    "usb": 0.25,
    "ethernet": 0.25,
    "wifi": 0.25,
    "bluetooth": 0.25,
    "gps": 0.25,
    
    # Sensors and actuators
    "sensor": 0.25,
    "actuator": 0.25,
    "motor": 0.25,
    "servo": 0.25,
    "stepper": 0.25,
    "dc_motor": 0.25,
    "ac_motor": 0.25,
    "generator": 0.25,
    
    # Power management
    "battery": 0.25,
    "charger": 0.25,
    "power_supply": 0.25,
    "inverter": 0.25,
    "converter": 0.25,
    "rectifier": 0.25,
}

# Default confidence threshold for unknown classes
DEFAULT_CONFIDENCE = 0.25

def get_confidence_threshold(class_name: str) -> float:
    """
    Get confidence threshold for a specific class.
    
    Args:
        class_name: Name of the component class
        
    Returns:
        Confidence threshold for the class
    """
    return CONFIDENCE_THRESHOLDS.get(class_name.lower(), DEFAULT_CONFIDENCE)

def filter_detections_by_confidence(detections: list, class_names: dict) -> list:
    """
    Filter detections based on per-class confidence thresholds.
    
    Args:
        detections: List of detection dictionaries
        class_names: Dictionary mapping class IDs to names
        
    Returns:
        Filtered list of detections
    """
    filtered_detections = []
    
    for detection in detections:
        class_id = detection.get("class_id")
        confidence = detection.get("confidence", 0.0)
        
        if class_id is not None and class_id in class_names:
            class_name = class_names[class_id]
            threshold = get_confidence_threshold(class_name)
            
            if confidence >= threshold:
                filtered_detections.append(detection)
        else:
            # Use default threshold for unknown classes
            if confidence >= DEFAULT_CONFIDENCE:
                filtered_detections.append(detection)
    
    return filtered_detections

def get_class_statistics(detections: list, class_names: dict) -> dict:
    """
    Get statistics about detections per class.
    
    Args:
        detections: List of detection dictionaries
        class_names: Dictionary mapping class IDs to names
        
    Returns:
        Dictionary with class statistics
    """
    stats = {}
    
    for detection in detections:
        class_id = detection.get("class_id")
        confidence = detection.get("confidence", 0.0)
        
        if class_id is not None and class_id in class_names:
            class_name = class_names[class_id]
            
            if class_name not in stats:
                stats[class_name] = {
                    "count": 0,
                    "total_confidence": 0.0,
                    "max_confidence": 0.0,
                    "min_confidence": 1.0,
                    "threshold": get_confidence_threshold(class_name)
                }
            
            stats[class_name]["count"] += 1
            stats[class_name]["total_confidence"] += confidence
            stats[class_name]["max_confidence"] = max(stats[class_name]["max_confidence"], confidence)
            stats[class_name]["min_confidence"] = min(stats[class_name]["min_confidence"], confidence)
    
    # Calculate average confidence
    for class_name, data in stats.items():
        if data["count"] > 0:
            data["avg_confidence"] = data["total_confidence"] / data["count"]
        else:
            data["avg_confidence"] = 0.0
    
    return stats

def update_thresholds_from_data(stats: dict, target_precision: float = 0.8) -> dict:
    """
    Suggest updated thresholds based on detection statistics.
    
    Args:
        stats: Class statistics from get_class_statistics
        target_precision: Target precision for threshold adjustment
        
    Returns:
        Dictionary with suggested new thresholds
    """
    suggestions = {}
    
    for class_name, data in stats.items():
        current_threshold = data["threshold"]
        avg_confidence = data["avg_confidence"]
        count = data["count"]
        
        # If we have enough data and average confidence is significantly different from threshold
        if count >= 10:
            if avg_confidence > current_threshold + 0.1:
                # Average confidence is higher, we can increase threshold
                suggestions[class_name] = min(avg_confidence - 0.05, 0.5)
            elif avg_confidence < current_threshold - 0.1:
                # Average confidence is lower, we should decrease threshold
                suggestions[class_name] = max(avg_confidence + 0.05, 0.1)
    
    return suggestions

