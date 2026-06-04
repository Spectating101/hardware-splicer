#!/usr/bin/env python3
"""
Populate component database with ElectroCom61 component data.
"""

import sys
import sqlite3
from pathlib import Path
from loguru import logger
import yaml

# Component descriptions and educational info
COMPONENT_INFO = {
    '1-5-Volt-Battery': {
        'category': 'Power Supply',
        'description': 'Standard 1.5V battery, commonly AA/AAA size. Powers low-voltage circuits.',
        'educational_value': 8.5,
        'market_value': 0.5,
        'applications': ['LED circuits', 'Small motors', 'Basic electronics projects']
    },
    '3-3-Volt-Battery': {
        'category': 'Power Supply',
        'description': '3.3V power source, common in IoT and embedded systems.',
        'educational_value': 8.0,
        'market_value': 1.0,
        'applications': ['ESP32 projects', 'Low-power sensors', 'Coin cell circuits']
    },
    '7-Segment-Display': {
        'category': 'Display',
        'description': 'LED display showing digits 0-9, used for counters and clocks.',
        'educational_value': 9.0,
        'market_value': 2.0,
        'applications': ['Digital clocks', 'Counters', 'Temperature displays']
    },
    '9-Volt-Battery': {
        'category': 'Power Supply',
        'description': '9V battery, ideal for higher voltage circuits and testing.',
        'educational_value': 8.0,
        'market_value': 2.0,
        'applications': ['Guitar pedals', 'Smoke detectors', 'General prototyping']
    },
    'Arduino-Mega': {
        'category': 'Microcontroller',
        'description': 'Arduino Mega 2560 - powerful microcontroller with 54 I/O pins.',
        'educational_value': 10.0,
        'market_value': 25.0,
        'applications': ['Complex robots', '3D printers', 'Large IoT projects']
    },
    'Arduino-Nano': {
        'category': 'Microcontroller',
        'description': 'Compact Arduino board, perfect for small embedded projects.',
        'educational_value': 10.0,
        'market_value': 5.0,
        'applications': ['Wearables', 'Small robots', 'Sensor networks']
    },
    'Arduino-Uno': {
        'category': 'Microcontroller',
        'description': 'Most popular Arduino board for beginners and education.',
        'educational_value': 10.0,
        'market_value': 15.0,
        'applications': ['Learning programming', 'Home automation', 'Basic robotics']
    },
    'BJT-Transistor': {
        'category': 'Semiconductor',
        'description': 'Bipolar Junction Transistor - for switching and amplification.',
        'educational_value': 9.5,
        'market_value': 0.10,
        'applications': ['Amplifiers', 'Switches', 'Signal processing']
    },
    'Bluetooth-Module': {
        'category': 'Communication',
        'description': 'Wireless Bluetooth module (HC-05/HC-06) for serial communication.',
        'educational_value': 9.0,
        'market_value': 5.0,
        'applications': ['Wireless control', 'Data logging', 'IoT connectivity']
    },
    'Breadboard': {
        'category': 'Prototyping',
        'description': 'Solderless prototyping board for testing circuits.',
        'educational_value': 10.0,
        'market_value': 3.0,
        'applications': ['Circuit testing', 'Rapid prototyping', 'Learning electronics']
    },
    'Bridge-Rectifier': {
        'category': 'Power',
        'description': 'Converts AC to DC using 4 diodes in bridge configuration.',
        'educational_value': 8.5,
        'market_value': 1.0,
        'applications': ['Power supplies', 'AC-DC conversion', 'Battery chargers']
    },
    'Buck-Converter': {
        'category': 'Power',
        'description': 'Step-down DC-DC converter, reduces voltage efficiently.',
        'educational_value': 8.0,
        'market_value': 3.0,
        'applications': ['Battery projects', 'Voltage regulation', 'Power management']
    },
    'Buzzer': {
        'category': 'Output',
        'description': 'Audio output device for alarms and notifications.',
        'educational_value': 7.5,
        'market_value': 0.50,
        'applications': ['Alarms', 'Game sounds', 'Notification systems']
    },
    'Capacitor-10mf': {
        'category': 'Passive',
        'description': '10μF electrolytic capacitor for filtering and energy storage.',
        'educational_value': 8.5,
        'market_value': 0.20,
        'applications': ['Power filtering', 'Timing circuits', 'Audio coupling']
    },
    'Capacitor-470mf': {
        'category': 'Passive',
        'description': '470μF large capacitor for power supply filtering.',
        'educational_value': 8.0,
        'market_value': 0.50,
        'applications': ['Power supplies', 'Motor smoothing', 'Energy storage']
    },
    'DC-Motor': {
        'category': 'Actuator',
        'description': 'DC motor for mechanical movement and robotics.',
        'educational_value': 9.0,
        'market_value': 2.0,
        'applications': ['Robots', 'Fans', 'Conveyor belts']
    },
    'Diode': {
        'category': 'Semiconductor',
        'description': 'One-way current flow component, essential for circuit protection.',
        'educational_value': 9.0,
        'market_value': 0.10,
        'applications': ['Rectification', 'Protection', 'Signal routing']
    },
    'ESP32': {
        'category': 'Microcontroller',
        'description': 'Powerful WiFi/Bluetooth microcontroller for IoT projects.',
        'educational_value': 10.0,
        'market_value': 8.0,
        'applications': ['IoT devices', 'Web servers', 'Wireless sensors']
    },
    'ESP32-CAM': {
        'category': 'Microcontroller',
        'description': 'ESP32 with integrated camera for vision projects.',
        'educational_value': 9.5,
        'market_value': 10.0,
        'applications': ['Security cameras', 'Face detection', 'Image capture']
    },
    'Resistor': {
        'category': 'Passive',
        'description': 'Current-limiting component, fundamental in all circuits.',
        'educational_value': 10.0,
        'market_value': 0.05,
        'applications': ['Voltage dividers', 'Current limiting', 'Pull-up/down']
    },
    'LED-Light': {
        'category': 'Output',
        'description': 'Light Emitting Diode for visual indicators.',
        'educational_value': 9.5,
        'market_value': 0.10,
        'applications': ['Indicators', 'Displays', 'Lighting projects']
    },
    'LCD-Display': {
        'category': 'Display',
        'description': 'Liquid Crystal Display (16x2 or 20x4) for text output.',
        'educational_value': 9.0,
        'market_value': 3.0,
        'applications': ['Status display', 'Menus', 'Data visualization']
    },
    'OLED-Display': {
        'category': 'Display',
        'description': 'High-contrast OLED display for graphics and text.',
        'educational_value': 9.0,
        'market_value': 5.0,
        'applications': ['Wearables', 'Small displays', 'Graphics projects']
    },
    'Relay-Module': {
        'category': 'Switching',
        'description': 'Electrically controlled switch for high-power loads.',
        'educational_value': 8.5,
        'market_value': 2.0,
        'applications': ['Home automation', 'Motor control', 'Power switching']
    },
    'Servo-Motor': {
        'category': 'Actuator',
        'description': 'Precision motor with position feedback for robotics.',
        'educational_value': 9.5,
        'market_value': 3.0,
        'applications': ['Robot arms', 'Pan-tilt', 'Precise positioning']
    },
    'Motor-Driver': {
        'category': 'Driver',
        'description': 'H-bridge motor driver (L298N/L293D) for DC motor control.',
        'educational_value': 9.0,
        'market_value': 2.0,
        'applications': ['Robot wheels', 'Motor speed control', 'Direction control']
    }
}

