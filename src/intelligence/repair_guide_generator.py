#!/usr/bin/env python3
"""
Repair Guide Generator
Creates step-by-step repair guides for phones, laptops, and consumer electronics
Integrates with visual fault detection for diagnostic assistance
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum


class DeviceType(Enum):
    """Supported device types."""
    IPHONE = "iphone"
    ANDROID = "android"
    LAPTOP = "laptop"
    TABLET = "tablet"
    MACBOOK = "macbook"


class IssueCategory(Enum):
    """Categories of repair issues."""
    SCREEN = "screen"
    BATTERY = "battery"
    CHARGING = "charging"
    AUDIO = "audio"
    CAMERA = "camera"
    BUTTONS = "buttons"
    WATER_DAMAGE = "water_damage"
    PERFORMANCE = "performance"
    CONNECTIVITY = "connectivity"


@dataclass
class RepairDifficulty:
    """Repair difficulty levels."""
    EASY = "easy"  # No soldering, basic tools
    MEDIUM = "medium"  # Some disassembly, specialized tools
    HARD = "hard"  # Soldering, micro components
    EXPERT = "expert"  # Board-level repair, microsoldering


class RepairGuideGenerator:
    """Generates step-by-step repair guides for consumer electronics."""

    def __init__(self):
        """Initialize repair guide generator."""
        self.guides = self._load_repair_guides()

    def _load_repair_guides(self) -> Dict:
        """Load repair guide templates."""
        return {
            # iPhone Issues
            'iPhone Screen Replacement': self._iphone_screen_replacement,
            'iPhone Battery Replacement': self._iphone_battery_replacement,
            'iPhone Charging Port': self._iphone_charging_port,
            'iPhone Water Damage': self._iphone_water_damage,
            'iPhone Camera Not Working': self._iphone_camera_repair,

            # Android/Samsung Issues
            'Samsung Screen Replacement': self._samsung_screen_replacement,
            'Android Battery Swelling': self._android_battery_swelling,

            # Laptop Issues
            'Laptop Screen Replacement': self._laptop_screen_replacement,
            'Laptop Not Charging': self._laptop_not_charging,
            'Laptop Overheating': self._laptop_overheating,
            'Laptop Keyboard Replacement': self._laptop_keyboard_replacement,
            'Laptop SSD/RAM Upgrade': self._laptop_ssd_ram_upgrade,
        }

    def list_available_guides(self) -> List[str]:
        """List all available repair guides."""
        return list(self.guides.keys())

    def generate_repair_guide(self, issue: str, device_model: str = None) -> Dict:
        """
        Generate complete repair guide for an issue.

        Args:
            issue: Type of issue (e.g., "iPhone Screen Replacement")
            device_model: Specific model if known (e.g., "iPhone 12")

        Returns:
            Dict with complete repair instructions
        """
        if issue in self.guides:
            guide = self.guides[issue]()
            if device_model:
                guide['device_model'] = device_model
            return guide
        else:
            return self._generate_generic_repair_guide(issue, device_model)

    def _iphone_screen_replacement(self) -> Dict:
        """Repair guide for iPhone screen replacement."""
        return {
            'issue_name': 'iPhone Screen Replacement',
            'device_type': 'iPhone',
            'category': 'screen',
            'difficulty': 'medium',
            'repair_time': '30-45 minutes',
            'skill_level': 'Intermediate',

            'symptoms': [
                'Cracked or shattered screen',
                'Display not responding to touch',
                'Dead pixels or lines on screen',
                'Screen completely black but phone works (can hear sounds)',
                'Touch working in some areas but not others'
            ],

            'tools_needed': [
                'Pentalobe screwdriver (P2)',
                'Tri-point screwdriver (Y000)',
                'Plastic opening picks',
                'Suction cup',
                'Tweezers',
                'Heat gun or hair dryer',
                'iSesamo or metal spudger',
                'Replacement screen assembly'
            ],

            'parts_needed': [
                {
                    'name': 'Replacement Screen Assembly (OLED)',
                    'cost_range': '$30-150',
                    'notes': 'Varies by iPhone model. OEM quality recommended.',
                    'where_to_buy': 'iFixit, Amazon, Mobile Defenders, Injured Gadgets'
                }
            ],

            'warnings': [
                '⚠️ Disconnect battery before working on screen to avoid shorts',
                '⚠️ Be gentle with ribbon cables - they tear easily',
                '⚠️ iPhone 12+ has magnets that can affect compass - recalibrate after repair',
                '⚠️ Face ID will be disabled if front camera cable is damaged',
                '⚠️ Work in a clean, well-lit area to avoid losing tiny screws',
                '⚠️ Use heat carefully - too much can damage LCD/OLED'
            ],

            'steps': [
                {
                    'number': 1,
                    'title': 'Power Off and Remove SIM Tray',
                    'description': 'Turn off iPhone completely. Use SIM ejector tool to remove SIM tray. This prevents accidental shorts.',
                    'time': '1 minute',
                    'tips': [
                        'Hold power button + volume down for iPhone X+',
                        'Slide to power off',
                        'Wait 30 seconds before proceeding'
                    ],
                    'image_reference': 'iphone_power_off.jpg'
                },
                {
                    'number': 2,
                    'title': 'Remove Bottom Pentalobe Screws',
                    'description': 'Use P2 Pentalobe screwdriver to remove the two screws at the bottom of the iPhone (next to charging port).',
                    'time': '1 minute',
                    'tools': ['P2 Pentalobe screwdriver'],
                    'tips': [
                        'These screws are 3.9mm long',
                        'Keep screws organized - use magnetic mat',
                        'Do not mix up screws from different steps'
                    ]
                },
                {
                    'number': 3,
                    'title': 'Apply Heat to Loosen Adhesive',
                    'description': 'Use heat gun or hair dryer to warm the edges of the screen for 1-2 minutes. This softens the waterproof adhesive.',
                    'time': '2 minutes',
                    'tools': ['Heat gun or hair dryer'],
                    'tips': [
                        'Heat to about 80°C (uncomfortable to touch but not burning)',
                        'Focus on bottom and sides',
                        'Do not overheat - LCD can get damaged',
                        'Move heat source constantly to avoid hot spots'
                    ],
                    'warnings': [
                        '⚠️ Too much heat can damage battery or screen'
                    ]
                },
                {
                    'number': 4,
                    'title': 'Create Initial Gap with Suction Cup',
                    'description': 'Place suction cup on lower half of screen. Pull up gently while holding the phone body. Insert opening pick into the gap.',
                    'time': '3 minutes',
                    'tools': ['Suction cup', 'Opening pick'],
                    'tips': [
                        'Pull at a slight angle, not straight up',
                        'You need only 1-2mm gap to insert pick',
                        'If adhesive is strong, apply more heat',
                        'For iPhone X+, avoid the curved edges at first'
                    ]
                },
                {
                    'number': 5,
                    'title': 'Slice Through Adhesive',
                    'description': 'Slide opening pick around the edges of the phone to cut through adhesive. Work slowly and carefully around corners.',
                    'time': '5 minutes',
                    'tools': ['Opening picks'],
                    'tips': [
                        'Leave picks in place as you go to prevent re-sealing',
                        'Use multiple picks for better control',
                        'Do NOT insert pick more than 3mm deep',
                        'Be extra careful around top (Face ID sensors)',
                        'Do NOT try to fully separate yet - cables are still connected!'
                    ],
                    'warnings': [
                        '⚠️ Do not insert too deep - can damage cables underneath',
                        '⚠️ Do not open from top hinge - cables connect there'
                    ]
                },
                {
                    'number': 6,
                    'title': 'Open Screen Like a Book (Right Side Hinge)',
                    'description': 'With adhesive cut, gently swing screen open from the LEFT side, keeping RIGHT side as hinge. Open to about 90 degrees. Display cables are on the right.',
                    'time': '1 minute',
                    'tips': [
                        'Think of it like opening a book',
                        'Do not open past 90 degrees - cables will stretch',
                        'Use a box or soft surface to rest screen on',
                        'Be mindful of the ribbon cables'
                    ],
                    'warnings': [
                        '⚠️ Do not force - cables can tear'
                    ]
                },
                {
                    'number': 7,
                    'title': 'Disconnect Battery',
                    'description': 'Remove the metal plate covering battery connector (usually 1-2 tri-point or Phillips screws). Use spudger to disconnect battery connector.',
                    'time': '2 minutes',
                    'tools': ['Y000 tri-point or Phillips #000', 'Spudger'],
                    'tips': [
                        'This is a safety step - always disconnect battery first',
                        'Gently pry up the connector, not the socket',
                        'Keep screws organized by step'
                    ],
                    'warnings': [
                        '⚠️ CRITICAL: This prevents shorts during repair'
                    ]
                },
                {
                    'number': 8,
                    'title': 'Disconnect Display Cables',
                    'description': 'Remove metal shield covering display connectors (3-5 screws). Disconnect display cables: digitizer, LCD, and home button/front camera (varies by model).',
                    'time': '3 minutes',
                    'tools': ['Y000 tri-point or Phillips #000', 'Spudger'],
                    'tips': [
                        'Typically 3-4 connectors under the shield',
                        'Disconnect in this order: Battery → Digitizer → LCD → Sensors',
                        'Use spudger or fingernail, not metal tools',
                        'Connectors pop straight up - do not pry sideways',
                        'Take a photo before disconnecting to remember order'
                    ],
                    'warnings': [
                        '⚠️ Be very gentle - these connectors are fragile',
                        '⚠️ Damaging front camera/sensor flex = Face ID disabled permanently'
                    ]
                },
                {
                    'number': 9,
                    'title': 'Remove Old Screen',
                    'description': 'Once all cables are disconnected, lift away the broken screen. Inspect for any remaining parts that need transfer.',
                    'time': '1 minute',
                    'tips': [
                        'Set aside carefully',
                        'Check for any components that may need transfer:',
                        '  - Home button (iPhone 7/8 - for Touch ID)',
                        '  - Front camera/sensor assembly (iPhone X+ - for Face ID)',
                        '  - Earpiece speaker',
                        '  - Proximity sensor'
                    ]
                },
                {
                    'number': 10,
                    'title': 'Transfer Components to New Screen',
                    'description': 'Transfer home button (if applicable), front camera assembly, earpiece speaker, and any other components from old screen to new screen.',
                    'time': '5-10 minutes',
                    'tools': ['Tweezers', 'Screwdrivers'],
                    'tips': [
                        'For iPhone 7/8: MUST transfer home button or Touch ID will not work',
                        'For iPhone X+: Transfer front camera/sensor assembly carefully',
                        'Remove protective films from new screen connectors',
                        'Ensure all screws are returned to exact positions',
                        'Components are usually held by 2-4 tiny screws'
                    ],
                    'warnings': [
                        '⚠️ iPhone 7/8: Home button is paired to logic board - replacements will not work',
                        '⚠️ iPhone X+: Face ID is paired - replacement sensors will disable Face ID'
                    ]
                },
                {
                    'number': 11,
                    'title': 'Connect New Screen',
                    'description': 'Connect new screen cables in reverse order: Sensors → LCD → Digitizer. Replace metal shield and screws.',
                    'time': '3 minutes',
                    'tools': ['Screwdrivers'],
                    'tips': [
                        'Connectors should snap into place easily',
                        'If resistance, check alignment - do not force',
                        'Ensure cables are seated fully and evenly',
                        'Replace shield before testing'
                    ]
                },
                {
                    'number': 12,
                    'title': 'Reconnect Battery and Test',
                    'description': 'Reconnect battery connector. Turn on phone and test screen functionality BEFORE sealing.',
                    'time': '3 minutes',
                    'testing_checklist': [
                        'Screen displays correctly',
                        'Touch response works everywhere',
                        'No dead pixels or lines',
                        'Brightness adjustment works',
                        'Face ID or Touch ID works (if applicable)',
                        'Front camera works',
                        'Proximity sensor works (screen turns off during calls)',
                        'Earpiece speaker works'
                    ],
                    'tips': [
                        'Test thoroughly before sealing',
                        'If something does not work, recheck cable connections',
                        'Screen may show "Important Display Message" - normal for non-OEM'
                    ]
                },
                {
                    'number': 13,
                    'title': 'Apply New Adhesive',
                    'description': 'Clean old adhesive residue. Apply new adhesive strips around edges of phone.',
                    'time': '5 minutes',
                    'tools': ['Isopropyl alcohol', 'Adhesive strips'],
                    'tips': [
                        'Pre-cut adhesive strips available from repair suppliers',
                        'Clean both phone frame and screen edges',
                        'Adhesive placement is critical for water resistance',
                        'Some opt for liquid adhesive (B-7000) instead of strips'
                    ]
                },
                {
                    'number': 14,
                    'title': 'Seal Screen and Replace Screws',
                    'description': 'Carefully close screen, ensuring no cables are pinched. Apply pressure around edges to seal adhesive. Replace bottom Pentalobe screws.',
                    'time': '2 minutes',
                    'tips': [
                        'Start from top, work down to bottom',
                        'Apply even pressure around all edges',
                        'Use clamp or books for 1-2 hours for best seal',
                        'Replace SIM tray'
                    ]
                },
                {
                    'number': 15,
                    'title': 'Final Testing and Calibration',
                    'description': 'Power on and perform complete functionality test. Recalibrate compass if iPhone 12+.',
                    'time': '5 minutes',
                    'testing_checklist': [
                        'All screen functions',
                        'Biometrics (Face ID / Touch ID)',
                        'Cameras (front and rear)',
                        'Compass calibration (iPhone 12+ with MagSafe)',
                        'True Tone (may need software recalibration)',
                        'Waterproof seal test (optional - submerge test strip)'
                    ],
                    'tips': [
                        'For compass: Open Compass app, follow calibration prompts',
                        'True Tone may not work without original screen or programmer',
                        'Test waterproofing with water detection stickers before real use'
                    ]
                }
            ],

            'total_repair_time': '30-45 minutes',
            'estimated_cost': '$30-150 for screen',

            'common_mistakes': [
                'Not disconnecting battery first (risk of short circuit)',
                'Forcing cables (causes permanent damage)',
                'Mixing up screws (wrong length can damage logic board)',
                'Forgetting to transfer home button or sensors',
                'Over-heating during adhesive removal',
                'Not testing before sealing',
                'Damaging Face ID/Touch ID components'
            ],

            'troubleshooting': {
                'Screen not turning on': [
                    'Recheck all cable connections',
                    'Ensure battery is charged',
                    'Try disconnecting and reconnecting battery',
                    'Check if backlight works (shine flashlight on screen in dark room)'
                ],
                'Touch not working': [
                    'Reconnect digitizer cable',
                    'Check for damage to digitizer flex cable',
                    'May be defective replacement screen'
                ],
                'Face ID not working': [
                    'Ensure front camera/sensor assembly was transferred correctly',
                    'Check flood illuminator and dot projector alignment',
                    'If still not working, sensors may be damaged (Face ID disabled permanently)'
                ],
                'Important Display Message': [
                    'Normal for non-OEM screens',
                    'Message will appear for 1-2 weeks then disappear',
                    'Does not affect functionality'
                ]
            },

            'professional_tips': [
                'Use anti-static mat and wrist strap',
                'Keep workspace organized with magnetic mat for screws',
                'Take photos at each step for reference',
                'Test screen before final assembly',
                'Consider aftermarket screen quality: OEM > OEM-Quality > Aftermarket Basic',
                'OEM screens support True Tone and have better color accuracy',
                'Budget screens ($30-50) may have lower brightness or touch sensitivity'
            ],

            'prevention': [
                'Use screen protector (tempered glass recommended)',
                'Use protective case',
                'Avoid drops (obvious but important)',
                'Keep phone away from extreme temperatures',
                'Do not place heavy objects on phone'
            ],

            'additional_resources': [
                'iFixit iPhone Screen Replacement Guides (specific models)',
                'YouTube: JerryRigEverything, Hugh Jeffreys (detailed teardowns)',
                'r/mobilerepair subreddit for troubleshooting',
                'Parts suppliers: iFixit, Mobile Defenders, Injured Gadgets, Wholesale Gadget Parts'
            ],

            'warranty_notes': [
                'DIY repair voids Apple warranty',
                'Apple will refuse service on modified devices',
                'Consider AppleCare+ if under warranty',
                'Third-party repair may be cheaper than Apple ($279+ for out-of-warranty screen)'
            ]
        }

    def _iphone_battery_replacement(self) -> Dict:
        """Repair guide for iPhone battery replacement."""
        return {
            'issue_name': 'iPhone Battery Replacement',
            'device_type': 'iPhone',
            'category': 'battery',
            'difficulty': 'medium',
            'repair_time': '20-40 minutes',
            'skill_level': 'Intermediate',

            'symptoms': [
                'Battery drains quickly (< 4 hours screen-on time)',
                'Phone shuts down at 20-30% battery',
                'Battery swelling (screen lifting, back bulging)',
                'Maximum capacity < 80% (Settings > Battery > Battery Health)',
                'Phone getting hot during charging',
                'Slow performance (throttling due to weak battery)',
                '"Service" message in Battery Health'
            ],

            'tools_needed': [
                'Pentalobe screwdriver (P2)',
                'Tri-point screwdriver (Y000)',
                'Phillips #000 screwdriver',
                'Plastic opening picks',
                'Suction cup',
                'Tweezers',
                'iSesamo or metal spudger',
                'Heat gun or hair dryer (for adhesive removal)',
                'Playing card or plastic card (for battery adhesive)',
                'Replacement battery',
                'Isopropyl alcohol 90%+ (optional, for stubborn adhesive)'
            ],

            'parts_needed': [
                {
                    'name': 'Replacement Battery (OEM quality)',
                    'cost_range': '$15-40',
                    'notes': 'Match exact model. Check capacity (mAh). OEM quality recommended for safety.',
                    'where_to_buy': 'iFixit, Amazon (AmazonBasics batteries), Mobile Sentrix, Injured Gadgets'
                }
            ],

            'warnings': [
                '⚠️ FIRE HAZARD: Damaged lithium battery can catch fire or explode',
                '⚠️ Do NOT puncture battery with tools',
                '⚠️ If battery is swollen, DO NOT bend or apply pressure',
                '⚠️ Work in well-ventilated area',
                '⚠️ Have fire extinguisher nearby (Type D for lithium fires)',
                '⚠️ Do NOT use sharp tools near battery',
                '⚠️ Dispose of old battery properly at electronics recycling center',
                '⚠️ Never throw lithium batteries in regular trash'
            ],

            'steps': [
                {
                    'number': 1,
                    'title': 'Discharge Battery Below 25%',
                    'description': 'Before starting, use phone until battery is below 25%. This reduces fire risk if battery is accidentally punctured.',
                    'time': 'Varies',
                    'tips': [
                        'Lower charge = less stored energy = safer',
                        'If phone will not turn on (battery dead), proceed carefully'
                    ],
                    'warnings': [
                        '⚠️ CRITICAL SAFETY STEP'
                    ]
                },
                {
                    'number': 2,
                    'title': 'Open iPhone (Follow Screen Removal Steps 1-6)',
                    'description': 'Follow iPhone screen removal steps 1-6 from screen replacement guide: Remove pentalobe screws, heat adhesive, open phone like a book.',
                    'time': '10 minutes',
                    'reference': 'See "iPhone Screen Replacement" guide for detailed instructions',
                    'tips': [
                        'You do not need to fully remove screen',
                        'Just open to access battery connector',
                        'Prop screen at 90 degrees with a box'
                    ]
                },
                {
                    'number': 3,
                    'title': 'Disconnect Battery Connector',
                    'description': 'Remove metal bracket covering battery connector. Use spudger to disconnect battery.',
                    'time': '2 minutes',
                    'tools': ['Y000 or Phillips #000', 'Spudger'],
                    'tips': [
                        'Always disconnect battery FIRST',
                        'Pry connector straight up, not sideways',
                        'Keep screws organized'
                    ]
                },
                {
                    'number': 4,
                    'title': 'Disconnect Display (Optional but Recommended)',
                    'description': 'For easier access, disconnect display cables and fully remove screen.',
                    'time': '3 minutes',
                    'tips': [
                        'Makes battery removal much easier',
                        'Prevents cable damage while maneuvering',
                        'See screen replacement guide for details'
                    ]
                },
                {
                    'number': 5,
                    'title': 'Locate Battery Adhesive Pull Tabs',
                    'description': 'Battery is held by 2-4 adhesive strips with white or black pull tabs at the bottom. Identify these tabs.',
                    'time': '1 minute',
                    'tips': [
                        'Tabs are usually at bottom edge of battery',
                        'May be hidden under battery flex cable'
                    ]
                },
                {
                    'number': 6,
                    'title': 'Pull Adhesive Strips',
                    'description': 'Gently pull each adhesive strip at a low angle (almost parallel to battery). Pull slowly and steadily. Strips will stretch and come out.',
                    'time': '5-10 minutes',
                    'tools': ['Tweezers'],
                    'tips': [
                        'Pull at LOW angle (15-20 degrees)',
                        'Pull SLOWLY - if you go fast, strips will tear',
                        'If strip tears, proceed to Plan B (next step)',
                        'Expect strips to stretch 10-20x their original length',
                        'This is the hardest part - be patient!'
                    ],
                    'warnings': [
                        '⚠️ Do NOT pull straight up - strips will tear',
                        '⚠️ If strip tears, DO NOT pry battery with metal tools'
                    ]
                },
                {
                    'number': 7,
                    'title': 'Plan B: Heat and Card Method (If Strips Tore)',
                    'description': 'If adhesive strips tore, apply heat to back of iPhone (where battery is). Use plastic card to slowly work under battery edge and lift.',
                    'time': '10-15 minutes',
                    'tools': ['Heat gun or hair dryer', 'Plastic card', 'Isopropyl alcohol (optional)'],
                    'tips': [
                        'Heat back of phone to 60-80°C (warm to touch)',
                        'Apply heat for 2-3 minutes',
                        'Use flexible plastic card (credit card, guitar pick)',
                        'Work from side edges, NOT center',
                        'Apply alcohol with syringe under battery to dissolve adhesive',
                        'Be VERY patient - this can take 15-20 minutes'
                    ],
                    'warnings': [
                        '⚠️ NEVER use metal tools - will puncture battery',
                        '⚠️ Do NOT bend battery - swollen batteries can ignite',
                        '⚠️ If battery is hot, STOP and let it cool'
                    ]
                },
                {
                    'number': 8,
                    'title': 'Remove Old Battery',
                    'description': 'Once adhesive is released, lift battery out. Disconnect battery flex cable if not already done.',
                    'time': '1 minute',
                    'tips': [
                        'Lift from bottom edge',
                        'Battery should come out freely',
                        'Do not force if still stuck - more heat needed'
                    ]
                },
                {
                    'number': 9,
                    'title': 'Clean Adhesive Residue',
                    'description': 'Remove old adhesive from battery cavity using isopropyl alcohol and plastic scraper.',
                    'time': '5 minutes',
                    'tools': ['Isopropyl alcohol 90%+', 'Plastic scraper or card'],
                    'tips': [
                        'Clean surface ensures new battery sits flat',
                        'Use alcohol sparingly - let it evaporate fully before installing new battery',
                        'Wipe with lint-free cloth'
                    ]
                },
                {
                    'number': 10,
                    'title': 'Prepare New Battery',
                    'description': 'Remove protective covering from new battery. Check that battery capacity and voltage match original.',
                    'time': '1 minute',
                    'tips': [
                        'Verify voltage: Usually 3.8V or 3.85V',
                        'Verify capacity matches or exceeds original (mAh)',
                        'Quality batteries include new adhesive strips',
                        'Some batteries come with connector pre-attached'
                    ]
                },
                {
                    'number': 11,
                    'title': 'Install New Battery Adhesive',
                    'description': 'Apply new adhesive strips to battery cavity (or to back of new battery if strips came pre-attached).',
                    'time': '2 minutes',
                    'tips': [
                        'Align adhesive carefully',
                        'Ensure pull tabs are accessible at bottom',
                        'Do not remove protective layer yet'
                    ]
                },
                {
                    'number': 12,
                    'title': 'Install New Battery',
                    'description': 'Remove adhesive protective layer. Carefully lower new battery into cavity. Press firmly to secure adhesive.',
                    'time': '2 minutes',
                    'tips': [
                        'Align battery connector with socket',
                        'Lower straight down - no sliding',
                        'Press all edges to secure adhesive',
                        'Ensure battery sits flat'
                    ]
                },
                {
                    'number': 13,
                    'title': 'Connect New Battery',
                    'description': 'Reconnect battery flex cable. Replace metal bracket and screws.',
                    'time': '2 minutes',
                    'tips': [
                        'Connector should snap in easily',
                        'Do not force - check alignment if resistance',
                        'Secure bracket with original screws'
                    ]
                },
                {
                    'number': 14,
                    'title': 'Test Before Sealing',
                    'description': 'Turn on phone and verify it boots. Check battery percentage displays correctly.',
                    'time': '2 minutes',
                    'testing_checklist': [
                        'Phone turns on',
                        'Battery percentage shows (may show 100% initially)',
                        'Charging works when plugged in',
                        'No "Unable to verify genuine battery" error (if using quality battery)'
                    ],
                    'tips': [
                        'Battery percentage may be inaccurate initially',
                        'Will calibrate after a few charge cycles',
                        'iOS 15+ may show "Unknown Part" warning for non-Apple batteries'
                    ]
                },
                {
                    'number': 15,
                    'title': 'Reassemble iPhone',
                    'description': 'Reconnect display, seal phone, and replace bottom screws.',
                    'time': '5 minutes',
                    'reference': 'See "iPhone Screen Replacement" steps 11-14',
                    'tips': [
                        'Ensure no cables are pinched',
                        'Apply new screen adhesive if needed',
                        'Test all functions after sealing'
                    ]
                },
                {
                    'number': 16,
                    'title': 'Calibrate New Battery',
                    'description': 'Calibrate battery for accurate percentage: Drain to 0%, charge uninterrupted to 100%, then use normally.',
                    'time': '24-48 hours',
                    'tips': [
                        'Full drain: Use phone until it shuts off',
                        'Full charge: Plug in and leave overnight (do not unplug)',
                        'Repeat 2-3 times for best calibration',
                        'Battery health percentage will show after 1-2 weeks',
                        'Initial capacity may show 95-100% (normal)'
                    ]
                }
            ],

            'total_repair_time': '20-40 minutes (plus calibration time)',
            'estimated_cost': '$15-40 for battery',

            'common_mistakes': [
                'Puncturing battery with metal tools (FIRE HAZARD)',
                'Pulling adhesive strips too fast (they tear)',
                'Using cheap batteries (swelling risk, poor longevity)',
                'Not discharging battery first (safety risk)',
                'Forcing battery out without removing adhesive fully',
                'Not testing before sealing phone',
                'Improper disposal of old battery'
            ],

            'troubleshooting': {
                'Battery not charging': [
                    'Check battery connector is fully seated',
                    'Try different charging cable',
                    'Clean charging port',
                    'May be defective battery - return/replace'
                ],
                'Battery percentage inaccurate': [
                    'Normal for first few days',
                    'Perform calibration cycles (drain to 0%, charge to 100%)',
                    'Will stabilize after 3-5 charge cycles'
                ],
                'Unknown Part warning': [
                    'Normal for non-Apple batteries in iOS 15+',
                    'Does not affect functionality',
                    'Warning will remain but battery works fine',
                    'Only genuine Apple batteries (from Apple service) will not trigger warning'
                ],
                'Battery swelling after replacement': [
                    'STOP USING IMMEDIATELY',
                    'Defective battery - likely cheap quality',
                    'Remove and dispose safely',
                    'Purchase higher-quality replacement'
                ]
            },

            'professional_tips': [
                'Invest in quality battery from reputable supplier',
                'iFixit, Mobile Sentrix, and Injured Gadgets have good reputations',
                'Avoid eBay/Amazon no-name batteries (fire risk)',
                'Check battery has built-in protection circuit (prevents overcharge)',
                'Use dental floss or fishing line to cut through stubborn adhesive',
                'Keep old battery for capacity reference',
                'Take "before" screenshot of Battery Health for comparison'
            ],

            'battery_health_tips': [
                'Keep charge between 20-80% for longevity',
                'Avoid extreme temperatures (especially heat)',
                'Use original or certified chargers',
                'Enable Optimized Battery Charging (iOS 13+)',
                'Remove case while charging (reduces heat)',
                'Avoid overnight charging every night (accelerates degradation)',
                'Replace battery when capacity drops below 80%'
            ],

            'disposal': [
                'NEVER throw lithium batteries in trash',
                'Take to Best Buy, Home Depot, or local recycling center',
                'Call2Recycle (call2recycle.org) has drop-off locations',
                'Some battery retailers offer mail-back recycling',
                'Tape battery terminals before disposal (prevents shorts)',
                'Store in fireproof container until disposal'
            ],

            'safety_notes': [
                '⚠️ Lithium batteries are DANGEROUS if damaged',
                '⚠️ If battery starts smoking, move to outdoor fireproof area immediately',
                '⚠️ Do NOT use water on lithium fire - use Type D extinguisher or sand',
                '⚠️ Work on non-flammable surface (metal table, concrete)',
                '⚠️ Wear safety glasses (battery can vent chemicals)',
                '⚠️ Swollen battery = HANDLE WITH EXTREME CARE'
            ]
        }

    def _iphone_charging_port(self) -> Dict:
        """Repair guide for iPhone charging port issues."""
        return {
            'issue_name': 'iPhone Charging Port Not Working',
            'device_type': 'iPhone',
            'category': 'charging',
            'difficulty': 'easy',  # Cleaning is easy, replacement is hard
            'repair_time': '5 minutes (cleaning) to 45 minutes (replacement)',
            'skill_level': 'Beginner (cleaning) to Advanced (replacement)',

            'symptoms': [
                'Phone not charging when plugged in',
                'Intermittent charging (works at certain angles)',
                'Charging cable falls out easily',
                'Moisture detected error',
                'Slow charging',
                'Cable must be wiggled to work'
            ],

            'diagnosis_steps': [
                {
                    'test': 'Try different cable and charger',
                    'if_fixes': 'Cable/charger issue, not port'
                },
                {
                    'test': 'Try wireless charging (iPhone 8+)',
                    'if_works': 'Port issue confirmed'
                },
                {
                    'test': 'Inspect port with flashlight',
                    'look_for': 'Lint/debris, bent pins, corrosion'
                },
                {
                    'test': 'Check for moisture',
                    'if_yes': 'Dry completely before attempting repair'
                }
            ],

            'solution_1_cleaning': {
                'title': 'Clean Charging Port (Try This First - 90% Success Rate)',
                'difficulty': 'easy',
                'time': '5 minutes',
                'tools': ['Wooden toothpick or plastic dental pick', 'Flashlight', 'Compressed air (optional)', 'Isopropyl alcohol 90%+ (optional)'],
                'steps': [
                    'Power off iPhone',
                    'Shine flashlight into charging port - look for lint/debris',
                    'Use wooden toothpick to GENTLY scrape out lint',
                    'Work toothpick around edges and bottom of port',
                    'You will likely pull out surprising amount of lint',
                    'Blow out loosened debris with compressed air or by blowing',
                    'For corrosion: Dip toothpick in isopropyl alcohol, gently scrub pins',
                    'Let dry 5 minutes',
                    'Test charging'
                ],
                'tips': [
                    'DO NOT use metal tools - will short pins',
                    'Toothpick or plastic floss pick works best',
                    'Lint builds up from pocket carry over months/years',
                    'You may pull out a full toothpick of compressed lint',
                    'Be gentle around the 8 contact pins',
                    'This fixes 90% of "charging port not working" issues'
                ],
                'warnings': [
                    '⚠️ NEVER use metal paperclip, needle, or screwdriver',
                    '⚠️ Can short circuit and kill phone instantly'
                ]
            },

            'solution_2_replacement': {
                'title': 'Replace Charging Port Flex Cable',
                'difficulty': 'hard',
                'time': '45-60 minutes',
                'skill_level': 'Advanced (requires full disassembly)',
                'note': 'Only attempt if cleaning did not fix issue',
                'summary': 'Requires removing screen, battery, logic board, and many components. Charging port is part of a flex cable at bottom of phone. Recommend professional repair unless experienced with microelectronics.',
                'tools': ['Complete iPhone repair kit', 'Pentalobe, Tri-point, Phillips screwdrivers', 'Heat gun', 'Spudgers', 'Tweezers', 'Replacement charging port flex cable'],
                'cost': '$10-25 for part, $50-100 for professional repair',
                'warning': 'This repair is significantly more complex than screen or battery replacement. High risk of damaging other components.'
            }
        }

    def _generic_repair_guide_template(self) -> Dict:
        """Template structure for repair guides."""
        return {
            'issue_name': '',
            'device_type': '',
            'category': '',
            'difficulty': '',
            'repair_time': '',
            'skill_level': '',
            'symptoms': [],
            'tools_needed': [],
            'parts_needed': [],
            'warnings': [],
            'steps': [],
            'total_repair_time': '',
            'estimated_cost': '',
            'common_mistakes': [],
            'troubleshooting': {},
            'professional_tips': [],
            'prevention': []
        }

    def _generate_generic_repair_guide(self, issue: str, device_model: str) -> Dict:
        """Generate a basic repair guide for unlisted issues."""
        return {
            'issue_name': issue,
            'device_model': device_model or 'Unknown',
            'status': 'generic',
            'message': f'Specific repair guide for "{issue}" not yet available. Please consult device-specific repair manual or professional technician.',
            'recommendations': [
                'Search iFixit.com for device-specific guides',
                'Check YouTube for video teardowns',
                'Consult r/mobilerepair or r/laptoprepair subreddits',
                'Visit local repair shop for assessment'
            ]
        }

    # Placeholder methods for additional guides (to be implemented)
    def _iphone_water_damage(self) -> Dict:
        return {'issue_name': 'iPhone Water Damage', 'status': 'coming_soon'}

    def _iphone_camera_repair(self) -> Dict:
        return {'issue_name': 'iPhone Camera Not Working', 'status': 'coming_soon'}

    def _samsung_screen_replacement(self) -> Dict:
        return {'issue_name': 'Samsung Screen Replacement', 'status': 'coming_soon'}

    def _android_battery_swelling(self) -> Dict:
        return {'issue_name': 'Android Battery Swelling', 'status': 'coming_soon'}

    def _laptop_screen_replacement(self) -> Dict:
        return {'issue_name': 'Laptop Screen Replacement', 'status': 'coming_soon'}

    def _laptop_not_charging(self) -> Dict:
        return {'issue_name': 'Laptop Not Charging', 'status': 'coming_soon'}

    def _laptop_overheating(self) -> Dict:
        return {'issue_name': 'Laptop Overheating', 'status': 'coming_soon'}

    def _laptop_keyboard_replacement(self) -> Dict:
        return {'issue_name': 'Laptop Keyboard Replacement', 'status': 'coming_soon'}

    def _laptop_ssd_ram_upgrade(self) -> Dict:
        return {'issue_name': 'Laptop SSD/RAM Upgrade', 'status': 'coming_soon'}


if __name__ == '__main__':
    """Demo repair guide generator."""
    generator = RepairGuideGenerator()

    print("="*70)
    print("  REPAIR GUIDE GENERATOR")
    print("="*70)
    print()

    print("Available Guides:")
    for guide_name in generator.list_available_guides():
        print(f"  - {guide_name}")
    print()

    # Generate example guide
    guide = generator.generate_repair_guide('iPhone Screen Replacement', 'iPhone 12')
    print(f"Generated guide: {guide['issue_name']}")
    print(f"Difficulty: {guide['difficulty']}")
    print(f"Steps: {len(guide['steps'])}")
    print(f"Estimated time: {guide['total_repair_time']}")
