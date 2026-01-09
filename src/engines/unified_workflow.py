#!/usr/bin/env python3
"""
Unified Workflow Engine
Integrates educational tools + professional validation into complete platform

This bridges:
- Recipe Optimizer (educational) → KiCAD Validator (professional)
- Build Instructions (beginner) → Power Tree Analysis (advanced)
- Learning Paths (curriculum) → Circuit Solver (validation)
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from enum import Enum
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from intelligence.recipe_optimizer import RecipeOptimizer, ProjectRecipe
from intelligence.build_instructions import BuildInstructionsGenerator
from intelligence.learning_paths import LearningPathGenerator
from integrations.pricing_service import UnifiedPricingService

# ChatGPT's validation engines
try:
    from engines.kicad_netlist_compiler import compile_kicad_netlist
    from engines.power_tree_validator import validate_pcb_power_tree, PowerTreeConstraints
    from engines.circuit_physics import SimulationIssue
    VALIDATION_AVAILABLE = True
except ImportError:
    VALIDATION_AVAILABLE = False
    compile_kicad_netlist = None
    validate_pcb_power_tree = None
    PowerTreeConstraints = None
    SimulationIssue = None


class UserLevel(Enum):
    BEGINNER = 1  # Never built anything
    HOBBYIST = 2  # Built a few projects
    INTERMEDIATE = 3  # Comfortable with circuits
    ADVANCED = 4  # Designs PCBs
    PROFESSIONAL = 5  # EE degree / commercial work


@dataclass
class UserProfile:
    """User profile for personalized workflows"""
    skill_level: UserLevel
    completed_projects: List[str]
    inventory: List[Dict]
    budget: float
    goal: str  # "learning", "roi", "speed"


@dataclass
class WorkflowResult:
    """Result of complete workflow"""
    status: str  # "success", "prerequisites_missing", "validation_failed"
    project: Optional[ProjectRecipe]
    instructions: Optional[Dict]
    validation_issues: List[SimulationIssue]
    manufacturing_files: Optional[Dict]
    next_steps: List[str]
    estimated_cost: float
    estimated_time_hours: float


class UnifiedWorkflowEngine:
    """
    Complete workflow engine integrating all systems

    Handles:
    1. Beginner workflow (learn → build → validate)
    2. Hobbyist workflow (optimize inventory → build → validate → PCB)
    3. Professional workflow (validate → fix → manufacture)
    4. Education workflow (assign → track → grade)
    """

    def __init__(self):
        # Educational components (My work)
        self.recipe_optimizer = RecipeOptimizer()
        self.instructions_gen = BuildInstructionsGenerator()
        self.learning_paths = LearningPathGenerator()
        self.pricing = UnifiedPricingService()

    def execute_beginner_workflow(self, user: UserProfile) -> WorkflowResult:
        """
        Complete beginner workflow

        Flow:
        1. Check skill level
        2. Recommend learning path if needed
        3. Suggest buildable projects
        4. Provide instructions
        5. (User builds)
        6. Validate design if uploaded
        """

        if user.skill_level == UserLevel.BEGINNER:
            # Brand new - recommend learning path
            paths = self.learning_paths.recommend_path(
                current_skills=[],
                interests=[user.goal] if user.goal != 'roi' else [],
                available_hours=None
            )

            if paths:
                best_path = paths[0]['path']
                first_project = best_path.modules[0].projects[0]

                return WorkflowResult(
                    status="prerequisites_missing",
                    project=None,
                    instructions=None,
                    validation_issues=[],
                    manufacturing_files=None,
                    next_steps=[
                        f"Start learning path: {best_path.name}",
                        f"First module: {best_path.modules[0].title}",
                        f"First project: {first_project}",
                        "Complete this module to unlock more projects"
                    ],
                    estimated_cost=0.0,
                    estimated_time_hours=best_path.modules[0].estimated_hours
                )

        # User has some experience - find buildable projects
        recipes = self.recipe_optimizer.generate_recipes(
            user.inventory,
            top_n=5
        )

        if not recipes:
            return WorkflowResult(
                status="no_projects",
                project=None,
                instructions=None,
                validation_issues=[],
                manufacturing_files=None,
                next_steps=[
                    "No buildable projects with current inventory",
                    f"Budget: ${user.budget}",
                    "Consider buying starter kit (Arduino Uno + sensors)"
                ],
                estimated_cost=25.0,  # Starter kit
                estimated_time_hours=0.0
            )

        # Get best project based on goal
        if user.goal == "learning":
            project = self._select_best_for_learning(recipes, user.skill_level)
        elif user.goal == "roi":
            project = recipes[0]  # Already sorted by ROI
        else:  # speed
            project = min(recipes, key=lambda r: r.build_time_hours)

        # Get build instructions
        instructions = self.instructions_gen.generate_instructions(project.name)

        return WorkflowResult(
            status="success",
            project=project,
            instructions=instructions,
            validation_issues=[],
            manufacturing_files=None,
            next_steps=[
                f"Build {project.name}",
                f"Follow {len(instructions.get('steps', []))} step instructions",
                "Upload your design for validation (optional)",
                f"Estimated time: {project.build_time_hours} hours"
            ],
            estimated_cost=project.missing_parts_cost,
            estimated_time_hours=project.build_time_hours
        )

    def execute_validation_workflow(self, kicad_file: str,
                                   hints: Optional[Dict] = None) -> WorkflowResult:
        """
        Professional validation workflow

        Flow:
        1. Parse KiCAD netlist
        2. Compile to circuit model
        3. Solve DC operating point
        4. Validate power tree
        5. Return quantitative fixes
        """

        if not VALIDATION_AVAILABLE:
            return WorkflowResult(
                status="validation_unavailable",
                project=None,
                instructions=None,
                validation_issues=[],
                manufacturing_files=None,
                next_steps=[
                    "KiCAD validation module not available",
                    "Install required dependencies"
                ],
                estimated_cost=0.0,
                estimated_time_hours=0.0
            )

        try:
            # Compile KiCAD netlist (ChatGPT's engine)
            compiled = compile_kicad_netlist(kicad_file, hints=hints)

            # Validate power tree (ChatGPT's engine)
            results, issues = validate_pcb_power_tree(
                compiled.netlist,
                constraints=compiled.constraints
            )

            # Categorize issues
            critical = [i for i in issues if i.severity == 'critical']
            errors = [i for i in issues if i.severity == 'error']
            warnings = [i for i in issues if i.severity == 'warning']

            if critical or errors:
                status = "validation_failed"
                next_steps = [
                    f"Fix {len(critical)} critical issues",
                    f"Fix {len(errors)} errors",
                    "Re-upload for validation"
                ]
            elif warnings:
                status = "validation_warning"
                next_steps = [
                    "Review warnings",
                    "Consider fixes for optimal performance",
                    "Generate manufacturing files"
                ]
            else:
                status = "validation_passed"
                next_steps = [
                    "Design validated successfully!",
                    "Generate Gerber files",
                    "Generate BOM",
                    "Order PCB from JLCPCB"
                ]

            return WorkflowResult(
                status=status,
                project=None,
                instructions=None,
                validation_issues=issues,
                manufacturing_files=None,
                next_steps=next_steps,
                estimated_cost=0.0,  # PCB cost calculated separately
                estimated_time_hours=0.0
            )

        except Exception as e:
            return WorkflowResult(
                status="error",
                project=None,
                instructions=None,
                validation_issues=[],
                manufacturing_files=None,
                next_steps=[
                    f"Error processing KiCAD file: {str(e)}",
                    "Check file format",
                    "Ensure it's a valid KiCAD netlist (.net)"
                ],
                estimated_cost=0.0,
                estimated_time_hours=0.0
            )

    def execute_complete_workflow(self, user: UserProfile,
                                  project_name: str,
                                  kicad_file: Optional[str] = None) -> WorkflowResult:
        """
        End-to-end complete workflow

        Flow:
        1. Get project from recipe optimizer
        2. Check if user has required skills
        3. Provide build instructions
        4. (User builds)
        5. If KiCAD file provided, validate
        6. Generate manufacturing files if valid
        """

        # Step 1: Get project details
        recipes = self.recipe_optimizer.generate_recipes(
            user.inventory,
            top_n=50  # Search all
        )

        project = None
        for recipe in recipes:
            if recipe.name == project_name:
                project = recipe
                break

        if not project:
            return WorkflowResult(
                status="project_not_found",
                project=None,
                instructions=None,
                validation_issues=[],
                manufacturing_files=None,
                next_steps=[
                    f"Project '{project_name}' not found",
                    "Check available projects",
                    "Or provide different inventory"
                ],
                estimated_cost=0.0,
                estimated_time_hours=0.0
            )

        # Step 2: Check skill prerequisites
        project_skill_level = self._estimate_skill_level(project.difficulty)
        if user.skill_level.value < project_skill_level.value:
            # Recommend learning path to get there
            path_recommendation = self.learning_paths.recommend_path(
                current_skills=[],
                interests=[project.category.value],
                available_hours=None
            )

            return WorkflowResult(
                status="prerequisites_missing",
                project=project,
                instructions=None,
                validation_issues=[],
                manufacturing_files=None,
                next_steps=[
                    f"Project requires {project_skill_level.name} level",
                    f"Your level: {user.skill_level.name}",
                    f"Recommended: {path_recommendation[0]['path'].name if path_recommendation else 'Arduino Basics'}",
                    "Complete learning path first"
                ],
                estimated_cost=project.missing_parts_cost,
                estimated_time_hours=project.build_time_hours
            )

        # Step 3: Get build instructions
        instructions = self.instructions_gen.generate_instructions(project.name)

        # Step 4: If KiCAD file provided, validate
        validation_issues = []
        manufacturing_files = None

        if kicad_file:
            validation_result = self.execute_validation_workflow(kicad_file)
            validation_issues = validation_result.validation_issues

            if validation_result.status == "validation_passed":
                # Generate manufacturing files
                manufacturing_files = {
                    'gerber_ready': True,
                    'bom_ready': True,
                    'note': 'Manufacturing files can be generated'
                }

        # Determine overall status
        if kicad_file and validation_issues:
            critical_or_errors = [i for i in validation_issues
                                if i.severity in ['critical', 'error']]
            if critical_or_errors:
                status = "validation_failed"
            else:
                status = "validation_warning"
        else:
            status = "success"

        return WorkflowResult(
            status=status,
            project=project,
            instructions=instructions,
            validation_issues=validation_issues,
            manufacturing_files=manufacturing_files,
            next_steps=self._generate_next_steps(status, project, kicad_file),
            estimated_cost=project.missing_parts_cost,
            estimated_time_hours=project.build_time_hours
        )

    def _select_best_for_learning(self, recipes: List[ProjectRecipe],
                                  skill_level: UserLevel) -> ProjectRecipe:
        """Select best project for learning based on current skill"""

        # Score each project for learning value
        scored = []
        for recipe in recipes:
            score = 0

            # Prefer projects slightly above current level
            project_level = self._estimate_skill_level(recipe.difficulty)
            if project_level.value == skill_level.value + 1:
                score += 10  # Perfect - one level up
            elif project_level.value == skill_level.value:
                score += 5  # Okay - at current level
            elif project_level.value > skill_level.value + 1:
                score -= 5  # Too hard

            # Prefer shorter projects (faster feedback)
            if recipe.build_time_hours < 2:
                score += 5
            elif recipe.build_time_hours < 4:
                score += 2

            # Prefer projects with full instructions
            if recipe.name in self.instructions_gen.templates:
                score += 10

            scored.append((recipe, score))

        # Return highest score
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[0][0]

    def _estimate_skill_level(self, difficulty: str) -> UserLevel:
        """Map project difficulty to skill level"""
        mapping = {
            'easy': UserLevel.BEGINNER,
            'medium': UserLevel.HOBBYIST,
            'hard': UserLevel.INTERMEDIATE
        }
        return mapping.get(difficulty, UserLevel.BEGINNER)

    def _generate_next_steps(self, status: str, project: ProjectRecipe,
                            has_kicad: bool) -> List[str]:
        """Generate contextual next steps"""

        if status == "success" and not has_kicad:
            return [
                f"Build {project.name}",
                f"Estimated time: {project.build_time_hours} hours",
                f"Cost: ${project.missing_parts_cost:.2f}",
                "Upload KiCAD design for validation (optional)"
            ]
        elif status == "validation_passed":
            return [
                "Design validated successfully!",
                "Generate Gerber files",
                "Order PCB",
                f"Build project (est. {project.build_time_hours} hours)"
            ]
        elif status == "validation_failed":
            return [
                "Fix critical validation issues",
                "Re-upload for validation",
                "Then generate manufacturing files"
            ]
        else:
            return ["Review result details"]


def demo():
    """Demo unified workflow"""
    print("="*70)
    print("  UNIFIED WORKFLOW ENGINE - Complete Integration")
    print("="*70)
    print()

    engine = UnifiedWorkflowEngine()

    # Demo 1: Beginner workflow
    print("DEMO 1: Complete Beginner")
    print("-"*70)

    beginner = UserProfile(
        skill_level=UserLevel.BEGINNER,
        completed_projects=[],
        inventory=[],
        budget=50.0,
        goal="learning"
    )

    result = engine.execute_beginner_workflow(beginner)

    print(f"Status: {result.status}")
    print(f"Next steps:")
    for step in result.next_steps:
        print(f"  • {step}")
    print(f"Estimated time: {result.estimated_time_hours} hours")
    print()

    # Demo 2: Hobbyist workflow
    print("DEMO 2: Hobbyist with Parts")
    print("-"*70)

    hobbyist = UserProfile(
        skill_level=UserLevel.HOBBYIST,
        completed_projects=["LED Blink", "Button Counter"],
        inventory=[
            {'id': 'esp32', 'condition': 'new', 'quantity': 1},
            {'id': 'bme280', 'condition': 'used', 'quantity': 1},
            {'id': 'oled_ssd1306', 'condition': 'new', 'quantity': 1}
        ],
        budget=20.0,
        goal="learning"
    )

    result = engine.execute_beginner_workflow(hobbyist)

    print(f"Status: {result.status}")
    if result.project:
        print(f"Recommended: {result.project.name}")
        print(f"  Difficulty: {result.project.difficulty}")
        print(f"  Build time: {result.project.build_time_hours}h")
        print(f"  Missing cost: ${result.project.missing_parts_cost:.2f}")
    print(f"Next steps:")
    for step in result.next_steps:
        print(f"  • {step}")
    print()

    # Demo 3: Complete workflow
    print("DEMO 3: Complete Workflow (Recipe → Instructions → Validation)")
    print("-"*70)

    result = engine.execute_complete_workflow(
        user=hobbyist,
        project_name="Air Quality Monitor",
        kicad_file=None  # No KiCAD file yet
    )

    print(f"Status: {result.status}")
    if result.project:
        print(f"Project: {result.project.name}")
        print(f"  You have: {result.project.inventory_match_percent:.0f}% of parts")
        print(f"  Cost: ${result.estimated_cost:.2f}")
        print(f"  Time: {result.estimated_time_hours}h")
    if result.instructions:
        print(f"Instructions: {len(result.instructions.get('steps', []))} steps")
    print(f"Next steps:")
    for step in result.next_steps:
        print(f"  • {step}")
    print()

    print("="*70)
    print("This integrates ALL systems:")
    print("  ✓ Recipe Optimizer (educational)")
    print("  ✓ Build Instructions (beginner-friendly)")
    print("  ✓ Learning Paths (curriculum)")
    print("  ✓ KiCAD Validation (professional)")
    print("  ✓ Power Tree Analysis (advanced)")
    print()
    print("Result: Complete end-to-end platform")
    print("="*70)


if __name__ == '__main__':
    demo()