def create_database():
    """Create SQLite database with component schema."""

    db_path = Path("data/circuit_ai.db")
    db_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"📦 Creating database at: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create components table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS components (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            category TEXT,
            description TEXT,
            educational_value REAL,
            market_value REAL,
            applications TEXT,
            datasheet_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    logger.info("✅ Database schema created")

    return conn

def populate_components(conn):
    """Populate database with component information."""

    cursor = conn.cursor()

    # Read component names from data.yaml
    yaml_path = Path("datasets/electrocom61_full/data.yaml")
    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    component_names = data.get('names', [])
    logger.info(f"📋 Found {len(component_names)} components in dataset")

    inserted = 0
    for name in component_names:
        # Get component info or use defaults
        info = COMPONENT_INFO.get(name, {
            'category': 'Unknown',
            'description': f'{name} - Electronic component',
            'educational_value': 5.0,
            'market_value': 1.0,
            'applications': ['General electronics']
        })

        try:
            cursor.execute("""
                INSERT OR IGNORE INTO components
                (name, category, description, educational_value, market_value, applications)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                name,
                info['category'],
                info['description'],
                info['educational_value'],
                info['market_value'],
                ', '.join(info['applications'])
            ))

            if cursor.rowcount > 0:
                inserted += 1

        except Exception as e:
            logger.warning(f"⚠️  Failed to insert {name}: {e}")

    conn.commit()
    logger.info(f"✅ Inserted {inserted} new components")

    # Show stats
    cursor.execute("SELECT COUNT(*) FROM components")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT category, COUNT(*) FROM components GROUP BY category")
    categories = cursor.fetchall()

    logger.info(f"\n📊 Database Statistics:")
    logger.info(f"   Total components: {total}")
    logger.info(f"   Categories:")
    for cat, count in categories:
        logger.info(f"      {cat}: {count}")

if __name__ == "__main__":
    logger.info("🚀 Component Database Population")
    logger.info("=" * 60)

    try:
        conn = create_database()
        populate_components(conn)
        conn.close()

        logger.info("\n✅ Component database ready!")
        logger.info("\nYou can now:")
        logger.info("1. Query components via API: GET /v1/components")
        logger.info("2. Search by category")
        logger.info("3. Get educational recommendations")

    except Exception as e:
        logger.error(f"❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
