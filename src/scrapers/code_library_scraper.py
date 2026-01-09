#!/usr/bin/env python3
"""
Code Library Scraper for Circuit-AI
Extracts working Arduino code examples from tutorials and builds template library
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict


@dataclass
class CodeExample:
    """Represents a scraped code example"""
    component: str  # e.g., "DHT22", "ESP8266"
    source_url: str
    source_name: str  # e.g., "Random Nerd Tutorials"
    full_code: str
    includes: List[str]
    defines: List[str]
    globals: List[str]
    setup_code: List[str]
    loop_code: List[str]
    libraries_needed: List[str]
    pins_used: Dict[str, str]  # pin_name -> gpio_number
    description: str


class CodeLibraryScraper:
    """Scrapes Arduino code examples from tutorials"""

    def __init__(self, cache_dir: Path = None):
        self.cache_dir = cache_dir or Path(__file__).parent.parent.parent / "data" / "code_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Known tutorial sources
        self.sources = {
            'random_nerd_tutorials': {
                'base_url': 'https://randomnerdtutorials.com',
                'projects': [
                    {
                        'url': 'https://randomnerdtutorials.com/esp32-dht11-dht22-temperature-humidity-sensor-arduino-ide/',
                        'components': ['ESP32', 'DHT22'],
                        'description': 'ESP32 with DHT22 temperature and humidity sensor'
                    },
                    {
                        'url': 'https://randomnerdtutorials.com/esp8266-dht11dht22-temperature-and-humidity-web-server-with-arduino-ide/',
                        'components': ['ESP8266', 'DHT22'],
                        'description': 'ESP8266 DHT22 web server'
                    },
                    {
                        'url': 'https://randomnerdtutorials.com/esp32-web-server-arduino-ide/',
                        'components': ['ESP32'],
                        'description': 'ESP32 web server'
                    }
                ]
            },
            'adafruit_learning': {
                'base_url': 'https://learn.adafruit.com',
                'projects': [
                    {
                        'url': 'https://learn.adafruit.com/dht',
                        'components': ['DHT22', 'DHT11'],
                        'description': 'DHT sensor tutorial'
                    }
                ]
            }
        }

    def extract_code_blocks(self, content: str) -> List[str]:
        """Extract code blocks from HTML/markdown content"""
        code_blocks = []

        # Pattern 1: Markdown code blocks with ```cpp or ```arduino
        pattern1 = r'```(?:cpp|arduino|c)\s*\n(.*?)\n```'
        blocks1 = re.findall(pattern1, content, re.DOTALL | re.IGNORECASE)
        code_blocks.extend(blocks1)

        # Pattern 2: <pre> or <code> tags
        pattern2 = r'<(?:pre|code)[^>]*>(.*?)</(?:pre|code)>'
        blocks2 = re.findall(pattern2, content, re.DOTALL | re.IGNORECASE)
        code_blocks.extend([self._clean_html(b) for b in blocks2])

        # Pattern 3: Indented code blocks (4 spaces)
        lines = content.split('\n')
        current_block = []
        for line in lines:
            if line.startswith('    ') and not line.strip().startswith('//'):
                current_block.append(line[4:])
            elif current_block:
                if len(current_block) > 3:  # Only save blocks with 3+ lines
                    code_blocks.append('\n'.join(current_block))
                current_block = []

        return [b.strip() for b in code_blocks if b.strip()]

    def _clean_html(self, text: str) -> str:
        """Remove HTML tags from text"""
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'&lt;', '<', text)
        text = re.sub(r'&gt;', '>', text)
        text = re.sub(r'&amp;', '&', text)
        text = re.sub(r'&quot;', '"', text)
        return text

    def parse_arduino_code(self, code: str) -> Dict:
        """Parse Arduino code into components"""
        lines = code.split('\n')

        parsed = {
            'includes': [],
            'defines': [],
            'globals': [],
            'setup_code': [],
            'loop_code': [],
            'libraries_needed': [],
            'pins_used': {}
        }

        in_setup = False
        in_loop = False
        brace_count = 0

        for line in lines:
            stripped = line.strip()

            # Track braces to know when we exit setup/loop
            brace_count += stripped.count('{') - stripped.count('}')

            # Extract includes
            if stripped.startswith('#include'):
                parsed['includes'].append(stripped)
                # Extract library name
                lib_match = re.search(r'#include\s*[<"]([^>"]+)[>"]', stripped)
                if lib_match:
                    lib_name = lib_match.group(1).replace('.h', '')
                    parsed['libraries_needed'].append(lib_name)

            # Extract defines
            elif stripped.startswith('#define'):
                parsed['defines'].append(stripped)
                # Extract pin assignments
                pin_match = re.search(r'#define\s+(\w+)\s+(\d+|[A-Z]\d+)', stripped)
                if pin_match and ('PIN' in pin_match.group(1).upper() or 'LED' in pin_match.group(1).upper()):
                    parsed['pins_used'][pin_match.group(1)] = pin_match.group(2)

            # Track setup function
            elif 'void setup()' in stripped or 'void setup(' in stripped:
                in_setup = True
                brace_count = 0
            elif in_setup:
                if brace_count == 0 and stripped == '}':
                    in_setup = False
                elif stripped and not stripped.startswith('//'):
                    parsed['setup_code'].append(stripped)

            # Track loop function
            elif 'void loop()' in stripped or 'void loop(' in stripped:
                in_loop = True
                brace_count = 0
            elif in_loop:
                if brace_count == 0 and stripped == '}':
                    in_loop = False
                elif stripped and not stripped.startswith('//'):
                    parsed['loop_code'].append(stripped)

            # Global variables (before setup/loop)
            elif not in_setup and not in_loop and stripped:
                if not stripped.startswith('//') and not stripped.startswith('/*'):
                    # Check if it's a global variable declaration
                    if any(keyword in stripped for keyword in ['DHT', 'WiFi', 'Server', 'Client', 'Adafruit']):
                        parsed['globals'].append(stripped)

        return parsed

    def identify_component_from_code(self, code: str) -> List[str]:
        """Identify which components are used in the code"""
        components = []
        code_upper = code.upper()

        component_patterns = {
            'DHT22': ['DHT22', 'DHT_22', 'DHTTYPE DHT22'],
            'DHT11': ['DHT11', 'DHT_11', 'DHTTYPE DHT11'],
            'BME280': ['BME280', 'BME_280', 'ADAFRUIT_BME280'],
            'BMP180': ['BMP180', 'BMP_180', 'ADAFRUIT_BMP085'],
            'DS18B20': ['DS18B20', 'DALLAS', 'ONEWIRE'],
            'OLED': ['SSD1306', 'OLED', 'ADAFRUIT_SSD1306'],
            'LCD': ['LIQUIDCRYSTAL', 'LCD'],
            'SERVO': ['SERVO.H', 'SERVO '],
            'ESP8266': ['ESP8266', 'NODEMCU'],
            'ESP32': ['ESP32'],
            'NRF24': ['NRF24', 'RF24'],
            'PIR': ['PIR', 'MOTION'],
            'ULTRASONIC': ['ULTRASONIC', 'HC-SR04', 'HCSR04'],
        }

        for component, patterns in component_patterns.items():
            if any(pattern in code_upper for pattern in patterns):
                components.append(component)

        return components

    def build_template_from_examples(self, examples: List[CodeExample]) -> Dict:
        """Build a reusable template from multiple code examples"""
        if not examples:
            return {}

        # Find most common includes, setup steps, etc.
        all_includes = []
        all_setup = []
        all_loop = []
        all_libraries = []

        for ex in examples:
            all_includes.extend(ex.includes)
            all_setup.extend(ex.setup_code)
            all_loop.extend(ex.loop_code)
            all_libraries.extend(ex.libraries_needed)

        # Count frequency
        from collections import Counter
        include_counts = Counter(all_includes)
        setup_counts = Counter(all_setup)
        loop_counts = Counter(all_loop)
        library_counts = Counter(all_libraries)

        template = {
            'component': examples[0].component,
            'common_includes': [inc for inc, count in include_counts.most_common(5)],
            'common_setup': [code for code, count in setup_counts.most_common(10)],
            'common_loop': [code for code, count in loop_counts.most_common(10)],
            'required_libraries': [lib for lib, count in library_counts.most_common()],
            'example_count': len(examples),
            'sources': [{'name': ex.source_name, 'url': ex.source_url} for ex in examples]
        }

        return template

    def scrape_from_content(self, url: str, content: str, components: List[str], source_name: str) -> List[CodeExample]:
        """Process scraped content and extract code examples"""
        examples = []

        code_blocks = self.extract_code_blocks(content)

        for code_block in code_blocks:
            # Only process blocks that look like Arduino code
            if not ('#include' in code_block or 'void setup' in code_block or 'void loop' in code_block):
                continue

            # Parse the code
            parsed = self.parse_arduino_code(code_block)

            # Identify components
            detected_components = self.identify_component_from_code(code_block)

            # Create example for each detected component
            for component in detected_components:
                example = CodeExample(
                    component=component,
                    source_url=url,
                    source_name=source_name,
                    full_code=code_block,
                    includes=parsed['includes'],
                    defines=parsed['defines'],
                    globals=parsed['globals'],
                    setup_code=parsed['setup_code'],
                    loop_code=parsed['loop_code'],
                    libraries_needed=parsed['libraries_needed'],
                    pins_used=parsed['pins_used'],
                    description=f"{component} example from {source_name}"
                )
                examples.append(example)

        return examples

    def save_examples(self, examples: List[CodeExample], filename: str = "scraped_examples.json"):
        """Save examples to cache"""
        cache_file = self.cache_dir / filename

        data = [asdict(ex) for ex in examples]

        with open(cache_file, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"✓ Saved {len(examples)} examples to {cache_file}")

    def load_examples(self, filename: str = "scraped_examples.json") -> List[CodeExample]:
        """Load examples from cache"""
        cache_file = self.cache_dir / filename

        if not cache_file.exists():
            return []

        with open(cache_file, 'r') as f:
            data = json.load(f)

        examples = [CodeExample(**ex) for ex in data]
        print(f"✓ Loaded {len(examples)} examples from cache")

        return examples

    def build_template_library(self, examples: List[CodeExample]) -> Dict[str, Dict]:
        """Build template library organized by component"""
        templates = {}

        # Group examples by component
        by_component = {}
        for ex in examples:
            if ex.component not in by_component:
                by_component[ex.component] = []
            by_component[ex.component].append(ex)

        # Build template for each component
        for component, comp_examples in by_component.items():
            templates[component] = self.build_template_from_examples(comp_examples)

        return templates

    def save_template_library(self, templates: Dict, filename: str = "code_templates.json"):
        """Save template library"""
        cache_file = self.cache_dir / filename

        with open(cache_file, 'w') as f:
            json.dump(templates, f, indent=2)

        print(f"✓ Saved {len(templates)} component templates to {cache_file}")


def demo_scraper_with_sample():
    """Demo the scraper with sample content"""
    print("="*70)
    print("  CODE LIBRARY SCRAPER - Demo with Sample Content")
    print("="*70)
    print()

    scraper = CodeLibraryScraper()

    # Sample content that looks like a tutorial
    sample_content = """
    # ESP32 with DHT22 Temperature Sensor Tutorial

    Here's the complete code for reading temperature with ESP32:

    ```cpp
    #include <DHT.h>

    #define DHTPIN 4
    #define DHTTYPE DHT22

    DHT dht(DHTPIN, DHTTYPE);

    void setup() {
      Serial.begin(115200);
      Serial.println("DHT22 test!");
      dht.begin();
    }

    void loop() {
      delay(2000);

      float h = dht.readHumidity();
      float t = dht.readTemperature();

      if (isnan(h) || isnan(t)) {
        Serial.println("Failed to read from DHT sensor!");
        return;
      }

      Serial.print("Humidity: ");
      Serial.print(h);
      Serial.print("%  Temperature: ");
      Serial.print(t);
      Serial.println("°C");
    }
    ```

    Upload this code to your ESP32!
    """

    print("Processing sample tutorial content...")
    examples = scraper.scrape_from_content(
        url="https://example.com/esp32-dht22",
        content=sample_content,
        components=['ESP32', 'DHT22'],
        source_name="Sample Tutorial"
    )

    print(f"\n✓ Extracted {len(examples)} code examples")

    for i, ex in enumerate(examples, 1):
        print(f"\n--- Example {i}: {ex.component} ---")
        print(f"Source: {ex.source_name}")
        print(f"Includes: {ex.includes}")
        print(f"Libraries needed: {ex.libraries_needed}")
        print(f"Pins used: {ex.pins_used}")
        print(f"Setup steps: {len(ex.setup_code)} lines")
        print(f"Loop code: {len(ex.loop_code)} lines")

    # Build template
    print("\n" + "="*70)
    print("Building template library...")
    templates = scraper.build_template_library(examples)

    for component, template in templates.items():
        print(f"\n--- Template for {component} ---")
        print(f"Based on {template['example_count']} examples")
        print(f"Common includes: {template['common_includes']}")
        print(f"Required libraries: {template['required_libraries']}")
        print(f"Common setup steps:")
        for step in template['common_setup'][:5]:
            print(f"  - {step}")

    # Save
    scraper.save_examples(examples, "demo_examples.json")
    scraper.save_template_library(templates, "demo_templates.json")

    print("\n" + "="*70)
    print("✓ Demo complete! Templates saved to data/code_cache/")
    print("="*70)


if __name__ == '__main__':
    demo_scraper_with_sample()
