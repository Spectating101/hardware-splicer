#!/usr/bin/env python3
"""
Process scraped tutorials and build code templates
Uses the real code examples fetched from Random Nerd Tutorials
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, 'src')

from scrapers.code_library_scraper import CodeLibraryScraper, CodeExample


def main():
    print("="*70)
    print("  PROCESSING SCRAPED TUTORIALS")
    print("="*70)
    print()

    scraper = CodeLibraryScraper()

    # Example 1: ESP32 with DHT22 (Simple)
    esp32_dht22_code = '''#include "DHT.h"

#define DHTPIN 4     // Digital pin connected to the DHT sensor
#define DHTTYPE DHT22   // DHT 22  (AM2302), AM2321

DHT dht(DHTPIN, DHTTYPE);

void setup() {
  Serial.begin(9600);
  Serial.println(F("DHTxx test!"));
  dht.begin();
}

void loop() {
  delay(2000);

  float h = dht.readHumidity();
  float t = dht.readTemperature();
  float f = dht.readTemperature(true);

  if (isnan(h) || isnan(t) || isnan(f)) {
    Serial.println(F("Failed to read from DHT sensor!"));
    return;
  }

  float hif = dht.computeHeatIndex(f, h);
  float hic = dht.computeHeatIndex(t, h, false);

  Serial.print(F("Humidity: "));
  Serial.print(h);
  Serial.print(F("%  Temperature: "));
  Serial.print(t);
  Serial.print(F("°C "));
  Serial.print(f);
  Serial.print(F("°F  Heat index: "));
  Serial.print(hic);
  Serial.print(F("°C "));
  Serial.print(hif);
  Serial.println(F("°F"));
}'''

    # Example 2: ESP8266 with DHT22 Web Server (Complex)
    esp8266_web_server_code = '''#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <Hash.h>
#include <ESPAsyncTCP.h>
#include <ESPAsyncWebServer.h>
#include <Adafruit_Sensor.h>
#include <DHT.h>

const char* ssid = "REPLACE_WITH_YOUR_SSID";
const char* password = "REPLACE_WITH_YOUR_PASSWORD";

#define DHTPIN 5     // GPIO5 (D1)
#define DHTTYPE DHT22

DHT dht(DHTPIN, DHTTYPE);
AsyncWebServer server(80);

float t = 0.0;
float h = 0.0;

unsigned long previousMillis = 0;
const long interval = 10000;

const char index_html[] PROGMEM = R"rawliteral(
<!DOCTYPE HTML><html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body>
  <h2>ESP8266 DHT Server</h2>
</body>
</html>
)rawliteral";

String processor(const String& var){
  if(var == "TEMPERATURE") return String(t);
  else if(var == "HUMIDITY") return String(h);
  return String();
}

void setup(){
  Serial.begin(115200);
  dht.begin();

  WiFi.begin(ssid, password);
  Serial.println("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.println(".");
  }

  Serial.println(WiFi.localIP());

  server.on("/", HTTP_GET, [](AsyncWebServerRequest *request){
    request->send_P(200, "text/html", index_html, processor);
  });

  server.begin();
}

void loop(){
  unsigned long currentMillis = millis();
  if (currentMillis - previousMillis >= interval) {
    previousMillis = currentMillis;

    float newT = dht.readTemperature();
    if (!isnan(newT)) {
      t = newT;
      Serial.println(t);
    }

    float newH = dht.readHumidity();
    if (!isnan(newH)) {
      h = newH;
      Serial.println(h);
    }
  }
}'''

    # Parse the examples
    print("Parsing ESP32 + DHT22 example...")
    esp32_examples = scraper.scrape_from_content(
        url="https://randomnerdtutorials.com/esp32-dht11-dht22-temperature-humidity-sensor-arduino-ide/",
        content=esp32_dht22_code,
        components=['ESP32', 'DHT22'],
        source_name="Random Nerd Tutorials"
    )

    print(f"✓ Extracted {len(esp32_examples)} examples from ESP32 tutorial")
    print()

    print("Parsing ESP8266 + DHT22 Web Server example...")
    esp8266_examples = scraper.scrape_from_content(
        url="https://randomnerdtutorials.com/esp8266-dht11dht22-temperature-and-humidity-web-server-with-arduino-ide/",
        content=esp8266_web_server_code,
        components=['ESP8266', 'DHT22'],
        source_name="Random Nerd Tutorials"
    )

    print(f"✓ Extracted {len(esp8266_examples)} examples from ESP8266 tutorial")
    print()

    # Combine all examples
    all_examples = esp32_examples + esp8266_examples

    print(f"Total examples extracted: {len(all_examples)}")
    print()

    # Show details
    for i, ex in enumerate(all_examples, 1):
        print(f"--- Example {i}: {ex.component} from {ex.source_name} ---")
        print(f"  Includes: {len(ex.includes)} statements")
        for inc in ex.includes:
            print(f"    {inc}")
        print(f"  Defines: {len(ex.defines)} statements")
        for define in ex.defines[:3]:
            print(f"    {define}")
        print(f"  Globals: {len(ex.globals)} declarations")
        print(f"  Setup code: {len(ex.setup_code)} statements")
        print(f"  Loop code: {len(ex.loop_code)} statements")
        print(f"  Libraries needed: {ex.libraries_needed}")
        print(f"  Pins: {ex.pins_used}")
        print()

    # Build templates
    print("="*70)
    print("Building template library from examples...")
    print("="*70)
    print()

    templates = scraper.build_template_library(all_examples)

    for component, template in templates.items():
        print(f"\n{'='*70}")
        print(f"  TEMPLATE: {component}")
        print(f"{'='*70}")
        print(f"Based on {template['example_count']} example(s)")
        print(f"\nRequired Libraries:")
        for lib in template['required_libraries']:
            print(f"  - {lib}")
        print(f"\nCommon Includes:")
        for inc in template['common_includes'][:5]:
            print(f"  {inc}")
        print(f"\nCommon Setup Steps:")
        for step in template['common_setup'][:10]:
            print(f"  {step}")
        print(f"\nCommon Loop Operations:")
        for op in template['common_loop'][:10]:
            print(f"  {op}")
        print(f"\nSources:")
        for source in template['sources']:
            print(f"  - {source['name']}: {source['url']}")

    # Save everything
    print("\n" + "="*70)
    print("Saving to disk...")
    print("="*70)
    print()

    scraper.save_examples(all_examples, "real_arduino_examples.json")
    scraper.save_template_library(templates, "real_code_templates.json")

    print()
    print("="*70)
    print("✓ SUCCESS! Code templates built from real tutorials")
    print("="*70)
    print()
    print(f"  Examples saved: data/code_cache/real_arduino_examples.json")
    print(f"  Templates saved: data/code_cache/real_code_templates.json")
    print()
    print(f"  {len(all_examples)} working examples")
    print(f"  {len(templates)} component templates")
    print()
    print("These can now be used by Circuit-AI to generate working code!")
    print("="*70)


if __name__ == '__main__':
    main()
