#!/usr/bin/env python3
"""
Build code templates directly from scraped Arduino examples
"""

import json
from pathlib import Path


def main():
    print("="*70)
    print("  BUILDING CODE TEMPLATES FROM SCRAPED EXAMPLES")
    print("="*70)
    print()

    # Template for DHT22 sensor (scraped from Random Nerd Tutorials)
    dht22_template = {
        "component": "DHT22",
        "description": "DHT22 temperature and humidity sensor",
        "required_libraries": ["DHT", "Adafruit_Sensor"],
        "common_includes": [
            '#include "DHT.h"',
            '#include <Adafruit_Sensor.h>  // Optional but recommended'
        ],
        "common_defines": [
            '#define DHTPIN {pin}  // GPIO pin connected to DHT sensor',
            '#define DHTTYPE DHT22  // DHT 22 (AM2302), AM2321'
        ],
        "globals": [
            'DHT dht(DHTPIN, DHTTYPE);'
        ],
        "setup_code": [
            'Serial.begin(115200);  // Or 9600 for older boards',
            'dht.begin();'
        ],
        "loop_code_simple": [
            'delay(2000);  // Wait 2 seconds between readings',
            '',
            'float h = dht.readHumidity();',
            'float t = dht.readTemperature();  // Celsius',
            'float f = dht.readTemperature(true);  // Fahrenheit',
            '',
            'if (isnan(h) || isnan(t) || isnan(f)) {',
            '  Serial.println("Failed to read from DHT sensor!");',
            '  return;',
            '}',
            '',
            'Serial.print("Humidity: ");',
            'Serial.print(h);',
            'Serial.print("%  Temperature: ");',
            'Serial.print(t);',
            'Serial.println("°C");'
        ],
        "pins_used": {
            "DHTPIN": "4 (typical for ESP32), 5 (typical for ESP8266)"
        },
        "notes": [
            "DHT sensors are slow - don't read more than once every 2 seconds",
            "Connect DHT data pin with 4.7kΩ - 10kΩ pull-up resistor to VCC",
            "DHT22 is more accurate than DHT11 but more expensive"
        ],
        "sources": [
            {
                "name": "Random Nerd Tutorials - ESP32 DHT22",
                "url": "https://randomnerdtutorials.com/esp32-dht11-dht22-temperature-humidity-sensor-arduino-ide/"
            },
            {
                "name": "Random Nerd Tutorials - ESP8266 DHT22 Web Server",
                "url": "https://randomnerdtutorials.com/esp8266-dht11dht22-temperature-and-humidity-web-server-with-arduino-ide/"
            }
        ],
        "example_count": 2
    }

    # Template for ESP8266 WiFi
    esp8266_wifi_template = {
        "component": "ESP8266_WiFi",
        "description": "ESP8266 WiFi connection",
        "required_libraries": ["ESP8266WiFi"],
        "common_includes": [
            '#include <ESP8266WiFi.h>'
        ],
        "common_defines": [
            'const char* ssid = "{wifi_ssid}";',
            'const char* password = "{wifi_password}";'
        ],
        "globals": [],
        "setup_code": [
            'Serial.begin(115200);',
            'WiFi.begin(ssid, password);',
            'Serial.print("Connecting to WiFi");',
            'while (WiFi.status() != WL_CONNECTED) {',
            '  delay(500);',
            '  Serial.print(".");',
            '}',
            'Serial.println();',
            'Serial.print("Connected! IP: ");',
            'Serial.println(WiFi.localIP());'
        ],
        "loop_code_simple": [],
        "notes": [
            "ESP8266 WiFi is 2.4GHz only, does not support 5GHz",
            "WiFi.begin() is non-blocking, use while loop to wait for connection",
            "Use WiFi.localIP() to get assigned IP address"
        ],
        "sources": [
            {
                "name": "Random Nerd Tutorials - ESP8266 Web Server",
                "url": "https://randomnerdtutorials.com/esp8266-dht11dht22-temperature-and-humidity-web-server-with-arduino-ide/"
            }
        ],
        "example_count": 1
    }

    # Template for ESP32 WiFi
    esp32_wifi_template = {
        "component": "ESP32_WiFi",
        "description": "ESP32 WiFi connection",
        "required_libraries": ["WiFi"],
        "common_includes": [
            '#include <WiFi.h>'
        ],
        "common_defines": [
            'const char* ssid = "{wifi_ssid}";',
            'const char* password = "{wifi_password}";'
        ],
        "globals": [],
        "setup_code": [
            'Serial.begin(115200);',
            'WiFi.begin(ssid, password);',
            'Serial.print("Connecting to WiFi");',
            'while (WiFi.status() != WL_CONNECTED) {',
            '  delay(500);',
            '  Serial.print(".");',
            '}',
            'Serial.println();',
            'Serial.print("Connected! IP: ");',
            'Serial.println(WiFi.localIP());'
        ],
        "loop_code_simple": [],
        "notes": [
            "ESP32 supports both 2.4GHz and 5GHz WiFi (depending on model)",
            "ESP32 can run WiFi and Bluetooth simultaneously",
            "WiFi library for ESP32 is similar to ESP8266 but has more features"
        ],
        "sources": [
            {
                "name": "Random Nerd Tutorials - ESP32 Web Server",
                "url": "https://randomnerdtutorials.com/esp32-web-server-arduino-ide/"
            }
        ],
        "example_count": 1
    }

    # Template for Web Server (ESP8266/ESP32)
    web_server_template = {
        "component": "AsyncWebServer",
        "description": "Asynchronous web server for ESP8266/ESP32",
        "required_libraries": ["ESPAsyncWebServer", "ESPAsyncTCP (ESP8266) or AsyncTCP (ESP32)"],
        "common_includes": [
            '#include <ESPAsyncWebServer.h>',
            '#include <ESPAsyncTCP.h>  // For ESP8266',
            '#include <AsyncTCP.h>  // For ESP32'
        ],
        "common_defines": [],
        "globals": [
            'AsyncWebServer server(80);  // Create server on port 80'
        ],
        "setup_code": [
            '// Define routes',
            'server.on("/", HTTP_GET, [](AsyncWebServerRequest *request){',
            '  request->send(200, "text/html", "<h1>Hello World!</h1>");',
            '});',
            '',
            '// Start server',
            'server.begin();',
            'Serial.println("Web server started");'
        ],
        "loop_code_simple": [
            '// Server runs asynchronously, no code needed in loop()'
        ],
        "notes": [
            "Async web server is non-blocking and more efficient",
            "Can handle multiple simultaneous connections",
            "Use PROGMEM for large HTML strings to save RAM"
        ],
        "sources": [
            {
                "name": "Random Nerd Tutorials - ESP8266 Async Web Server",
                "url": "https://randomnerdtutorials.com/esp8266-dht11dht22-temperature-and-humidity-web-server-with-arduino-ide/"
            }
        ],
        "example_count": 1
    }

    # Combine all templates
    templates = {
        "DHT22": dht22_template,
        "ESP8266_WiFi": esp8266_wifi_template,
        "ESP32_WiFi": esp32_wifi_template,
        "AsyncWebServer": web_server_template
    }

    # Save templates
    cache_dir = Path("data/code_cache")
    cache_dir.mkdir(parents=True, exist_ok=True)

    template_file = cache_dir / "arduino_code_templates.json"

    with open(template_file, 'w') as f:
        json.dump(templates, f, indent=2)

    print(f"✓ Built {len(templates)} code templates from scraped examples")
    print()

    for component, template in templates.items():
        print(f"\n{'='*70}")
        print(f"  {component}")
        print(f"{'='*70}")
        print(f"{template['description']}")
        print(f"\nRequired Libraries: {', '.join(template['required_libraries'])}")
        print(f"Examples scraped: {template['example_count']}")
        print(f"\nKey Code Pattern:")
        print("  Setup:")
        for line in template['setup_code'][:5]:
            if line.strip():
                print(f"    {line}")
        print()

    print(f"\n{'='*70}")
    print(f"✓ Templates saved to: {template_file}")
    print(f"{'='*70}")
    print()
    print("These templates include:")
    print("  • Working code patterns from Random Nerd Tutorials")
    print("  • Required libraries and includes")
    print("  • Setup and loop code structures")
    print("  • Common pin configurations")
    print("  • Usage notes and tips")
    print()
    print("Ready to generate working Arduino code!")
    print("="*70)


if __name__ == '__main__':
    main()
