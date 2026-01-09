#!/usr/bin/env python3
"""
Learning Path System
Structures projects into educational curriculums
Guides users from beginner to advanced
"""

from typing import List, Dict
from dataclasses import dataclass
from enum import Enum


class SkillLevel(Enum):
    """Skill progression levels"""
    ABSOLUTE_BEGINNER = "absolute_beginner"
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


@dataclass
class LearningModule:
    """A single learning module in a path"""
    module_number: int
    title: str
    description: str
    skill_level: SkillLevel
    projects: List[str]  # Project names
    concepts_taught: List[str]
    estimated_hours: float
    prerequisites: List[str]  # Previous module numbers


@dataclass
class LearningPath:
    """A complete learning path"""
    path_id: str
    name: str
    description: str
    target_audience: str
    total_modules: int
    total_hours: float
    modules: List[LearningModule]
    skills_gained: List[str]


class LearningPathGenerator:
    """Generates structured learning paths"""

    def __init__(self):
        self.paths = self._create_learning_paths()

    def _create_learning_paths(self) -> Dict[str, LearningPath]:
        """Create all learning paths"""
        return {
            'arduino_basics': self._create_arduino_basics_path(),
            'iot_fundamentals': self._create_iot_path(),
            'home_automation': self._create_home_automation_path(),
            'robotics': self._create_robotics_path(),
            'advanced_projects': self._create_advanced_path()
        }

    def _create_arduino_basics_path(self) -> LearningPath:
        """Arduino Basics: From Zero to Hero"""
        modules = [
            LearningModule(
                module_number=1,
                title="Hello Arduino: Your First Program",
                description="Learn the absolute basics - blinking an LED",
                skill_level=SkillLevel.ABSOLUTE_BEGINNER,
                projects=['LED Blink Trainer'],
                concepts_taught=[
                    'Arduino IDE setup',
                    'Digital output (HIGH/LOW)',
                    'delay() function',
                    'pinMode()',
                    'Circuit polarity (anode/cathode)'
                ],
                estimated_hours=1.0,
                prerequisites=[]
            ),

            LearningModule(
                module_number=2,
                title="Reading Input: Buttons and Sensors",
                description="Learn to read digital inputs",
                skill_level=SkillLevel.BEGINNER,
                projects=['Button Counter', 'Door Open Alarm'],
                concepts_taught=[
                    'Digital input (digitalRead)',
                    'Pull-up/pull-down resistors',
                    'Debouncing',
                    'Serial communication',
                    'if/else logic'
                ],
                estimated_hours=2.0,
                prerequisites=[1]
            ),

            LearningModule(
                module_number=3,
                title="Analog Sensing: Temperature & Light",
                description="Work with analog sensors",
                skill_level=SkillLevel.BEGINNER,
                projects=['Digital Thermometer', 'Light Intensity Logger'],
                concepts_taught=[
                    'Analog vs Digital',
                    'analogRead()',
                    'Sensor calibration',
                    'Data types (int, float)',
                    'Mathematical operations'
                ],
                estimated_hours=3.0,
                prerequisites=[2]
            ),

            LearningModule(
                module_number=4,
                title="Displays: Showing Data",
                description="Learn to use LCD and OLED displays",
                skill_level=SkillLevel.BEGINNER,
                projects=['Digital Clock', 'Countdown Timer'],
                concepts_taught=[
                    'LCD library usage',
                    'String formatting',
                    'Display positioning',
                    'Custom characters',
                    'Refresh rates'
                ],
                estimated_hours=3.0,
                prerequisites=[3]
            ),

            LearningModule(
                module_number=5,
                title="Actuators: Making Things Move",
                description="Control motors and servos",
                skill_level=SkillLevel.INTERMEDIATE,
                projects=['Distance Parking Sensor'],
                concepts_taught=[
                    'Servo library',
                    'PWM (Pulse Width Modulation)',
                    'Servo angles (0-180°)',
                    'Power considerations',
                    'External power supplies'
                ],
                estimated_hours=4.0,
                prerequisites=[4]
            ),

            LearningModule(
                module_number=6,
                title="Communication: I2C & Serial",
                description="Connect multiple devices together",
                skill_level=SkillLevel.INTERMEDIATE,
                projects=['Desk Weather Display'],
                concepts_taught=[
                    'I2C protocol',
                    'Wire library',
                    'Device addresses',
                    'Multiple sensors on one bus',
                    'Debugging I2C'
                ],
                estimated_hours=4.0,
                prerequisites=[5]
            ),

            LearningModule(
                module_number=7,
                title="Final Project: Weather Station",
                description="Combine everything learned",
                skill_level=SkillLevel.INTERMEDIATE,
                projects=['WiFi Weather Station'],
                concepts_taught=[
                    'Project planning',
                    'Multiple sensors integration',
                    'Error handling',
                    'Code organization',
                    'Real-world deployment'
                ],
                estimated_hours=6.0,
                prerequisites=[6]
            )
        ]

        return LearningPath(
            path_id='arduino_basics',
            name='Arduino Basics: From Zero to Hero',
            description='Complete beginner path teaching Arduino fundamentals through 7 progressive projects',
            target_audience='Absolute beginners with no programming or electronics experience',
            total_modules=7,
            total_hours=23.0,
            modules=modules,
            skills_gained=[
                'Arduino IDE proficiency',
                'Basic electronics understanding',
                'Sensor integration',
                'Display control',
                'Servo motors',
                'I2C communication',
                'Project integration'
            ]
        )

    def _create_iot_path(self) -> LearningPath:
        """IoT Fundamentals: Connected Devices"""
        modules = [
            LearningModule(
                module_number=1,
                title="WiFi Basics: Connecting ESP32",
                description="Get your first device online",
                skill_level=SkillLevel.INTERMEDIATE,
                projects=['Smart Doorbell'],
                concepts_taught=[
                    'ESP32 vs Arduino',
                    'WiFi library',
                    'Connecting to network',
                    'IP addresses',
                    'HTTP requests'
                ],
                estimated_hours=3.0,
                prerequisites=[]
            ),

            LearningModule(
                module_number=2,
                title="Cloud Integration: ThingSpeak & MQTT",
                description="Send data to the cloud",
                skill_level=SkillLevel.INTERMEDIATE,
                projects=['WiFi Environmental Monitor'],
                concepts_taught=[
                    'REST APIs',
                    'MQTT protocol',
                    'Cloud platforms',
                    'Data visualization',
                    'API keys'
                ],
                estimated_hours=4.0,
                prerequisites=[1]
            ),

            LearningModule(
                module_number=3,
                title="Home Automation: Smart Control",
                description="Build controllable devices",
                skill_level=SkillLevel.ADVANCED,
                projects=['Garage Door Monitor', 'Automatic Blind Controller'],
                concepts_taught=[
                    'Remote control',
                    'Security considerations',
                    'Relay control',
                    'Status monitoring',
                    'Notifications'
                ],
                estimated_hours=6.0,
                prerequisites=[2]
            ),

            LearningModule(
                module_number=4,
                title="Advanced IoT: Complex Systems",
                description="Multi-device integration",
                skill_level=SkillLevel.ADVANCED,
                projects=['Energy Monitor'],
                concepts_taught=[
                    'Multiple data streams',
                    'Real-time monitoring',
                    'Data logging',
                    'Alert systems',
                    'Dashboard creation'
                ],
                estimated_hours=8.0,
                prerequisites=[3]
            )
        ]

        return LearningPath(
            path_id='iot_fundamentals',
            name='IoT Fundamentals: Connected Devices',
            description='Learn to build Internet-connected smart devices with ESP32',
            target_audience='Makers with basic Arduino knowledge wanting to learn IoT',
            total_modules=4,
            total_hours=21.0,
            modules=modules,
            skills_gained=[
                'WiFi connectivity',
                'Cloud integration',
                'MQTT messaging',
                'Remote control',
                'Data logging',
                'Home automation'
            ]
        )

    def _create_home_automation_path(self) -> LearningPath:
        """Home Automation Specialist Path"""
        modules = [
            LearningModule(
                module_number=1,
                title="Motion & Light Control",
                description="Automatic lighting systems",
                skill_level=SkillLevel.BEGINNER,
                projects=['Motion Sensor Light'],
                concepts_taught=[
                    'PIR sensors',
                    'Relay modules',
                    'AC vs DC',
                    'Safety considerations',
                    'Timing logic'
                ],
                estimated_hours=2.0,
                prerequisites=[]
            ),

            LearningModule(
                module_number=2,
                title="Smart Monitoring",
                description="Watch your home remotely",
                skill_level=SkillLevel.INTERMEDIATE,
                projects=['Garage Door Monitor', 'Water Level Alarm'],
                concepts_taught=[
                    'Distance sensors',
                    'Alert systems',
                    'WiFi notifications',
                    'Status LEDs',
                    'Battery backup'
                ],
                estimated_hours=4.0,
                prerequisites=[1]
            ),

            LearningModule(
                module_number=3,
                title="Automated Care Systems",
                description="Taking care of pets and plants",
                skill_level=SkillLevel.INTERMEDIATE,
                projects=['Pet Feeder Timer', 'Smart Plant Monitor', 'Soil Moisture Monitor'],
                concepts_taught=[
                    'Scheduling',
                    'RTC (Real-Time Clock)',
                    'Moisture sensors',
                    'Automated watering',
                    'Multi-day programming'
                ],
                estimated_hours=6.0,
                prerequisites=[2]
            ),

            LearningModule(
                module_number=4,
                title="Advanced Automation",
                description="Complex integrated systems",
                skill_level=SkillLevel.ADVANCED,
                projects=['Aquarium Controller'],
                concepts_taught=[
                    'Multiple subsystems',
                    'Temperature control',
                    'Lighting schedules',
                    'Feeding automation',
                    'System integration'
                ],
                estimated_hours=8.0,
                prerequisites=[3]
            )
        ]

        return LearningPath(
            path_id='home_automation',
            name='Home Automation Specialist',
            description='Build smart home systems from simple sensors to complex automation',
            target_audience='Makers wanting to automate their homes',
            total_modules=4,
            total_hours=20.0,
            modules=modules,
            skills_gained=[
                'Motion detection',
                'Relay control',
                'Remote monitoring',
                'Scheduling',
                'Multi-system integration',
                'Safety protocols'
            ]
        )

    def _create_robotics_path(self) -> LearningPath:
        """Robotics Engineering Path"""
        modules = [
            LearningModule(
                module_number=1,
                title="Robot Basics: Motors & Movement",
                description="Make your first moving robot",
                skill_level=SkillLevel.INTERMEDIATE,
                projects=['Simple Robot Car'],
                concepts_taught=[
                    'DC motors',
                    'H-bridge control',
                    'Motor drivers',
                    'Forward/reverse/turn',
                    'Power distribution'
                ],
                estimated_hours=5.0,
                prerequisites=[]
            ),

            LearningModule(
                module_number=2,
                title="Sensor Integration: Obstacle Avoidance",
                description="Teach robots to see",
                skill_level=SkillLevel.INTERMEDIATE,
                projects=['Distance Parking Sensor'],  # Simpler version
                concepts_taught=[
                    'Ultrasonic sensors',
                    'Distance measurement',
                    'Decision logic',
                    'Sensor fusion',
                    'Response algorithms'
                ],
                estimated_hours=4.0,
                prerequisites=[1]
            ),

            LearningModule(
                module_number=3,
                title="Advanced Navigation",
                description="Line following and path planning",
                skill_level=SkillLevel.ADVANCED,
                projects=['Line Following Robot'],
                concepts_taught=[
                    'IR sensors',
                    'PID control',
                    'Calibration',
                    'Algorithm tuning',
                    'Competition readiness'
                ],
                estimated_hours=6.0,
                prerequisites=[2]
            ),

            LearningModule(
                module_number=4,
                title="Gesture Control & IMU",
                description="Control robots with motion",
                skill_level=SkillLevel.ADVANCED,
                projects=['Gesture Controlled Robot'],
                concepts_taught=[
                    'IMU (Inertial Measurement Unit)',
                    'Accelerometer data',
                    'Gyroscope readings',
                    'Wireless communication',
                    'Hand gesture recognition'
                ],
                estimated_hours=7.0,
                prerequisites=[3]
            )
        ]

        return LearningPath(
            path_id='robotics',
            name='Robotics Engineering',
            description='Learn to build autonomous robots from basic movement to advanced control',
            target_audience='Intermediate makers interested in robotics',
            total_modules=4,
            total_hours=22.0,
            modules=modules,
            skills_gained=[
                'Motor control',
                'Sensor integration',
                'Autonomous navigation',
                'Line following',
                'IMU/accelerometer',
                'Wireless control'
            ]
        )

    def _create_advanced_path(self) -> LearningPath:
        """Advanced Projects for Experienced Makers"""
        modules = [
            LearningModule(
                module_number=1,
                title="Environmental Monitoring",
                description="Professional-grade sensor systems",
                skill_level=SkillLevel.ADVANCED,
                projects=['Air Quality Monitor'],
                concepts_taught=[
                    'Multiple sensor fusion',
                    'Data validation',
                    'Accuracy & precision',
                    'Calibration techniques',
                    'Professional deployment'
                ],
                estimated_hours=4.0,
                prerequisites=[]
            ),

            LearningModule(
                module_number=2,
                title="Energy Management",
                description="Monitor and control power usage",
                skill_level=SkillLevel.ADVANCED,
                projects=['Energy Monitor'],
                concepts_taught=[
                    'Current sensing',
                    'Power calculations',
                    'Non-invasive monitoring',
                    'Data analytics',
                    'Cost tracking'
                ],
                estimated_hours=6.0,
                prerequisites=[1]
            ),

            LearningModule(
                module_number=3,
                title="Complex Automation Systems",
                description="Multi-subsystem integration",
                skill_level=SkillLevel.EXPERT,
                projects=['Aquarium Controller', 'Automatic Blind Controller'],
                concepts_taught=[
                    'System architecture',
                    'Fail-safe design',
                    'State machines',
                    'Error recovery',
                    'Professional reliability'
                ],
                estimated_hours=10.0,
                prerequisites=[2]
            )
        ]

        return LearningPath(
            path_id='advanced_projects',
            name='Advanced Projects',
            description='Complex professional-grade projects for experienced makers',
            target_audience='Experienced makers ready for challenging projects',
            total_modules=3,
            total_hours=20.0,
            modules=modules,
            skills_gained=[
                'Professional sensor integration',
                'Energy monitoring',
                'Complex system design',
                'Reliability engineering',
                'Production-ready projects'
            ]
        )

    def get_path(self, path_id: str) -> LearningPath:
        """Get a specific learning path"""
        return self.paths.get(path_id)

    def get_all_paths(self) -> List[LearningPath]:
        """Get all learning paths"""
        return list(self.paths.values())

    def recommend_path(self, current_skills: List[str] = None, interests: List[str] = None,
                       available_hours: float = None) -> List[Dict]:
        """
        Recommend learning paths based on skills, interests, and time available

        Args:
            current_skills: List of current skills (optional)
            interests: ['iot', 'robotics', 'home_automation', 'general'] (optional)
            available_hours: Available time in hours (optional)

        Returns:
            List of recommended paths with scores and reasons
        """
        current_skills = current_skills or []
        interests = interests or []
        recommendations = []

        # Determine skill level
        skill_level = 'beginner'
        if 'arduino_basics' in current_skills or 'sensors' in current_skills:
            skill_level = 'intermediate'
        if 'iot' in current_skills or 'robotics' in current_skills:
            skill_level = 'advanced'

        # Score each path
        for path_id, path in self.paths.items():
            score = 0
            reasons = []

            # Skill level match
            target = path.target_audience.lower()
            if skill_level == 'beginner' and 'beginner' in target:
                score += 10
                reasons.append("Perfect for beginners")
            elif skill_level == 'intermediate' and ('intermediate' in target or 'zero' in target):
                score += 8
                reasons.append("Matches your intermediate skills")
            elif skill_level == 'advanced' and 'advanced' in target:
                score += 10
                reasons.append("Perfect for advanced users")
            elif skill_level == 'advanced':
                score += 5
                reasons.append("Suitable for your advanced level")

            # Interest match
            for interest in interests:
                if interest.lower() in path.path_id.lower() or interest.lower() in path.name.lower():
                    score += 15
                    reasons.append(f"Matches your interest in {interest}")
                # Check skills gained
                for skill in path.skills_gained:
                    if interest.lower() in skill.lower():
                        score += 5

            # Time availability match
            if available_hours:
                if path.total_hours <= available_hours:
                    score += 5
                    reasons.append(f"Can complete within {available_hours} hours")
                elif path.total_hours <= available_hours * 1.5:
                    score += 2
                    reasons.append(f"Close to your available time")

            # Default reason if no specific match
            if not reasons:
                reasons.append("Good general path")

            recommendations.append({
                'path': path,
                'score': score,
                'reason': '; '.join(reasons)
            })

        # Sort by score
        recommendations.sort(key=lambda x: x['score'], reverse=True)

        return recommendations

    def get_next_project(self, path_id: str, completed_modules: List[int]) -> Dict:
        """
        Get the next recommended project in a learning path

        Args:
            path_id: Learning path ID
            completed_modules: List of completed module numbers

        Returns:
            Next module recommendation
        """
        path = self.get_path(path_id)
        if not path:
            return None

        for module in path.modules:
            if module.module_number not in completed_modules:
                # Check prerequisites
                if all(prereq in completed_modules for prereq in module.prerequisites):
                    return {
                        'module_number': module.module_number,
                        'title': module.title,
                        'description': module.description,
                        'projects': module.projects,
                        'estimated_hours': module.estimated_hours,
                        'concepts': module.concepts_taught
                    }

        return {'message': 'Path completed! Choose a new path to continue learning.'}


