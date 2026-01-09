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
        # To be implemented
        pass

    def _generate_parking_sensor_instructions(self) -> Dict:
        # To be implemented
        pass

    def _generate_thermometer_instructions(self) -> Dict:
        # To be implemented
        pass

    def _generate_motion_light_instructions(self) -> Dict:
        # To be implemented
        pass


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
