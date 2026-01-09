#!/usr/bin/env python3
"""
Recipe Optimizer
Generates project "recipes" from available inventory
Optimizes for maximum value/ROI
"""

from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum
import json


class ProjectCategory(Enum):
    """Project categories for marketplaces"""
    HOME_AUTOMATION = "home_automation"
    WEATHER_STATION = "weather_station"
    ROBOTICS = "robotics"
    WEARABLES = "wearables"
    SENSORS = "sensors"
    DISPLAYS = "displays"
    IOT = "iot"
    EDUCATIONAL = "educational"


@dataclass
class ComponentPrice:
    """Component pricing data"""
    component_id: str
    name: str
    typical_price: float  # USD
    salvage_value: float  # If broken/used
    market_demand: str  # high/medium/low


@dataclass
class ProjectRecipe:
    """A complete project that can be built"""
    name: str
    category: ProjectCategory
    description: str
    difficulty: str  # easy/medium/hard

    # Components
    required_components: List[str]
    optional_components: List[str]

    # Economics
    parts_cost: float  # Total component cost
    build_time_hours: float
    market_price_low: float  # eBay/Etsy low end
    market_price_high: float  # eBay/Etsy high end

    # Inventory match
    components_owned: List[str]
    components_needed: List[str]
    inventory_match_percent: float

    # Value metrics
    profit_margin: float
    roi_percent: float
    missing_parts_cost: float

    # Validation
    validated: bool = False
    validation_issues: List[str] = None


class ComponentPriceDatabase:
    """Database of component prices and market values"""

    def __init__(self):
        # Real component prices (approximate, from DigiKey/Amazon)
        self.prices = {
            # Microcontrollers
            'arduino_uno': ComponentPrice('arduino_uno', 'Arduino Uno R3', 25.0, 15.0, 'high'),
            'arduino_nano': ComponentPrice('arduino_nano', 'Arduino Nano', 5.0, 3.0, 'high'),
            'arduino_mega': ComponentPrice('arduino_mega', 'Arduino Mega 2560', 40.0, 25.0, 'medium'),
            'esp32': ComponentPrice('esp32', 'ESP32 Dev Board', 8.0, 5.0, 'high'),
            'esp8266': ComponentPrice('esp8266', 'ESP8266 NodeMCU', 6.0, 3.0, 'high'),

            # Sensors
            'bme280': ComponentPrice('bme280', 'BME280 Sensor', 8.0, 5.0, 'high'),
            'bmp280': ComponentPrice('bmp280', 'BMP280 Sensor', 5.0, 3.0, 'medium'),
            'dht22': ComponentPrice('dht22', 'DHT22 Temp/Humidity', 4.0, 2.0, 'high'),
            'dht11': ComponentPrice('dht11', 'DHT11 Temp/Humidity', 2.0, 1.0, 'medium'),
            'hc_sr04': ComponentPrice('hc_sr04', 'HC-SR04 Ultrasonic', 3.0, 1.5, 'medium'),
            'mpu6050': ComponentPrice('mpu6050', 'MPU6050 Gyro', 5.0, 3.0, 'medium'),

            # Displays
            'oled_ssd1306': ComponentPrice('oled_ssd1306', '0.96" OLED Display', 6.0, 4.0, 'high'),
            'lcd_16x2': ComponentPrice('lcd_16x2', '16x2 LCD Display', 8.0, 5.0, 'medium'),

            # Actuators
            'servo_sg90': ComponentPrice('servo_sg90', 'SG90 Micro Servo', 3.0, 1.5, 'high'),
            'relay': ComponentPrice('relay', '5V Relay Module', 2.0, 1.0, 'high'),

            # Basic components
            'led': ComponentPrice('led', '5mm LED', 0.10, 0.05, 'low'),
            'led_rgb': ComponentPrice('led_rgb', 'RGB LED', 0.50, 0.25, 'medium'),
            'resistor': ComponentPrice('resistor', 'Resistor', 0.05, 0.01, 'low'),
            'capacitor': ComponentPrice('capacitor', 'Capacitor', 0.10, 0.05, 'low'),

            # Power
            'battery_holder': ComponentPrice('battery_holder', '9V Battery Holder', 1.0, 0.5, 'low'),
            'power_supply': ComponentPrice('power_supply', '5V Power Supply', 5.0, 3.0, 'medium'),
        }

    def get_price(self, component_id: str, condition: str = 'new') -> float:
        """Get component price"""
        comp = self.prices.get(component_id.lower())
        if not comp:
            return 0.0

        return comp.typical_price if condition == 'new' else comp.salvage_value

    def get_component(self, component_id: str) -> Optional[ComponentPrice]:
        """Get component info"""
        return self.prices.get(component_id.lower())


