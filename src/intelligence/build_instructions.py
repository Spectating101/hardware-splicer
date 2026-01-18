#!/usr/bin/env python3
"""
Build Instructions Generator
Creates step-by-step assembly guides for each project recipe
"""

from typing import Dict, List
from dataclasses import dataclass


@dataclass
class WiringConnection:
    """A single wire connection"""
    component: str
    pin: str
    connects_to: str
    connects_to_pin: str
    wire_type: str = "jumper"  # jumper, power, ground


@dataclass
class BuildStep:
    """A single build step"""
    step_number: int
    title: str
    description: str
    components_needed: List[str]
    wiring: List[WiringConnection]
    image_url: str = None
    tips: List[str] = None
    warnings: List[str] = None


class ComponentPinouts:
    """Standard pinouts for common components"""

    PINOUTS = {
        'arduino_uno': {
            'power': ['5V', '3.3V', 'GND', 'VIN'],
            'digital': [f'D{i}' for i in range(14)],
            'analog': [f'A{i}' for i in range(6)],
            'i2c': {'SDA': 'A4', 'SCL': 'A5'}
        },
        'arduino_nano': {
            'power': ['5V', '3.3V', 'GND', 'VIN'],
            'digital': [f'D{i}' for i in range(14)],
            'analog': [f'A{i}' for i in range(8)],
            'i2c': {'SDA': 'A4', 'SCL': 'A5'}
        },
        'esp32': {
            'power': ['3.3V', 'GND', '5V'],
            'gpio': [f'GPIO{i}' for i in [0, 1, 2, 3, 4, 5, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 23, 25, 26, 27, 32, 33]],
            'i2c': {'SDA': 'GPIO21', 'SCL': 'GPIO22'}
        },
        'esp8266': {
            'power': ['3.3V', 'GND'],
            'gpio': ['D0', 'D1', 'D2', 'D3', 'D4', 'D5', 'D6', 'D7', 'D8'],
            'i2c': {'SDA': 'D2', 'SCL': 'D1'}
        },
        'bme280': {
            'power': ['VCC', 'GND'],
            'i2c': ['SDA', 'SCL'],
            'voltage': '3.3V'
        },
        'dht22': {
            'pins': ['VCC', 'DATA', 'NC', 'GND'],
            'voltage': '3.3V-5V'
        },
        'hc_sr04': {
            'pins': ['VCC', 'TRIG', 'ECHO', 'GND'],
            'voltage': '5V'
        },
        'servo_sg90': {
            'pins': ['VCC', 'GND', 'SIGNAL'],
            'voltage': '5V',
            'current': '500-650mA'
        },
        'oled_ssd1306': {
            'power': ['VCC', 'GND'],
            'i2c': ['SDA', 'SCL'],
            'voltage': '3.3V-5V'
        },
        'lcd_16x2': {
            'pins': ['VSS', 'VDD', 'V0', 'RS', 'RW', 'E', 'D0-D7', 'A', 'K'],
            'voltage': '5V'
        },
        'relay': {
            'pins': ['VCC', 'GND', 'IN'],
            'voltage': '5V'
        }
    }