def main():
    """Demo learning paths"""
    print("="*70)
    print("  LEARNING PATH SYSTEM")
    print("="*70)
    print()

    generator = LearningPathGenerator()

    # Show all paths
    print("Available Learning Paths:")
    print("-"*70)
    for path in generator.get_all_paths():
        print(f"\n{path.name}")
        print(f"  Target: {path.target_audience}")
        print(f"  Modules: {path.total_modules} | Hours: {path.total_hours}")
        print(f"  Skills: {', '.join(path.skills_gained[:3])}...")
    print()

    # Demonstrate a full path
    print("="*70)
    print("  ARDUINO BASICS PATH (Full Curriculum)")
    print("="*70)
    print()

    arduino_path = generator.get_path('arduino_basics')

    for module in arduino_path.modules:
        print(f"Module {module.module_number}: {module.title}")
        print(f"  Level: {module.skill_level.value}")
        print(f"  Time: {module.estimated_hours} hours")
        print(f"  Projects: {', '.join(module.projects)}")
        print(f"  Learn: {', '.join(module.concepts_taught[:3])}...")
        if module.prerequisites:
            print(f"  Prerequisites: Module(s) {', '.join(map(str, module.prerequisites))}")
        print()

    # Test recommendation
    print("="*70)
    print("  RECOMMENDATION ENGINE")
    print("="*70)
    print()

    rec = generator.recommend_path('beginner', ['iot', 'home'])
    print(f"For beginner interested in IoT/Home:")
    print(f"  → Recommended: {rec.name}")
    print()

    # Test progress tracking
    print("="*70)
    print("  PROGRESS TRACKING")
    print("="*70)
    print()

    completed = [1, 2]  # Completed modules 1 and 2
    next_project = generator.get_next_project('arduino_basics', completed)

    print(f"Completed: Modules {completed}")
    print(f"Next: Module {next_project['module_number']} - {next_project['title']}")
    print(f"  Projects: {', '.join(next_project['projects'])}")
    print()

    print("="*70)
    print("  LEARNING PATHS READY")
    print("="*70)


if __name__ == '__main__':
    main()