class ProjectRecipeDatabase:
    """Database of project recipes"""

    def __init__(self):
        self.recipes = self._load_recipes()

    def _load_recipes(self) -> List[Dict]:
        """Load project recipe templates"""
        return [
            {
                'name': 'WiFi Weather Station',
                'category': ProjectCategory.WEATHER_STATION,
                'description': 'ESP32-based weather station with BME280 sensor and OLED display. Uploads to ThingSpeak/MQTT.',
                'difficulty': 'easy',
                'required_components': ['esp32', 'bme280', 'oled_ssd1306'],
                'optional_components': ['battery_holder', 'resistor', 'led'],
                'build_time_hours': 2.0,
                'market_price_low': 20.0,  # Updated based on eBay research
                'market_price_high': 35.0,  # Kits sell for $17-21, assembled maybe $25-35
                'tags': ['wifi', 'iot', 'weather', 'sensors'],
                'etsy_comparable': 'Weather Station Kit',
                'ebay_search': 'ESP32 Weather Station',
                'notes': 'Price based on eBay comparable kits ($20-21) + assembly value'
            },

            {
                'name': 'Smart Plant Monitor',
                'category': ProjectCategory.HOME_AUTOMATION,
                'description': 'Monitors soil moisture, temperature, and light. Sends notifications when plant needs water.',
                'difficulty': 'easy',
                'required_components': ['arduino_nano', 'dht22', 'oled_ssd1306'],
                'optional_components': ['led', 'resistor', 'battery_holder'],
                'build_time_hours': 1.5,
                'market_price_low': 25.0,
                'market_price_high': 45.0,
                'tags': ['plants', 'gardening', 'automation'],
                'etsy_comparable': 'Plant Watering Monitor',
                'ebay_search': 'Arduino Plant Monitor'
            },

            {
                'name': 'Distance Parking Sensor',
                'category': ProjectCategory.HOME_AUTOMATION,
                'description': 'Helps park car in garage. LED lights change color as you get closer to wall.',
                'difficulty': 'easy',
                'required_components': ['arduino_uno', 'hc_sr04', 'led', 'led', 'led'],
                'optional_components': ['resistor', 'power_supply'],
                'build_time_hours': 1.0,
                'market_price_low': 20.0,
                'market_price_high': 40.0,
                'tags': ['parking', 'garage', 'ultrasonic'],
                'etsy_comparable': 'Garage Parking Assistant',
                'ebay_search': 'Parking Distance Sensor'
            },

            {
                'name': 'Temperature Logger',
                'category': ProjectCategory.SENSORS,
                'description': 'Logs temperature data to SD card. Great for monitoring server rooms, greenhouses, etc.',
                'difficulty': 'medium',
                'required_components': ['arduino_uno', 'dht22', 'lcd_16x2'],
                'optional_components': ['resistor', 'power_supply', 'led'],
                'build_time_hours': 2.5,
                'market_price_low': 30.0,
                'market_price_high': 55.0,
                'tags': ['logging', 'temperature', 'monitoring'],
                'etsy_comparable': 'Temperature Data Logger',
                'ebay_search': 'Arduino Temperature Logger'
            },

            {
                'name': 'IoT Smart Relay Controller',
                'category': ProjectCategory.HOME_AUTOMATION,
                'description': 'WiFi-controlled relay for home automation. Control lights, fans, or appliances via phone.',
                'difficulty': 'medium',
                'required_components': ['esp8266', 'relay', 'led'],
                'optional_components': ['resistor', 'power_supply', 'oled_ssd1306'],
                'build_time_hours': 2.0,
                'market_price_low': 25.0,
                'market_price_high': 50.0,
                'tags': ['wifi', 'home automation', 'relay', 'iot'],
                'etsy_comparable': 'WiFi Smart Switch',
                'ebay_search': 'ESP8266 Relay Controller'
            },

            {
                'name': 'Air Quality Monitor',
                'category': ProjectCategory.SENSORS,
                'description': 'Monitors air quality, temperature, humidity, and pressure. Shows data on OLED display.',
                'difficulty': 'medium',
                'required_components': ['esp32', 'bme280', 'oled_ssd1306'],
                'optional_components': ['led_rgb', 'resistor', 'battery_holder'],
                'build_time_hours': 3.0,
                'market_price_low': 25.0,  # Updated: basic monitors $26-35 on eBay
                'market_price_high': 45.0,  # More realistic than $80
                'tags': ['air quality', 'sensors', 'wifi', 'monitoring'],
                'etsy_comparable': 'Air Quality Monitor',
                'ebay_search': 'ESP32 Air Quality',
                'notes': 'Commercial monitors $26-35, DIY assembled adds some premium'
            },

            {
                'name': 'Simple Robot Car',
                'category': ProjectCategory.ROBOTICS,
                'description': 'Obstacle-avoiding robot car using ultrasonic sensor. Great educational project.',
                'difficulty': 'medium',
                'required_components': ['arduino_uno', 'hc_sr04', 'servo_sg90'],
                'optional_components': ['led', 'resistor', 'battery_holder'],
                'build_time_hours': 4.0,
                'market_price_low': 40.0,
                'market_price_high': 75.0,
                'tags': ['robotics', 'education', 'obstacle avoidance'],
                'etsy_comparable': 'Arduino Robot Car Kit',
                'ebay_search': 'Arduino Obstacle Avoiding Robot'
            },

            {
                'name': 'Desk Weather Display',
                'category': ProjectCategory.DISPLAYS,
                'description': 'Compact desk display showing temperature, humidity, and time. USB powered.',
                'difficulty': 'easy',
                'required_components': ['arduino_nano', 'bme280', 'lcd_16x2'],
                'optional_components': ['resistor', 'led'],
                'build_time_hours': 1.5,
                'market_price_low': 25.0,
                'market_price_high': 45.0,
                'tags': ['desk', 'display', 'weather', 'usb'],
                'etsy_comparable': 'Desk Weather Station',
                'ebay_search': 'Arduino Desk Display'
            },

            # === BEGINNER PROJECTS ===

            {
                'name': 'LED Blink Trainer',
                'category': ProjectCategory.EDUCATIONAL,
                'description': 'Learn Arduino basics with programmable LED patterns. Perfect first project.',
                'difficulty': 'easy',
                'required_components': ['arduino_uno', 'led', 'resistor'],
                'optional_components': [],
                'build_time_hours': 0.5,
                'market_price_low': 10.0,
                'market_price_high': 18.0,
                'tags': ['beginner', 'education', 'basics'],
                'etsy_comparable': 'Arduino Starter Kit',
                'ebay_search': 'Arduino LED Kit'
            },

            {
                'name': 'Digital Thermometer',
                'category': ProjectCategory.SENSORS,
                'description': 'Simple temperature display with DHT22 sensor and LCD screen.',
                'difficulty': 'easy',
                'required_components': ['arduino_uno', 'dht22', 'lcd_16x2'],
                'optional_components': ['resistor'],
                'build_time_hours': 1.0,
                'market_price_low': 15.0,
                'market_price_high': 28.0,
                'tags': ['temperature', 'display', 'sensors'],
                'etsy_comparable': 'Digital Thermometer',
                'ebay_search': 'Arduino Thermometer'
            },

            {
                'name': 'Button Counter',
                'category': ProjectCategory.EDUCATIONAL,
                'description': 'Learn digital input with button presses counted on display.',
                'difficulty': 'easy',
                'required_components': ['arduino_nano', 'lcd_16x2'],
                'optional_components': ['led', 'resistor'],
                'build_time_hours': 0.75,
                'market_price_low': 12.0,
                'market_price_high': 22.0,
                'tags': ['input', 'beginner', 'education'],
                'etsy_comparable': 'Arduino Learning Kit',
                'ebay_search': 'Arduino Button Kit'
            },

            # === HOME AUTOMATION ===

            {
                'name': 'Motion Sensor Light',
                'category': ProjectCategory.HOME_AUTOMATION,
                'description': 'Automatic light that turns on when motion detected. Perfect for closets/hallways.',
                'difficulty': 'easy',
                'required_components': ['arduino_nano', 'hc_sr04', 'relay', 'led'],
                'optional_components': ['resistor'],
                'build_time_hours': 1.5,
                'market_price_low': 18.0,
                'market_price_high': 32.0,
                'tags': ['motion', 'automation', 'lighting'],
                'etsy_comparable': 'Motion Sensor Light',
                'ebay_search': 'Arduino Motion Light'
            },

            {
                'name': 'Smart Doorbell',
                'category': ProjectCategory.HOME_AUTOMATION,
                'description': 'WiFi doorbell that sends notifications to your phone when pressed.',
                'difficulty': 'medium',
                'required_components': ['esp8266', 'relay', 'led'],
                'optional_components': ['resistor', 'oled_ssd1306'],
                'build_time_hours': 2.5,
                'market_price_low': 22.0,
                'market_price_high': 38.0,
                'tags': ['wifi', 'doorbell', 'notifications'],
                'etsy_comparable': 'Smart Doorbell',
                'ebay_search': 'WiFi Doorbell Arduino'
            },

            {
                'name': 'Garage Door Monitor',
                'category': ProjectCategory.HOME_AUTOMATION,
                'description': 'Know if your garage door is open from anywhere. WiFi-enabled with phone alerts.',
                'difficulty': 'medium',
                'required_components': ['esp8266', 'hc_sr04', 'led'],
                'optional_components': ['relay', 'oled_ssd1306'],
                'build_time_hours': 2.0,
                'market_price_low': 20.0,
                'market_price_high': 35.0,
                'tags': ['garage', 'wifi', 'monitoring'],
                'etsy_comparable': 'Garage Door Sensor',
                'ebay_search': 'WiFi Garage Monitor'
            },

            {
                'name': 'Pet Feeder Timer',
                'category': ProjectCategory.HOME_AUTOMATION,
                'description': 'Automatic pet feeder with customizable schedule. Servo-controlled dispenser.',
                'difficulty': 'medium',
                'required_components': ['arduino_uno', 'servo_sg90', 'lcd_16x2'],
                'optional_components': ['led', 'resistor'],
                'build_time_hours': 3.0,
                'market_price_low': 28.0,
                'market_price_high': 48.0,
                'tags': ['pets', 'automation', 'timer'],
                'etsy_comparable': 'Automatic Pet Feeder',
                'ebay_search': 'Arduino Pet Feeder'
            },

            # === ROBOTICS ===

            {
                'name': 'Line Following Robot',
                'category': ProjectCategory.ROBOTICS,
                'description': 'Robot that follows black lines on white surface. Great for competitions.',
                'difficulty': 'medium',
                'required_components': ['arduino_uno', 'servo_sg90'],
                'optional_components': ['led', 'resistor'],
                'build_time_hours': 4.0,
                'market_price_low': 35.0,
                'market_price_high': 60.0,
                'tags': ['robotics', 'competition', 'automation'],
                'etsy_comparable': 'Line Following Robot',
                'ebay_search': 'Arduino Line Follower'
            },

            {
                'name': 'Gesture Controlled Robot',
                'category': ProjectCategory.ROBOTICS,
                'description': 'Control robot with hand gestures using MPU6050 accelerometer.',
                'difficulty': 'hard',
                'required_components': ['arduino_uno', 'mpu6050', 'servo_sg90'],
                'optional_components': ['led', 'oled_ssd1306'],
                'build_time_hours': 5.0,
                'market_price_low': 45.0,
                'market_price_high': 75.0,
                'tags': ['robotics', 'gesture', 'advanced'],
                'etsy_comparable': 'Gesture Robot',
                'ebay_search': 'Gesture Controlled Arduino'
            },

            # === IoT & SENSORS ===

            {
                'name': 'Soil Moisture Monitor',
                'category': ProjectCategory.SENSORS,
                'description': 'Monitor soil moisture for plants. Alerts when watering needed.',
                'difficulty': 'easy',
                'required_components': ['arduino_nano', 'led'],
                'optional_components': ['lcd_16x2', 'resistor'],
                'build_time_hours': 1.0,
                'market_price_low': 12.0,
                'market_price_high': 24.0,
                'tags': ['plants', 'sensors', 'monitoring'],
                'etsy_comparable': 'Soil Moisture Sensor',
                'ebay_search': 'Arduino Soil Monitor'
            },

            {
                'name': 'Water Level Alarm',
                'category': ProjectCategory.SENSORS,
                'description': 'Alerts when water level too high/low. Good for tanks, basements.',
                'difficulty': 'easy',
                'required_components': ['arduino_nano', 'relay', 'led'],
                'optional_components': ['resistor'],
                'build_time_hours': 1.5,
                'market_price_low': 15.0,
                'market_price_high': 28.0,
                'tags': ['water', 'alarm', 'safety'],
                'etsy_comparable': 'Water Level Alarm',
                'ebay_search': 'Arduino Water Alarm'
            },

            {
                'name': 'Light Intensity Logger',
                'category': ProjectCategory.SENSORS,
                'description': 'Log light levels over time. Good for greenhouse monitoring.',
                'difficulty': 'medium',
                'required_components': ['arduino_uno', 'oled_ssd1306'],
                'optional_components': ['led'],
                'build_time_hours': 2.0,
                'market_price_low': 18.0,
                'market_price_high': 32.0,
                'tags': ['light', 'logging', 'monitoring'],
                'etsy_comparable': 'Light Logger',
                'ebay_search': 'Arduino Light Sensor'
            },

            {
                'name': 'WiFi Environmental Monitor',
                'category': ProjectCategory.IOT,
                'description': 'Monitor temp, humidity, pressure from anywhere. Cloud logging.',
                'difficulty': 'medium',
                'required_components': ['esp32', 'bme280', 'oled_ssd1306'],
                'optional_components': ['led'],
                'build_time_hours': 3.0,
                'market_price_low': 28.0,
                'market_price_high': 48.0,
                'tags': ['wifi', 'iot', 'monitoring', 'cloud'],
                'etsy_comparable': 'WiFi Environment Monitor',
                'ebay_search': 'ESP32 Environment Sensor'
            },

            # === DISPLAYS & CLOCKS ===

            {
                'name': 'Digital Clock',
                'category': ProjectCategory.DISPLAYS,
                'description': 'Simple digital clock with LCD display. Time/date shown.',
                'difficulty': 'easy',
                'required_components': ['arduino_uno', 'lcd_16x2'],
                'optional_components': ['led', 'resistor'],
                'build_time_hours': 1.5,
                'market_price_low': 18.0,
                'market_price_high': 30.0,
                'tags': ['clock', 'display', 'time'],
                'etsy_comparable': 'Digital Clock',
                'ebay_search': 'Arduino Clock LCD'
            },

            {
                'name': 'Countdown Timer',
                'category': ProjectCategory.DISPLAYS,
                'description': 'Programmable countdown timer with alarm. Good for kitchen/gym.',
                'difficulty': 'easy',
                'required_components': ['arduino_nano', 'lcd_16x2', 'led'],
                'optional_components': ['resistor'],
                'build_time_hours': 1.0,
                'market_price_low': 15.0,
                'market_price_high': 26.0,
                'tags': ['timer', 'countdown', 'alarm'],
                'etsy_comparable': 'Countdown Timer',
                'ebay_search': 'Arduino Timer'
            },

            {
                'name': 'Scrolling Message Display',
                'category': ProjectCategory.DISPLAYS,
                'description': 'LED matrix showing scrolling messages. Customizable text.',
                'difficulty': 'medium',
                'required_components': ['arduino_uno', 'oled_ssd1306'],
                'optional_components': ['led'],
                'build_time_hours': 2.0,
                'market_price_low': 22.0,
                'market_price_high': 38.0,
                'tags': ['display', 'led', 'messages'],
                'etsy_comparable': 'LED Message Board',
                'ebay_search': 'Arduino LED Matrix'
            },

            # === SECURITY ===

            {
                'name': 'Door Open Alarm',
                'category': ProjectCategory.HOME_AUTOMATION,
                'description': 'Simple alarm when door/window opened. Battery powered.',
                'difficulty': 'easy',
                'required_components': ['arduino_nano', 'led', 'resistor'],
                'optional_components': ['relay'],
                'build_time_hours': 1.0,
                'market_price_low': 12.0,
                'market_price_high': 22.0,
                'tags': ['security', 'alarm', 'door'],
                'etsy_comparable': 'Door Alarm',
                'ebay_search': 'Arduino Door Sensor'
            },

            {
                'name': 'Motion Detection Camera Trigger',
                'category': ProjectCategory.HOME_AUTOMATION,
                'description': 'Triggers camera when motion detected. Good for wildlife/security.',
                'difficulty': 'medium',
                'required_components': ['arduino_uno', 'hc_sr04', 'relay'],
                'optional_components': ['led', 'oled_ssd1306'],
                'build_time_hours': 2.5,
                'market_price_low': 25.0,
                'market_price_high': 42.0,
                'tags': ['motion', 'camera', 'security'],
                'etsy_comparable': 'Camera Trigger',
                'ebay_search': 'Arduino Camera Trigger'
            },

            # === ADVANCED/SPECIAL ===

            {
                'name': 'Energy Monitor',
                'category': ProjectCategory.SENSORS,
                'description': 'Monitor home electricity usage in real-time. Track consumption.',
                'difficulty': 'hard',
                'required_components': ['esp32', 'oled_ssd1306'],
                'optional_components': ['led'],
                'build_time_hours': 4.0,
                'market_price_low': 35.0,
                'market_price_high': 65.0,
                'tags': ['energy', 'monitoring', 'wifi'],
                'etsy_comparable': 'Energy Monitor',
                'ebay_search': 'ESP32 Energy Monitor'
            },

            {
                'name': 'Automatic Blind Controller',
                'category': ProjectCategory.HOME_AUTOMATION,
                'description': 'Open/close blinds automatically based on time or light. WiFi controllable.',
                'difficulty': 'hard',
                'required_components': ['esp8266', 'servo_sg90'],
                'optional_components': ['oled_ssd1306', 'led'],
                'build_time_hours': 4.5,
                'market_price_low': 40.0,
                'market_price_high': 70.0,
                'tags': ['automation', 'blinds', 'wifi'],
                'etsy_comparable': 'Smart Blind Controller',
                'ebay_search': 'WiFi Blind Motor'
            },

            {
                'name': 'Aquarium Controller',
                'category': ProjectCategory.SENSORS,
                'description': 'Control temperature, lighting, feeding for aquarium. Full automation.',
                'difficulty': 'hard',
                'required_components': ['arduino_mega', 'dht22', 'relay', 'servo_sg90'],
                'optional_components': ['lcd_16x2', 'led'],
                'build_time_hours': 6.0,
                'market_price_low': 50.0,
                'market_price_high': 85.0,
                'tags': ['aquarium', 'automation', 'complex'],
                'etsy_comparable': 'Aquarium Controller',
                'ebay_search': 'Arduino Aquarium System'
            }
        ]

    def get_all_recipes(self) -> List[Dict]:
        """Get all recipe templates"""
        return self.recipes

    def filter_by_components(self, available_components: List[str]) -> List[Dict]:
        """Filter recipes that can be built with available components"""
        matching = []

        for recipe in self.recipes:
            required = set(recipe['required_components'])
            available = set(available_components)

            # Calculate match percentage
            match_count = len(required & available)
            match_percent = (match_count / len(required)) * 100 if required else 0

            # Include if at least 50% match
            if match_percent >= 50:
                recipe['match_percent'] = match_percent
                recipe['missing'] = list(required - available)
                matching.append(recipe)

        # Sort by match percentage
        return sorted(matching, key=lambda x: x['match_percent'], reverse=True)