class BuildInstructionsGenerator:
    """Generates step-by-step build instructions for projects"""

    def __init__(self):
        self.pinouts = ComponentPinouts()

        # Pre-defined instruction templates for common project types
        self.templates = self._load_instruction_templates()

    def _load_instruction_templates(self) -> Dict:
        """Load instruction templates for different project types"""
        return {
            'Air Quality Monitor': self._generate_air_quality_instructions,
            'WiFi Weather Station': self._generate_weather_station_instructions,
            'Simple Robot Car': self._generate_robot_car_instructions,
            'Smart Plant Monitor': self._generate_plant_monitor_instructions,
            'Distance Parking Sensor': self._generate_parking_sensor_instructions,
            'LED Blink Trainer': self._generate_led_blink_instructions,
            'Digital Thermometer': self._generate_thermometer_instructions,
            'Motion Sensor Light': self._generate_motion_light_instructions,
            'Automatic Blind Controller': self._generate_blind_controller_instructions,
            'IoT Smart Relay Controller': self._generate_smart_relay_instructions,
            'Smart Doorbell': self._generate_smart_doorbell_instructions,
            'Energy Monitor': self._generate_energy_monitor_instructions,
            'Soil Moisture Monitor': self._generate_soil_moisture_instructions,
            'Door Open Alarm': self._generate_door_alarm_instructions,
            'Water Level Alarm': self._generate_water_level_instructions,
            # Add more as needed
        }

    def list_available_projects(self) -> List[str]:
        """
        List all projects with available build instructions
        """
        return list(self.templates.keys())

    def generate_instructions(self, project_name: str, components: List[str] = None) -> Dict:
        """
        Generate complete build instructions for a project

        Args:
            project_name: Name of the project
            components: List of component IDs needed

        Returns:
            Dict with complete instructions
        """
        # Check if we have a template for this project
        if project_name in self.templates:
            return self.templates[project_name]()
        else:
            # Generate generic instructions
            return self._generate_generic_instructions(project_name, components)

    def _generate_air_quality_instructions(self) -> Dict:
        """Instructions for Air Quality Monitor (ESP32 + BME280 + OLED)"""
        return {
            'project_name': 'Air Quality Monitor',
            'difficulty': 'medium',
            'build_time': '3 hours',
            'skill_level': 'Intermediate',

            'tools_needed': [
                'Breadboard',
                'Jumper wires (male-to-male)',
                'USB cable for ESP32',
                'Computer with Arduino IDE'
            ],

            'components': [
                {'id': 'esp32', 'quantity': 1, 'notes': 'Any ESP32 dev board works'},
                {'id': 'bme280', 'quantity': 1, 'notes': 'I2C version recommended'},
                {'id': 'oled_ssd1306', 'quantity': 1, 'notes': '0.96" I2C OLED display'}
            ],

            'steps': [
                {
                    'number': 1,
                    'title': 'Prepare Components',
                    'description': 'Gather all components and verify they work individually.',
                    'details': [
                        'Place ESP32 on breadboard',
                        'Verify BME280 sensor is intact (no bent pins)',
                        'Check OLED display for any damage'
                    ],
                    'time': '5 minutes',
                    'tips': [
                        'Test each component before assembly to save debugging time'
                    ]
                },
                {
                    'number': 2,
                    'title': 'Wire Power Rails',
                    'description': 'Set up breadboard power distribution.',
                    'wiring': [
                        {'from': 'ESP32 3.3V', 'to': 'Breadboard + rail', 'color': 'red'},
                        {'from': 'ESP32 GND', 'to': 'Breadboard - rail', 'color': 'black'}
                    ],
                    'details': [
                        'Connect ESP32 3.3V pin to breadboard positive rail',
                        'Connect ESP32 GND to breadboard negative rail',
                        'This creates a shared power bus for all components'
                    ],
                    'time': '5 minutes',
                    'warnings': [
                        '⚠️ Use 3.3V NOT 5V - BME280 is 3.3V only!',
                        '⚠️ Using 5V will damage the BME280 permanently'
                    ]
                },
                {
                    'number': 3,
                    'title': 'Connect BME280 Sensor',
                    'description': 'Wire BME280 to ESP32 I2C bus.',
                    'wiring': [
                        {'from': 'BME280 VCC', 'to': '3.3V rail', 'color': 'red'},
                        {'from': 'BME280 GND', 'to': 'GND rail', 'color': 'black'},
                        {'from': 'BME280 SDA', 'to': 'ESP32 GPIO21', 'color': 'yellow'},
                        {'from': 'BME280 SCL', 'to': 'ESP32 GPIO22', 'color': 'green'}
                    ],
                    'details': [
                        'VCC → 3.3V (power)',
                        'GND → GND (ground)',
                        'SDA → GPIO21 (I2C data)',
                        'SCL → GPIO22 (I2C clock)'
                    ],
                    'time': '10 minutes',
                    'tips': [
                        'Keep I2C wires short for reliable communication',
                        'SDA and SCL can be shared with other I2C devices'
                    ]
                },
                {
                    'number': 4,
                    'title': 'Connect OLED Display',
                    'description': 'Wire OLED to the same I2C bus as BME280.',
                    'wiring': [
                        {'from': 'OLED VCC', 'to': '3.3V rail', 'color': 'red'},
                        {'from': 'OLED GND', 'to': 'GND rail', 'color': 'black'},
                        {'from': 'OLED SDA', 'to': 'ESP32 GPIO21', 'color': 'yellow'},
                        {'from': 'OLED SCL', 'to': 'ESP32 GPIO22', 'color': 'green'}
                    ],
                    'details': [
                        'VCC → 3.3V (shared with BME280)',
                        'GND → GND (shared ground)',
                        'SDA → GPIO21 (same as BME280 SDA)',
                        'SCL → GPIO22 (same as BME280 SCL)'
                    ],
                    'time': '10 minutes',
                    'tips': [
                        'Multiple I2C devices can share the same bus',
                        'Each device has a unique address (BME280: 0x76, OLED: 0x3C)'
                    ]
                },
                {
                    'number': 5,
                    'title': 'Verify Wiring',
                    'description': 'Double-check all connections before powering on.',
                    'checklist': [
                        '✓ All VCC connections go to 3.3V (NOT 5V)',
                        '✓ All GND connections are secure',
                        '✓ SDA wires go to GPIO21',
                        '✓ SCL wires go to GPIO22',
                        '✓ No loose wires or short circuits'
                    ],
                    'time': '5 minutes',
                    'warnings': [
                        '⚠️ Double-check voltage before power on!',
                        '⚠️ One wrong connection can fry components'
                    ]
                },
                {
                    'number': 6,
                    'title': 'Install Libraries',
                    'description': 'Install required Arduino libraries.',
                    'details': [
                        'Open Arduino IDE',
                        'Go to Tools → Manage Libraries',
                        'Install: "Adafruit BME280 Library"',
                        'Install: "Adafruit SSD1306"',
                        'Install: "Adafruit GFX Library"'
                    ],
                    'time': '10 minutes',
                    'code': '''
// Library includes
#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BME280.h>
#include <Adafruit_SSD1306.h>
'''
                },
                {
                    'number': 7,
                    'title': 'Upload Code',
                    'description': 'Flash the Arduino sketch to ESP32.',
                    'details': [
                        'Copy the provided code into Arduino IDE',
                        'Select Board: "ESP32 Dev Module"',
                        'Select Port: (your ESP32 port)',
                        'Click Upload',
                        'Wait for "Done uploading" message'
                    ],
                    'time': '15 minutes',
                    'tips': [
                        'If upload fails, hold BOOT button on ESP32',
                        'Check that USB cable supports data (not just power)'
                    ]
                },
                {
                    'number': 8,
                    'title': 'Test & Calibrate',
                    'description': 'Verify all sensors work correctly.',
                    'details': [
                        'Open Serial Monitor (Tools → Serial Monitor)',
                        'Set baud rate to 115200',
                        'You should see temperature, humidity, pressure readings',
                        'OLED should display sensor data',
                        'Breathe on sensor to see humidity increase'
                    ],
                    'time': '10 minutes',
                    'troubleshooting': [
                        'No display? Check I2C addresses with scanner sketch',
                        'Wrong readings? Sensor might be faulty',
                        'No serial output? Check baud rate'
                    ]
                },
                {
                    'number': 9,
                    'title': 'Optional: Add WiFi Logging',
                    'description': 'Connect to cloud for data logging (optional).',
                    'details': [
                        'Sign up for ThingSpeak (free account)',
                        'Create a new channel',
                        'Add your WiFi credentials and API key to code',
                        'Re-upload sketch',
                        'Data will now log to cloud every 15 seconds'
                    ],
                    'time': '20 minutes (optional)',
                    'tips': [
                        'ThingSpeak free tier allows 3 million messages/year',
                        'Can create graphs and alerts'
                    ]
                }
            ],

            'code_template': '''
#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BME280.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1

Adafruit_BME280 bme;
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

void setup() {
  Serial.begin(115200);

  // Initialize BME280
  if (!bme.begin(0x76)) {
    Serial.println("BME280 sensor not found!");
    while (1);
  }

  // Initialize OLED
  if(!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("OLED not found!");
    while (1);
  }

  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
}

void loop() {
  float temp = bme.readTemperature();
  float humidity = bme.readHumidity();
  float pressure = bme.readPressure() / 100.0F;

  // Display on OLED
  display.clearDisplay();
  display.setCursor(0,0);
  display.print("Temp: ");
  display.print(temp);
  display.println(" C");
  display.print("Humidity: ");
  display.print(humidity);
  display.println(" %");
  display.print("Pressure: ");
  display.print(pressure);
  display.println(" hPa");
  display.display();

  // Print to Serial
  Serial.print("Temperature: ");
  Serial.print(temp);
  Serial.println(" °C");

  delay(2000);
}
''',

            'total_build_time': '3 hours',
            'estimated_cost': '$22-30',

            'next_steps': [
                'Add battery power for portable use',
                'Create enclosure with 3D printing',
                'Add WiFi data logging',
                'Set up alerts for poor air quality'
            ],

            'common_issues': {
                'OLED not displaying': 'Check I2C address (might be 0x3D instead of 0x3C)',
                'BME280 not found': 'Verify 3.3V power (NOT 5V!), check I2C wiring',
                'Garbled display': 'Bad power supply, add capacitor across power pins',
                'Upload fails': 'Hold BOOT button during upload, check USB cable'
            }
        }

    def _generate_weather_station_instructions(self) -> Dict:
        """Instructions for WiFi Weather Station"""
        # Similar structure to air quality monitor
        return {
            'project_name': 'WiFi Weather Station',
            'difficulty': 'easy',
            'build_time': '2 hours',
            # ... similar structure
        }

    def _generate_led_blink_instructions(self) -> Dict:
        """Instructions for LED Blink Trainer (beginner project)"""
        return {
            'project_name': 'LED Blink Trainer',
            'difficulty': 'easy',
            'build_time': '30 minutes',
            'skill_level': 'Absolute Beginner',

            'components': [
                {'id': 'arduino_uno', 'quantity': 1},
                {'id': 'led', 'quantity': 1, 'notes': 'Any color 5mm LED'},
                {'id': 'resistor', 'quantity': 1, 'notes': '220Ω resistor (red-red-brown)'}
            ],

            'steps': [
                {
                    'number': 1,
                    'title': 'Place LED in Breadboard',
                    'description': 'LEDs have polarity - long leg is positive (+)',
                    'details': [
                        'Find the LED - it has two legs',
                        'Long leg = Anode (positive)',
                        'Short leg = Cathode (negative)',
                        'Insert LED into breadboard'
                    ],
                    'warnings': ['⚠️ LED only works one way - long leg to positive!']
                },
                {
                    'number': 2,
                    'title': 'Add Resistor',
                    'description': 'Protect LED from too much current',
                    'wiring': [
                        {'from': 'LED short leg', 'to': 'Resistor', 'color': 'any'},
                        {'from': 'Resistor other end', 'to': 'Arduino GND', 'color': 'black'}
                    ],
                    'warnings': ['⚠️ Without resistor, LED will burn out!']
                },
                {
                    'number': 3,
                    'title': 'Connect to Arduino',
                    'description': 'Wire LED to digital pin',
                    'wiring': [
                        {'from': 'LED long leg', 'to': 'Arduino Pin 13', 'color': 'red'}
                    ]
                },
                {
                    'number': 4,
                    'title': 'Upload Blink Code',
                    'description': 'Flash the classic blink sketch',
                    'time': '5 minutes'
                }
            ],

            'code_template': '''
// LED Blink - Your first Arduino program!
int ledPin = 13;

void setup() {
  pinMode(ledPin, OUTPUT);  // Set pin 13 as output
}

void loop() {
  digitalWrite(ledPin, HIGH);  // Turn LED on
  delay(1000);                 // Wait 1 second
  digitalWrite(ledPin, LOW);   // Turn LED off
  delay(1000);                 // Wait 1 second
}
'''
        }

    def _generate_generic_instructions(self, project_name: str, components: List[str]) -> Dict:
        """Generate basic instructions for projects without specific templates"""
        return {
            'project_name': project_name,
            'note': 'Generic instructions - specific wiring details may vary',
            'components': [{'id': comp, 'quantity': 1} for comp in components],
            'steps': [
                {
                    'number': 1,
                    'title': 'Gather Components',
                    'description': f'Collect all parts needed for {project_name}'
                },
                {
                    'number': 2,
                    'title': 'Plan Layout',
                    'description': 'Arrange components on breadboard before wiring'
                },
                {
                    'number': 3,
                    'title': 'Wire Power',
                    'description': 'Connect power and ground rails first'
                },
                {
                    'number': 4,
                    'title': 'Wire Components',
                    'description': 'Connect each component according to pinout'
                },
                {
                    'number': 5,
                    'title': 'Upload Code',
                    'description': 'Flash Arduino sketch'
                },
                {
                    'number': 6,
                    'title': 'Test',
                    'description': 'Verify all functions work'
                }
            ],
            'code_template': '// Code template not yet available for this project',
            'note': 'For detailed instructions, check Arduino project tutorials online'
        }

    # Add more project-specific instruction generators
    def _generate_robot_car_instructions(self) -> Dict:
        # To be implemented
        pass

    def _generate_plant_monitor_instructions(self) -> Dict:
        """Instructions for Smart Plant Monitor (ESP32 + Soil Moisture + OLED + DHT22)"""
        return {
            'project_name': 'Smart Plant Monitor',
            'difficulty': 'beginner',
            'build_time': '2-3 hours',
            'skill_level': 'Beginner',

            'tools_needed': [
                'Breadboard',
                'Jumper wires (male-to-male)',
                'USB cable for ESP32',
                'Computer with Arduino IDE',
                'Small screwdriver (for adjusting potentiometer if needed)'
            ],

            'components': [
                {'id': 'esp32', 'quantity': 1, 'notes': 'Any ESP32 dev board works'},
                {'id': 'soil_moisture', 'quantity': 1, 'notes': 'Capacitive or resistive sensor'},
                {'id': 'oled_ssd1306', 'quantity': 1, 'notes': '0.96" I2C OLED display'},
                {'id': 'dht22', 'quantity': 1, 'notes': 'Temperature/humidity sensor (optional)'}
            ],

            'market_analysis': {
                'build_cost': 25.00,
                'market_price_low': 45.00,
                'market_price_high': 65.00,
                'profit_margin': '80-160%',
                'comparable_products': [
                    'Amazon plant monitors: $50-70',
                    'Etsy handmade monitors: $40-60'
                ]
            },

            'steps': [
                {
                    'number': 1,
                    'title': 'Prepare Components',
                    'description': 'Gather all components and verify they work.',
                    'details': [
                        'Place ESP32 on breadboard',
                        'Verify soil moisture sensor probes are clean',
                        'Check OLED display for any damage',
                        'Test DHT22 sensor if using (optional)'
                    ],
                    'time': '5 minutes',
                    'tips': [
                        'Clean soil moisture sensor with isopropyl alcohol if used before',
                        'Capacitive sensors are more durable than resistive ones'
                    ]
                },
                {
                    'number': 2,
                    'title': 'Wire Power Rails',
                    'description': 'Set up breadboard power distribution.',
                    'wiring': [
                        {'from': 'ESP32 3.3V', 'to': 'Breadboard + rail', 'color': 'red'},
                        {'from': 'ESP32 GND', 'to': 'Breadboard - rail', 'color': 'black'}
                    ],
                    'details': [
                        'Connect ESP32 3.3V pin to breadboard positive rail',
                        'Connect ESP32 GND to breadboard negative rail',
                        'This creates a shared power bus for all components'
                    ],
                    'time': '5 minutes',
                    'warnings': [
                        '⚠️ Ensure solid connections - poor power can cause sensor errors'
                    ]
                },
                {
                    'number': 3,
                    'title': 'Connect Soil Moisture Sensor',
                    'description': 'Wire soil sensor to ESP32 analog input.',
                    'wiring': [
                        {'from': 'Sensor VCC', 'to': '3.3V rail', 'color': 'red'},
                        {'from': 'Sensor GND', 'to': 'GND rail', 'color': 'black'},
                        {'from': 'Sensor AOUT', 'to': 'ESP32 GPIO34', 'color': 'yellow'}
                    ],
                    'details': [
                        'VCC → 3.3V (power for sensor)',
                        'GND → GND (ground)',
                        'AOUT → GPIO34 (analog reading)',
                        'Note: GPIO34 is an ADC-capable pin on ESP32'
                    ],
                    'time': '10 minutes',
                    'tips': [
                        'GPIO34-39 are ADC1 pins on ESP32, good for analog sensors',
                        'Avoid GPIO0, GPIO2 (used for boot mode)',
                        'Test sensor in dry air vs glass of water to verify readings'
                    ]
                },
                {
                    'number': 4,
                    'title': 'Connect OLED Display',
                    'description': 'Wire OLED display to ESP32 I2C bus.',
                    'wiring': [
                        {'from': 'OLED VCC', 'to': '3.3V rail', 'color': 'red'},
                        {'from': 'OLED GND', 'to': 'GND rail', 'color': 'black'},
                        {'from': 'OLED SDA', 'to': 'ESP32 GPIO21', 'color': 'blue'},
                        {'from': 'OLED SCL', 'to': 'ESP32 GPIO22', 'color': 'green'}
                    ],
                    'details': [
                        'VCC → 3.3V (power)',
                        'GND → GND (ground)',
                        'SDA → GPIO21 (I2C data line)',
                        'SCL → GPIO22 (I2C clock line)'
                    ],
                    'time': '10 minutes',
                    'tips': [
                        'GPIO21/22 are the default I2C pins for ESP32',
                        'OLED typically uses I2C address 0x3C',
                        'Some OLEDs have pin order VCC-GND vs GND-VCC, check yours!'
                    ]
                },
                {
                    'number': 5,
                    'title': 'Connect DHT22 Sensor (Optional)',
                    'description': 'Add temperature/humidity monitoring for plant environment.',
                    'wiring': [
                        {'from': 'DHT22 VCC', 'to': '3.3V rail', 'color': 'red'},
                        {'from': 'DHT22 GND', 'to': 'GND rail', 'color': 'black'},
                        {'from': 'DHT22 DATA', 'to': 'ESP32 GPIO4', 'color': 'yellow'}
                    ],
                    'details': [
                        'Pin 1 (VCC) → 3.3V',
                        'Pin 2 (DATA) → GPIO4',
                        'Pin 3 (NC) → Not connected',
                        'Pin 4 (GND) → GND'
                    ],
                    'time': '10 minutes (optional)',
                    'tips': [
                        'DHT22 is more accurate than DHT11 (±0.5°C vs ±2°C)',
                        'No external pull-up resistor needed for most breakout boards',
                        'Readings update every 2 seconds max'
                    ]
                },
                {
                    'number': 6,
                    'title': 'Verify Wiring',
                    'description': 'Double-check all connections before powering on.',
                    'checklist': [
                        '✓ All VCC → 3.3V rail',
                        '✓ All GND → GND rail',
                        '✓ Soil sensor AOUT → GPIO34',
                        '✓ OLED SDA → GPIO21',
                        '✓ OLED SCL → GPIO22',
                        '✓ DHT22 DATA → GPIO4 (if used)',
                        '✓ No loose wires or shorts'
                    ],
                    'time': '5 minutes',
                    'warnings': [
                        '⚠️ Double-check before powering on!',
                        '⚠️ Wrong connections can damage sensors'
                    ]
                },
                {
                    'number': 7,
                    'title': 'Install Arduino Libraries',
                    'description': 'Install required libraries in Arduino IDE.',
                    'details': [
                        'Open Arduino IDE',
                        'Go to Tools → Manage Libraries',
                        'Install: "Adafruit SSD1306" (for OLED)',
                        'Install: "Adafruit GFX Library" (graphics)',
                        'Install: "DHT sensor library" by Adafruit (if using DHT22)'
                    ],
                    'time': '10 minutes',
                    'tips': [
                        'Install "Adafruit Unified Sensor" if prompted',
                        'Restart Arduino IDE after installing libraries'
                    ]
                },
                {
                    'number': 8,
                    'title': 'Upload Code to ESP32',
                    'description': 'Flash the Arduino sketch to your ESP32.',
                    'details': [
                        'Copy the provided code into Arduino IDE',
                        'Go to Tools → Board → ESP32 Arduino → "ESP32 Dev Module"',
                        'Go to Tools → Port → Select your ESP32 port',
                        'Click the Upload button (right arrow)',
                        'Wait for "Done uploading" message'
                    ],
                    'time': '15 minutes',
                    'troubleshooting': [
                        'Upload fails? Try holding BOOT button during upload',
                        'Port not showing? Check USB cable (must support data)',
                        'Wrong board? Ensure ESP32 board package is installed'
                    ]
                },
                {
                    'number': 9,
                    'title': 'Calibrate Soil Moisture Sensor',
                    'description': 'Find sensor dry and wet values for accurate readings.',
                    'details': [
                        'Open Serial Monitor (Tools → Serial Monitor)',
                        'Set baud rate to 115200',
                        'Note the reading with sensor in dry air (dry value)',
                        'Note the reading with sensor in water (wet value)',
                        'Update SOIL_DRY and SOIL_WET in code with these values',
                        'Re-upload code'
                    ],
                    'time': '15 minutes',
                    'tips': [
                        'Typical values: Dry=3000-4095, Wet=1000-1500 (12-bit ADC)',
                        'Calibrate in actual soil for best accuracy',
                        'Different sensors have different ranges - always calibrate!'
                    ]
                },
                {
                    'number': 10,
                    'title': 'Test Complete System',
                    'description': 'Verify all sensors and display work together.',
                    'details': [
                        'Insert sensor into plant soil',
                        'OLED should display:',
                        '  - Soil moisture percentage',
                        '  - Temperature (if DHT22 used)',
                        '  - Humidity (if DHT22 used)',
                        '  - Watering recommendation',
                        'Serial monitor shows detailed readings every 2 seconds'
                    ],
                    'time': '10 minutes',
                    'success_criteria': [
                        '✓ Display shows clear readings',
                        '✓ Moisture % changes when you water plant',
                        '✓ Temperature is within expected range',
                        '✓ No sensor errors in serial monitor'
                    ]
                },
                {
                    'number': 11,
                    'title': 'Optional: Add WiFi Notifications',
                    'description': 'Get watering reminders on your phone (advanced).',
                    'details': [
                        'Option 1: Use Blynk app for mobile notifications',
                        'Option 2: Use ThingSpeak for cloud data logging',
                        'Option 3: Setup IFTTT webhook for push notifications',
                        'Add WiFi credentials to code',
                        'Configure your chosen platform',
                        'Re-upload sketch with WiFi features enabled'
                    ],
                    'time': '30 minutes (optional)',
                    'tips': [
                        'Blynk is easiest for beginners',
                        'ThingSpeak good for data analysis/graphs',
                        'IFTTT can trigger other smart home devices'
                    ]
                }
            ],

            'total_build_time': '2-3 hours (basic) / 4 hours (with WiFi)',
            'estimated_cost': '$25.00',

            'code_template': '''
/*
 * Smart Plant Monitor
 * Monitors soil moisture, temperature, and humidity
 * Displays on OLED and logs to Serial
 *
 * Components:
 * - ESP32 Dev Board
 * - Capacitive soil moisture sensor (GPIO34)
 * - SSD1306 OLED display (I2C: SDA=GPIO21, SCL=GPIO22)
 * - DHT22 temperature/humidity sensor (GPIO4) - optional
 */

#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <DHT.h>

// OLED display settings
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1
#define SCREEN_ADDRESS 0x3C

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

// Sensor pins
#define SOIL_PIN 34        // Analog pin for soil moisture
#define DHT_PIN 4          // Digital pin for DHT22
#define DHT_TYPE DHT22

DHT dht(DHT_PIN, DHT_TYPE);

// Calibration values (MUST calibrate for your sensor!)
#define SOIL_DRY 3200      // Reading in dry air
#define SOIL_WET 1200      // Reading in water
#define MOISTURE_LOW 30    // % - needs watering
#define MOISTURE_OK 60     // % - happy plant

void setup() {
  Serial.begin(115200);

  // Initialize OLED
  if(!display.begin(SSD1306_SWITCHCAPVCC, SCREEN_ADDRESS)) {
    Serial.println(F("SSD1306 allocation failed"));
    for(;;);
  }

  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0,0);
  display.println(F("Plant Monitor"));
  display.println(F("Initializing..."));
  display.display();

  // Initialize DHT22
  dht.begin();

  delay(2000);
  Serial.println(F("Smart Plant Monitor Ready!"));
}

void loop() {
  // Read soil moisture (analog 0-4095 on ESP32)
  int soilRaw = analogRead(SOIL_PIN);

  // Convert to percentage (0% = dry, 100% = wet)
  int moisture = map(soilRaw, SOIL_DRY, SOIL_WET, 0, 100);
  moisture = constrain(moisture, 0, 100);

  // Read temperature & humidity
  float temp = dht.readTemperature();     // Celsius
  float humidity = dht.readHumidity();    // %

  // Determine plant status
  String status;
  if (moisture < MOISTURE_LOW) {
    status = "WATER NOW!";
  } else if (moisture < MOISTURE_OK) {
    status = "Water soon";
  } else {
    status = "Happy plant";
  }

  // Display on OLED
  display.clearDisplay();
  display.setTextSize(1);
  display.setCursor(0,0);
  display.println(F("Plant Monitor"));
  display.drawLine(0, 10, SCREEN_WIDTH, 10, SSD1306_WHITE);

  display.setCursor(0,15);
  display.print(F("Moisture: "));
  display.print(moisture);
  display.println(F("%"));

  // Draw moisture bar graph
  int barWidth = map(moisture, 0, 100, 0, SCREEN_WIDTH);
  display.fillRect(0, 25, barWidth, 8, SSD1306_WHITE);
  display.drawRect(0, 25, SCREEN_WIDTH, 8, SSD1306_WHITE);

  display.setCursor(0,37);
  if (!isnan(temp)) {
    display.print(F("Temp: "));
    display.print(temp, 1);
    display.println(F("C"));
  }

  display.setCursor(0,47);
  if (!isnan(humidity)) {
    display.print(F("Humid: "));
    display.print(humidity, 0);
    display.println(F("%"));
  }

  display.setCursor(0,57);
  display.setTextSize(1);
  display.print(status);

  display.display();

  // Print to serial
  Serial.println("==================");
  Serial.print("Soil Raw: "); Serial.println(soilRaw);
  Serial.print("Moisture: "); Serial.print(moisture); Serial.println("%");
  Serial.print("Temperature: "); Serial.print(temp); Serial.println("°C");
  Serial.print("Humidity: "); Serial.print(humidity); Serial.println("%");
  Serial.print("Status: "); Serial.println(status);

  delay(2000);  // Update every 2 seconds
}
''',

            'business_notes': {
                'marketability': 'HIGH - Popular product on Etsy/Amazon',
                'target_audience': 'Plant lovers, home gardeners, tech-savvy hobbyists',
                'upsell_opportunities': [
                    'Custom enclosure (3D printed) - add $15',
                    'Solar panel power - add $10',
                    'Multi-plant monitoring (4-8 sensors) - add $30',
                    'Mobile app integration - premium tier'
                ],
                'manufacturing_notes': [
                    'PCB version can reduce cost to $18/unit at qty 100',
                    'Custom injection molded enclosure: ~$3/unit at qty 500',
                    'Can private label and brand for retail channels'
                ]
            },

            'next_steps': [
                'Build 1-2 prototypes for testing',
                'Use for 1-2 weeks to validate reliability',
                'Design custom enclosure (optional)',
                'Take professional product photos',
                'Create listing on Etsy/Amazon',
                'Start with 10 units, scale based on demand'
            ]
        }

    def _generate_parking_sensor_instructions(self) -> Dict:
        """Instructions for Distance Parking Sensor (Arduino + HC-SR04 + LEDs)"""
        return {
            'project_name': 'Distance Parking Sensor',
            'difficulty': 'beginner',
            'build_time': '1-1.5 hours',
            'skill_level': 'Beginner',

            'tools_needed': [
                'Breadboard',
                'Jumper wires (male-to-male)',
                'USB cable for Arduino',
                'Computer with Arduino IDE'
            ],

            'components': [
                {'id': 'arduino_uno', 'quantity': 1, 'notes': 'Arduino Uno or compatible'},
                {'id': 'hc_sr04', 'quantity': 1, 'notes': 'Ultrasonic distance sensor'},
                {'id': 'led', 'quantity': 3, 'notes': 'Green, Yellow, Red LEDs'},
                {'id': 'resistor', 'quantity': 3, 'notes': '220Ω resistors'},
                {'id': 'buzzer', 'quantity': 1, 'notes': 'Optional: piezo buzzer for alerts'}
            ],

            'market_analysis': {
                'build_cost': 15.00,
                'market_price_low': 25.00,
                'market_price_high': 45.00,
                'profit_margin': '67-200%',
                'comparable_products': [
                    'Amazon parking sensors: $30-50',
                    'Etsy DIY kits: $25-40'
                ]
            },

            'steps': [
                {
                    'number': 1,
                    'title': 'Prepare Components',
                    'description': 'Gather all components and understand their purpose.',
                    'details': [
                        'Place Arduino Uno on breadboard or nearby',
                        'Identify HC-SR04 pins: VCC, TRIG, ECHO, GND',
                        'Sort LEDs by color: Green (far), Yellow (medium), Red (close)',
                        'Have 3x 220Ω resistors ready (red-red-brown bands)'
                    ],
                    'time': '5 minutes',
                    'tips': [
                        'HC-SR04 measures distance 2cm to 400cm accurately',
                        'LEDs need resistors to prevent burnout'
                    ]
                },
                {
                    'number': 2,
                    'title': 'Wire Power Rails',
                    'description': 'Set up breadboard power distribution.',
                    'wiring': [
                        {'from': 'Arduino 5V', 'to': 'Breadboard + rail', 'color': 'red'},
                        {'from': 'Arduino GND', 'to': 'Breadboard - rail', 'color': 'black'}
                    ],
                    'details': [
                        'Connect Arduino 5V to breadboard positive (+) rail',
                        'Connect Arduino GND to breadboard negative (-) rail',
                        'This provides power for all components'
                    ],
                    'time': '3 minutes'
                },
                {
                    'number': 3,
                    'title': 'Connect HC-SR04 Ultrasonic Sensor',
                    'description': 'Wire distance sensor to Arduino.',
                    'wiring': [
                        {'from': 'HC-SR04 VCC', 'to': '5V rail', 'color': 'red'},
                        {'from': 'HC-SR04 GND', 'to': 'GND rail', 'color': 'black'},
                        {'from': 'HC-SR04 TRIG', 'to': 'Arduino Pin 9', 'color': 'yellow'},
                        {'from': 'HC-SR04 ECHO', 'to': 'Arduino Pin 10', 'color': 'blue'}
                    ],
                    'details': [
                        'VCC → 5V (power)',
                        'GND → GND (ground)',
                        'TRIG → Pin 9 (trigger pulse)',
                        'ECHO → Pin 10 (echo pulse)'
                    ],
                    'time': '8 minutes',
                    'tips': [
                        'TRIG sends ultrasonic pulse, ECHO receives it',
                        'Keep sensor wires under 20cm for best accuracy',
                        'Sensor works by timing sound wave reflections'
                    ]
                },
                {
                    'number': 4,
                    'title': 'Connect Green LED (Far Distance)',
                    'description': 'Green LED lights when distance > 100cm (safe).',
                    'wiring': [
                        {'from': 'Green LED long leg', 'to': 'Arduino Pin 6', 'color': 'green'},
                        {'from': 'Green LED short leg', 'to': '220Ω resistor', 'color': 'black'},
                        {'from': 'Resistor', 'to': 'GND rail', 'color': 'black'}
                    ],
                    'details': [
                        'Long leg (anode) → Pin 6',
                        'Short leg (cathode) → Resistor → GND',
                        'Green = Safe distance, keep going'
                    ],
                    'time': '5 minutes',
                    'warnings': [
                        '⚠️ LEDs are polarized - long leg is positive!',
                        '⚠️ Always use resistor or LED will burn out'
                    ]
                },
                {
                    'number': 5,
                    'title': 'Connect Yellow LED (Medium Distance)',
                    'description': 'Yellow LED lights when 50cm < distance < 100cm (caution).',
                    'wiring': [
                        {'from': 'Yellow LED long leg', 'to': 'Arduino Pin 5', 'color': 'yellow'},
                        {'from': 'Yellow LED short leg', 'to': '220Ω resistor', 'color': 'black'},
                        {'from': 'Resistor', 'to': 'GND rail', 'color': 'black'}
                    ],
                    'details': [
                        'Long leg → Pin 5',
                        'Short leg → Resistor → GND',
                        'Yellow = Slow down, getting close'
                    ],
                    'time': '5 minutes'
                },
                {
                    'number': 6,
                    'title': 'Connect Red LED (Close Distance)',
                    'description': 'Red LED lights when distance < 50cm (stop!).',
                    'wiring': [
                        {'from': 'Red LED long leg', 'to': 'Arduino Pin 4', 'color': 'red'},
                        {'from': 'Red LED short leg', 'to': '220Ω resistor', 'color': 'black'},
                        {'from': 'Resistor', 'to': 'GND rail', 'color': 'black'}
                    ],
                    'details': [
                        'Long leg → Pin 4',
                        'Short leg → Resistor → GND',
                        'Red = STOP! Too close to wall'
                    ],
                    'time': '5 minutes'
                },
                {
                    'number': 7,
                    'title': 'Verify Wiring',
                    'description': 'Double-check all connections before powering on.',
                    'checklist': [
                        '✓ HC-SR04 VCC → 5V',
                        '✓ HC-SR04 GND → GND',
                        '✓ HC-SR04 TRIG → Pin 9',
                        '✓ HC-SR04 ECHO → Pin 10',
                        '✓ Green LED → Pin 6 (with resistor to GND)',
                        '✓ Yellow LED → Pin 5 (with resistor to GND)',
                        '✓ Red LED → Pin 4 (with resistor to GND)',
                        '✓ All LED long legs go to Arduino pins',
                        '✓ All LED short legs go through resistors to GND'
                    ],
                    'time': '5 minutes',
                    'warnings': [
                        '⚠️ Wrong LED polarity = no light',
                        '⚠️ Missing resistor = burned LED'
                    ]
                },
                {
                    'number': 8,
                    'title': 'Upload Code to Arduino',
                    'description': 'Flash the parking sensor sketch.',
                    'details': [
                        'Copy the provided code into Arduino IDE',
                        'Select Board: Tools → Board → Arduino Uno',
                        'Select Port: Tools → Port → (your Arduino port)',
                        'Click Upload (right arrow icon)',
                        'Wait for "Done uploading" message'
                    ],
                    'time': '10 minutes',
                    'troubleshooting': [
                        'Upload fails? Check USB cable (must support data)',
                        'Wrong port? Try unplugging and replugging Arduino',
                        'Compilation error? Ensure code copied completely'
                    ]
                },
                {
                    'number': 9,
                    'title': 'Test the Sensor',
                    'description': 'Verify distance measurement and LED behavior.',
                    'details': [
                        'Open Serial Monitor (Tools → Serial Monitor)',
                        'Set baud rate to 9600',
                        'Point sensor at wall/object',
                        'Watch distance readings in Serial Monitor',
                        'Move closer/farther and observe LED changes:',
                        '  - Far (>100cm): Green LED on',
                        '  - Medium (50-100cm): Yellow LED on',
                        '  - Close (<50cm): Red LED on'
                    ],
                    'time': '10 minutes',
                    'success_criteria': [
                        '✓ Serial Monitor shows distance in cm',
                        '✓ Green LED when far from wall',
                        '✓ Yellow LED when medium distance',
                        '✓ Red LED when very close',
                        '✓ Distance readings are accurate (±3cm)'
                    ]
                },
                {
                    'number': 10,
                    'title': 'Calibrate Thresholds',
                    'description': 'Adjust distance thresholds for your garage.',
                    'details': [
                        'Measure your garage depth',
                        'Park car at ideal stop position',
                        'Measure distance from sensor to car bumper',
                        'Update threshold values in code:',
                        '  - FAR_THRESHOLD: When to start showing green',
                        '  - MEDIUM_THRESHOLD: When to switch to yellow',
                        '  - CLOSE_THRESHOLD: When to show red STOP',
                        'Re-upload code and test'
                    ],
                    'time': '15 minutes',
                    'tips': [
                        'Typical garage: FAR=150cm, MEDIUM=75cm, CLOSE=30cm',
                        'Leave 20-30cm buffer for safety',
                        'Test with actual car before permanent install'
                    ]
                },
                {
                    'number': 11,
                    'title': 'Optional: Add Buzzer Alarm',
                    'description': 'Add audio alert when too close (advanced).',
                    'wiring': [
                        {'from': 'Buzzer +', 'to': 'Arduino Pin 3', 'color': 'purple'},
                        {'from': 'Buzzer -', 'to': 'GND rail', 'color': 'black'}
                    ],
                    'details': [
                        'Connect piezo buzzer to Pin 3',
                        'Uncomment buzzer code in sketch',
                        'Re-upload code',
                        'Buzzer beeps rapidly when distance < 30cm'
                    ],
                    'time': '10 minutes (optional)',
                    'tips': [
                        'Buzzer can be annoying - test volume first',
                        'Add potentiometer for volume control (advanced)'
                    ]
                }
            ],

            'total_build_time': '1-1.5 hours (2 hours with buzzer)',
            'estimated_cost': '$15.00',

            'code_template': '''
/*
 * Distance Parking Sensor
 * Helps you park perfectly in your garage every time!
 *
 * Components:
 * - Arduino Uno
 * - HC-SR04 Ultrasonic Sensor (TRIG=Pin9, ECHO=Pin10)
 * - Green LED on Pin 6 (far distance, safe)
 * - Yellow LED on Pin 5 (medium distance, slow down)
 * - Red LED on Pin 4 (close distance, STOP!)
 * - Optional: Buzzer on Pin 3 (alarm when too close)
 */

// Pin definitions
const int TRIG_PIN = 9;
const int ECHO_PIN = 10;
const int GREEN_LED = 6;
const int YELLOW_LED = 5;
const int RED_LED = 4;
const int BUZZER = 3;  // Optional

// Distance thresholds (in cm) - ADJUST FOR YOUR GARAGE!
const int FAR_THRESHOLD = 100;     // > 100cm = green (safe)
const int MEDIUM_THRESHOLD = 50;   // 50-100cm = yellow (caution)
const int CLOSE_THRESHOLD = 30;    // < 30cm = red + buzzer (STOP!)

void setup() {
  Serial.begin(9600);

  // Initialize HC-SR04
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);

  // Initialize LEDs
  pinMode(GREEN_LED, OUTPUT);
  pinMode(YELLOW_LED, OUTPUT);
  pinMode(RED_LED, OUTPUT);
  pinMode(BUZZER, OUTPUT);

  Serial.println("Parking Sensor Ready!");
}

void loop() {
  // Measure distance
  long distance = measureDistance();

  // Print to serial
  Serial.print("Distance: ");
  Serial.print(distance);
  Serial.println(" cm");

  // Turn off all LEDs first
  digitalWrite(GREEN_LED, LOW);
  digitalWrite(YELLOW_LED, LOW);
  digitalWrite(RED_LED, LOW);
  digitalWrite(BUZZER, LOW);

  // Determine which LED to light
  if (distance > FAR_THRESHOLD) {
    // Safe distance - green light
    digitalWrite(GREEN_LED, HIGH);
    Serial.println("Status: SAFE - Keep going");
  }
  else if (distance > MEDIUM_THRESHOLD) {
    // Medium distance - yellow light
    digitalWrite(YELLOW_LED, HIGH);
    Serial.println("Status: CAUTION - Slow down");
  }
  else if (distance > CLOSE_THRESHOLD) {
    // Close distance - red light
    digitalWrite(RED_LED, HIGH);
    Serial.println("Status: CLOSE - Almost there");
  }
  else {
    // Too close! - red light + buzzer
    digitalWrite(RED_LED, HIGH);

    // Uncomment for buzzer alarm
    // tone(BUZZER, 2000, 100);  // 2kHz beep for 100ms

    Serial.println("Status: STOP!!! Too close!");
  }

  delay(200);  // Update 5 times per second
}

long measureDistance() {
  // Send 10us pulse to trigger
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  // Read echo pulse duration
  long duration = pulseIn(ECHO_PIN, HIGH);

  // Calculate distance in cm
  // Speed of sound: 343 m/s = 0.0343 cm/μs
  // Distance = (duration / 2) / 29.1 cm/μs
  long distance = duration * 0.034 / 2;

  // Limit to sensor range
  if (distance > 400) distance = 400;
  if (distance < 2) distance = 2;

  return distance;
}
''',

            'business_notes': {
                'marketability': 'HIGH - Practical everyday use, easy to understand',
                'target_audience': 'Homeowners with garages, DIY enthusiasts, car owners',
                'upsell_opportunities': [
                    'Weatherproof enclosure - add $10',
                    'Dual sensor setup (front + rear) - add $20',
                    'Smartphone app via Bluetooth - add $25',
                    'LED strip instead of single LEDs - add $8'
                ],
                'manufacturing_notes': [
                    'Can mount in custom 3D printed case',
                    'Use automotive-grade components for durability',
                    'Add cable management kit for clean install',
                    'Include mounting hardware in package'
                ]
            },

            'next_steps': [
                'Build prototype and test in actual garage',
                'Measure typical garage dimensions for default thresholds',
                'Create installation guide with photos',
                'Design mounting bracket (3D printable)',
                'Take before/after photos of clean parking',
                'List on Etsy/Amazon with installation service option'
            ]
        }

    def _generate_thermometer_instructions(self) -> Dict:
        """Instructions for Digital Thermometer (Arduino + DHT22 + LCD)"""
        return {
            'project_name': 'Digital Thermometer',
            'difficulty': 'beginner',
            'build_time': '1.5-2 hours',
            'skill_level': 'Beginner',

            'tools_needed': [
                'Breadboard',
                'Jumper wires (male-to-male)',
                'USB cable for Arduino',
                'Computer with Arduino IDE',
                'Small screwdriver (for LCD contrast adjustment)'
            ],

            'components': [
                {'id': 'arduino_uno', 'quantity': 1, 'notes': 'Arduino Uno or compatible'},
                {'id': 'dht22', 'quantity': 1, 'notes': 'Temperature/humidity sensor'},
                {'id': 'lcd_16x2', 'quantity': 1, 'notes': '16x2 LCD with I2C backpack (easier) or standard'},
                {'id': 'resistor', 'quantity': 1, 'notes': '10kΩ potentiometer for LCD contrast'}
            ],

            'market_analysis': {
                'build_cost': 18.00,
                'market_price_low': 30.00,
                'market_price_high': 50.00,
                'profit_margin': '67-178%',
                'comparable_products': [
                    'Amazon digital thermometers: $35-55',
                    'Etsy custom thermometers: $30-45'
                ]
            },

            'steps': [
                {
                    'number': 1,
                    'title': 'Choose LCD Version',
                    'description': 'Decide between I2C LCD (easier) or standard LCD (more wiring).',
                    'details': [
                        'I2C LCD: Uses only 2 data pins (SDA, SCL) - RECOMMENDED',
                        'Standard LCD: Uses 6-8 data pins - more complex wiring',
                        'This guide covers I2C version (add I2C backpack to standard LCD)'
                    ],
                    'time': '2 minutes',
                    'tips': [
                        'I2C backpack costs $1-2 and saves 30 minutes of wiring',
                        'Most eBay/Amazon LCDs come with I2C pre-soldered'
                    ]
                },
                {
                    'number': 2,
                    'title': 'Wire Power Rails',
                    'description': 'Set up breadboard power.',
                    'wiring': [
                        {'from': 'Arduino 5V', 'to': 'Breadboard + rail', 'color': 'red'},
                        {'from': 'Arduino GND', 'to': 'Breadboard - rail', 'color': 'black'}
                    ],
                    'time': '3 minutes'
                },
                {
                    'number': 3,
                    'title': 'Connect DHT22 Sensor',
                    'description': 'Wire temperature/humidity sensor to Arduino.',
                    'wiring': [
                        {'from': 'DHT22 VCC (Pin 1)', 'to': '5V rail', 'color': 'red'},
                        {'from': 'DHT22 DATA (Pin 2)', 'to': 'Arduino Pin 2', 'color': 'yellow'},
                        {'from': 'DHT22 GND (Pin 4)', 'to': 'GND rail', 'color': 'black'}
                    ],
                    'details': [
                        'Pin 1 (VCC) → 5V',
                        'Pin 2 (DATA) → Arduino Pin 2',
                        'Pin 3 (NC) → Not connected',
                        'Pin 4 (GND) → GND'
                    ],
                    'time': '8 minutes',
                    'tips': [
                        'DHT22 is more accurate than DHT11 (±0.5°C vs ±2°C)',
                        'Most DHT22 breakout boards have built-in pull-up resistor',
                        'Sensor measures both temperature AND humidity'
                    ]
                },
                {
                    'number': 4,
                    'title': 'Connect I2C LCD Display',
                    'description': 'Wire 16x2 LCD with I2C backpack.',
                    'wiring': [
                        {'from': 'LCD GND', 'to': 'GND rail', 'color': 'black'},
                        {'from': 'LCD VCC', 'to': '5V rail', 'color': 'red'},
                        {'from': 'LCD SDA', 'to': 'Arduino A4', 'color': 'blue'},
                        {'from': 'LCD SCL', 'to': 'Arduino A5', 'color': 'green'}
                    ],
                    'details': [
                        'GND → GND (ground)',
                        'VCC → 5V (power)',
                        'SDA → A4 (I2C data)',
                        'SCL → A5 (I2C clock)'
                    ],
                    'time': '10 minutes',
                    'tips': [
                        'A4/A5 are the I2C pins on Arduino Uno',
                        'LCD should light up when powered (even without code)',
                        'If no backlight, check I2C backpack solder joints'
                    ]
                },
                {
                    'number': 5,
                    'title': 'Verify Wiring',
                    'description': 'Double-check all connections.',
                    'checklist': [
                        '✓ DHT22 VCC → 5V',
                        '✓ DHT22 DATA → Pin 2',
                        '✓ DHT22 GND → GND',
                        '✓ LCD VCC → 5V',
                        '✓ LCD GND → GND',
                        '✓ LCD SDA → A4',
                        '✓ LCD SCL → A5',
                        '✓ All power connections secure'
                    ],
                    'time': '5 minutes'
                },
                {
                    'number': 6,
                    'title': 'Install Required Libraries',
                    'description': 'Add DHT and LCD libraries to Arduino IDE.',
                    'details': [
                        'Open Arduino IDE',
                        'Go to Tools → Manage Libraries',
                        'Search and install: "DHT sensor library" by Adafruit',
                        'Install: "Adafruit Unified Sensor" (dependency)',
                        'Install: "LiquidCrystal I2C" by Frank de Brabander'
                    ],
                    'time': '10 minutes',
                    'tips': [
                        'Make sure to install ALL three libraries',
                        'Restart Arduino IDE after installation'
                    ]
                },
                {
                    'number': 7,
                    'title': 'Find LCD I2C Address',
                    'description': 'Scan for LCD I2C address (usually 0x27 or 0x3F).',
                    'details': [
                        'Upload I2C scanner sketch (File → Examples → Wire → i2c_scanner)',
                        'Open Serial Monitor (9600 baud)',
                        'Note the address shown (e.g., "0x27" or "0x3F")',
                        'Update this address in the main code'
                    ],
                    'time': '10 minutes',
                    'troubleshooting': [
                        'No address found? Check SDA/SCL wiring',
                        'Multiple addresses? You may have other I2C devices connected'
                    ]
                },
                {
                    'number': 8,
                    'title': 'Upload Thermometer Code',
                    'description': 'Flash the temperature display sketch.',
                    'details': [
                        'Copy the provided code into Arduino IDE',
                        'Update LCD I2C address if different from 0x27',
                        'Select Board: Tools → Board → Arduino Uno',
                        'Select Port: Tools → Port → (your Arduino port)',
                        'Click Upload'
                    ],
                    'time': '10 minutes'
                },
                {
                    'number': 9,
                    'title': 'Adjust LCD Contrast',
                    'description': 'Fine-tune display brightness and contrast.',
                    'details': [
                        'Look at LCD - you should see temperature reading',
                        'If display too dim/bright: Find potentiometer on I2C backpack',
                        'Use small screwdriver to adjust pot until text is clear',
                        'Typical setting: turn pot about 1/4 turn from one end'
                    ],
                    'time': '5 minutes',
                    'tips': [
                        'If you see boxes but no text, contrast is too high',
                        'If display blank, contrast is too low or wiring issue'
                    ]
                },
                {
                    'number': 10,
                    'title': 'Test Temperature Readings',
                    'description': 'Verify sensor accuracy.',
                    'details': [
                        'LCD should show:',
                        '  Line 1: "Temp: XX.X°C"',
                        '  Line 2: "Humidity: XX%"',
                        'Compare to room thermometer (±2°C is normal)',
                        'Breathe on sensor - humidity should increase',
                        'Hold sensor in hand - temperature should rise'
                    ],
                    'time': '10 minutes',
                    'success_criteria': [
                        '✓ Temperature reading updates every 2 seconds',
                        '✓ Humidity reading makes sense (30-80% indoor)',
                        '✓ Sensor responds to temperature changes',
                        '✓ No "nan" or error readings'
                    ]
                },
                {
                    'number': 11,
                    'title': 'Add Enclosure (Optional)',
                    'description': 'Mount in case for finished look.',
                    'details': [
                        'Design/buy small project enclosure',
                        'Cut holes for LCD display and sensor',
                        'Mount Arduino with standoffs or double-sided tape',
                        'Route USB cable through case for power',
                        'Add labels or decorative front panel'
                    ],
                    'time': '30 minutes (optional)',
                    'tips': [
                        '3D print custom case for professional look',
                        'Laser-cut acrylic case is also popular',
                        'Sensor needs airflow - do not seal it completely'
                    ]
                }
            ],

            'total_build_time': '1.5-2 hours (3 hours with custom enclosure)',
            'estimated_cost': '$18.00',

            'code_template': '''
/*
 * Digital Thermometer & Humidity Monitor
 * Displays temperature and humidity on 16x2 LCD
 *
 * Components:
 * - Arduino Uno
 * - DHT22 sensor on Pin 2
 * - 16x2 LCD with I2C backpack (SDA=A4, SCL=A5)
 */

#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <DHT.h>

// DHT22 sensor setup
#define DHT_PIN 2
#define DHT_TYPE DHT22
DHT dht(DHT_PIN, DHT_TYPE);

// LCD setup - CHANGE ADDRESS IF NEEDED (0x27 or 0x3F)
LiquidCrystal_I2C lcd(0x27, 16, 2);  // Address, columns, rows

void setup() {
  Serial.begin(9600);

  // Initialize DHT sensor
  dht.begin();

  // Initialize LCD
  lcd.init();
  lcd.backlight();  // Turn on backlight

  // Welcome message
  lcd.setCursor(0, 0);
  lcd.print("Thermometer");
  lcd.setCursor(0, 1);
  lcd.print("Starting...");

  delay(2000);
  lcd.clear();
}

void loop() {
  // Read sensor (takes ~250ms)
  float humidity = dht.readHumidity();
  float temperature = dht.readTemperature();  // Celsius

  // Check if readings are valid
  if (isnan(humidity) || isnan(temperature)) {
    // Sensor error
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Sensor Error!");
    lcd.setCursor(0, 1);
    lcd.print("Check Wiring");

    Serial.println("Failed to read from DHT sensor!");

    delay(2000);
    return;
  }

  // Display on LCD
  lcd.clear();

  // Line 1: Temperature
  lcd.setCursor(0, 0);
  lcd.print("Temp: ");
  lcd.print(temperature, 1);  // 1 decimal place
  lcd.print((char)223);       // Degree symbol
  lcd.print("C");

  // Line 2: Humidity
  lcd.setCursor(0, 1);
  lcd.print("Humidity: ");
  lcd.print(humidity, 0);  // No decimals
  lcd.print("%");

  // Print to serial for debugging
  Serial.print("Temperature: ");
  Serial.print(temperature);
  Serial.print("°C  Humidity: ");
  Serial.print(humidity);
  Serial.println("%");

  delay(2000);  // Update every 2 seconds
}
''',

            'business_notes': {
                'marketability': 'MEDIUM-HIGH - Practical for home/office, good gift item',
                'target_audience': 'Home users, office workers, plant enthusiasts, DIY hobbyists',
                'upsell_opportunities': [
                    'Weather station upgrade (add barometer) - add $15',
                    'Data logging to SD card - add $8',
                    'WiFi connectivity (ESP32 version) - add $12',
                    'Custom wooden/acrylic case - add $15-25',
                    'Wall-mount version with battery - add $10'
                ],
                'manufacturing_notes': [
                    'Pre-assemble in custom enclosure for higher perceived value',
                    'Use high-quality LCD for better appearance',
                    'Add calibration certificate for professional touch',
                    'Include desktop stand or wall mount bracket'
                ]
            },

            'next_steps': [
                'Build prototype and test for 1 week',
                'Design custom enclosure (3D print or laser-cut acrylic)',
                'Create product photos with lifestyle shots',
                'Write product description emphasizing accuracy',
                'List on Etsy as "Custom Digital Thermometer"',
                'Offer temperature units option (C/F) as upgrade'
            ]
        }

    def _generate_motion_light_instructions(self) -> Dict:
        # To be implemented
        pass

    def _generate_blind_controller_instructions(self) -> Dict:
        """Instructions for Automatic Blind Controller (ESP8266 + Servo + WiFi)"""
        return {
            'project_name': 'Automatic Blind Controller',
            'difficulty': 'hard',
            'build_time': '4-5 hours',
            'skill_level': 'Advanced',

            'tools_needed': [
                'Breadboard (for prototyping)',
                'Jumper wires',
                'USB cable for ESP8266',
                'Computer with Arduino IDE',
                'Smartphone (for WiFi control testing)',
                'Optional: 3D printer for mounting bracket'
            ],

            'components': [
                {'id': 'esp8266', 'quantity': 1, 'notes': 'NodeMCU or Wemos D1 Mini'},
                {'id': 'servo_sg90', 'quantity': 1, 'notes': 'SG90 or MG996R for stronger torque'},
                {'id': 'power_supply', 'quantity': 1, 'notes': '5V 2A power adapter'},
                {'id': 'led', 'quantity': 2, 'notes': 'Status indicators (optional)'}
            ],

            'market_analysis': {
                'build_cost': 9.00,
                'market_price_low': 40.00,
                'market_price_high': 70.00,
                'profit_margin': '344-678%',
                'comparable_products': [
                    'Amazon smart blinds: $60-100',
                    'Etsy DIY blind controllers: $40-70',
                    'Commercial systems: $150-300 per window'
                ]
            },

            'steps': [
                {
                    'number': 1,
                    'title': 'Choose Servo Motor',
                    'description': 'Select servo based on blind weight and size.',
                    'details': [
                        'SG90: Light blinds (< 1kg), low cost ($3)',
                        'MG996R: Heavy blinds (up to 3kg), metal gears ($8)',
                        'Check your blind weight and pulling force needed',
                        'Test servo torque before final installation'
                    ],
                    'time': '10 minutes',
                    'tips': [
                        'Start with SG90 for prototyping',
                        'MG996R recommended for production units',
                        'Continuous rotation servos work but need different code'
                    ]
                },
                {
                    'number': 2,
                    'title': 'Wire ESP8266 and Servo',
                    'description': 'Connect servo motor to ESP8266 with external power.',
                    'wiring': [
                        {'from': 'Servo Orange (Signal)', 'to': 'ESP8266 D1 (GPIO5)', 'color': 'orange'},
                        {'from': 'Servo Red (VCC)', 'to': '5V Power Supply +', 'color': 'red'},
                        {'from': 'Servo Brown (GND)', 'to': 'Power Supply - AND ESP8266 GND', 'color': 'black'}
                    ],
                    'details': [
                        'Signal wire → D1 (GPIO5)',
                        'VCC → External 5V power (NOT ESP8266 5V!)',
                        'GND → Common ground (power supply AND ESP8266)',
                        'ESP8266 USB power is separate from servo power'
                    ],
                    'time': '15 minutes',
                    'warnings': [
                        '⚠️ CRITICAL: Servo draws too much current for ESP8266 regulator',
                        '⚠️ Always use external 5V power supply for servo',
                        '⚠️ Common ground is REQUIRED or servo will not work',
                        '⚠️ Wrong wiring can damage ESP8266'
                    ]
                },
                {
                    'number': 3,
                    'title': 'Add Status LEDs (Optional)',
                    'description': 'Add LED indicators for WiFi status and blind position.',
                    'wiring': [
                        {'from': 'WiFi LED +', 'to': 'ESP8266 D2 (GPIO4)', 'color': 'blue'},
                        {'from': 'WiFi LED -', 'to': 'GND (via 220Ω resistor)', 'color': 'black'},
                        {'from': 'Status LED +', 'to': 'ESP8266 D3 (GPIO0)', 'color': 'green'},
                        {'from': 'Status LED -', 'to': 'GND (via 220Ω resistor)', 'color': 'black'}
                    ],
                    'details': [
                        'Blue LED: WiFi connected status',
                        'Green LED: Blind open/closed indicator',
                        'Both use 220Ω resistors to limit current'
                    ],
                    'time': '10 minutes (optional)'
                },
                {
                    'number': 4,
                    'title': 'Verify Power and Wiring',
                    'description': 'Critical safety check before powering on.',
                    'checklist': [
                        '✓ Servo VCC connected to EXTERNAL 5V (not ESP8266)',
                        '✓ Servo GND connected to power supply GND',
                        '✓ ESP8266 GND connected to power supply GND (common ground)',
                        '✓ Servo signal wire to D1 (GPIO5)',
                        '✓ 5V power supply is 2A minimum',
                        '✓ ESP8266 has separate USB power',
                        '✓ No short circuits visible'
                    ],
                    'time': '5 minutes',
                    'warnings': [
                        '⚠️ Double-check common ground connection',
                        '⚠️ Servo MUST have external power'
                    ]
                },
                {
                    'number': 5,
                    'title': 'Install Arduino Libraries',
                    'description': 'Add required libraries for ESP8266 and servo control.',
                    'details': [
                        'Open Arduino IDE',
                        'Go to File → Preferences',
                        'Add ESP8266 board URL: http://arduino.esp8266.com/stable/package_esp8266com_index.json',
                        'Go to Tools → Board → Boards Manager',
                        'Search "esp8266" and install',
                        'Install library: "Servo" (built-in)',
                        'Install library: "ESPAsyncWebServer" by me-no-dev',
                        'Install library: "ESPAsyncTCP" (dependency)'
                    ],
                    'time': '20 minutes',
                    'tips': [
                        'Restart Arduino IDE after installing board package',
                        'ESPAsyncWebServer enables web control interface'
                    ]
                },
                {
                    'number': 6,
                    'title': 'Configure WiFi Credentials',
                    'description': 'Set your WiFi network name and password in code.',
                    'details': [
                        'Copy the provided code into Arduino IDE',
                        'Find lines near top:',
                        '  const char* ssid = "YOUR_WIFI_NAME";',
                        '  const char* password = "YOUR_WIFI_PASSWORD";',
                        'Replace with your actual WiFi credentials',
                        'Keep quotation marks intact'
                    ],
                    'time': '5 minutes',
                    'warnings': [
                        '⚠️ ESP8266 only works with 2.4GHz WiFi (not 5GHz)',
                        '⚠️ WiFi password is case-sensitive'
                    ]
                },
                {
                    'number': 7,
                    'title': 'Upload Code to ESP8266',
                    'description': 'Flash the blind controller sketch.',
                    'details': [
                        'Select Board: Tools → Board → ESP8266 → NodeMCU 1.0',
                        'Select Port: Tools → Port → (your ESP8266 port)',
                        'Set Upload Speed: 115200',
                        'Click Upload',
                        'Wait for "Done uploading" message'
                    ],
                    'time': '10 minutes',
                    'troubleshooting': [
                        'Upload fails? Hold FLASH button during upload',
                        'Port not found? Install CH340 or CP2102 USB driver',
                        'Compilation error? Check library installations'
                    ]
                },
                {
                    'number': 8,
                    'title': 'Test Servo Movement',
                    'description': 'Verify servo responds to commands before mounting.',
                    'details': [
                        'Open Serial Monitor (115200 baud)',
                        'ESP8266 will print its IP address',
                        'Note the IP address (e.g., 192.168.1.100)',
                        'On phone/computer, open web browser',
                        'Go to: http://[ESP8266_IP]',
                        'You should see blind control web page',
                        'Test OPEN and CLOSE buttons',
                        'Watch servo rotate to each position'
                    ],
                    'time': '15 minutes',
                    'success_criteria': [
                        '✓ ESP8266 connects to WiFi',
                        '✓ IP address displayed in Serial Monitor',
                        '✓ Web page loads successfully',
                        '✓ Servo rotates smoothly 0° to 180°',
                        '✓ Buttons respond immediately'
                    ]
                },
                {
                    'number': 9,
                    'title': 'Calibrate Blind Positions',
                    'description': 'Adjust open and close angles for your specific blinds.',
                    'details': [
                        'Default: OPEN=0°, CLOSE=180°',
                        'Your blinds may need different angles',
                        'Modify in code:',
                        '  int BLIND_OPEN = 0;    // Adjust this',
                        '  int BLIND_CLOSE = 180;  // Adjust this',
                        'Test different values:',
                        '  - Try 90° for half-open',
                        '  - Try 45° increments',
                        '  - Find perfect open/close positions',
                        'Re-upload code after changes'
                    ],
                    'time': '20 minutes',
                    'tips': [
                        'Mark servo positions with tape during testing',
                        'Some blinds need 90° rotation, others need 180°',
                        'Continuous servos need different timing code'
                    ]
                },
                {
                    'number': 10,
                    'title': 'Mount Servo to Blind Mechanism',
                    'description': 'Physically attach servo to blind pull cord or wand.',
                    'details': [
                        'Option 1: Cord wrap method',
                        '  - Attach servo horn to blind pull cord',
                        '  - Servo rotation winds/unwinds cord',
                        '  - Works for most blinds',
                        'Option 2: Direct wand attach',
                        '  - 3D print adapter for blind wand',
                        '  - Servo directly rotates wand',
                        '  - Most reliable method',
                        'Option 3: Chain drive',
                        '  - Servo pulls bead chain',
                        '  - Good for vertical blinds',
                        'Secure with strong tape or screws',
                        'Test movement with actual blind attached'
                    ],
                    'time': '30-60 minutes',
                    'warnings': [
                        '⚠️ Servo must have enough torque for your blind',
                        '⚠️ Test extensively before leaving unattended',
                        '⚠️ Add limit switches if blinds can jam'
                    ]
                },
                {
                    'number': 11,
                    'title': 'Add Schedule/Automation (Advanced)',
                    'description': 'Program automatic open/close based on time or light.',
                    'details': [
                        'Option 1: Time-based schedule',
                        '  - Open at 7AM, close at 9PM',
                        '  - Uses NTP (network time)',
                        '  - Add TimeLib library',
                        'Option 2: Light sensor trigger',
                        '  - Open when bright, close when dark',
                        '  - Add LDR (light dependent resistor)',
                        '  - Threshold adjustable',
                        'Option 3: Smart home integration',
                        '  - Alexa/Google Home control',
                        '  - Use fauxmoESP library',
                        '  - Voice commands: "Alexa, open the blinds"',
                        'Uncomment automation code in sketch'
                    ],
                    'time': '30-60 minutes (advanced)',
                    'tips': [
                        'Start with manual control, add automation later',
                        'NTP requires internet connection',
                        'Test automation thoroughly before trusting it'
                    ]
                },
                {
                    'number': 12,
                    'title': 'Create Enclosure',
                    'description': 'Build protective case for electronics.',
                    'details': [
                        '3D print custom enclosure design',
                        'Or use small project box from hardware store',
                        'Cut holes for:',
                        '  - USB cable (ESP8266 power)',
                        '  - Servo wires',
                        '  - Status LEDs (if used)',
                        '  - Ventilation slots',
                        'Mount ESP8266 with standoffs or tape',
                        'Label box with WiFi SSID and default IP',
                        'Add reset button access if possible'
                    ],
                    'time': '30-45 minutes',
                    'tips': [
                        'Leave access to USB port for updates',
                        'Add cable management for clean look',
                        'Test everything before sealing enclosure'
                    ]
                }
            ],

            'total_build_time': '4-5 hours (basic) / 6-8 hours (with automation)',
            'estimated_cost': '$9.00',

            'code_template': '''
/*
 * Automatic Blind Controller
 * WiFi-controlled motorized blinds using ESP8266 and servo
 *
 * Components:
 * - ESP8266 (NodeMCU or Wemos D1)
 * - Servo motor (SG90 or MG996R)
 * - 5V 2A power supply (for servo)
 * - LEDs for status (optional)
 *
 * Features:
 * - Web-based control interface
 * - Open/Close/Stop commands
 * - Position feedback
 * - WiFi status indicator
 * - Optional: Time-based automation
 */

#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <Servo.h>

// WiFi credentials - CHANGE THESE!
const char* ssid = "YOUR_WIFI_NAME";
const char* password = "YOUR_WIFI_PASSWORD";

// Hardware pins
#define SERVO_PIN D1      // GPIO5
#define LED_WIFI D2       // GPIO4 - Blue LED for WiFi status
#define LED_STATUS D3     // GPIO0 - Green LED for blind status

// Servo positions - CALIBRATE FOR YOUR BLINDS!
#define BLIND_OPEN 0      // Fully open angle
#define BLIND_CLOSE 180   // Fully closed angle

Servo blindServo;
ESP8266WebServer server(80);

int currentPosition = BLIND_OPEN;  // Start open
bool isMoving = false;

void setup() {
  Serial.begin(115200);

  // Initialize pins
  pinMode(LED_WIFI, OUTPUT);
  pinMode(LED_STATUS, OUTPUT);

  // Initialize servo
  blindServo.attach(SERVO_PIN);
  blindServo.write(BLIND_OPEN);

  // Connect to WiFi
  Serial.println();
  Serial.print("Connecting to WiFi: ");
  Serial.println(ssid);

  WiFi.begin(ssid, password);
  digitalWrite(LED_WIFI, LOW);  // WiFi LED off while connecting

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    digitalWrite(LED_WIFI, !digitalRead(LED_WIFI));  // Blink while connecting
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println();
    Serial.println("WiFi connected!");
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());
    Serial.println("Open this IP in your browser to control blinds");
    digitalWrite(LED_WIFI, HIGH);  // WiFi LED solid on
  } else {
    Serial.println();
    Serial.println("WiFi connection failed! Check credentials");
    digitalWrite(LED_WIFI, LOW);
  }

  // Setup web server routes
  server.on("/", handleRoot);
  server.on("/open", handleOpen);
  server.on("/close", handleClose);
  server.on("/stop", handleStop);
  server.on("/status", handleStatus);

  server.begin();
  Serial.println("Web server started");
}

void loop() {
  server.handleClient();

  // Update status LED based on position
  if (currentPosition < 45) {
    digitalWrite(LED_STATUS, HIGH);  // Fully open - LED on
  } else if (currentPosition > 135) {
    digitalWrite(LED_STATUS, LOW);   // Fully closed - LED off
  } else {
    // Blink if in middle
    static unsigned long lastBlink = 0;
    if (millis() - lastBlink > 500) {
      digitalWrite(LED_STATUS, !digitalRead(LED_STATUS));
      lastBlink = millis();
    }
  }
}

void handleRoot() {
  // Serve web control interface
  String html = R"=====(
<!DOCTYPE html>
<html>
<head>
  <title>Blind Controller</title>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <style>
    body {
      font-family: Arial, sans-serif;
      text-align: center;
      padding: 20px;
      background: #f0f0f0;
    }
    h1 {
      color: #333;
    }
    .button {
      display: inline-block;
      padding: 20px 40px;
      margin: 10px;
      font-size: 24px;
      border: none;
      border-radius: 10px;
      cursor: pointer;
      color: white;
      text-decoration: none;
    }
    .open { background: #4CAF50; }
    .close { background: #f44336; }
    .stop { background: #FFC107; color: #333; }
    .button:active {
      transform: scale(0.95);
    }
    .status {
      margin-top: 30px;
      padding: 15px;
      background: white;
      border-radius: 10px;
      font-size: 18px;
    }
  </style>
</head>
<body>
  <h1>🪟 Blind Controller</h1>
  <p>WiFi: )=====";

  html += ssid;
  html += R"=====(</p>

  <div>
    <a href='/open' class='button open'>▲ OPEN</a>
    <a href='/stop' class='button stop'>■ STOP</a>
    <a href='/close' class='button close'>▼ CLOSE</a>
  </div>

  <div class='status'>
    <div>Position: <span id='pos'>)=====";

  html += String(currentPosition);
  html += R"=====(</span>°</div>
    <div>Status: <span id='status'>)=====";

  if (currentPosition < 45) html += "OPEN";
  else if (currentPosition > 135) html += "CLOSED";
  else html += "PARTIAL";

  html += R"=====(</span></div>
  </div>

  <p style='margin-top: 30px; color: #666; font-size: 14px;'>
    Built with Circuit-AI<br>
    IP: )=====";

  html += WiFi.localIP().toString();
  html += R"=====(
  </p>

  <script>
    // Auto-refresh status every 2 seconds
    setInterval(function() {
      fetch('/status')
        .then(r => r.json())
        .then(data => {
          document.getElementById('pos').textContent = data.position;
          document.getElementById('status').textContent = data.status;
        });
    }, 2000);
  </script>
</body>
</html>
)=====";

  server.send(200, "text/html", html);
}

void handleOpen() {
  Serial.println("Command: OPEN");
  moveBlind(BLIND_OPEN);
  server.sendHeader("Location", "/");
  server.send(303);
}

void handleClose() {
  Serial.println("Command: CLOSE");
  moveBlind(BLIND_CLOSE);
  server.sendHeader("Location", "/");
  server.send(303);
}

void handleStop() {
  Serial.println("Command: STOP");
  // Servo holds position automatically
  server.sendHeader("Location", "/");
  server.send(303);
}

void handleStatus() {
  String status;
  if (currentPosition < 45) status = "OPEN";
  else if (currentPosition > 135) status = "CLOSED";
  else status = "PARTIAL";

  String json = "{";
  json += "\\"position\\":" + String(currentPosition) + ",";
  json += "\\"status\\":\\"" + status + "\\"";
  json += "}";

  server.send(200, "application/json", json);
}

void moveBlind(int targetPosition) {
  isMoving = true;

  // Smooth movement
  int step = (targetPosition > currentPosition) ? 1 : -1;

  while (currentPosition != targetPosition) {
    currentPosition += step;
    blindServo.write(currentPosition);
    delay(15);  // Adjust speed here (lower = faster)
  }

  isMoving = false;
  Serial.print("Moved to position: ");
  Serial.println(currentPosition);
}
''',

            'business_notes': {
                'marketability': 'VERY HIGH - Practical home automation, high perceived value',
                'target_audience': 'Smart home enthusiasts, home owners, apartment renters, tech-savvy homeowners',
                'upsell_opportunities': [
                    'Multi-window package (3-5 windows) - add $15 each',
                    'Solar panel + battery power - add $25',
                    'Light sensor automation - add $5',
                    'Professional installation service - add $40-80',
                    'Smart home hub integration (Alexa/Google) - add $10',
                    'Smartphone app with scheduling - add $20'
                ],
                'manufacturing_notes': [
                    'Use MG996R metal gear servos for reliability',
                    'Custom PCB reduces cost to $6/unit at qty 100',
                    '3D printed mounting brackets add professional touch',
                    'Pre-programmed with customer WiFi for plug-and-play',
                    'Package includes installation hardware and guide',
                    'Offer premium version with solar power'
                ],
                'competitive_advantages': [
                    'Commercial systems cost $150-300 PER WINDOW',
                    'DIY solution is 85-95% cheaper',
                    'Easy smartphone control',
                    'No subscription fees',
                    'Customizable automation',
                    'Works with existing blinds'
                ]
            },

            'next_steps': [
                'Build prototype and test for 1-2 weeks',
                'Measure servo torque requirements for different blind types',
                'Design universal mounting bracket (3D printable)',
                'Create professional product photos and demo video',
                'Develop smartphone app or use web interface',
                'Test WiFi range and reliability',
                'Add safety features (jam detection, limits)',
                'List on Etsy with installation guide and video',
                'Offer installation service for local customers ($50-100)',
                'Scale production with bulk component orders'
            ],

            'safety_notes': [
                'Test extensively before leaving unattended',
                'Add manual override mechanism',
                'Consider fire safety - blinds must be manually operable',
                'Check local building codes for motorized window coverings',
                'Warn users about pinch points and moving parts',
                'Include emergency stop function in web interface'
            ]
        }

    def _generate_smart_relay_instructions(self) -> Dict:
        """Instructions for IoT Smart Relay Controller (ESP8266 + Relay + WiFi)"""
        return {
            'project_name': 'IoT Smart Relay Controller',
            'difficulty': 'medium',
            'build_time': '2-3 hours',
            'skill_level': 'Intermediate',

            'tools_needed': [
                'Breadboard (for prototyping)',
                'Jumper wires',
                'USB cable for ESP8266',
                'Computer with Arduino IDE',
                'Smartphone (for WiFi control testing)',
                'Multimeter (for safety checks)'
            ],

            'components': [
                {'id': 'esp8266', 'quantity': 1, 'notes': 'NodeMCU or Wemos D1 Mini'},
                {'id': 'relay', 'quantity': 1, 'notes': '5V relay module (1-channel or 4-channel)'},
                {'id': 'led', 'quantity': 2, 'notes': 'Status indicators (optional)'},
                {'id': 'resistor', 'quantity': 2, 'notes': '220 ohm for LEDs (optional)'},
                {'id': 'power_supply', 'quantity': 1, 'notes': '5V 1A power adapter (optional - can use USB)'}
            ],

            'market_analysis': {
                'build_cost': 8.10,
                'market_price_low': 25.00,
                'market_price_high': 50.00,
                'profit_margin': '208-517%',
                'comparable_products': [
                    'Smart plugs (Wemo, TP-Link): $25-40',
                    'DIY home automation switches on Etsy: $30-50',
                    'Commercial IoT relays: $45-100'
                ]
            },

            'steps': [
                {
                    'number': 1,
                    'title': 'Choose Relay Module',
                    'description': 'Select appropriate relay for your application.',
                    'details': [
                        '1-channel relay: Single device control ($2-3)',
                        '2-channel relay: Two devices independently ($3-4)',
                        '4-channel relay: Four devices ($5-7)',
                        'Make sure relay is 5V trigger voltage',
                        'Check relay current rating (10A typical)',
                        'Active HIGH or LOW trigger (check module specs)'
                    ],
                    'time': '10 minutes',
                    'tips': [
                        'Start with 1-channel for learning',
                        '4-channel lets you control multiple lights/fans',
                        'Optocoupler isolation provides safety'
                    ]
                },
                {
                    'number': 2,
                    'title': 'Wire ESP8266 and Relay Module',
                    'description': 'Connect relay module to ESP8266 for control.',
                    'wiring': [
                        {'from': 'Relay VCC', 'to': 'ESP8266 5V (VIN)', 'color': 'red'},
                        {'from': 'Relay GND', 'to': 'ESP8266 GND', 'color': 'black'},
                        {'from': 'Relay IN1', 'to': 'ESP8266 D1 (GPIO5)', 'color': 'yellow'},
                        {'from': 'Relay IN2', 'to': 'ESP8266 D2 (GPIO4)', 'color': 'orange'},
                        {'from': 'Relay IN3', 'to': 'ESP8266 D5 (GPIO14)', 'color': 'green'},
                        {'from': 'Relay IN4', 'to': 'ESP8266 D6 (GPIO12)', 'color': 'blue'}
                    ],
                    'details': [
                        'For 1-channel: Only wire IN1',
                        'For 4-channel: Wire IN1-IN4 as shown',
                        'VCC from relay → ESP8266 VIN (5V)',
                        'GND from relay → ESP8266 GND',
                        'Signal pins → GPIO pins as listed'
                    ],
                    'time': '15 minutes',
                    'warnings': [
                        '⚠️ NEVER connect AC power while breadboarding',
                        '⚠️ Relay controls HIGH VOLTAGE - understand wiring first',
                        '⚠️ Always disconnect AC power before changing wiring',
                        '⚠️ Test with low-voltage loads (LED, 12V bulb) first'
                    ]
                },
                {
                    'number': 3,
                    'title': 'Add Status LEDs (Optional)',
                    'description': 'Visual indicators for WiFi and relay status.',
                    'wiring': [
                        {'from': 'WiFi LED +', 'to': 'ESP8266 D7 (GPIO13)', 'color': 'blue'},
                        {'from': 'WiFi LED -', 'to': 'GND (via 220Ω resistor)', 'color': 'black'},
                        {'from': 'Relay LED +', 'to': 'ESP8266 D8 (GPIO15)', 'color': 'green'},
                        {'from': 'Relay LED -', 'to': 'GND (via 220Ω resistor)', 'color': 'black'}
                    ],
                    'details': [
                        'Blue LED: WiFi connection status',
                        'Green LED: Relay ON/OFF status',
                        'Use 220Ω resistors for current limiting'
                    ],
                    'time': '10 minutes (optional)'
                },
                {
                    'number': 4,
                    'title': 'Install Arduino Libraries',
                    'description': 'Add required libraries for ESP8266 WiFi control.',
                    'details': [
                        'Open Arduino IDE',
                        'Go to File → Preferences',
                        'Add ESP8266 board URL: http://arduino.esp8266.com/stable/package_esp8266com_index.json',
                        'Go to Tools → Board → Boards Manager',
                        'Search "esp8266" and install',
                        'Library: ESP8266WiFi (built-in)',
                        'Library: ESP8266WebServer (built-in)'
                    ],
                    'time': '15 minutes',
                    'tips': [
                        'Restart Arduino IDE after installing board package',
                        'No external libraries needed - all built-in!'
                    ]
                },
                {
                    'number': 5,
                    'title': 'Configure WiFi Credentials',
                    'description': 'Set your WiFi network name and password.',
                    'details': [
                        'Copy provided code into Arduino IDE',
                        'Find lines near top:',
                        '  const char* ssid = "YOUR_WIFI_NAME";',
                        '  const char* password = "YOUR_WIFI_PASSWORD";',
                        'Replace with your actual WiFi credentials',
                        'Keep quotation marks intact'
                    ],
                    'time': '5 minutes',
                    'warnings': [
                        '⚠️ ESP8266 only works with 2.4GHz WiFi (not 5GHz)',
                        '⚠️ WiFi password is case-sensitive',
                        '⚠️ Avoid special characters in WiFi SSID if possible'
                    ]
                },
                {
                    'number': 6,
                    'title': 'Upload Code to ESP8266',
                    'description': 'Flash the relay controller sketch.',
                    'details': [
                        'Select Board: Tools → Board → ESP8266 → NodeMCU 1.0',
                        'Select Port: Tools → Port → (your ESP8266 port)',
                        'Set Upload Speed: 115200',
                        'Click Upload button',
                        'Wait for "Done uploading" message'
                    ],
                    'time': '10 minutes',
                    'troubleshooting': [
                        'Upload fails? Hold FLASH button during upload',
                        'Port not found? Install CH340 or CP2102 USB driver',
                        'Compilation error? Check WiFi credentials syntax'
                    ]
                },
                {
                    'number': 7,
                    'title': 'Test Relay Control',
                    'description': 'Verify relay switches before connecting AC power.',
                    'details': [
                        'Open Serial Monitor (115200 baud)',
                        'ESP8266 will print its IP address',
                        'Note the IP (e.g., 192.168.1.100)',
                        'Open web browser on phone/computer',
                        'Go to: http://[ESP8266_IP]',
                        'You should see relay control web page',
                        'Click ON/OFF buttons',
                        'Listen for relay click sound',
                        'Watch relay LED indicator change'
                    ],
                    'time': '15 minutes',
                    'success_criteria': [
                        '✓ ESP8266 connects to WiFi',
                        '✓ Web page loads successfully',
                        '✓ Relay clicks ON and OFF',
                        '✓ LED indicators working (if installed)',
                        '✓ Buttons respond immediately'
                    ]
                },
                {
                    'number': 8,
                    'title': 'Wire Load to Relay (ADVANCED)',
                    'description': 'DANGEROUS: Connect device to be controlled.',
                    'details': [
                        'SAFETY FIRST: Disconnect all power sources',
                        'Understand relay terminal labels:',
                        '  - COM (Common): Connect to load',
                        '  - NO (Normally Open): Load OFF when relay OFF',
                        '  - NC (Normally Closed): Load ON when relay OFF',
                        'Most common wiring (NO configuration):',
                        '  1. Cut HOT wire of device',
                        '  2. One end → COM',
                        '  3. Other end → NO',
                        '  4. When relay ON, circuit closes',
                        'Use terminal blocks for solid connections',
                        'Insulate all connections with heat shrink'
                    ],
                    'time': '30 minutes',
                    'warnings': [
                        '⚠️ DANGER: AC voltage can KILL - get professional help if unsure',
                        '⚠️ Only modify device cord, NEVER wall wiring',
                        '⚠️ Use proper wire gauge (18AWG minimum)',
                        '⚠️ Check relay current rating vs device current draw',
                        '⚠️ Add fuse inline for safety',
                        '⚠️ Never work on live circuits',
                        '⚠️ Follow local electrical codes'
                    ]
                },
                {
                    'number': 9,
                    'title': 'Add Scheduling/Automation (Optional)',
                    'description': 'Program time-based or sensor-triggered control.',
                    'details': [
                        'Option 1: Time-based schedule',
                        '  - Turn lights ON at 6PM, OFF at 11PM',
                        '  - Uses NTP (network time protocol)',
                        '  - Add TimeLib library',
                        'Option 2: Temperature trigger',
                        '  - Add DHT22 sensor',
                        '  - Turn fan ON when temp > 75°F',
                        '  - Automatic climate control',
                        'Option 3: Smart home integration',
                        '  - Alexa/Google Home control',
                        '  - Use fauxmoESP library',
                        '  - Voice: "Alexa, turn on the fan"',
                        'Option 4: MQTT for advanced automation',
                        '  - Integrate with Home Assistant',
                        '  - Complex automation rules'
                    ],
                    'time': '30-60 minutes (advanced)',
                    'tips': [
                        'Start with manual control first',
                        'Add automation features one at a time',
                        'NTP requires internet connection'
                    ]
                },
                {
                    'number': 10,
                    'title': 'Create Enclosure',
                    'description': 'Build protective case for electronics.',
                    'details': [
                        'Use electrical project box from hardware store',
                        'Or 3D print custom enclosure',
                        'Cut holes for:',
                        '  - USB cable (ESP8266 power)',
                        '  - Relay wires (to controlled device)',
                        '  - Status LEDs (if used)',
                        '  - Ventilation holes (relay can heat up)',
                        'Mount ESP8266 and relay with standoffs',
                        'Label clearly: "CAUTION: HIGH VOLTAGE"',
                        'Add reset button access if possible',
                        'Include IP address sticker for easy access'
                    ],
                    'time': '30-45 minutes',
                    'tips': [
                        'Leave access to USB port for updates',
                        'Use DIN rail mount for professional install',
                        'Add cable management inside enclosure'
                    ]
                }
            ],

            'total_build_time': '2-3 hours (basic) / 4-5 hours (with AC wiring + automation)',
            'estimated_cost': '$8.10',

            'code_template': '''
/*
 * IoT Smart Relay Controller
 * WiFi-controlled relay for home automation
 *
 * Components:
 * - ESP8266 (NodeMCU or Wemos D1)
 * - 5V Relay module (1, 2, or 4 channel)
 * - LEDs for status (optional)
 *
 * Features:
 * - Web-based control interface
 * - Multiple relay support (1-4 channels)
 * - ON/OFF/Toggle commands
 * - Status feedback
 * - WiFi status indicator
 * - Responsive mobile interface
 */

#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>

// WiFi credentials - CHANGE THESE!
const char* ssid = "YOUR_WIFI_NAME";
const char* password = "YOUR_WIFI_PASSWORD";

// Hardware pins
#define RELAY1_PIN D1     // GPIO5
#define RELAY2_PIN D2     // GPIO4 (if using 2+ channel relay)
#define RELAY3_PIN D5     // GPIO14 (if using 3+ channel relay)
#define RELAY4_PIN D6     // GPIO12 (if using 4 channel relay)
#define LED_WIFI D7       // GPIO13 - WiFi status LED
#define LED_RELAY D8      // GPIO15 - Relay status LED

// Relay configuration
#define NUM_RELAYS 1      // Change to 2, 3, or 4 based on your relay module
#define ACTIVE_LOW true   // true if relay triggers on LOW, false if HIGH

ESP8266WebServer server(80);

// Relay states (false = OFF, true = ON)
bool relayStates[4] = {false, false, false, false};

void setup() {
  Serial.begin(115200);

  // Initialize relay pins
  pinMode(RELAY1_PIN, OUTPUT);
  if (NUM_RELAYS >= 2) pinMode(RELAY2_PIN, OUTPUT);
  if (NUM_RELAYS >= 3) pinMode(RELAY3_PIN, OUTPUT);
  if (NUM_RELAYS >= 4) pinMode(RELAY4_PIN, OUTPUT);

  // Initialize status LEDs
  pinMode(LED_WIFI, OUTPUT);
  pinMode(LED_RELAY, OUTPUT);

  // Turn all relays OFF initially
  setRelay(0, false);
  if (NUM_RELAYS >= 2) setRelay(1, false);
  if (NUM_RELAYS >= 3) setRelay(2, false);
  if (NUM_RELAYS >= 4) setRelay(3, false);

  // Connect to WiFi
  Serial.println();
  Serial.print("Connecting to WiFi: ");
  Serial.println(ssid);

  WiFi.begin(ssid, password);
  digitalWrite(LED_WIFI, LOW);  // WiFi LED off while connecting

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    digitalWrite(LED_WIFI, !digitalRead(LED_WIFI));  // Blink while connecting
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println();
    Serial.println("WiFi connected!");
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());
    Serial.println("Open this IP in your browser to control relays");
    digitalWrite(LED_WIFI, HIGH);  // WiFi LED solid on
  } else {
    Serial.println();
    Serial.println("WiFi connection failed! Check credentials");
    digitalWrite(LED_WIFI, LOW);
  }

  // Setup web server routes
  server.on("/", handleRoot);
  server.on("/relay1/on", []() { setRelay(0, true); server.sendHeader("Location", "/"); server.send(303); });
  server.on("/relay1/off", []() { setRelay(0, false); server.sendHeader("Location", "/"); server.send(303); });
  server.on("/relay1/toggle", []() { setRelay(0, !relayStates[0]); server.sendHeader("Location", "/"); server.send(303); });

  if (NUM_RELAYS >= 2) {
    server.on("/relay2/on", []() { setRelay(1, true); server.sendHeader("Location", "/"); server.send(303); });
    server.on("/relay2/off", []() { setRelay(1, false); server.sendHeader("Location", "/"); server.send(303); });
    server.on("/relay2/toggle", []() { setRelay(1, !relayStates[1]); server.sendHeader("Location", "/"); server.send(303); });
  }

  if (NUM_RELAYS >= 3) {
    server.on("/relay3/on", []() { setRelay(2, true); server.sendHeader("Location", "/"); server.send(303); });
    server.on("/relay3/off", []() { setRelay(2, false); server.sendHeader("Location", "/"); server.send(303); });
    server.on("/relay3/toggle", []() { setRelay(2, !relayStates[2]); server.sendHeader("Location", "/"); server.send(303); });
  }

  if (NUM_RELAYS >= 4) {
    server.on("/relay4/on", []() { setRelay(3, true); server.sendHeader("Location", "/"); server.send(303); });
    server.on("/relay4/off", []() { setRelay(3, false); server.sendHeader("Location", "/"); server.send(303); });
    server.on("/relay4/toggle", []() { setRelay(3, !relayStates[3]); server.sendHeader("Location", "/"); server.send(303); });
  }

  server.on("/status", handleStatus);

  server.begin();
  Serial.println("Web server started");
}

void loop() {
  server.handleClient();

  // Update relay status LED (ON if any relay is active)
  bool anyRelayOn = false;
  for (int i = 0; i < NUM_RELAYS; i++) {
    if (relayStates[i]) anyRelayOn = true;
  }
  digitalWrite(LED_RELAY, anyRelayOn ? HIGH : LOW);
}

void setRelay(int relayNum, bool state) {
  if (relayNum < 0 || relayNum >= NUM_RELAYS) return;

  relayStates[relayNum] = state;

  // Set physical pin (invert if ACTIVE_LOW)
  bool pinState = ACTIVE_LOW ? !state : state;

  switch(relayNum) {
    case 0: digitalWrite(RELAY1_PIN, pinState); break;
    case 1: digitalWrite(RELAY2_PIN, pinState); break;
    case 2: digitalWrite(RELAY3_PIN, pinState); break;
    case 3: digitalWrite(RELAY4_PIN, pinState); break;
  }

  Serial.print("Relay ");
  Serial.print(relayNum + 1);
  Serial.print(": ");
  Serial.println(state ? "ON" : "OFF");
}

void handleRoot() {
  String html = R"=====(
<!DOCTYPE html>
<html>
<head>
  <title>Smart Relay Controller</title>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <style>
    body {
      font-family: Arial, sans-serif;
      text-align: center;
      padding: 20px;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: white;
    }
    h1 {
      margin-bottom: 10px;
    }
    .subtitle {
      color: #ddd;
      margin-bottom: 30px;
    }
    .relay-card {
      background: rgba(255,255,255,0.1);
      border-radius: 15px;
      padding: 20px;
      margin: 15px auto;
      max-width: 400px;
      backdrop-filter: blur(10px);
    }
    .button {
      display: inline-block;
      padding: 15px 30px;
      margin: 5px;
      font-size: 18px;
      border: none;
      border-radius: 8px;
      cursor: pointer;
      color: white;
      text-decoration: none;
      font-weight: bold;
      transition: transform 0.1s;
    }
    .on-btn { background: #4CAF50; }
    .off-btn { background: #f44336; }
    .toggle-btn { background: #FF9800; }
    .button:active {
      transform: scale(0.95);
    }
    .status-badge {
      display: inline-block;
      padding: 8px 20px;
      border-radius: 20px;
      font-weight: bold;
      margin: 10px 0;
    }
    .status-on {
      background: #4CAF50;
      color: white;
    }
    .status-off {
      background: #ccc;
      color: #333;
    }
    .footer {
      margin-top: 30px;
      font-size: 12px;
      color: #ddd;
    }
  </style>
</head>
<body>
  <h1>⚡ Smart Relay Controller</h1>
  <p class='subtitle'>WiFi: )=====";

  html += ssid;
  html += R"=====(</p>
)=====";

  // Generate relay control cards
  for (int i = 0; i < NUM_RELAYS; i++) {
    html += "<div class='relay-card'>";
    html += "<h2>Relay " + String(i + 1) + "</h2>";
    html += "<div class='status-badge status-";
    html += relayStates[i] ? "on'>ON" : "off'>OFF";
    html += "</div><br>";
    html += "<a href='/relay" + String(i + 1) + "/on' class='button on-btn'>ON</a>";
    html += "<a href='/relay" + String(i + 1) + "/off' class='button off-btn'>OFF</a>";
    html += "<a href='/relay" + String(i + 1) + "/toggle' class='button toggle-btn'>TOGGLE</a>";
    html += "</div>";
  }

  html += R"=====(
  <div class='footer'>
    Built with Circuit-AI<br>
    IP: )=====";
  html += WiFi.localIP().toString();
  html += R"=====(
  </div>

  <script>
    // Auto-refresh status every 3 seconds
    setInterval(function() {
      fetch('/status')
        .then(r => r.json())
        .then(data => {
          // Update would go here (simplified for now)
          location.reload();
        });
    }, 10000);  // Reload every 10 seconds
  </script>
</body>
</html>
)=====";

  server.send(200, "text/html", html);
}

void handleStatus() {
  String json = "{";
  json += "\\"relays\\":[";
  for (int i = 0; i < NUM_RELAYS; i++) {
    if (i > 0) json += ",";
    json += relayStates[i] ? "true" : "false";
  }
  json += "],";
  json += "\\"wifi\\":\\"connected\\",";
  json += "\\"ip\\":\\"" + WiFi.localIP().toString() + "\\"";
  json += "}";

  server.send(200, "application/json", json);
}
''',

            'business_notes': {
                'marketability': 'VERY HIGH - Universal home automation, everyone needs it',
                'target_audience': 'Smart home enthusiasts, renters, homeowners, tech hobbyists, small businesses',
                'upsell_opportunities': [
                    'Multi-outlet version (4-channel relay) - add $5, sell for +$15',
                    'Outdoor weatherproof enclosure - add $10, sell for +$25',
                    'Energy monitoring (add current sensor) - add $8, sell for +$30',
                    'Voice control integration (Alexa/Google) - add $5, sell for +$15',
                    'Smartphone app instead of web - add $20 value',
                    'Pre-configured with customer WiFi - premium service +$10'
                ],
                'manufacturing_notes': [
                    'Buy relays in bulk: $1.50 each at qty 100',
                    'Custom PCB reduces cost to $5/unit at qty 50',
                    'Pre-flashed ESP8266 modules save assembly time',
                    'Use quality relay modules with optocoupler isolation',
                    'Include safety documentation and disclaimers',
                    'Offer both kit (DIY) and assembled versions'
                ],
                'competitive_advantages': [
                    'Commercial smart plugs cost $25-40 EACH',
                    'Your 4-channel relay controls 4 devices for $35 total',
                    '85-90% cheaper than commercial solutions',
                    'No monthly subscription fees (unlike many commercial products)',
                    'Fully customizable and hackable',
                    'Works offline - no cloud dependency',
                    'Open source - users can modify code'
                ]
            },

            'next_steps': [
                'Build and test for 1-2 weeks with safe low-voltage loads',
                'Test WiFi reliability and range',
                'Design professional enclosure (3D print or buy project box)',
                'Create detailed safety guide for AC wiring',
                'Get electrical safety certification if selling commercially',
                'Develop smartphone app or refine web interface',
                'Add MQTT support for Home Assistant integration',
                'Create demo video showing multiple use cases',
                'List on Etsy as both kit and assembled versions',
                'Offer installation service for local customers ($30-50)',
                'Partner with electricians for professional installations'
            ],

            'safety_notes': [
                'CRITICAL: AC voltage is LETHAL - users must understand electrical safety',
                'Recommend professional electrician for permanent installations',
                'Include warning labels and safety documentation',
                'Only control device cords, never modify building wiring without license',
                'Use properly rated relays for intended load',
                'Add inline fuse for extra protection',
                'Test with low-voltage loads (12V bulbs) before AC',
                'Never work on live circuits',
                'Follow all local electrical codes and regulations',
                'Consider liability insurance if selling commercially'
            ]
        }

    def _generate_smart_doorbell_instructions(self) -> Dict:
        """Instructions for Smart Doorbell (ESP8266 + Button + Buzzer + WiFi Notifications)"""
        return {
            'project_name': 'Smart Doorbell',
            'difficulty': 'medium',
            'build_time': '2-3 hours',
            'skill_level': 'Intermediate',

            'tools_needed': [
                'Breadboard (for prototyping)',
                'Jumper wires',
                'USB cable for ESP8266',
                'Computer with Arduino IDE',
                'Smartphone (for notification testing)',
                'Optional: 3D printer for custom enclosure'
            ],

            'components': [
                {'id': 'esp8266', 'quantity': 1, 'notes': 'NodeMCU or Wemos D1 Mini'},
                {'id': 'relay', 'quantity': 1, 'notes': '5V relay for existing doorbell chime (optional)'},
                {'id': 'led', 'quantity': 2, 'notes': 'Status indicators'},
                {'id': 'resistor', 'quantity': 3, 'notes': '10k pull-up + 220 ohm for LEDs'},
                {'id': 'oled_ssd1306', 'quantity': 1, 'notes': 'Optional display for visitor count'}
            ],

            'market_analysis': {
                'build_cost': 8.10,
                'market_price_low': 22.00,
                'market_price_high': 38.00,
                'profit_margin': '171-369%',
                'comparable_products': [
                    'Ring Doorbell (basic): $100-150',
                    'Nest Hello: $200-230',
                    'DIY WiFi doorbells on Etsy: $25-40',
                    'Basic wireless doorbells: $15-30'
                ]
            },

            'steps': [
                {
                    'number': 1,
                    'title': 'Wire Button Input',
                    'description': 'Connect pushbutton for doorbell press detection.',
                    'wiring': [
                        {'from': 'Button Pin 1', 'to': 'ESP8266 D1 (GPIO5)', 'color': 'yellow'},
                        {'from': 'Button Pin 1', 'to': '3.3V (via 10kΩ resistor)', 'color': 'red'},
                        {'from': 'Button Pin 2', 'to': 'GND', 'color': 'black'}
                    ],
                    'details': [
                        'Use momentary pushbutton (normally open)',
                        'Button press connects D1 to GND',
                        '10kΩ pull-up resistor keeps D1 HIGH when not pressed',
                        'When pressed: D1 reads LOW',
                        'When released: D1 reads HIGH',
                        'Debouncing handled in software'
                    ],
                    'time': '10 minutes',
                    'tips': [
                        'Weatherproof buttons available for outdoor use',
                        'Illuminated buttons look professional',
                        'Consider arcade-style buttons for fun aesthetic'
                    ]
                },
                {
                    'number': 2,
                    'title': 'Add Status LEDs',
                    'description': 'Visual feedback for WiFi and doorbell status.',
                    'wiring': [
                        {'from': 'WiFi LED +', 'to': 'ESP8266 D2 (GPIO4)', 'color': 'blue'},
                        {'from': 'WiFi LED -', 'to': 'GND (via 220Ω resistor)', 'color': 'black'},
                        {'from': 'Doorbell LED +', 'to': 'ESP8266 D3 (GPIO0)', 'color': 'green'},
                        {'from': 'Doorbell LED -', 'to': 'GND (via 220Ω resistor)', 'color': 'black'}
                    ],
                    'details': [
                        'Blue LED: WiFi connection status (solid when connected)',
                        'Green LED: Flashes when doorbell pressed',
                        'Both use 220Ω current-limiting resistors'
                    ],
                    'time': '10 minutes'
                },
                {
                    'number': 3,
                    'title': 'Optional: Add Relay for Existing Chime',
                    'description': 'Trigger your existing doorbell chime when button pressed.',
                    'wiring': [
                        {'from': 'Relay IN', 'to': 'ESP8266 D5 (GPIO14)', 'color': 'orange'},
                        {'from': 'Relay VCC', 'to': 'ESP8266 VIN (5V)', 'color': 'red'},
                        {'from': 'Relay GND', 'to': 'ESP8266 GND', 'color': 'black'},
                        {'from': 'Relay COM', 'to': 'Doorbell transformer wire', 'color': 'varies'},
                        {'from': 'Relay NO', 'to': 'Existing chime input', 'color': 'varies'}
                    ],
                    'details': [
                        'Relay wired in parallel with existing doorbell button',
                        'When ESP8266 triggers relay, existing chime rings',
                        'Allows smart features while keeping traditional doorbell',
                        'Check your doorbell voltage (usually 12-24V AC)'
                    ],
                    'time': '20 minutes',
                    'warnings': [
                        '⚠️ Turn off power to doorbell transformer before wiring',
                        '⚠️ Low voltage but still disconnect power first'
                    ]
                },
                {
                    'number': 4,
                    'title': 'Install Arduino Libraries',
                    'description': 'Add libraries for WiFi and notifications.',
                    'details': [
                        'Open Arduino IDE',
                        'Install ESP8266 board support (as before)',
                        'Libraries needed:',
                        '  - ESP8266WiFi (built-in)',
                        '  - ESP8266WebServer (built-in)',
                        '  - ESP8266HTTPClient (built-in)',
                        '  - Optional: Pushover library for phone notifications',
                        '  - Optional: Telegram Bot library',
                        '  - Optional: Adafruit SSD1306 for OLED display'
                    ],
                    'time': '15 minutes',
                    'tips': [
                        'Start without notifications, add later',
                        'Web-based notifications work without extra libraries'
                    ]
                },
                {
                    'number': 5,
                    'title': 'Configure WiFi and Settings',
                    'description': 'Set network credentials and notification preferences.',
                    'details': [
                        'Update WiFi credentials in code',
                        'Choose notification method:',
                        '  1. Web dashboard (built-in, easiest)',
                        '  2. Email via SMTP',
                        '  3. Pushover app ($5 one-time)',
                        '  4. Telegram bot (free)',
                        '  5. IFTTT webhooks (free)',
                        'Set custom doorbell sound URL if desired',
                        'Configure visitor log settings'
                    ],
                    'time': '10 minutes'
                },
                {
                    'number': 6,
                    'title': 'Upload and Test',
                    'description': 'Flash code and verify button detection.',
                    'details': [
                        'Upload code to ESP8266',
                        'Open Serial Monitor (115200 baud)',
                        'ESP8266 will print IP address',
                        'Press doorbell button',
                        'Verify Serial Monitor shows "Doorbell pressed!"',
                        'Check green LED flashes',
                        'Navigate to ESP8266 IP in browser',
                        'Check web dashboard shows press count'
                    ],
                    'time': '15 minutes',
                    'success_criteria': [
                        '✓ ESP8266 connects to WiFi',
                        '✓ Button press detected',
                        '✓ Serial output correct',
                        '✓ LED flashes on press',
                        '✓ Web dashboard accessible'
                    ]
                },
                {
                    'number': 7,
                    'title': 'Setup Phone Notifications (Optional)',
                    'description': 'Get alerts on your phone when doorbell pressed.',
                    'details': [
                        'Option 1: IFTTT Webhooks (Easiest)',
                        '  - Create free IFTTT account',
                        '  - Create applet: Webhook → Notification',
                        '  - Copy webhook key into code',
                        '  - Test: Press button, get phone notification',
                        'Option 2: Telegram Bot',
                        '  - Chat with @BotFather on Telegram',
                        '  - Create new bot, get API token',
                        '  - Get your chat ID',
                        '  - Update code with token + chat ID',
                        'Option 3: Pushover',
                        '  - Buy Pushover app ($5)',
                        '  - Get user key and API token',
                        '  - Update code, instant push notifications'
                    ],
                    'time': '20-30 minutes',
                    'tips': [
                        'IFTTT is free but has 3-second delay',
                        'Pushover is instant but costs $5',
                        'Telegram is free and reasonably fast'
                    ]
                },
                {
                    'number': 8,
                    'title': 'Add Camera Integration (Advanced)',
                    'description': 'Capture photo of visitor when doorbell pressed.',
                    'details': [
                        'Option 1: ESP32-CAM instead of ESP8266',
                        '  - ESP32-CAM has built-in camera ($10)',
                        '  - Captures photo when button pressed',
                        '  - Sends image via Telegram/email',
                        'Option 2: Trigger external camera',
                        '  - Use relay to trigger USB webcam',
                        '  - Or send command to IP camera',
                        '  - Raspberry Pi for advanced processing',
                        'Option 3: Video doorbell',
                        '  - ESP32-CAM with continuous streaming',
                        '  - View live feed on phone',
                        '  - Two-way audio with microphone'
                    ],
                    'time': '1-2 hours (advanced)',
                    'notes': [
                        'ESP32-CAM requires different code',
                        'Image capture adds 5-10 seconds delay',
                        'Consider privacy implications'
                    ]
                },
                {
                    'number': 9,
                    'title': 'Create Enclosure',
                    'description': 'Weatherproof housing for outdoor installation.',
                    'details': [
                        'Requirements:',
                        '  - Weatherproof IP65 rated',
                        '  - UV resistant plastic',
                        '  - Clear window for status LEDs',
                        '  - Ventilation to prevent condensation',
                        'Options:',
                        '  1. 3D print custom enclosure (STL files available online)',
                        '  2. Use electrical junction box ($5-10)',
                        '  3. Repurpose old doorbell housing',
                        'Include:',
                        '  - Cable gland for wires',
                        '  - Mounting holes for screws',
                        '  - Access to USB port for updates',
                        '  - Label with WiFi network name'
                    ],
                    'time': '30-60 minutes',
                    'tips': [
                        'Test outdoors for 24 hours before permanent install',
                        'Silicone sealant around button prevents water ingress',
                        'Add desiccant packet inside for moisture control'
                    ]
                },
                {
                    'number': 10,
                    'title': 'Install and Fine-Tune',
                    'description': 'Mount doorbell and optimize settings.',
                    'details': [
                        'Installation location:',
                        '  - Standard height: 48 inches from ground',
                        '  - Protected from direct rain if possible',
                        '  - Within WiFi range (test with phone first)',
                        '  - Well-lit for camera if using ESP32-CAM',
                        'Power options:',
                        '  1. USB power adapter (easiest)',
                        '  2. Existing doorbell transformer',
                        '  3. Battery pack (rechargeable)',
                        '  4. Solar panel + battery',
                        'Fine-tuning:',
                        '  - Adjust notification cooldown (prevent spam)',
                        '  - Set quiet hours (no notifications at night)',
                        '  - Test WiFi reliability',
                        '  - Configure backup notifications if WiFi drops'
                    ],
                    'time': '30 minutes',
                    'tips': [
                        'Run cable through existing doorbell hole',
                        'Use outdoor-rated USB cable if needed',
                        'Add UPS battery backup for power outages'
                    ]
                }
            ],

            'total_build_time': '2-3 hours (basic) / 4-5 hours (with camera + notifications)',
            'estimated_cost': '$8.10 (basic) / $18 (with ESP32-CAM)',

            'code_template': '''
/*
 * Smart WiFi Doorbell
 * ESP8266-based doorbell with phone notifications
 *
 * Components:
 * - ESP8266 (NodeMCU or Wemos D1)
 * - Pushbutton (momentary, normally open)
 * - LEDs for status (optional)
 * - Relay for existing chime (optional)
 *
 * Features:
 * - Web dashboard with visitor log
 * - Phone notifications (IFTTT/Telegram/Pushover)
 * - Press counter
 * - Timestamp logging
 * - Optional relay trigger for existing doorbell
 * - Debounced button input
 */

#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClientSecure.h>

// WiFi credentials
const char* ssid = "YOUR_WIFI_NAME";
const char* password = "YOUR_WIFI_PASSWORD";

// Hardware pins
#define BUTTON_PIN D1       // GPIO5
#define LED_WIFI D2         // GPIO4
#define LED_DOORBELL D3     // GPIO0
#define RELAY_PIN D5        // GPIO14 (optional - existing chime)

// Notification settings
#define USE_IFTTT true      // Set to true to enable IFTTT notifications
String ifttt_key = "YOUR_IFTTT_KEY";  // Get from https://ifttt.com/maker_webhooks
String ifttt_event = "doorbell_pressed";

// Doorbell settings
unsigned long lastPressTime = 0;
const unsigned long debounceDelay = 300;    // 300ms debounce
const unsigned long cooldownTime = 3000;    // 3 second cooldown between presses
int pressCount = 0;

ESP8266WebServer server(80);
WiFiClientSecure client;

void setup() {
  Serial.begin(115200);

  // Initialize pins
  pinMode(BUTTON_PIN, INPUT_PULLUP);  // Built-in pull-up
  pinMode(LED_WIFI, OUTPUT);
  pinMode(LED_DOORBELL, OUTPUT);
  pinMode(RELAY_PIN, OUTPUT);

  digitalWrite(RELAY_PIN, LOW);  // Relay OFF initially
  digitalWrite(LED_DOORBELL, LOW);

  // Connect to WiFi
  Serial.println();
  Serial.print("Connecting to WiFi: ");
  Serial.println(ssid);

  WiFi.begin(ssid, password);
  digitalWrite(LED_WIFI, LOW);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    digitalWrite(LED_WIFI, !digitalRead(LED_WIFI));
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println();
    Serial.println("WiFi connected!");
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());
    digitalWrite(LED_WIFI, HIGH);
  } else {
    Serial.println();
    Serial.println("WiFi connection failed!");
    digitalWrite(LED_WIFI, LOW);
  }

  // Setup web server
  server.on("/", handleRoot);
  server.on("/status", handleStatus);
  server.on("/reset", handleReset);
  server.begin();

  Serial.println("Smart Doorbell ready!");
  Serial.println("Press button to test");

  client.setInsecure();  // For HTTPS requests (IFTTT)
}

void loop() {
  server.handleClient();

  // Check button state
  if (digitalRead(BUTTON_PIN) == LOW) {
    unsigned long currentTime = millis();

    // Debounce and cooldown check
    if (currentTime - lastPressTime > cooldownTime) {
      handleDoorbellPress();
      lastPressTime = currentTime;
    }
  }
}

void handleDoorbellPress() {
  Serial.println("🔔 Doorbell pressed!");
  pressCount++;

  // Flash LED
  for (int i = 0; i < 3; i++) {
    digitalWrite(LED_DOORBELL, HIGH);
    delay(100);
    digitalWrite(LED_DOORBELL, LOW);
    delay(100);
  }

  // Trigger existing doorbell chime (if relay installed)
  digitalWrite(RELAY_PIN, HIGH);
  delay(200);  // Brief pulse
  digitalWrite(RELAY_PIN, LOW);

  // Send notification
  if (USE_IFTTT && WiFi.status() == WL_CONNECTED) {
    sendIFTTTNotification();
  }
}

void sendIFTTTNotification() {
  HTTPClient http;
  WiFiClient client;

  String url = "http://maker.ifttt.com/trigger/" + ifttt_event + "/with/key/" + ifttt_key;

  http.begin(client, url);
  http.addHeader("Content-Type", "application/json");

  String payload = "{\\"value1\\":\\"" + String(pressCount) + "\\"}";

  int httpCode = http.POST(payload);

  if (httpCode > 0) {
    Serial.println("Notification sent! Code: " + String(httpCode));
  } else {
    Serial.println("Notification failed: " + http.errorToString(httpCode));
  }

  http.end();
}

void handleRoot() {
  String html = R"=====(
<!DOCTYPE html>
<html>
<head>
  <title>Smart Doorbell</title>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <meta http-equiv='refresh' content='5'>
  <style>
    body {
      font-family: Arial, sans-serif;
      text-align: center;
      padding: 20px;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: white;
    }
    h1 {
      font-size: 48px;
      margin: 20px 0;
    }
    .stat-card {
      background: rgba(255,255,255,0.15);
      border-radius: 15px;
      padding: 30px;
      margin: 20px auto;
      max-width: 400px;
      backdrop-filter: blur(10px);
    }
    .count {
      font-size: 72px;
      font-weight: bold;
      margin: 10px 0;
    }
    .label {
      font-size: 24px;
      color: #ddd;
    }
    .button {
      display: inline-block;
      padding: 15px 30px;
      margin: 10px;
      background: #f44336;
      color: white;
      text-decoration: none;
      border-radius: 8px;
      font-weight: bold;
    }
    .button:active {
      transform: scale(0.95);
    }
    .footer {
      margin-top: 30px;
      font-size: 14px;
      color: #ddd;
    }
  </style>
</head>
<body>
  <h1>🔔 Smart Doorbell</h1>

  <div class='stat-card'>
    <div class='count'>)=====";

  html += String(pressCount);
  html += R"=====(</div>
    <div class='label'>Total Visitors</div>
  </div>

  <div class='stat-card'>
    <div class='label'>WiFi Status</div>
    <div class='count' style='font-size:48px;'>✓</div>
    <div class='label'>Connected</div>
  </div>

  <a href='/reset' class='button'>Reset Counter</a>

  <div class='footer'>
    Built with Circuit-AI<br>
    IP: )=====";
  html += WiFi.localIP().toString();
  html += R"=====(
  </div>
</body>
</html>
)=====";

  server.send(200, "text/html", html);
}

void handleStatus() {
  String json = "{";
  json += "\\"press_count\\":" + String(pressCount) + ",";
  json += "\\"wifi\\":\\"connected\\",";
  json += "\\"ip\\":\\"" + WiFi.localIP().toString() + "\\"";
  json += "}";

  server.send(200, "application/json", json);
}

void handleReset() {
  pressCount = 0;
  Serial.println("Counter reset");
  server.sendHeader("Location", "/");
  server.send(303);
}
''',

            'business_notes': {
                'marketability': 'EXTREMELY HIGH - Everyone with a home needs a doorbell',
                'target_audience': 'Homeowners, renters, parents, security-conscious individuals, tech enthusiasts',
                'upsell_opportunities': [
                    'Camera version (ESP32-CAM) - add $10, sell for +$30',
                    'Battery-powered version with solar panel - add $15, sell for +$35',
                    'Multi-chime system (multiple indoor chimes) - add $8 each, sell for +$25',
                    'Video doorbell with two-way audio - add $25, sell for +$80',
                    'Professional installation service - charge $40-60',
                    'Smart home integration package (Alexa/Google) - add $15 value'
                ],
                'manufacturing_notes': [
                    'Weatherproof enclosures in bulk: $2-3 each at qty 50',
                    'Custom PCB reduces assembly time significantly',
                    'Pre-flash firmware with QR code for WiFi setup',
                    'Offer kit and assembled versions at different price points',
                    'Consider CE/FCC certification for commercial sales',
                    'Partner with doorbell button manufacturers for bulk pricing'
                ],
                'competitive_advantages': [
                    'Ring Doorbell costs $100-150 PLUS monthly subscription',
                    'Your doorbell: $25-40 one-time, NO subscription',
                    '85-90% cheaper than commercial alternatives',
                    'No cloud dependency - works offline',
                    'Fully customizable firmware',
                    'Works with existing doorbell chime',
                    'Open source - community support',
                    'Privacy-focused - data stays on device'
                ]
            },

            'next_steps': [
                'Build and test indoors for 1 week',
                'Test outdoors in various weather conditions',
                'Design professional 3D-printed enclosure',
                'Create step-by-step installation video',
                'Write detailed user manual with FAQ',
                'Add multiple notification methods (Telegram, Pushover, email)',
                'Implement web-based initial setup wizard',
                'Create smartphone app for advanced features',
                'Add visitor face detection with ESP32-CAM',
                'List on Etsy with multiple configuration options',
                'Offer installation service for local customers ($40-60)'
            ],

            'safety_notes': [
                'Low voltage (5V) but still follow electrical safety practices',
                'Ensure weatherproof sealing for outdoor installations',
                'Use outdoor-rated cables and connectors',
                'Test WiFi range before permanent installation',
                'Include backup notification method if WiFi fails',
                'Clearly label if connecting to existing doorbell transformer',
                'Add surge protection if using existing doorbell power',
                'Consider battery backup for power outages',
                'Include privacy notice if using camera',
                'Follow local regulations for outdoor electronics'
            ]
        }

    def _generate_energy_monitor_instructions(self) -> Dict:
        """Instructions for Energy Monitor (ESP32 + SCT-013 Current Sensor)"""
        return {
            'project_name': 'Energy Monitor',
            'difficulty': 'hard',
            'build_time': '4-5 hours',
            'skill_level': 'Advanced',
            'tools_needed': [
                'Soldering iron and solder',
                'Wire strippers',
                'Multimeter',
                'Screwdriver',
                'Breadboard (for prototyping)',
                'Electrical tape',
                'Heat shrink tubing (optional)',
                '3.5mm audio jack breakout (or DIY)'
            ],
            'components': [
                {'name': 'ESP32 Development Board', 'quantity': 1, 'cost': 8.0, 'where_to_buy': 'AliExpress, Amazon'},
                {'name': 'SCT-013 30A Non-Invasive Current Sensor', 'quantity': 1, 'cost': 7.0, 'where_to_buy': 'Amazon, eBay'},
                {'name': '10kΩ Resistor', 'quantity': 2, 'cost': 0.1, 'where_to_buy': 'Amazon, Local electronics'},
                {'name': '10µF Capacitor', 'quantity': 1, 'cost': 0.1, 'where_to_buy': 'Amazon, Local electronics'},
                {'name': '3.5mm Audio Jack', 'quantity': 1, 'cost': 0.5, 'where_to_buy': 'Amazon, Local electronics'},
                {'name': 'Micro USB Cable', 'quantity': 1, 'cost': 2.0, 'where_to_buy': 'Amazon, Local electronics'},
                {'name': 'Enclosure (optional)', 'quantity': 1, 'cost': 3.0, 'where_to_buy': 'Amazon, 3D print'}
            ],
            'market_analysis': {
                'build_cost': 20.7,
                'market_price_low': 35.0,
                'market_price_high': 65.0,
                'profit_margin': '69-214%',
                'comparable_products': [
                    'Kill A Watt P3 - $40-50',
                    'Emporia Vue - $50-80',
                    'Sense Energy Monitor - $299',
                    'IoTaWatt - $150'
                ]
            },
            'steps': [
                {
                    'number': 1,
                    'title': 'Understanding the Current Sensor',
                    'description': 'The SCT-013 is a non-invasive current transformer (CT) that clamps around a live wire without cutting it. It outputs a small AC voltage proportional to the current flowing through the wire. We will convert this to a safe DC voltage for the ESP32.',
                    'time': '5 minutes',
                    'components': ['SCT-013 sensor'],
                    'warnings': [
                        '⚠️ DANGER: Working with AC mains voltage (120V/220V) can be LETHAL',
                        '⚠️ Only clamp sensor around ONE wire (hot OR neutral, not both)',
                        '⚠️ Turn off circuit breaker before accessing main panel',
                        '⚠️ If unsure, hire a licensed electrician',
                        '⚠️ The sensor itself is safe, but installation requires care'
                    ]
                },
                {
                    'number': 2,
                    'title': 'Build Voltage Divider Circuit',
                    'description': 'The SCT-013 outputs 0-1V AC. We need to bias this to 1.65V DC (half of 3.3V) so the ESP32 ADC can read both positive and negative swings. Build a voltage divider with two 10kΩ resistors to create 1.65V reference, then add the AC signal on top.',
                    'time': '15 minutes',
                    'components': ['2x 10kΩ resistors', '10µF capacitor', 'Breadboard'],
                    'wiring': [
                        '1. ESP32 3.3V → First 10kΩ resistor',
                        '2. First 10kΩ resistor → Junction (this is 1.65V reference)',
                        '3. Junction → Second 10kΩ resistor → ESP32 GND',
                        '4. Junction → 10µF capacitor → 3.5mm jack tip (SCT-013 signal)',
                        '5. 3.5mm jack sleeve (SCT-013 ground) → ESP32 GND',
                        '6. Junction → ESP32 GPIO34 (ADC1_CH6)'
                    ],
                    'tips': [
                        'Use a breadboard first to test before soldering',
                        'Capacitor blocks DC, passes AC signal',
                        'GPIO34 is a good ADC pin on ESP32',
                        'Double-check resistor values with multimeter'
                    ]
                },
                {
                    'number': 3,
                    'title': 'Connect SCT-013 Sensor',
                    'description': 'Plug the SCT-013 into the 3.5mm audio jack. Verify connections with multimeter - you should see ~1.65V on GPIO34 with no load.',
                    'time': '5 minutes',
                    'components': ['SCT-013 sensor', '3.5mm jack'],
                    'tips': [
                        'SCT-013 has a 3.5mm plug output (some models)',
                        'Polarity does not matter for AC measurement',
                        'Test voltage should be stable at 1.65V'
                    ]
                },
                {
                    'number': 4,
                    'title': 'Upload Calibration Sketch',
                    'description': 'Before full code, upload a simple sketch to read ADC values and verify the sensor is working. Open Arduino IDE, select ESP32 board, and upload the test code.',
                    'time': '10 minutes',
                    'components': ['ESP32', 'USB cable', 'Computer'],
                    'code_snippet': '''
// Simple ADC test
void setup() {
  Serial.begin(115200);
}

void loop() {
  int adc = analogRead(34);
  float voltage = adc * (3.3 / 4095.0);
  Serial.print("ADC: ");
  Serial.print(adc);
  Serial.print(" Voltage: ");
  Serial.println(voltage);
  delay(100);
}
''',
                    'tips': [
                        'Install ESP32 board support in Arduino IDE',
                        'Select "ESP32 Dev Module" as board',
                        'Check serial monitor at 115200 baud',
                        'Should see ADC ~2048 and voltage ~1.65V with no load'
                    ]
                },
                {
                    'number': 5,
                    'title': 'Install Required Libraries',
                    'description': 'Install necessary libraries for WiFi and web server functionality.',
                    'time': '5 minutes',
                    'components': ['Computer with Arduino IDE'],
                    'tips': [
                        'WiFi library is built-in for ESP32',
                        'WebServer library is built-in',
                        'No external libraries needed'
                    ]
                },
                {
                    'number': 6,
                    'title': 'Upload Main Energy Monitor Code',
                    'description': 'Upload the complete energy monitoring code that calculates RMS current, power, and energy consumption over time. Configure WiFi credentials in the code.',
                    'time': '10 minutes',
                    'components': ['ESP32', 'Computer'],
                    'tips': [
                        'Update WiFi SSID and password in code',
                        'Calibration value may need adjustment',
                        'Code calculates true RMS current',
                        'Power = Voltage * Current (assuming power factor ~1)'
                    ]
                },
                {
                    'number': 7,
                    'title': 'Install Current Sensor on Wire',
                    'description': '⚠️ DANGER STEP - Turn off circuit breaker. Open main panel (or appliance cord). Identify the HOT wire (usually black). Clamp SCT-013 around ONLY the hot wire. Close panel. Turn breaker back on.',
                    'time': '20 minutes',
                    'components': ['SCT-013 installed'],
                    'warnings': [
                        '⚠️ TURN OFF CIRCUIT BREAKER FIRST',
                        '⚠️ Use voltage tester to confirm power is OFF',
                        '⚠️ Clamp around ONE wire only (hot wire)',
                        '⚠️ Do not clamp around both hot and neutral (will read 0)',
                        '⚠️ Ensure sensor is fully closed (clicks shut)',
                        '⚠️ If measuring an appliance, you can clamp around the cord externally',
                        '⚠️ Never open a live panel without proper training'
                    ],
                    'tips': [
                        'For testing, use a desk lamp or space heater cord (safer)',
                        'Can clamp around extension cord',
                        'Direction of clamp may affect positive/negative reading (does not matter for RMS)',
                        'Ensure 3.5mm cable has slack, will not pull loose'
                    ]
                },
                {
                    'number': 8,
                    'title': 'Calibrate the Sensor',
                    'description': 'With a known load (e.g., 100W light bulb), check the readings. US 120V system: 100W / 120V = 0.833A. Adjust calibration constant in code until readings match.',
                    'time': '15 minutes',
                    'components': ['Known wattage appliance (e.g., 60W or 100W bulb)'],
                    'tips': [
                        'SCT-013-030 has 30A max, outputs 1V at 30A',
                        'Calibration = (30A / 1V) * (3.3V / 4095 ADC)',
                        'Typical value ~0.0242',
                        'Fine-tune by comparing to Kill-A-Watt meter if available'
                    ]
                },
                {
                    'number': 9,
                    'title': 'Access Web Dashboard',
                    'description': 'Connect to ESP32 WiFi network or note its IP address from serial monitor. Open browser and go to http://[ESP32_IP]. You should see real-time current, power, and cumulative energy.',
                    'time': '5 minutes',
                    'components': ['Smartphone or computer with browser'],
                    'tips': [
                        'Dashboard auto-refreshes every 2 seconds',
                        'Energy resets when ESP32 reboots',
                        'Can log data to SD card or cloud for persistence (advanced)'
                    ]
                },
                {
                    'number': 10,
                    'title': 'Mount and Finalize',
                    'description': 'Place ESP32 in enclosure. Secure sensor to wire with zip ties. Route cables neatly. Add labels. Optionally power ESP32 from a phone charger for standalone operation.',
                    'time': '20 minutes',
                    'components': ['Enclosure', 'Zip ties', 'Labels'],
                    'tips': [
                        '3D print an enclosure or use project box',
                        'Ensure ventilation for ESP32 heat',
                        'Use cable management for clean install',
                        'Consider battery backup (power bank) for data continuity'
                    ]
                },
                {
                    'number': 11,
                    'title': 'Test and Monitor',
                    'description': 'Turn on various appliances and watch real-time updates. Verify readings make sense (e.g., hair dryer = 1200-1800W, LED bulb = 10-15W). Monitor for 24 hours to validate stability.',
                    'time': '1-24 hours',
                    'components': ['Various appliances'],
                    'tips': [
                        'Compare to appliance rated power (usually within 10-20%)',
                        'Power factor can cause discrepancies for motors/transformers',
                        'Energy accumulation should be consistent over time'
                    ]
                }
            ],
            'total_build_time': '4-5 hours (plus 24hr testing)',
            'estimated_cost': '$20.70',
            'code_template': '''
/*
 * ESP32 Energy Monitor with SCT-013 Current Sensor
 * Real-time home electricity monitoring
 * Non-invasive installation
 */

#include <WiFi.h>
#include <WebServer.h>

// WiFi credentials
const char* ssid = "YourWiFiSSID";
const char* password = "YourWiFiPassword";

// Hardware pins
const int CURRENT_SENSOR_PIN = 34;  // ADC1_CH6

// Calibration (adjust after testing)
const float VOLTAGE = 120.0;  // US standard (use 220.0 for EU)
const float CALIBRATION = 30.0;  // 30A / 1V for SCT-013-030

// Energy tracking
float totalEnergy = 0.0;  // kWh
unsigned long lastTime = 0;

WebServer server(80);

void setup() {
  Serial.begin(115200);

  // Configure ADC
  analogReadResolution(12);  // 12-bit resolution (0-4095)
  analogSetAttenuation(ADC_11db);  // 0-3.3V range

  // Connect to WiFi
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  Serial.println("WiFi connected!");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());

  // Setup web server
  server.on("/", handleRoot);
  server.on("/data", handleData);
  server.begin();
  Serial.println("Web server started");

  lastTime = millis();
}

void loop() {
  server.handleClient();

  // Calculate energy every second
  unsigned long currentTime = millis();
  if (currentTime - lastTime >= 1000) {
    float current = readCurrent();
    float power = VOLTAGE * current;  // Watts
    float energyIncrement = (power / 1000.0) * ((currentTime - lastTime) / 3600000.0);  // kWh
    totalEnergy += energyIncrement;
    lastTime = currentTime;

    // Debug output
    Serial.print("Current: ");
    Serial.print(current, 2);
    Serial.print(" A, Power: ");
    Serial.print(power, 1);
    Serial.print(" W, Energy: ");
    Serial.print(totalEnergy, 4);
    Serial.println(" kWh");
  }
}

float readCurrent() {
  const int numSamples = 1000;
  unsigned long sum = 0;

  // Read samples over ~1 AC cycle (60Hz = 16.7ms, 50Hz = 20ms)
  for (int i = 0; i < numSamples; i++) {
    int adc = analogRead(CURRENT_SENSOR_PIN);
    // Remove DC bias (1.65V = 2048 at 12-bit)
    int centered = adc - 2048;
    sum += (unsigned long)(centered * centered);
  }

  // Calculate RMS
  float rms = sqrt(sum / (float)numSamples);

  // Convert to current
  float voltage = rms * (3.3 / 4095.0);  // ADC to voltage
  float current = voltage * CALIBRATION;  // Voltage to current

  return current;
}

void handleRoot() {
  float current = readCurrent();
  float power = VOLTAGE * current;

  String html = "<!DOCTYPE html><html><head>";
  html += "<meta charset='UTF-8'>";
  html += "<meta name='viewport' content='width=device-width, initial-scale=1.0'>";
  html += "<title>Energy Monitor</title>";
  html += "<style>";
  html += "body { font-family: Arial; text-align: center; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; }";
  html += ".container { max-width: 600px; margin: 0 auto; background: rgba(255,255,255,0.1); border-radius: 15px; padding: 30px; }";
  html += "h1 { font-size: 2.5em; margin-bottom: 10px; }";
  html += ".metric { background: rgba(255,255,255,0.2); border-radius: 10px; padding: 20px; margin: 15px 0; }";
  html += ".value { font-size: 3em; font-weight: bold; margin: 10px 0; }";
  html += ".unit { font-size: 1.2em; opacity: 0.8; }";
  html += ".label { font-size: 1.5em; margin-bottom: 10px; }";
  html += "</style>";
  html += "<script>";
  html += "setInterval(function() { location.reload(); }, 2000);";  // Auto-refresh every 2 seconds
  html += "</script>";
  html += "</head><body>";
  html += "<div class='container'>";
  html += "<h1>⚡ Energy Monitor</h1>";

  html += "<div class='metric'>";
  html += "<div class='label'>Current</div>";
  html += "<div class='value'>" + String(current, 2) + "</div>";
  html += "<div class='unit'>Amps</div>";
  html += "</div>";

  html += "<div class='metric'>";
  html += "<div class='label'>Power</div>";
  html += "<div class='value'>" + String(power, 0) + "</div>";
  html += "<div class='unit'>Watts</div>";
  html += "</div>";

  html += "<div class='metric'>";
  html += "<div class='label'>Total Energy</div>";
  html += "<div class='value'>" + String(totalEnergy, 3) + "</div>";
  html += "<div class='unit'>kWh</div>";
  html += "</div>";

  html += "<p style='opacity:0.6; margin-top:30px;'>IP: " + WiFi.localIP().toString() + "</p>";
  html += "</div></body></html>";

  server.send(200, "text/html", html);
}

void handleData() {
  float current = readCurrent();
  float power = VOLTAGE * current;

  String json = "{";
  json += "\\"current\\":" + String(current, 2) + ",";
  json += "\\"power\\":" + String(power, 1) + ",";
  json += "\\"energy\\":" + String(totalEnergy, 4);
  json += "}";

  server.send(200, "application/json", json);
}
''',
            'business_notes': {
                'marketability': 'HIGH - Rising energy costs make this very attractive. Commercial solutions are $100-300. Your $35-65 version offers 70-80% savings. Huge market: homeowners, renters, small businesses.',
                'target_audience': 'Eco-conscious homeowners, DIY enthusiasts, energy-conscious renters, electricians, energy auditors',
                'upsell_opportunities': [
                    'Multi-channel version (monitor multiple circuits) - add $15/channel, sell for +$30/channel',
                    'Cloud logging with historical graphs (Firebase/ThingSpeak) - add $0, sell for +$20',
                    'Solar panel monitoring mode - add $5, sell for +$35',
                    'Integration with Home Assistant/MQTT - add $0, sell for +$15',
                    'Battery backup with real-time clock - add $8, sell for +$25',
                    'Professional installation service - charge $50-100'
                ],
                'manufacturing_notes': [
                    'Design custom PCB for bias circuit (costs $2, looks professional)',
                    'Use screw terminals for easy sensor connection',
                    '3D print enclosure with DIN rail mount for electrical panels',
                    'Include calibration certificate for professional credibility',
                    'Pre-program with default WiFi or AP mode for easy setup'
                ],
                'competitive_advantages': [
                    'Kill A Watt measures only plug-in devices ($45), yours measures whole house',
                    'Sense Energy Monitor is $299 + pro install, yours is $40-65 DIY',
                    'Open source - can be customized and expanded',
                    'No monthly fees or cloud dependence',
                    'Real-time web interface accessible on local network',
                    'Educational value - learn about electricity and electronics'
                ]
            },
            'next_steps': [
                'Add data logging to SD card for long-term analysis',
                'Integrate with Home Assistant via MQTT',
                'Add cost calculation based on local electricity rates',
                'Create mobile app for better UX',
                'Add alerts for high usage (email/SMS)',
                'Support multiple sensors for whole-home monitoring',
                'Add solar panel monitoring (bidirectional current)',
                'Battery backup with RTC to preserve energy totals during outages'
            ],
            'safety_notes': [
                '⚠️ DANGER: Working with AC mains (120V/220V) can be LETHAL - turn off breakers first',
                '⚠️ Hire licensed electrician if you are not trained to open electrical panels',
                '⚠️ The sensor itself is non-invasive and safe - installation is the risk',
                '⚠️ Always use a voltage tester to confirm power is OFF before opening panels',
                '⚠️ Clamp sensor around ONE wire only (hot wire), not both hot and neutral',
                '⚠️ Ensure sensor is fully closed (clicks) for accurate readings and safety',
                '⚠️ For beginners: test on an appliance cord or extension cord first (much safer)',
                '⚠️ Never work alone when accessing electrical panels',
                '⚠️ Follow all local electrical codes and regulations',
                '⚠️ Consider liability insurance if selling to others',
                '⚠️ Include comprehensive safety warnings in product documentation'
            ]
        }

    def _generate_soil_moisture_instructions(self) -> Dict:
        """Instructions for Soil Moisture Monitor (Arduino Nano + Capacitive Sensor)"""
        return {
            'project_name': 'Soil Moisture Monitor',
            'difficulty': 'easy',
            'build_time': '1-2 hours',
            'skill_level': 'Beginner',
            'tools_needed': [
                'Soldering iron (optional)',
                'Screwdriver',
                'Wire strippers (optional)',
                'USB cable for programming'
            ],
            'components': [
                {'name': 'Arduino Nano', 'quantity': 1, 'cost': 3.0, 'where_to_buy': 'AliExpress, Amazon'},
                {'name': 'Capacitive Soil Moisture Sensor v1.2', 'quantity': 1, 'cost': 4.0, 'where_to_buy': 'Amazon, eBay'},
                {'name': 'LED (Red)', 'quantity': 1, 'cost': 0.1, 'where_to_buy': 'Amazon, Local electronics'},
                {'name': 'LED (Yellow)', 'quantity': 1, 'cost': 0.1, 'where_to_buy': 'Amazon, Local electronics'},
                {'name': 'LED (Green)', 'quantity': 1, 'cost': 0.1, 'where_to_buy': 'Amazon, Local electronics'},
                {'name': '220Ω Resistor', 'quantity': 3, 'cost': 0.15, 'where_to_buy': 'Amazon, Local electronics'},
                {'name': 'Buzzer (optional)', 'quantity': 1, 'cost': 1.0, 'where_to_buy': 'Amazon, Local electronics'},
                {'name': 'Mini USB Cable', 'quantity': 1, 'cost': 1.5, 'where_to_buy': 'Amazon'},
                {'name': 'Jumper wires', 'quantity': 5, 'cost': 0.5, 'where_to_buy': 'Amazon'}
            ],
            'market_analysis': {
                'build_cost': 10.45,
                'market_price_low': 12.0,
                'market_price_high': 24.0,
                'profit_margin': '15-130%',
                'comparable_products': [
                    'Xiaomi Mi Flora - $15-25',
                    'XLUX Soil Moisture Meter - $10-15',
                    'Generic Arduino Soil Sensor - $12-18'
                ]
            },
            'steps': [
                {
                    'number': 1,
                    'title': 'Understand the Capacitive Sensor',
                    'description': 'Capacitive soil moisture sensors measure the dielectric constant of soil, which changes with water content. Unlike resistive sensors, they do not corrode. The sensor outputs an analog voltage (0-3V) proportional to moisture level.',
                    'time': '5 minutes',
                    'components': ['Capacitive sensor'],
                    'tips': [
                        'Capacitive sensors last much longer than resistive types',
                        'Do not submerge the electronics part, only the prongs',
                        'Sensor needs calibration for different soil types'
                    ]
                },
                {
                    'number': 2,
                    'title': 'Wire the Sensor to Arduino',
                    'description': 'Connect the capacitive sensor to the Arduino Nano. Sensor has 3 pins: VCC (red), GND (black), and AOUT (yellow/blue).',
                    'time': '10 minutes',
                    'components': ['Arduino Nano', 'Capacitive sensor', 'Jumper wires'],
                    'wiring': [
                        '1. Sensor VCC (red) → Arduino 5V',
                        '2. Sensor GND (black) → Arduino GND',
                        '3. Sensor AOUT (analog output) → Arduino A0'
                    ],
                    'tips': [
                        'Use jumper wires or solder for permanent connections',
                        'Double-check polarity - reversed power can damage sensor',
                        'Keep wiring neat for reliability'
                    ]
                },
                {
                    'number': 3,
                    'title': 'Add LED Indicators',
                    'description': 'Wire 3 LEDs (red, yellow, green) to indicate moisture levels: red = dry, yellow = moderate, green = wet. Each LED needs a 220Ω current-limiting resistor.',
                    'time': '15 minutes',
                    'components': ['3x LEDs', '3x 220Ω resistors'],
                    'wiring': [
                        '1. Red LED anode (+) → 220Ω resistor → Arduino D2',
                        '2. Red LED cathode (-) → Arduino GND',
                        '3. Yellow LED anode → 220Ω resistor → Arduino D3',
                        '4. Yellow LED cathode → Arduino GND',
                        '5. Green LED anode → 220Ω resistor → Arduino D4',
                        '6. Green LED cathode → Arduino GND'
                    ],
                    'tips': [
                        'LED longer leg is anode (+), shorter is cathode (-)',
                        'Resistor can go on either side of LED',
                        'Test each LED individually if unsure'
                    ]
                },
                {
                    'number': 4,
                    'title': 'Optional: Add Buzzer Alert',
                    'description': 'Connect a buzzer to alert when soil is too dry. Buzzer will beep when red LED is on.',
                    'time': '5 minutes',
                    'components': ['Buzzer (optional)'],
                    'wiring': [
                        '1. Buzzer positive (+) → Arduino D5',
                        '2. Buzzer negative (-) → Arduino GND'
                    ],
                    'tips': [
                        'Active buzzer = just apply voltage, passive = needs tone signal',
                        'Code uses tone() function for melodic alert',
                        'Can be disabled in code if too annoying'
                    ]
                },
                {
                    'number': 5,
                    'title': 'Upload Calibration Sketch',
                    'description': 'Before uploading the main code, run a calibration sketch to determine dry and wet values for your specific sensor and soil type.',
                    'time': '10 minutes',
                    'components': ['Arduino with sensor connected'],
                    'code_snippet': '''
// Calibration sketch
void setup() {
  Serial.begin(9600);
}

void loop() {
  int value = analogRead(A0);
  Serial.print("Sensor value: ");
  Serial.println(value);
  delay(1000);
}
// 1. Place sensor in DRY soil, note value (typically 500-700)
// 2. Water soil thoroughly, note WET value (typically 250-350)
''',
                    'tips': [
                        'Test in actual soil, not water (different readings)',
                        'Dry value = sensor in air or dry soil',
                        'Wet value = sensor in saturated soil',
                        'Write down these values for main code'
                    ]
                },
                {
                    'number': 6,
                    'title': 'Upload Main Code',
                    'description': 'Upload the complete moisture monitoring code with your calibration values. Code will display moisture level via LEDs and optional buzzer alert.',
                    'time': '10 minutes',
                    'components': ['Computer with Arduino IDE'],
                    'tips': [
                        'Update DRY_VALUE and WET_VALUE in code with your calibration',
                        'Select "Arduino Nano" and correct COM port in IDE',
                        'If upload fails, try "Old Bootloader" processor option',
                        'Serial monitor shows real-time moisture percentage'
                    ]
                },
                {
                    'number': 7,
                    'title': 'Test the System',
                    'description': 'Insert sensor into plant soil. Observe LED indicators. Test by watering plant and watching LEDs change from red → yellow → green.',
                    'time': '15 minutes',
                    'components': ['Potted plant'],
                    'tips': [
                        'Allow 2-3 minutes after watering for reading to stabilize',
                        'Sensor should be inserted 2-3 inches deep',
                        'Do not leave sensor in soil when not in use (corrosion)',
                        'For multiple plants, use multiple sensors'
                    ]
                },
                {
                    'number': 8,
                    'title': 'Power Options',
                    'description': 'Choose power source: USB power bank for portable, USB wall adapter for permanent installation, or 9V battery with barrel jack.',
                    'time': '5 minutes',
                    'components': ['Power source of choice'],
                    'tips': [
                        'USB power bank = 1-2 weeks runtime',
                        'Wall adapter = permanent installation',
                        '9V battery = 1-2 days only (not recommended)',
                        'Solar panel + rechargeable battery = best for outdoor'
                    ]
                },
                {
                    'number': 9,
                    'title': 'Enclosure and Mounting',
                    'description': 'Place Arduino and LEDs in weatherproof enclosure if used outdoors. Mount near plant pot or in garden.',
                    'time': '10 minutes',
                    'components': ['Enclosure (optional)'],
                    'tips': [
                        'Drill holes for sensor cable and LEDs',
                        'Use hot glue to secure LEDs in holes',
                        'Silicone sealant for waterproofing',
                        'Label LEDs: red = WATER ME, green = OK'
                    ]
                },
                {
                    'number': 10,
                    'title': 'Usage and Maintenance',
                    'description': 'Check the LEDs daily or enable buzzer alerts. Water when red LED illuminates. Clean sensor monthly with soft cloth.',
                    'time': 'Ongoing',
                    'components': ['Completed system'],
                    'tips': [
                        'Sensor accuracy degrades if left in soil 24/7',
                        'Remove and clean every 2-4 weeks',
                        'Recalibrate if readings seem off',
                        'Consider multiple sensors for garden monitoring'
                    ]
                }
            ],
            'total_build_time': '1-2 hours',
            'estimated_cost': '$10.45',
            'code_template': '''
/*
 * Soil Moisture Monitor
 * Displays moisture level with 3 LEDs
 * Optional buzzer alert when dry
 */

// Calibration values (UPDATE THESE)
const int DRY_VALUE = 600;   // Sensor value in dry soil
const int WET_VALUE = 300;   // Sensor value in wet soil

// Hardware pins
const int MOISTURE_PIN = A0;
const int RED_LED = 2;
const int YELLOW_LED = 3;
const int GREEN_LED = 4;
const int BUZZER = 5;  // Optional

void setup() {
  Serial.begin(9600);

  pinMode(RED_LED, OUTPUT);
  pinMode(YELLOW_LED, OUTPUT);
  pinMode(GREEN_LED, OUTPUT);
  pinMode(BUZZER, OUTPUT);

  Serial.println("Soil Moisture Monitor Started");
  Serial.print("Dry value: ");
  Serial.println(DRY_VALUE);
  Serial.print("Wet value: ");
  Serial.println(WET_VALUE);
}

void loop() {
  int sensorValue = analogRead(MOISTURE_PIN);

  // Convert to percentage (0% = dry, 100% = wet)
  int moisture = map(sensorValue, DRY_VALUE, WET_VALUE, 0, 100);
  moisture = constrain(moisture, 0, 100);

  // Print to serial
  Serial.print("Sensor: ");
  Serial.print(sensorValue);
  Serial.print(" | Moisture: ");
  Serial.print(moisture);
  Serial.println("%");

  // Turn off all LEDs
  digitalWrite(RED_LED, LOW);
  digitalWrite(YELLOW_LED, LOW);
  digitalWrite(GREEN_LED, LOW);
  noTone(BUZZER);

  // Set LEDs based on moisture level
  if (moisture < 30) {
    // DRY - Water needed
    digitalWrite(RED_LED, HIGH);
    // Alert every 10 seconds
    tone(BUZZER, 1000, 200);  // 1kHz beep for 200ms
  }
  else if (moisture < 60) {
    // MODERATE - OK for now
    digitalWrite(YELLOW_LED, HIGH);
  }
  else {
    // WET - Good moisture
    digitalWrite(GREEN_LED, HIGH);
  }

  delay(2000);  // Check every 2 seconds
}
''',
            'business_notes': {
                'marketability': 'MEDIUM - Simple product but competitive market. Best sold as part of smart home garden system or multi-sensor package.',
                'target_audience': 'Indoor plant enthusiasts, gardeners, greenhouse operators, forgetful plant owners',
                'upsell_opportunities': [
                    'WiFi version with app notifications (ESP8266) - add $5, sell for +$15',
                    'Multi-plant monitor (4-8 sensors) - add $15, sell for +$40',
                    'Solar powered outdoor version - add $10, sell for +$25',
                    'Auto-watering system integration (add pump) - add $15, sell for +$50',
                    'Data logging with SD card - add $3, sell for +$15',
                    'Custom enclosure with plant identification labels - add $2, sell for +$10'
                ],
                'manufacturing_notes': [
                    'Solder all connections for reliability',
                    'Use heat shrink tubing on sensor connections',
                    'Pre-calibrate for common potting soil',
                    'Include calibration instructions card',
                    'Package with small potted plant as gift set'
                ],
                'competitive_advantages': [
                    'Much cheaper than Xiaomi Mi Flora ($25)',
                    'No app/Bluetooth required - instant visual feedback',
                    'Capacitive sensor = long lifespan vs. resistive',
                    'Customizable thresholds for different plants',
                    'Educational - teaches electronics and plant care'
                ]
            },
            'next_steps': [
                'Add WiFi (ESP8266) for smartphone notifications',
                'Multiple sensors for garden-wide monitoring',
                'Integration with automatic watering pump',
                'Temperature and light sensors for complete plant health',
                'Data logging to track watering history',
                'OLED display showing moisture percentage',
                'Solar panel for outdoor/remote installations'
            ],
            'safety_notes': [
                'Low voltage (5V) - very safe',
                'Do not submerge Arduino or electronics in water',
                'Only sensor prongs should touch soil',
                'Ensure good insulation if used outdoors',
                'Buzzer can be loud - disable if annoying',
                'Sensor is not food-safe - for ornamental plants only'
            ]
        }

    def _generate_door_alarm_instructions(self) -> Dict:
        """Instructions for Door Open Alarm (Arduino Nano + Reed Switch + Buzzer)"""
        return {
            'project_name': 'Door Open Alarm',
            'difficulty': 'easy',
            'build_time': '1-2 hours',
            'skill_level': 'Beginner',
            'tools_needed': [
                'Soldering iron (optional)',
                'Screwdriver',
                'Drill (for mounting)',
                'Double-sided tape or screws'
            ],
            'components': [
                {'name': 'Arduino Nano', 'quantity': 1, 'cost': 3.0, 'where_to_buy': 'AliExpress, Amazon'},
                {'name': 'Reed Switch (magnetic door sensor)', 'quantity': 1, 'cost': 1.5, 'where_to_buy': 'Amazon, eBay'},
                {'name': 'Buzzer (active or passive)', 'quantity': 1, 'cost': 1.0, 'where_to_buy': 'Amazon'},
                {'name': 'LED (Red)', 'quantity': 1, 'cost': 0.1, 'where_to_buy': 'Amazon'},
                {'name': '220Ω Resistor', 'quantity': 1, 'cost': 0.05, 'where_to_buy': 'Amazon'},
                {'name': '9V Battery + Connector', 'quantity': 1, 'cost': 3.0, 'where_to_buy': 'Amazon'},
                {'name': 'Small project box', 'quantity': 1, 'cost': 2.0, 'where_to_buy': 'Amazon'},
                {'name': 'Jumper wires', 'quantity': 5, 'cost': 0.5, 'where_to_buy': 'Amazon'}
            ],
            'market_analysis': {
                'build_cost': 11.15,
                'market_price_low': 15.0,
                'market_price_high': 35.0,
                'profit_margin': '35-214%',
                'comparable_products': [
                    'GE Personal Security Window/Door Alarm - $8-12 (single unit)',
                    'SABRE Door Alarm - $15-20',
                    'Doberman Security Door Alarm - $10-18',
                    'Ring Contact Sensor - $20 (requires hub)'
                ]
            },
            'steps': [
                {
                    'number': 1,
                    'title': 'Understand Reed Switch Operation',
                    'description': 'A reed switch is a magnetic sensor with two metal contacts in a glass tube. When a magnet approaches, contacts close (completing circuit). When magnet moves away, contacts open. Perfect for detecting door/window opening.',
                    'time': '5 minutes',
                    'components': ['Reed switch'],
                    'tips': [
                        'Reed switch = sensor on door frame',
                        'Magnet = attached to door itself',
                        'Gap of 1-2cm maximum for reliable operation',
                        'Test with multimeter in continuity mode'
                    ]
                },
                {
                    'number': 2,
                    'title': 'Wire Reed Switch to Arduino',
                    'description': 'Connect reed switch between Arduino digital pin and ground. Use internal pull-up resistor to detect open/closed state.',
                    'time': '10 minutes',
                    'components': ['Arduino Nano', 'Reed switch', 'Jumper wires'],
                    'wiring': [
                        '1. Reed switch terminal 1 → Arduino D2',
                        '2. Reed switch terminal 2 → Arduino GND',
                        '3. (Internal pull-up resistor enabled in code)'
                    ],
                    'tips': [
                        'Reed switch has no polarity - either way works',
                        'INPUT_PULLUP mode: LOW when closed, HIGH when open',
                        'Can extend wires if needed for door installation',
                        'Use shielded cable for long runs to prevent false triggers'
                    ]
                },
                {
                    'number': 3,
                    'title': 'Add Buzzer and LED',
                    'description': 'Connect buzzer for audio alarm and LED for visual indicator.',
                    'time': '10 minutes',
                    'components': ['Buzzer', 'LED', '220Ω resistor'],
                    'wiring': [
                        '1. Buzzer positive (+) → Arduino D3',
                        '2. Buzzer negative (-) → Arduino GND',
                        '3. LED anode (+) → 220Ω resistor → Arduino D4',
                        '4. LED cathode (-) → Arduino GND'
                    ],
                    'tips': [
                        'Active buzzer = simpler, passive = more tones',
                        'Code uses tone() for siren effect',
                        'LED indicates system armed/triggered',
                        'Buzzer can be loud - adjust volume in code'
                    ]
                },
                {
                    'number': 4,
                    'title': 'Add Arming Button (Optional)',
                    'description': 'Add a push button to arm/disarm alarm. This prevents false alarms during normal use.',
                    'time': '5 minutes',
                    'components': ['Push button (optional)'],
                    'wiring': [
                        '1. Button terminal 1 → Arduino D5',
                        '2. Button terminal 2 → Arduino GND',
                        '3. (Internal pull-up resistor enabled in code)'
                    ],
                    'tips': [
                        'Press button = toggle armed state',
                        'LED blinks when armed',
                        'Can use magnetic key switch instead for security',
                        'Advanced: add keypad for PIN code'
                    ]
                },
                {
                    'number': 5,
                    'title': 'Upload the Code',
                    'description': 'Upload door alarm code with entry delay, alarm duration, and arming features.',
                    'time': '10 minutes',
                    'components': ['Computer with Arduino IDE'],
                    'tips': [
                        'Select "Arduino Nano" in board manager',
                        'Try "Old Bootloader" if upload fails',
                        'Serial monitor shows door status for debugging',
                        'Customize delay times in code'
                    ]
                },
                {
                    'number': 6,
                    'title': 'Test on Breadboard',
                    'description': 'Before final assembly, test the system. Move magnet near/far from reed switch. Verify buzzer sounds and LED lights when door opens.',
                    'time': '10 minutes',
                    'components': ['All components on breadboard'],
                    'tips': [
                        'Door closed = magnet near switch = no alarm',
                        'Door opens = magnet moves away = ALARM',
                        'Test arming button if included',
                        'Adjust sensitivity if needed (magnet distance)'
                    ]
                },
                {
                    'number': 7,
                    'title': 'Install Battery Power',
                    'description': 'Connect 9V battery to Arduino VIN and GND for portable operation. Alarm will work without USB cable.',
                    'time': '5 minutes',
                    'components': ['9V battery', 'Battery connector'],
                    'wiring': [
                        '1. Battery red (+) → Arduino VIN',
                        '2. Battery black (-) → Arduino GND'
                    ],
                    'tips': [
                        '9V battery lasts 1-3 days depending on alarm usage',
                        'Use 3x AA battery pack (4.5V) for longer life',
                        'Add power switch to conserve battery',
                        'Consider rechargeable battery for permanent install'
                    ],
                    'warnings': [
                        '⚠️ Never connect both USB and battery simultaneously (use one or the other)'
                    ]
                },
                {
                    'number': 8,
                    'title': 'Mount in Enclosure',
                    'description': 'Place Arduino, buzzer, and LED in project box. Drill holes for wires and LED. Secure with hot glue or screws.',
                    'time': '15 minutes',
                    'components': ['Project box', 'Hot glue or screws'],
                    'tips': [
                        'LED visible through front hole',
                        'Buzzer facing out for maximum volume',
                        'Label box: "ALARM SYSTEM - DO NOT TAMPER"',
                        'Add ventilation holes for heat dissipation'
                    ]
                },
                {
                    'number': 9,
                    'title': 'Install on Door',
                    'description': 'Mount reed switch on door frame. Mount magnet on door aligned with switch (within 1-2cm gap when closed). Mount main unit nearby.',
                    'time': '20 minutes',
                    'components': ['Double-sided tape or screws'],
                    'tips': [
                        'Test alignment with multimeter before mounting',
                        'Switch on stationary frame, magnet on moving door',
                        'Use screws for security, tape for temporary/rental',
                        'Hide wires along frame with cable clips',
                        'Position unit where buzzer is most effective'
                    ],
                    'warnings': [
                        'Ensure magnet and switch align when door is closed',
                        'Gap too large = false alarms',
                        'Test multiple times before securing permanently'
                    ]
                },
                {
                    'number': 10,
                    'title': 'Test and Adjust',
                    'description': 'Arm system. Open door. Verify alarm sounds. Test entry delay. Adjust position if false alarms occur.',
                    'time': '15 minutes',
                    'components': ['Installed system'],
                    'tips': [
                        'Fine-tune magnet position for reliability',
                        'Test with different door opening speeds',
                        'Verify battery life indicator (if coded)',
                        'Document arming/disarming procedure'
                    ]
                }
            ],
            'total_build_time': '1-2 hours',
            'estimated_cost': '$11.15',
            'code_template': '''
/*
 * Door Open Alarm System
 * Arduino-based security alarm with reed switch
 * Battery powered, portable
 */

// Hardware pins
const int REED_SWITCH = 2;
const int BUZZER = 3;
const int LED = 4;
const int ARM_BUTTON = 5;  // Optional

// Alarm settings
const int ENTRY_DELAY = 5;     // Seconds to close door before alarm
const int ALARM_DURATION = 30; // Seconds alarm will sound
bool armed = true;             // Start armed (change to false for manual arming)

// State tracking
bool doorWasOpen = false;
unsigned long entryTime = 0;
unsigned long alarmTime = 0;
bool alarmActive = false;

void setup() {
  Serial.begin(9600);

  pinMode(REED_SWITCH, INPUT_PULLUP);  // Internal pull-up
  pinMode(ARM_BUTTON, INPUT_PULLUP);   // Internal pull-up
  pinMode(BUZZER, OUTPUT);
  pinMode(LED, OUTPUT);

  Serial.println("Door Alarm System Started");
  Serial.print("Armed: ");
  Serial.println(armed ? "YES" : "NO");

  // Visual startup indicator
  for(int i=0; i<3; i++) {
    digitalWrite(LED, HIGH);
    delay(200);
    digitalWrite(LED, LOW);
    delay(200);
  }
}

void loop() {
  // Check arming button
  if (digitalRead(ARM_BUTTON) == LOW) {
    armed = !armed;
    Serial.print("Armed: ");
    Serial.println(armed ? "YES" : "NO");

    // Blink LED to indicate state change
    for(int i=0; i<5; i++) {
      digitalWrite(LED, HIGH);
      delay(100);
      digitalWrite(LED, LOW);
      delay(100);
    }

    delay(1000);  // Debounce
  }

  // Read door status
  bool doorOpen = (digitalRead(REED_SWITCH) == HIGH);

  // Door status (armed systems blink LED slowly)
  if (armed && !alarmActive) {
    digitalWrite(LED, (millis() / 1000) % 2);  // Blink every second
  }

  // Door opened
  if (doorOpen && !doorWasOpen && armed) {
    Serial.println("DOOR OPENED!");
    entryTime = millis();
    doorWasOpen = true;
  }

  // Door closed
  if (!doorOpen && doorWasOpen) {
    Serial.println("Door closed");
    doorWasOpen = false;
    entryTime = 0;
    alarmActive = false;
    alarmTime = 0;
    noTone(BUZZER);
  }

  // Entry delay countdown
  if (doorWasOpen && armed && !alarmActive) {
    unsigned long elapsed = (millis() - entryTime) / 1000;

    if (elapsed < ENTRY_DELAY) {
      // Warning beeps during entry delay
      if ((millis() / 500) % 2) {
        tone(BUZZER, 2000);
      } else {
        noTone(BUZZER);
      }
      digitalWrite(LED, (millis() / 200) % 2);  // Fast blink

      Serial.print("Entry delay: ");
      Serial.print(ENTRY_DELAY - elapsed);
      Serial.println(" seconds");
    } else {
      // ALARM!
      alarmActive = true;
      alarmTime = millis();
      Serial.println("*** ALARM TRIGGERED ***");
    }
  }

  // Sound alarm
  if (alarmActive && armed) {
    unsigned long alarmElapsed = (millis() - alarmTime) / 1000;

    if (alarmElapsed < ALARM_DURATION) {
      // Siren effect
      int freq = 800 + (millis() % 1000);
      tone(BUZZER, freq);
      digitalWrite(LED, HIGH);

      Serial.print("ALARM! ");
      Serial.print(ALARM_DURATION - alarmElapsed);
      Serial.println(" seconds remaining");
    } else {
      // Alarm timeout
      alarmActive = false;
      noTone(BUZZER);
      Serial.println("Alarm timeout - waiting for door to close");
    }
  }

  delay(100);  // Small delay for stability
}
''',
            'business_notes': {
                'marketability': 'MEDIUM - Competitive market but customizable features can differentiate. Best as multi-pack (4-6 units) for whole home.',
                'target_audience': 'Homeowners, renters, dorm students, parents (child safety), small businesses, workshops',
                'upsell_opportunities': [
                    'WiFi notification version (ESP8266 + Blynk) - add $5, sell for +$20',
                    'Multi-sensor package (4-pack for doors/windows) - add $40, sell for +$50',
                    'Keypad arming with PIN code - add $8, sell for +$25',
                    'SMS alert integration (SIM800L module) - add $12, sell for +$40',
                    'Rechargeable battery with solar panel - add $15, sell for +$30',
                    'Integration with smart home systems (MQTT/Home Assistant) - add $0, sell for +$15'
                ],
                'manufacturing_notes': [
                    'Use rechargeable LiPo battery for better economics',
                    'Custom 3D printed enclosure looks professional',
                    'Pre-calibrate and test each unit before shipping',
                    'Include installation template for easy mounting',
                    'Sell in pairs or 4-packs for better margins'
                ],
                'competitive_advantages': [
                    'Customizable alarm sounds and delays',
                    'No subscription fees (unlike Ring/SimpliSafe)',
                    'Battery powered = works during power outages',
                    'Easy DIY installation = no professional needed',
                    'Open source = expandable and hackable',
                    'Educational value for learning electronics'
                ]
            },
            'next_steps': [
                'Add WiFi for smartphone notifications',
                'SMS alerts via SIM800L GSM module',
                'Multiple sensors on one Arduino (monitor 4-6 doors/windows)',
                'Keypad with PIN code arming',
                'Integration with Home Assistant/MQTT',
                'Tamper detection (detect if unit is removed from wall)',
                'Battery level monitoring and low battery alert',
                'Data logging of entry/exit times to SD card'
            ],
            'safety_notes': [
                'Low voltage (9V max) - very safe',
                'Do not install where it could cause panic (hospitals, etc.)',
                'Not a replacement for professional security systems',
                'Clearly label "ALARM SYSTEM" to deter tampering',
                'Test weekly to ensure battery is charged',
                'Buzzer can be very loud - consider neighbors',
                'Not suitable for high-security applications (jewelry stores, etc.)',
                'Keep away from moisture (not outdoor rated without enclosure mod)'
            ]
        }

    def _generate_water_level_instructions(self) -> Dict:
        """Instructions for Water Level Alarm (Arduino Nano + Water Sensor + Buzzer)"""
        return {
            'project_name': 'Water Level Alarm',
            'difficulty': 'easy',
            'build_time': '1-2 hours',
            'skill_level': 'Beginner',
            'tools_needed': [
                'Soldering iron (optional)',
                'Wire strippers',
                'Drill (for mounting)',
                'Screwdriver'
            ],
            'components': [
                {'name': 'Arduino Nano', 'quantity': 1, 'cost': 3.0, 'where_to_buy': 'AliExpress, Amazon'},
                {'name': 'Water Level Sensor Module', 'quantity': 1, 'cost': 2.0, 'where_to_buy': 'Amazon, eBay'},
                {'name': 'Buzzer (active)', 'quantity': 1, 'cost': 1.0, 'where_to_buy': 'Amazon'},
                {'name': 'LED (Red)', 'quantity': 1, 'cost': 0.1, 'where_to_buy': 'Amazon'},
                {'name': 'LED (Blue)', 'quantity': 1, 'cost': 0.1, 'where_to_buy': 'Amazon'},
                {'name': '220Ω Resistor', 'quantity': 2, 'cost': 0.1, 'where_to_buy': 'Amazon'},
                {'name': '9V Battery + Connector', 'quantity': 1, 'cost': 3.0, 'where_to_buy': 'Amazon'},
                {'name': 'Waterproof wire (for sensor)', 'quantity': 1, 'cost': 1.5, 'where_to_buy': 'Amazon'},
                {'name': 'Project box', 'quantity': 1, 'cost': 2.0, 'where_to_buy': 'Amazon'}
            ],
            'market_analysis': {
                'build_cost': 12.8,
                'market_price_low': 15.0,
                'market_price_high': 28.0,
                'profit_margin': '17-119%',
                'comparable_products': [
                    'Glentronics BWD-HWA Basement Watchdog - $25-35',
                    'UTILITECH Water Alarm - $15-20',
                    'Zircon Leak Alert - $10-15',
                    'Govee Water Sensor (WiFi) - $20-30'
                ]
            },
            'steps': [
                {
                    'number': 1,
                    'title': 'Understanding Water Level Sensors',
                    'description': 'Water level sensors detect water presence using exposed traces that conduct electricity when wet. Output is analog voltage proportional to water depth. Simple, cheap, but corrodes over time.',
                    'time': '5 minutes',
                    'components': ['Water level sensor'],
                    'tips': [
                        'Sensor has series of exposed traces',
                        'More traces covered = higher voltage output',
                        'Analog output: 0V (dry) to ~3V (fully submerged)',
                        'Digital output available on some modules (HIGH/LOW threshold)'
                    ],
                    'warnings': [
                        'Sensor will corrode over months of use (normal)',
                        'Do not apply constant power - only read periodically',
                        'Coating with nail polish extends life but reduces sensitivity'
                    ]
                },
                {
                    'number': 2,
                    'title': 'Connect Water Sensor to Arduino',
                    'description': 'Wire the water level sensor module to Arduino. Sensor has 3 pins: VCC (+), GND (-), and analog output (S).',
                    'time': '10 minutes',
                    'components': ['Arduino Nano', 'Water sensor', 'Jumper wires'],
                    'wiring': [
                        '1. Sensor VCC (+) → Arduino D6 (power on demand to reduce corrosion)',
                        '2. Sensor GND (-) → Arduino GND',
                        '3. Sensor S (signal) → Arduino A0 (analog input)'
                    ],
                    'tips': [
                        'Powering sensor from D6 allows turning it on only when reading',
                        'This extends sensor life significantly (10x longer)',
                        'Use waterproof wire if sensor is distant from Arduino',
                        'Sensor wire can be extended up to 3-5 meters'
                    ]
                },
                {
                    'number': 3,
                    'title': 'Add Buzzer and LEDs',
                    'description': 'Connect buzzer for audio alert and LEDs for visual status (blue = normal, red = water detected).',
                    'time': '10 minutes',
                    'components': ['Buzzer', '2x LEDs', '2x 220Ω resistors'],
                    'wiring': [
                        '1. Buzzer (+) → Arduino D7',
                        '2. Buzzer (-) → Arduino GND',
                        '3. Blue LED anode (+) → 220Ω resistor → Arduino D8',
                        '4. Blue LED cathode (-) → Arduino GND',
                        '5. Red LED anode (+) → 220Ω resistor → Arduino D9',
                        '6. Red LED cathode (-) → Arduino GND'
                    ],
                    'tips': [
                        'Blue LED = system OK, monitoring',
                        'Red LED = WATER DETECTED',
                        'Buzzer sounds continuous alarm when triggered',
                        'LEDs visible from distance for at-a-glance status'
                    ]
                },
                {
                    'number': 4,
                    'title': 'Optional: Add Reset Button',
                    'description': 'Add push button to silence alarm (acknowledge water detection). Alarm will re-trigger if water still present.',
                    'time': '5 minutes',
                    'components': ['Push button (optional)'],
                    'wiring': [
                        '1. Button terminal 1 → Arduino D10',
                        '2. Button terminal 2 → Arduino GND',
                        '3. (Internal pull-up resistor in code)'
                    ],
                    'tips': [
                        'Press to silence alarm temporarily',
                        'Useful for overnight monitoring without continuous noise',
                        'Alarm resets and checks again after 1 minute'
                    ]
                },
                {
                    'number': 5,
                    'title': 'Upload Calibration Code',
                    'description': 'Upload simple code to determine water threshold value for your specific sensor.',
                    'time': '10 minutes',
                    'components': ['Arduino', 'Water sensor'],
                    'code_snippet': '''
// Calibration
void setup() {
  pinMode(6, OUTPUT);
  Serial.begin(9600);
}

void loop() {
  digitalWrite(6, HIGH);  // Power sensor
  delay(10);
  int value = analogRead(A0);
  digitalWrite(6, LOW);   // Power off

  Serial.print("Sensor: ");
  Serial.println(value);
  delay(2000);
}
// 1. Run with sensor DRY, note value (typically 0-50)
// 2. Dip sensor in water 1cm, note value (typically 200-400)
// 3. Set THRESHOLD in main code between these values
''',
                    'tips': [
                        'Test with actual tank/basement water if possible',
                        'Different water (tap, rain, salt) has different conductivity',
                        'Set threshold conservatively to avoid false alarms'
                    ]
                },
                {
                    'number': 6,
                    'title': 'Upload Main Code',
                    'description': 'Upload the complete water alarm code with your calibrated threshold value.',
                    'time': '10 minutes',
                    'components': ['Computer with Arduino IDE'],
                    'tips': [
                        'Update WATER_THRESHOLD value from calibration',
                        'Adjust CHECK_INTERVAL for battery life vs responsiveness',
                        'Longer interval = longer battery life',
                        'Serial monitor shows real-time sensor readings'
                    ]
                },
                {
                    'number': 7,
                    'title': 'Test the System',
                    'description': 'Test alarm by dipping sensor in water. Verify buzzer sounds, red LED lights, and blue LED turns off.',
                    'time': '10 minutes',
                    'components': ['Cup of water for testing'],
                    'tips': [
                        'Dry sensor = blue LED on, no sound',
                        'Wet sensor = red LED on, buzzer sounds',
                        'Test reset button functionality',
                        'Ensure sensor wire is waterproof if extended'
                    ]
                },
                {
                    'number': 8,
                    'title': 'Install Battery Power',
                    'description': 'Connect 9V battery for portable operation. Essential for basement/tank monitoring away from outlets.',
                    'time': '5 minutes',
                    'components': ['9V battery', 'Battery connector'],
                    'wiring': [
                        '1. Battery red (+) → Arduino VIN',
                        '2. Battery black (-) → Arduino GND'
                    ],
                    'tips': [
                        '9V battery lasts 1-2 weeks with 10-second check interval',
                        'Use 4x AA battery pack for 2-4 weeks runtime',
                        'Rechargeable LiPo + solar for permanent installation',
                        'Add power switch to conserve battery when not needed'
                    ],
                    'warnings': [
                        '⚠️ Never connect USB and battery at same time'
                    ]
                },
                {
                    'number': 9,
                    'title': 'Mount in Enclosure',
                    'description': 'Place Arduino and components in waterproof box. Sensor stays outside, Arduino inside dry enclosure.',
                    'time': '15 minutes',
                    'components': ['Waterproof project box'],
                    'tips': [
                        'Drill holes for sensor wire and LEDs',
                        'Seal holes with silicone or hot glue',
                        'Mount box above expected water level',
                        'LEDs visible from outside',
                        'Buzzer facing out for maximum sound',
                        'Include desiccant packet to absorb moisture'
                    ],
                    'warnings': [
                        'Arduino must stay DRY - only sensor touches water',
                        'Test enclosure waterproofing before deployment'
                    ]
                },
                {
                    'number': 10,
                    'title': 'Install in Target Location',
                    'description': 'Place sensor probe at lowest point of basement floor, bottom of water tank, or sump pump area. Mount control box on wall nearby.',
                    'time': '20 minutes',
                    'components': ['Completed system', 'Mounting hardware'],
                    'tips': [
                        'Basement: place sensor in corner where water collects',
                        'Tank: mount sensor at FULL level',
                        'Sump pump: place near pump to detect failure',
                        'Aquarium: mount at overflow level',
                        'Test by pouring water to trigger sensor',
                        'Label system clearly: "WATER ALARM - DO NOT REMOVE"'
                    ]
                },
                {
                    'number': 11,
                    'title': 'Maintenance and Testing',
                    'description': 'Test weekly by pouring water on sensor. Clean sensor monthly with soft cloth. Replace battery every 2-4 weeks.',
                    'time': 'Ongoing',
                    'components': ['Completed system'],
                    'tips': [
                        'Weekly test ensures system is working',
                        'Check battery voltage monthly (needs >7V)',
                        'Clean sensor corrosion with vinegar + brush',
                        'Replace sensor every 6-12 months (cheap)',
                        'Keep spare battery and sensor on hand'
                    ]
                }
            ],
            'total_build_time': '1-2 hours',
            'estimated_cost': '$12.80',
            'code_template': '''
/*
 * Water Level Alarm System
 * Detects water leaks and floods
 * Battery powered for basements/remote locations
 */

// Calibration (UPDATE THIS)
const int WATER_THRESHOLD = 300;  // Sensor value indicating water (calibrate!)

// Hardware pins
const int SENSOR_POWER = 6;
const int SENSOR_PIN = A0;
const int BUZZER = 7;
const int BLUE_LED = 8;   // Normal status
const int RED_LED = 9;    // Alarm status
const int RESET_BUTTON = 10;  // Optional

// Settings
const int CHECK_INTERVAL = 10000;  // Check every 10 seconds (adjust for battery life)

// State
bool alarmTriggered = false;
bool alarmSilenced = false;
unsigned long lastCheck = 0;

void setup() {
  Serial.begin(9600);

  pinMode(SENSOR_POWER, OUTPUT);
  pinMode(BUZZER, OUTPUT);
  pinMode(BLUE_LED, OUTPUT);
  pinMode(RED_LED, OUTPUT);
  pinMode(RESET_BUTTON, INPUT_PULLUP);

  // Keep sensor powered off until reading
  digitalWrite(SENSOR_POWER, LOW);

  Serial.println("Water Level Alarm Started");
  Serial.print("Threshold: ");
  Serial.println(WATER_THRESHOLD);
  Serial.print("Check interval: ");
  Serial.print(CHECK_INTERVAL / 1000);
  Serial.println(" seconds");

  // Startup indicator
  for(int i=0; i<3; i++) {
    digitalWrite(BLUE_LED, HIGH);
    digitalWrite(RED_LED, HIGH);
    delay(300);
    digitalWrite(BLUE_LED, LOW);
    digitalWrite(RED_LED, LOW);
    delay(300);
  }
}

void loop() {
  unsigned long currentTime = millis();

  // Check reset button
  if (digitalRead(RESET_BUTTON) == LOW) {
    alarmSilenced = true;
    alarmTriggered = false;
    noTone(BUZZER);
    digitalWrite(RED_LED, LOW);
    digitalWrite(BLUE_LED, HIGH);
    Serial.println("Alarm silenced");
    delay(1000);  // Debounce
  }

  // Periodic water level check
  if (currentTime - lastCheck >= CHECK_INTERVAL) {
    lastCheck = currentTime;

    // Power on sensor
    digitalWrite(SENSOR_POWER, HIGH);
    delay(10);  // Allow sensor to stabilize

    // Read sensor
    int sensorValue = analogRead(SENSOR_PIN);

    // Power off sensor (extend life)
    digitalWrite(SENSOR_POWER, LOW);

    // Print reading
    Serial.print("Water level: ");
    Serial.print(sensorValue);

    // Check for water
    if (sensorValue > WATER_THRESHOLD) {
      Serial.println(" - WATER DETECTED!");

      if (!alarmTriggered) {
        alarmTriggered = true;
        alarmSilenced = false;
      }
    } else {
      Serial.println(" - OK");

      // Auto-reset if water gone
      if (alarmTriggered) {
        Serial.println("Water cleared - alarm reset");
        alarmTriggered = false;
        alarmSilenced = false;
        noTone(BUZZER);
      }
    }
  }

  // Alarm state
  if (alarmTriggered && !alarmSilenced) {
    // ALARM!
    digitalWrite(BLUE_LED, LOW);
    digitalWrite(RED_LED, HIGH);

    // Pulsing alarm sound
    int freq = 1000 + (millis() % 500);
    tone(BUZZER, freq);
  }
  else if (alarmTriggered && alarmSilenced) {
    // Silenced but water still present
    digitalWrite(RED_LED, (millis() / 1000) % 2);  // Slow blink
    digitalWrite(BLUE_LED, LOW);
    noTone(BUZZER);

    // Re-check after 1 minute
    if (currentTime - lastCheck > 60000) {
      alarmSilenced = false;
    }
  }
  else {
    // Normal monitoring
    digitalWrite(BLUE_LED, (millis() / 2000) % 2);  // Very slow blink
    digitalWrite(RED_LED, LOW);
    noTone(BUZZER);
  }

  delay(100);  // Small delay for stability
}
''',
            'business_notes': {
                'marketability': 'MEDIUM-HIGH - Every homeowner with a basement needs this. Insurance companies love proactive prevention. Great gift for new homeowners.',
                'target_audience': 'Homeowners with basements, sump pump owners, aquarium enthusiasts, boat owners, RV owners, property managers',
                'upsell_opportunities': [
                    'WiFi version with smartphone alerts (ESP8266 + Blynk/IFTTT) - add $5, sell for +$20',
                    'Multiple sensor zones (3-4 sensors, one Arduino) - add $6, sell for +$25',
                    'SMS alerts via GSM module - add $12, sell for +$40',
                    'Auto-shutoff valve integration (turn off water main) - add $45, sell for +$150',
                    'Solar powered with rechargeable battery - add $15, sell for +$30',
                    'Temperature monitoring (frozen pipe prevention) - add $3, sell for +$15'
                ],
                'manufacturing_notes': [
                    'Use silicone-coated sensors for longer life',
                    'Include 3-meter sensor cable standard',
                    'Professional 3D printed case with IP65 rating',
                    'Pre-calibrate for fresh water',
                    'Include mounting template and hardware',
                    'Offer insurance-approved certification for premium pricing'
                ],
                'competitive_advantages': [
                    'Much cheaper than professional systems ($50-200)',
                    'No monthly monitoring fees',
                    'Battery powered = works during power outages (sump pump failures)',
                    'Customizable threshold and check interval',
                    'Can expand to multiple sensors',
                    'DIY installation = no technician needed',
                    'Educational value for electronics learning'
                ]
            },
            'next_steps': [
                'WiFi connectivity for remote alerts',
                'Integration with Home Assistant/SmartThings',
                'SMS alerts when water detected',
                'Multiple sensor support (monitor several locations)',
                'Temperature sensor for frozen pipe detection',
                'Humidity sensor for mold prevention',
                'Auto water shutoff valve control',
                'Data logging of water events',
                'Solar panel + rechargeable battery for permanent install',
                'Cellular connectivity for properties without WiFi'
            ],
            'safety_notes': [
                'Low voltage (9V max) - safe around water',
                'Arduino must stay DRY - only sensor touches water',
                'Ensure enclosure is waterproof before installation',
                'Test weekly to ensure functionality',
                'Not a replacement for proper drainage/waterproofing',
                'Water sensor will corrode over time - replace yearly',
                'Do not use in drinking water systems (not food safe)',
                'For flood insurance discounts, may need professional installation cert',
                'Ensure buzzer is loud enough to be heard from living areas',
                'Consider neighbors if in shared building (noise)'
            ]
        }


def main():
    """Demo build instructions generator"""
    print("="*70)
    print("  BUILD INSTRUCTIONS GENERATOR")
    print("="*70)
    print()

    generator = BuildInstructionsGenerator()

    # Generate instructions for Air Quality Monitor
    instructions = generator.generate_instructions('Air Quality Monitor', ['esp32', 'bme280', 'oled_ssd1306'])

    print(f"Project: {instructions['project_name']}")
    print(f"Difficulty: {instructions['difficulty']}")
    print(f"Build Time: {instructions['build_time']}")
    print()

    print("Build Steps:")
    print("-"*70)
    for step in instructions['steps']:
        print(f"\nStep {step['number']}: {step['title']}")
        print(f"  {step['description']}")
        if 'warnings' in step:
            for warning in step['warnings']:
                print(f"  {warning}")
        if 'time' in step:
            print(f"  Time: {step['time']}")

    print()
    print(f"\nTotal Build Time: {instructions['total_build_time']}")
    print(f"Estimated Cost: {instructions['estimated_cost']}")
    print()

    print("="*70)
    print("  INSTRUCTIONS GENERATED SUCCESSFULLY")
    print("="*70)


if __name__ == '__main__':
    main()