class RecipeOptimizer:
    """Optimizes project recipes based on inventory and value"""

    # Pricing disclaimer
    DISCLAIMER = """
    ⚠️  PRICING DISCLAIMER:

    • Market prices are ESTIMATES based on comparable eBay listings
    • Actual selling prices may vary significantly
    • ROI calculations do NOT include:
      - Selling fees (eBay 12.9%, Etsy 6.5%)
      - Shipping costs ($5-10)
      - Packaging materials ($2-5)
      - Your labor time

    • This tool is for PLANNING and OPTIMIZATION, not guaranteed profit
    • Focus on inventory value and project ideas, not resale profit
    """

    def __init__(self):
        self.price_db = ComponentPriceDatabase()
        self.recipe_db = ProjectRecipeDatabase()

    def analyze_inventory(self, inventory: List[Dict]) -> Dict:
        """
        Analyze inventory value

        Args:
            inventory: List of components with condition
                [{'id': 'arduino_uno', 'condition': 'used', 'quantity': 1}, ...]

        Returns:
            {
                'total_value': 50.0,
                'component_count': 5,
                'categories': {...}
            }
        """
        total_value = 0.0
        component_count = 0
        categories = {}

        for item in inventory:
            comp_id = item['id']
            condition = item.get('condition', 'used')
            quantity = item.get('quantity', 1)

            price = self.price_db.get_price(comp_id, condition)
            value = price * quantity
            total_value += value
            component_count += quantity

            # Categorize
            comp = self.price_db.get_component(comp_id)
            if comp:
                category = self._categorize_component(comp_id)
                categories[category] = categories.get(category, 0) + quantity

        return {
            'total_value': round(total_value, 2),
            'component_count': component_count,
            'categories': categories,
            'inventory': inventory
        }

    def _categorize_component(self, comp_id: str) -> str:
        """Categorize component type"""
        if 'arduino' in comp_id or 'esp' in comp_id:
            return 'microcontroller'
        elif any(s in comp_id for s in ['bme', 'bmp', 'dht', 'hc_sr', 'mpu']):
            return 'sensor'
        elif any(d in comp_id for d in ['oled', 'lcd']):
            return 'display'
        elif any(a in comp_id for a in ['servo', 'relay']):
            return 'actuator'
        else:
            return 'basic'

    def generate_recipes(self, inventory: List[Dict], top_n: int = 5) -> List[ProjectRecipe]:
        """
        Generate optimized project recipes from inventory

        Args:
            inventory: List of available components
            top_n: Return top N recipes by ROI

        Returns:
            List of ProjectRecipe objects, sorted by ROI
        """
        # Extract component IDs
        available_ids = [item['id'] for item in inventory]

        # Find matching recipes
        matching_recipes = self.recipe_db.filter_by_components(available_ids)

        # Calculate economics for each recipe
        project_recipes = []

        for recipe_template in matching_recipes:
            recipe = self._calculate_recipe_economics(
                recipe_template,
                inventory,
                available_ids
            )
            project_recipes.append(recipe)

        # Sort by ROI
        sorted_recipes = sorted(project_recipes, key=lambda x: x.roi_percent, reverse=True)

        return sorted_recipes[:top_n]

    def _calculate_recipe_economics(
        self,
        template: Dict,
        inventory: List[Dict],
        available_ids: List[str]
    ) -> ProjectRecipe:
        """Calculate full economics for a recipe"""

        required = template['required_components']
        optional = template.get('optional_components', [])

        # Calculate costs
        parts_cost = 0.0
        components_owned = []
        components_needed = []
        missing_parts_cost = 0.0

        for comp_id in required:
            if comp_id in available_ids:
                components_owned.append(comp_id)
                # Use salvage value (already own it)
                parts_cost += self.price_db.get_price(comp_id, 'used')
            else:
                components_needed.append(comp_id)
                # Need to buy it
                cost = self.price_db.get_price(comp_id, 'new')
                parts_cost += cost
                missing_parts_cost += cost

        # Calculate match percentage
        match_percent = (len(components_owned) / len(required)) * 100 if required else 0

        # Calculate profit and ROI
        avg_market_price = (template['market_price_low'] + template['market_price_high']) / 2
        profit = avg_market_price - parts_cost
        roi_percent = (profit / parts_cost * 100) if parts_cost > 0 else 0

        return ProjectRecipe(
            name=template['name'],
            category=template['category'],
            description=template['description'],
            difficulty=template['difficulty'],
            required_components=required,
            optional_components=optional,
            parts_cost=round(parts_cost, 2),
            build_time_hours=template['build_time_hours'],
            market_price_low=template['market_price_low'],
            market_price_high=template['market_price_high'],
            components_owned=components_owned,
            components_needed=components_needed,
            inventory_match_percent=round(match_percent, 1),
            profit_margin=round(profit, 2),
            roi_percent=round(roi_percent, 1),
            missing_parts_cost=round(missing_parts_cost, 2)
        )

    def generate_shopping_list(self, recipe: ProjectRecipe) -> Dict:
        """Generate shopping list for missing components"""
        shopping_list = []
        total_cost = 0.0

        for comp_id in recipe.components_needed:
            comp = self.price_db.get_component(comp_id)
            if comp:
                shopping_list.append({
                    'component': comp.name,
                    'id': comp_id,
                    'price': comp.typical_price,
                    'buy_url': f'https://www.amazon.com/s?k={comp.name.replace(" ", "+")}'
                })
                total_cost += comp.typical_price

        return {
            'items': shopping_list,
            'total_cost': round(total_cost, 2),
            'count': len(shopping_list)
        }

    def generate_recipes_filtered(
        self,
        inventory: List[Dict],
        max_difficulty: str = None,  # 'easy', 'medium', 'hard'
        max_build_hours: float = None,
        max_budget: float = None,
        min_match_percent: float = 50.0,
        top_n: int = 10
    ) -> List[ProjectRecipe]:
        """
        Generate recipes with advanced filtering

        Args:
            inventory: Available components
            max_difficulty: Filter by difficulty ('easy', 'medium', 'hard')
            max_build_hours: Maximum build time in hours
            max_budget: Maximum budget for missing parts
            min_match_percent: Minimum inventory match percentage
            top_n: Return top N results

        Returns:
            Filtered and sorted recipes
        """
        # Get base recipes
        available_ids = [item['id'] for item in inventory]
        matching_recipes = self.recipe_db.filter_by_components(available_ids)

        # Apply filters
        filtered_recipes = []

        for recipe_template in matching_recipes:
            # Filter by difficulty
            if max_difficulty:
                difficulty_order = {'easy': 0, 'medium': 1, 'hard': 2}
                if difficulty_order.get(recipe_template['difficulty'], 3) > difficulty_order.get(max_difficulty, 0):
                    continue

            # Filter by build time
            if max_build_hours and recipe_template['build_time_hours'] > max_build_hours:
                continue

            # Calculate economics
            recipe = self._calculate_recipe_economics(
                recipe_template,
                inventory,
                available_ids
            )

            # Filter by budget
            if max_budget and recipe.missing_parts_cost > max_budget:
                continue

            # Filter by match percentage
            if recipe.inventory_match_percent < min_match_percent:
                continue

            filtered_recipes.append(recipe)

        # Sort by ROI
        sorted_recipes = sorted(filtered_recipes, key=lambda x: x.roi_percent, reverse=True)

        return sorted_recipes[:top_n]

    def optimize_for_budget(
        self,
        inventory: List[Dict],
        budget: float,
        goal: str = 'roi'  # 'roi', 'learning', 'complexity', 'speed'
    ) -> Dict:
        """
        Optimize project selection for a given budget

        Args:
            inventory: Available components
            budget: Total budget available (for missing parts)
            goal: Optimization goal
                - 'roi': Maximize return on investment
                - 'learning': Best for education/skill building
                - 'complexity': Most features for budget
                - 'speed': Fastest to build

        Returns:
            Dict with recommendations and budget breakdown
        """
        # Get all recipes that fit budget
        available_ids = [item['id'] for item in inventory]
        matching_recipes = self.recipe_db.filter_by_components(available_ids)

        affordable_recipes = []

        for recipe_template in matching_recipes:
            recipe = self._calculate_recipe_economics(
                recipe_template,
                inventory,
                available_ids
            )

            if recipe.missing_parts_cost <= budget:
                affordable_recipes.append(recipe)

        if not affordable_recipes:
            return {
                'recommendation': None,
                'message': f'No projects fit within ${budget} budget. Minimum needed: ${min(r.missing_parts_cost for r in matching_recipes) if matching_recipes else 0}',
                'alternatives': []
            }

        # Sort by goal
        if goal == 'roi':
            sorted_recipes = sorted(affordable_recipes, key=lambda x: x.roi_percent, reverse=True)
        elif goal == 'learning':
            # Prioritize medium difficulty, good documentation
            sorted_recipes = sorted(affordable_recipes, key=lambda x: (
                1 if x.difficulty == 'medium' else 0,
                x.inventory_match_percent
            ), reverse=True)
        elif goal == 'complexity':
            # Most components / features
            sorted_recipes = sorted(affordable_recipes, key=lambda x: len(x.required_components), reverse=True)
        elif goal == 'speed':
            # Fastest to build
            sorted_recipes = sorted(affordable_recipes, key=lambda x: x.build_time_hours)
        else:
            sorted_recipes = affordable_recipes

        best = sorted_recipes[0]

        return {
            'recommendation': {
                'name': best.name,
                'description': best.description,
                'difficulty': best.difficulty,
                'build_time_hours': best.build_time_hours,
                'economics': {
                    'parts_cost': best.parts_cost,
                    'missing_parts_cost': best.missing_parts_cost,
                    'market_price_low': best.market_price_low,
                    'market_price_high': best.market_price_high,
                    'profit_margin': best.profit_margin,
                    'roi_percent': best.roi_percent
                },
                'inventory': {
                    'match_percent': best.inventory_match_percent,
                    'components_owned': best.components_owned,
                    'components_needed': best.components_needed
                }
            },
            'budget_breakdown': {
                'total_budget': budget,
                'needed_for_project': best.missing_parts_cost,
                'remaining': round(budget - best.missing_parts_cost, 2)
            },
            'alternatives': [
                {
                    'name': r.name,
                    'missing_cost': r.missing_parts_cost,
                    'roi': r.roi_percent,
                    'build_time': r.build_time_hours
                }
                for r in sorted_recipes[1:4]  # Top 3 alternatives
            ],
            'message': f'Best project for ${budget} budget ({goal} optimized): {best.name}'
        }


def main():
    """Demo recipe optimizer"""
    print("="*70)
    print("  PROJECT RECIPE OPTIMIZER")
    print("  Turn Your Junk Drawer Into Profit")
    print("="*70)
    print()

    # Example inventory (what you have lying around)
    inventory = [
        {'id': 'arduino_uno', 'condition': 'used', 'quantity': 1},
        {'id': 'esp32', 'condition': 'new', 'quantity': 1},
        {'id': 'bme280', 'condition': 'used', 'quantity': 1},
        {'id': 'oled_ssd1306', 'condition': 'new', 'quantity': 1},
        {'id': 'hc_sr04', 'condition': 'used', 'quantity': 2},
        {'id': 'led', 'condition': 'new', 'quantity': 10},
        {'id': 'resistor', 'condition': 'new', 'quantity': 20},
        {'id': 'servo_sg90', 'condition': 'used', 'quantity': 1},
    ]

    print("YOUR INVENTORY:")
    print("-"*70)
    for item in inventory:
        print(f"  • {item['quantity']}x {item['id']} ({item['condition']})")
    print()

    # Analyze inventory value
    optimizer = RecipeOptimizer()
    analysis = optimizer.analyze_inventory(inventory)

    print("INVENTORY ANALYSIS:")
    print("-"*70)
    print(f"  Total Value: ${analysis['total_value']}")
    print(f"  Component Count: {analysis['component_count']}")
    print(f"  Categories: {analysis['categories']}")
    print()

    # Generate optimized recipes
    print("RECOMMENDED PROJECTS (Sorted by ROI):")
    print("="*70)
    print()

    recipes = optimizer.generate_recipes(inventory, top_n=5)

    for i, recipe in enumerate(recipes, 1):
        print(f"{i}. {recipe.name}")
        print(f"   Category: {recipe.category.value} | Difficulty: {recipe.difficulty}")
        print(f"   {recipe.description}")
        print()
        print(f"   📊 ECONOMICS:")
        print(f"      Parts Cost:    ${recipe.parts_cost}")
        print(f"      Market Price:  ${recipe.market_price_low}-${recipe.market_price_high}")
        print(f"      Profit:        ${recipe.profit_margin}")
        print(f"      ROI:           {recipe.roi_percent}%")
        print()
        print(f"   📦 INVENTORY:")
        print(f"      Match:         {recipe.inventory_match_percent}%")
        print(f"      Have:          {len(recipe.components_owned)}/{len(recipe.required_components)} components")
        print(f"      Need to buy:   ${recipe.missing_parts_cost}")
        print()

        if recipe.components_needed:
            shopping = optimizer.generate_shopping_list(recipe)
            print(f"   🛒 SHOPPING LIST:")
            for item in shopping['items']:
                print(f"      • {item['component']} - ${item['price']}")
        else:
            print(f"   ✅ You have everything needed!")

        print()
        print("-"*70)
        print()

    # Summary
    print("="*70)
    print("  VALUE SUMMARY")
    print("="*70)
    print()
    print(f"Current inventory value: ${analysis['total_value']}")
    print()
    print("Top 3 projects you can build:")
    for i, recipe in enumerate(recipes[:3], 1):
        print(f"  {i}. {recipe.name}")
        print(f"     Investment: ${recipe.parts_cost} → Sell for: ${recipe.market_price_high}")
        print(f"     Profit: ${recipe.profit_margin} ({recipe.roi_percent}% ROI)")
    print()
    print("💰 Turn $50 of parts into $150+ of products!")
    print()


if __name__ == '__main__':
    main()
