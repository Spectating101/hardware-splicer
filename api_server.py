#!/usr/bin/env python3
"""
Circuit-AI Web API
Minimal Flask API for circuit validation and Fritzing export
"""

from flask import Flask, request, jsonify, send_file, make_response, g
from pathlib import Path
from functools import wraps
from datetime import datetime, timezone
import hashlib
import os
import sqlite3
import sys
import tempfile
import uuid

sys.path.insert(0, 'src')

from intelligence.circuit_validator import CircuitValidator
from integrations.fritzing_integration import FritzingPartsLibrary, FritzingFileGenerator
from intelligence.recipe_optimizer import RecipeOptimizer
from intelligence.build_instructions import BuildInstructionsGenerator
from intelligence.learning_paths import LearningPathGenerator
from integrations.pricing_service import UnifiedPricingService
from engines.unified_workflow import UnifiedWorkflowEngine, UserProfile, UserLevel

app = Flask(__name__, static_folder='static', static_url_path='/static')

# ============================================================================
# Monetization hooks: API keys + daily quotas (v2 endpoints)
# ============================================================================

def _configured_api_keys() -> set[str]:
    raw = (os.environ.get("CIRCUIT_AI_API_KEYS") or "").strip()
    if not raw:
        return set()
    parts = [p.strip() for p in raw.replace("\n", ",").split(",")]
    return {p for p in parts if p}


def _api_key_required() -> bool:
    if (os.environ.get("CIRCUIT_AI_REQUIRE_API_KEY") or "").strip().lower() in ("1", "true", "yes", "on"):
        return True
    return bool(_configured_api_keys())


def _extract_api_key() -> str | None:
    auth = (request.headers.get("Authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        if token:
            return token
    x_api_key = (request.headers.get("X-API-Key") or "").strip()
    if x_api_key:
        return x_api_key
    q = (request.args.get("api_key") or "").strip()
    return q or None


def _quota_limit(action: str) -> int:
    action_u = (action or "").upper()
    env_key = f"CIRCUIT_AI_QUOTA_{action_u}_PER_DAY"
    raw = (os.environ.get(env_key) or "").strip()
    if raw.isdigit():
        return int(raw)
    default_raw = (os.environ.get("CIRCUIT_AI_QUOTA_DEFAULT_PER_DAY") or "200").strip()
    return int(default_raw) if default_raw.isdigit() else 200


def _usage_db_path() -> Path:
    # Use a tmp db by default; deploys can override for persistence.
    raw = (os.environ.get("CIRCUIT_AI_USAGE_DB") or "").strip()
    if raw:
        return Path(raw)
    return Path(tempfile.gettempdir()) / "circuit-ai-usage.sqlite"


def _key_hash(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:32]


def _check_and_increment_usage(api_key: str, action: str) -> tuple[bool, int, int]:
    """
    Returns (allowed, remaining, limit).
    """
    limit = _quota_limit(action)
    if limit <= 0:
        return False, 0, limit

    day = datetime.now(timezone.utc).date().isoformat()
    kh = _key_hash(api_key)
    db_path = _usage_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(str(db_path))
    try:
        con.execute(
            "CREATE TABLE IF NOT EXISTS usage (day TEXT NOT NULL, key_hash TEXT NOT NULL, action TEXT NOT NULL, count INTEGER NOT NULL, PRIMARY KEY(day, key_hash, action))"
        )
        row = con.execute("SELECT count FROM usage WHERE day=? AND key_hash=? AND action=?", (day, kh, action)).fetchone()
        used = int(row[0]) if row else 0
        if used >= limit:
            return False, 0, limit
        new_used = used + 1
        con.execute(
            "INSERT INTO usage(day, key_hash, action, count) VALUES(?,?,?,?) ON CONFLICT(day, key_hash, action) DO UPDATE SET count=excluded.count",
            (day, kh, action, new_used),
        )
        con.commit()
        return True, max(0, limit - new_used), limit
    finally:
        con.close()


def require_api_key(action: str):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not _api_key_required():
                return fn(*args, **kwargs)

            api_key = _extract_api_key()
            if not api_key:
                return jsonify({"error": "missing_api_key"}), 401

            allowed_keys = _configured_api_keys()
            if allowed_keys and api_key not in allowed_keys:
                return jsonify({"error": "invalid_api_key"}), 403

            ok, remaining, limit = _check_and_increment_usage(api_key, action)
            if not ok:
                return jsonify({"error": "quota_exceeded", "action": action, "limit_per_day": limit}), 429

            g.circuit_ai_api_key_hash = _key_hash(api_key)
            out = fn(*args, **kwargs)
            resp = make_response(out)
            resp.headers["X-CircuitAI-Quota-Limit"] = str(limit)
            resp.headers["X-CircuitAI-Quota-Remaining"] = str(remaining)
            return resp

        return wrapper

    return decorator

# Small helper endpoint for debugging quotas/keys during rollout.
@app.route("/api/v2/usage", methods=["GET"])
@require_api_key("usage")
def usage():
    return jsonify(
        {
            "ok": True,
            "key_hash": getattr(g, "circuit_ai_api_key_hash", None),
            "quota_default_per_day": _quota_limit("default"),
            "usage_db": str(_usage_db_path()),
        }
    )

# Initialize services
validator = CircuitValidator()
fritzing_lib = FritzingPartsLibrary()
fritzing_gen = FritzingFileGenerator(fritzing_lib)
recipe_optimizer = RecipeOptimizer()
instructions_gen = BuildInstructionsGenerator()
learning_paths = LearningPathGenerator()
pricing_service = UnifiedPricingService()

# Initialize unified workflow engine (v2 API)
workflow_engine = UnifiedWorkflowEngine()


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'service': 'Circuit-AI API',
        'version': '0.1.0'
    })


@app.route('/api/validate', methods=['POST'])
def validate_circuit():
    """
    Validate a circuit design

    Request body:
    {
        "microcontroller": "arduino_uno",
        "components": ["bme280", "servo_sg90"],
        "external_power": false
    }

    Returns:
    {
        "valid": true/false,
        "issues": [...],
        "summary": {
            "critical": 0,
            "errors": 0,
            "warnings": 0
        }
    }
    """
    try:
        design = request.get_json()

        if not design:
            return jsonify({'error': 'No design provided'}), 400

        if 'microcontroller' not in design:
            return jsonify({'error': 'microcontroller field required'}), 400

        # Run validation
        issues = validator.validate_circuit(design)

        # Categorize issues
        critical = [i for i in issues if i.severity.value == 'critical']
        errors = [i for i in issues if i.severity.value == 'error']
        warnings = [i for i in issues if i.severity.value == 'warning']

        # Format response
        result = {
            'valid': len(critical) == 0 and len(errors) == 0,
            'issues': [
                {
                    'severity': i.severity.value,
                    'component': i.component,
                    'issue': i.issue,
                    'explanation': i.explanation,
                    'solution': i.solution,
                    'source': i.source
                }
                for i in issues
            ],
            'summary': {
                'critical': len(critical),
                'errors': len(errors),
                'warnings': len(warnings),
                'total': len(issues)
            },
            'message': 'Circuit looks good!' if len(issues) == 0 else f'Found {len(issues)} issue(s)'
        }

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/export/fritzing', methods=['POST'])
def export_fritzing():
    """
    Export circuit design to Fritzing .fzz file

    Request body:
    {
        "project_name": "My Circuit",
        "microcontroller": "arduino_uno",
        "components": ["bme280", "led", "resistor"]
    }

    Returns: .fzz file (application/zip)
    """
    try:
        design = request.get_json()

        if not design:
            return jsonify({'error': 'No design provided'}), 400

        # Generate unique filename
        project_name = design.get('project_name', 'circuit')
        filename = f"{project_name.replace(' ', '_')}_{uuid.uuid4().hex[:8]}.fzz"

        # Use temp directory for output
        temp_dir = Path(tempfile.gettempdir()) / 'circuit-ai'
        temp_dir.mkdir(exist_ok=True)
        output_path = temp_dir / filename

        # Generate .fzz file
        fzz_path = fritzing_gen.generate_fzz(design, str(output_path))

        # Send file
        return send_file(
            fzz_path,
            mimetype='application/zip',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/design', methods=['POST'])
def design_and_validate():
    """
    Complete workflow: Design, validate, and optionally export

    Request body:
    {
        "project_name": "Temperature Monitor",
        "microcontroller": "arduino_uno",
        "components": ["bme280", "led"],
        "export": true  // optional
    }

    Returns:
    {
        "validation": {...},
        "export_url": "/api/export/fritzing" (if export=true)
    }
    """
    try:
        design = request.get_json()

        if not design:
            return jsonify({'error': 'No design provided'}), 400

        # Step 1: Validate
        issues = validator.validate_circuit(design)

        critical = [i for i in issues if i.severity.value == 'critical']
        errors = [i for i in issues if i.severity.value == 'error']
        warnings = [i for i in issues if i.severity.value == 'warning']

        validation_result = {
            'valid': len(critical) == 0 and len(errors) == 0,
            'issues': [
                {
                    'severity': i.severity.value,
                    'component': i.component,
                    'issue': i.issue,
                    'solution': i.solution
                }
                for i in issues
            ],
            'summary': {
                'critical': len(critical),
                'errors': len(errors),
                'warnings': len(warnings)
            }
        }

        result = {
            'validation': validation_result,
            'message': 'Circuit validated successfully'
        }

        # Step 2: Export if requested
        if design.get('export', False):
            project_name = design.get('project_name', 'circuit')
            filename = f"{project_name.replace(' ', '_')}.fzz"

            temp_dir = Path(tempfile.gettempdir()) / 'circuit-ai'
            temp_dir.mkdir(exist_ok=True)
            output_path = temp_dir / filename

            fzz_path = fritzing_gen.generate_fzz(design, str(output_path))
            result['export_file'] = str(fzz_path)
            result['message'] += ' and exported to Fritzing'

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/components', methods=['GET'])
def list_components():
    """List available components"""
    components = {
        'microcontrollers': [
            'arduino_uno', 'arduino_nano', 'arduino_mega', 'arduino_leonardo',
            'esp32', 'esp8266'
        ],
        'sensors': [
            'bme280', 'bmp280', 'dht22', 'dht11', 'hc_sr04', 'mpu6050'
        ],
        'displays': [
            'oled_ssd1306', 'lcd_16x2', 'lcd_20x4'
        ],
        'actuators': [
            'servo_sg90', 'servo', 'relay'
        ],
        'basic': [
            'led', 'led_rgb', 'ws2812b', 'resistor', 'capacitor'
        ]
    }

    # Count Fritzing mappings
    mapped = sum(
        1 for comp_list in components.values()
        for comp in comp_list
        if fritzing_lib.find_part(comp)
    )

    return jsonify({
        'components': components,
        'total': sum(len(v) for v in components.values()),
        'fritzing_mapped': mapped
    })


@app.route('/api/recipes/analyze-inventory', methods=['POST'])
def analyze_inventory():
    """
    Analyze inventory value

    Request body:
    {
        "inventory": [
            {"id": "arduino_uno", "condition": "used", "quantity": 1},
            {"id": "bme280", "condition": "new", "quantity": 1}
        ]
    }

    Returns inventory analysis with total value
    """
    try:
        data = request.get_json()

        if not data or 'inventory' not in data:
            return jsonify({'error': 'inventory field required'}), 400

        analysis = recipe_optimizer.analyze_inventory(data['inventory'])

        return jsonify(analysis)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/recipes/generate', methods=['POST'])
def generate_recipes():
    """
    Generate project recipes from inventory

    Request body:
    {
        "inventory": [
            {"id": "arduino_uno", "condition": "used", "quantity": 1},
            {"id": "bme280", "condition": "new", "quantity": 1}
        ],
        "top_n": 5,
        "validate": true  // optional: validate circuits
    }

    Returns list of project recipes sorted by ROI
    """
    try:
        data = request.get_json()

        if not data or 'inventory' not in data:
            return jsonify({'error': 'inventory field required'}), 400

        inventory = data['inventory']
        top_n = data.get('top_n', 5)
        validate_circuits = data.get('validate', False)

        # Generate recipes
        recipes = recipe_optimizer.generate_recipes(inventory, top_n)

        # Optionally validate each recipe
        if validate_circuits:
            for recipe in recipes:
                design = {
                    'project_name': recipe.name,
                    'microcontroller': recipe.required_components[0],  # First is usually MCU
                    'components': recipe.required_components[1:]
                }
                issues = validator.validate_circuit(design)
                recipe.validated = len(issues) == 0
                recipe.validation_issues = [i.issue for i in issues[:3]]  # Top 3 issues

        # Format response
        result = {
            'recipes': [
                {
                    'name': r.name,
                    'category': r.category.value,
                    'description': r.description,
                    'difficulty': r.difficulty,
                    'economics': {
                        'parts_cost': r.parts_cost,
                        'market_price_low': r.market_price_low,
                        'market_price_high': r.market_price_high,
                        'profit_margin': r.profit_margin,
                        'roi_percent': r.roi_percent,
                        'missing_parts_cost': r.missing_parts_cost
                    },
                    'inventory': {
                        'match_percent': r.inventory_match_percent,
                        'components_owned': r.components_owned,
                        'components_needed': r.components_needed,
                        'has_all_parts': len(r.components_needed) == 0
                    },
                    'build_time_hours': r.build_time_hours,
                    'validated': r.validated if validate_circuits else None,
                    'validation_issues': r.validation_issues if validate_circuits else None
                }
                for r in recipes
            ],
            'count': len(recipes)
        }

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/recipes/shopping-list', methods=['POST'])
def generate_shopping_list():
    """
    Generate shopping list for missing components

    Request body:
    {
        "inventory": [...],
        "recipe_name": "WiFi Weather Station"
    }

    Returns shopping list with prices and buy links
    """
    try:
        data = request.get_json()

        if not data or 'inventory' not in data or 'recipe_name' not in data:
            return jsonify({'error': 'inventory and recipe_name required'}), 400

        # Generate recipes to find the requested one
        recipes = recipe_optimizer.generate_recipes(data['inventory'], top_n=20)

        # Find matching recipe
        target_recipe = None
        for recipe in recipes:
            if recipe.name == data['recipe_name']:
                target_recipe = recipe
                break

        if not target_recipe:
            return jsonify({'error': 'Recipe not found'}), 404

        # Generate shopping list
        shopping = recipe_optimizer.generate_shopping_list(target_recipe)

        return jsonify(shopping)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/recipes/filter', methods=['POST'])
def filter_recipes():
    """
    Generate recipes with advanced filtering

    Request body:
    {
        "inventory": [...],
        "max_difficulty": "easy",  // optional: 'easy', 'medium', 'hard'
        "max_build_hours": 2.0,    // optional: max build time
        "max_budget": 15.0,         // optional: max missing parts cost
        "min_match_percent": 80.0,  // optional: min inventory match
        "top_n": 5                  // optional: number of results
    }

    Returns filtered recipes
    """
    try:
        data = request.get_json()

        if not data or 'inventory' not in data:
            return jsonify({'error': 'inventory field required'}), 400

        # Extract filter parameters
        inventory = data['inventory']
        max_difficulty = data.get('max_difficulty')
        max_build_hours = data.get('max_build_hours')
        max_budget = data.get('max_budget')
        min_match_percent = data.get('min_match_percent', 50.0)
        top_n = data.get('top_n', 10)

        # Generate filtered recipes
        recipes = recipe_optimizer.generate_recipes_filtered(
            inventory=inventory,
            max_difficulty=max_difficulty,
            max_build_hours=max_build_hours,
            max_budget=max_budget,
            min_match_percent=min_match_percent,
            top_n=top_n
        )

        # Format response
        result = {
            'recipes': [
                {
                    'name': r.name,
                    'category': r.category.value,
                    'description': r.description,
                    'difficulty': r.difficulty,
                    'build_time_hours': r.build_time_hours,
                    'economics': {
                        'parts_cost': r.parts_cost,
                        'market_price_low': r.market_price_low,
                        'market_price_high': r.market_price_high,
                        'profit_margin': r.profit_margin,
                        'roi_percent': r.roi_percent,
                        'missing_parts_cost': r.missing_parts_cost
                    },
                    'inventory': {
                        'match_percent': r.inventory_match_percent,
                        'components_owned': r.components_owned,
                        'components_needed': r.components_needed
                    }
                }
                for r in recipes
            ],
            'count': len(recipes),
            'filters_applied': {
                'max_difficulty': max_difficulty,
                'max_build_hours': max_build_hours,
                'max_budget': max_budget,
                'min_match_percent': min_match_percent
            }
        }

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/recipes/budget-optimize', methods=['POST'])
def budget_optimize():
    """
    Optimize project selection for a budget

    Request body:
    {
        "inventory": [...],
        "budget": 20.0,              // max budget for missing parts
        "goal": "learning"           // 'roi', 'learning', 'complexity', 'speed'
    }

    Returns optimized recommendation
    """
    try:
        data = request.get_json()

        if not data or 'inventory' not in data or 'budget' not in data:
            return jsonify({'error': 'inventory and budget fields required'}), 400

        inventory = data['inventory']
        budget = data['budget']
        goal = data.get('goal', 'roi')

        # Optimize
        result = recipe_optimizer.optimize_for_budget(
            inventory=inventory,
            budget=budget,
            goal=goal
        )

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/instructions/<project_name>', methods=['GET'])
def get_build_instructions(project_name):
    """
    Get step-by-step build instructions for a project

    Returns detailed assembly guide with wiring diagrams, code, and troubleshooting
    """
    try:
        # Get instructions
        instructions = instructions_gen.generate_instructions(project_name)

        if not instructions:
            return jsonify({'error': f'Instructions not found for project: {project_name}'}), 404

        return jsonify(instructions)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/instructions', methods=['GET'])
def list_available_instructions():
    """
    List all projects with available build instructions
    """
    try:
        available = instructions_gen.list_available_projects()

        return jsonify({
            'available_projects': available,
            'count': len(available)
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/learning-paths', methods=['GET'])
def list_learning_paths():
    """
    List all available learning paths

    Returns overview of all learning paths with metadata
    """
    try:
        paths = learning_paths.get_all_paths()

        result = {
            'learning_paths': [
                {
                    'id': p.path_id,
                    'name': p.name,
                    'description': p.description,
                    'total_modules': p.total_modules,
                    'total_hours': p.total_hours,
                    'target_audience': p.target_audience,
                    'skills_gained': p.skills_gained
                }
                for p in paths
            ],
            'count': len(paths)
        }

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/learning-paths/<path_id>', methods=['GET'])
def get_learning_path(path_id):
    """
    Get detailed learning path with all modules and projects

    Returns complete curriculum with module-by-module breakdown
    """
    try:
        path = learning_paths.get_path(path_id)

        if not path:
            return jsonify({'error': f'Learning path not found: {path_id}'}), 404

        result = {
            'id': path.path_id,
            'name': path.name,
            'description': path.description,
            'target_audience': path.target_audience,
            'total_modules': path.total_modules,
            'total_hours': path.total_hours,
            'skills_gained': path.skills_gained,
            'modules': [
                {
                    'number': m.module_number,
                    'title': m.title,
                    'description': m.description,
                    'estimated_hours': m.estimated_hours,
                    'projects': m.projects,
                    'concepts_taught': m.concepts_taught,
                    'prerequisites': m.prerequisites
                }
                for m in path.modules
            ]
        }

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/learning-paths/recommend', methods=['POST'])
def recommend_learning_path():
    """
    Get personalized learning path recommendations

    Request body:
    {
        "current_skills": ["arduino_basics", "sensors"],  // optional
        "interests": ["iot", "home_automation"],          // optional
        "available_hours": 20                             // optional
    }

    Returns recommended learning paths ranked by match
    """
    try:
        data = request.get_json() or {}

        current_skills = data.get('current_skills', [])
        interests = data.get('interests', [])
        available_hours = data.get('available_hours')

        recommendations = learning_paths.recommend_path(
            current_skills=current_skills,
            interests=interests,
            available_hours=available_hours
        )

        result = {
            'recommendations': [
                {
                    'id': r['path'].path_id,
                    'name': r['path'].name,
                    'description': r['path'].description,
                    'total_hours': r['path'].total_hours,
                    'match_score': r['score'],
                    'reason': r['reason']
                }
                for r in recommendations
            ],
            'count': len(recommendations)
        }

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/pricing/component', methods=['POST'])
def get_component_pricing():
    """
    Get real-time component pricing

    Request body:
    {
        "components": [
            {"id": "arduino_uno", "condition": "new", "quantity": 1},
            {"id": "bme280", "condition": "used", "quantity": 2}
        ]
    }

    Returns detailed pricing breakdown with supplier info
    """
    try:
        data = request.get_json()

        if not data or 'components' not in data:
            return jsonify({'error': 'components field required'}), 400

        breakdown = pricing_service.get_price_breakdown(data['components'])

        return jsonify(breakdown)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/pricing/market/<project_name>', methods=['GET'])
def get_market_pricing(project_name):
    """
    Get market pricing for a completed project

    Returns price range from eBay/Etsy comparable listings
    """
    try:
        # Decode URL-encoded project name
        from urllib.parse import unquote
        project_name = unquote(project_name)

        market_data = pricing_service.get_project_market_price(project_name)

        return jsonify(market_data)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# V2 API - UNIFIED WORKFLOW ENGINE
# Integrates educational tools (recipe optimizer, learning paths, instructions)
# with professional validation (KiCAD, circuit solver, power tree validator)
# ============================================================================

@app.route('/api/v2/workflow/beginner', methods=['POST'])
@require_api_key("workflow_beginner")
def beginner_workflow():
    """
    Complete beginner workflow

    Request body:
    {
        "skill_level": 1,                           // 1-5 (BEGINNER-PROFESSIONAL)
        "completed_projects": ["LED Blink"],        // optional
        "inventory": [                              // optional
            {"id": "arduino_uno", "condition": "used", "quantity": 1},
            {"id": "bme280", "condition": "new", "quantity": 1}
        ],
        "budget": 50.0,                             // optional (default: 50)
        "goal": "learning"                          // "learning", "roi", or "speed"
    }

    Returns:
    {
        "status": "success" | "prerequisites_missing" | "no_projects",
        "project": {...},                           // if available
        "instructions": {...},                      // if project selected
        "next_steps": [...],
        "estimated_cost": 0.0,
        "estimated_time_hours": 0.0
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'Request body required'}), 400

        # Build user profile
        user = UserProfile(
            skill_level=UserLevel(data.get('skill_level', 1)),
            completed_projects=data.get('completed_projects', []),
            inventory=data.get('inventory', []),
            budget=data.get('budget', 50.0),
            goal=data.get('goal', 'learning')
        )

        # Execute beginner workflow
        result = workflow_engine.execute_beginner_workflow(user)

        # Format response
        response = {
            'status': result.status,
            'next_steps': result.next_steps,
            'estimated_cost': result.estimated_cost,
            'estimated_time_hours': result.estimated_time_hours
        }

        # Add project details if available
        if result.project:
            response['project'] = {
                'name': result.project.name,
                'category': result.project.category.value,
                'description': result.project.description,
                'difficulty': result.project.difficulty,
                'build_time_hours': result.project.build_time_hours,
                'economics': {
                    'parts_cost': result.project.parts_cost,
                    'market_price_low': result.project.market_price_low,
                    'market_price_high': result.project.market_price_high,
                    'roi_percent': result.project.roi_percent,
                    'missing_parts_cost': result.project.missing_parts_cost
                },
                'inventory': {
                    'match_percent': result.project.inventory_match_percent,
                    'components_owned': result.project.components_owned,
                    'components_needed': result.project.components_needed
                }
            }

        # Add instructions if available
        if result.instructions:
            response['instructions'] = result.instructions

        return jsonify(response)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/v2/workflow/complete', methods=['POST'])
@require_api_key("workflow_complete")
def complete_workflow():
    """
    End-to-end complete workflow

    Request body:
    {
        "user": {
            "skill_level": 2,                       // 1-5 (BEGINNER-PROFESSIONAL)
            "completed_projects": ["LED Blink"],    // optional
            "inventory": [...],                     // optional
            "budget": 20.0,                         // optional
            "goal": "learning"                      // "learning", "roi", or "speed"
        },
        "project_name": "Air Quality Monitor",
        "kicad_file": "/path/to/design.net"        // optional - for validation
    }

    Returns complete workflow result with:
    - Project details
    - Build instructions
    - Validation issues (if KiCAD file provided)
    - Manufacturing readiness
    - Next steps
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'Request body required'}), 400

        if 'user' not in data or 'project_name' not in data:
            return jsonify({'error': 'user and project_name fields required'}), 400

        # Build user profile
        user_data = data['user']
        user = UserProfile(
            skill_level=UserLevel(user_data.get('skill_level', 2)),
            completed_projects=user_data.get('completed_projects', []),
            inventory=user_data.get('inventory', []),
            budget=user_data.get('budget', 50.0),
            goal=user_data.get('goal', 'learning')
        )

        # Execute complete workflow
        result = workflow_engine.execute_complete_workflow(
            user=user,
            project_name=data['project_name'],
            kicad_file=data.get('kicad_file')
        )

        # Format response
        response = {
            'status': result.status,
            'next_steps': result.next_steps,
            'estimated_cost': result.estimated_cost,
            'estimated_time_hours': result.estimated_time_hours
        }

        # Add project details
        if result.project:
            response['project'] = {
                'name': result.project.name,
                'category': result.project.category.value,
                'description': result.project.description,
                'difficulty': result.project.difficulty,
                'build_time_hours': result.project.build_time_hours,
                'economics': {
                    'parts_cost': result.project.parts_cost,
                    'roi_percent': result.project.roi_percent,
                    'missing_parts_cost': result.project.missing_parts_cost
                }
            }

        # Add instructions
        if result.instructions:
            response['instructions'] = result.instructions

        # Add validation issues
        if result.validation_issues:
            response['validation'] = {
                'issues_count': len(result.validation_issues),
                'issues': [
                    {
                        'severity': i.severity,
                        'component': i.component,
                        'issue': i.issue,
                        'solution': i.solution
                    }
                    for i in result.validation_issues
                ]
            }

        # Add manufacturing status
        if result.manufacturing_files:
            response['manufacturing'] = result.manufacturing_files

        return jsonify(response)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/v2/workflow/validate-kicad', methods=['POST'])
@require_api_key("validate_kicad")
def validate_kicad_workflow():
    """
    Professional KiCAD validation workflow

    Request (multipart/form-data or JSON):
    - kicad_file: Path to .net or .kicad_pcb file, or file upload
    - hints: JSON hints (optional - will auto-generate if missing)

    Hints schema:
    {
        "sources": [
            {"name": "VUSB", "net": "VBUS", "volts": 5.0, "max_current_a": 0.5}
        ],
        "loads_cc": [
            {"name": "ESP32", "net": "+3V3", "amps": 0.24}
        ],
        "voltage_constraints": [
            {"net": "+3V3", "min_v": 3.0, "max_v": 3.6}
        ]
    }

    Returns:
    {
        "status": "validation_passed" | "validation_warning" | "validation_failed",
        "validation": {
            "issues_count": 2,
            "critical": 0,
            "errors": 0,
            "warnings": 2,
            "issues": [
                {
                    "severity": "warning",
                    "component": "Trace +3V3",
                    "issue": "Excessive voltage drop",
                    "physics": {
                        "current_a": 1.2,
                        "voltage_drop": 0.35,
                        "current_width_mm": 0.5,
                        "required_width_mm": 2.0
                    },
                    "solution": "Widen trace to 2.0mm or use copper pour"
                }
            ]
        },
        "manufacturing_ready": false,
        "next_steps": [...]
    }
    """
    try:
        # Handle both JSON and multipart form data
        if request.is_json:
            data = request.get_json()
            kicad_file = data.get('kicad_file')
            hints = data.get('hints')
        else:
            # Handle file upload
            if 'kicad_file' not in request.files:
                return jsonify({'error': 'kicad_file required (path or file upload)'}), 400

            # Save uploaded file temporarily
            file = request.files['kicad_file']
            temp_dir = Path(tempfile.gettempdir()) / 'circuit-ai'
            temp_dir.mkdir(exist_ok=True)
            orig_suffix = Path(file.filename or "").suffix.lower()
            suffix = ".kicad_pcb" if orig_suffix == ".kicad_pcb" else ".net"
            kicad_file = temp_dir / f"{uuid.uuid4().hex[:8]}{suffix}"
            file.save(str(kicad_file))

            hints = request.form.get('hints')
            if hints:
                import json
                hints = json.loads(hints)

        if not kicad_file:
            return jsonify({'error': 'kicad_file required'}), 400

        # Execute validation workflow
        result = workflow_engine.execute_validation_workflow(
            kicad_file=str(kicad_file),
            hints=hints
        )

        # Format response
        response = {
            'status': result.status,
            'next_steps': result.next_steps
        }

        # Add validation details
        if result.validation_issues:
            critical = [i for i in result.validation_issues if i.severity == 'critical']
            errors = [i for i in result.validation_issues if i.severity == 'error']
            warnings = [i for i in result.validation_issues if i.severity == 'warning']

            response['validation'] = {
                'issues_count': len(result.validation_issues),
                'critical': len(critical),
                'errors': len(errors),
                'warnings': len(warnings),
                'issues': [
                    {
                        'severity': i.severity,
                        'component': i.component,
                        'issue': i.issue,
                        'solution': i.solution,
                        'physics': i.physics if hasattr(i, 'physics') else None
                    }
                    for i in result.validation_issues
                ]
            }

            response['manufacturing_ready'] = (len(critical) == 0 and len(errors) == 0)
        else:
            response['validation'] = {
                'issues_count': 0,
                'critical': 0,
                'errors': 0,
                'warnings': 0,
                'issues': []
            }
            response['manufacturing_ready'] = True

        # Optional: include geometry for `.kicad_pcb` inputs (enables 2.5D/3D viewer)
        try:
            if str(kicad_file).lower().endswith(".kicad_pcb"):
                from src.engines.kicad_pcb_geometry import extract_pcb_geometry

                response["pcb_geometry"] = extract_pcb_geometry(str(kicad_file))
        except Exception:
            # Geometry is best-effort; validation results should still return.
            pass

        return jsonify(response)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/v2/manufacture/bom', methods=['POST'])
@require_api_key("manufacture_bom")
def generate_bom():
    """
    Generate Bill of Materials (BOM) from KiCAD netlist

    Request (multipart/form-data or JSON):
    - netlist_path: Path to .net file or file upload
    - include_pricing: Boolean (optional, default: false)
    - format: "json" or "csv" (optional, default: "json")

    Returns:
    {
        "status": "success",
        "summary": {
            "total_components": 15,
            "unique_parts": 7,
            "parts_with_digikey_numbers": 5,
            "estimated_total_cost": 12.50
        },
        "items": [
            {
                "references": ["R1", "R2"],
                "value": "10K",
                "footprint": "Resistor_SMD:R_0805",
                "quantity": 2,
                "part_number": "RMCF0805FT10K0CT-ND",
                "supplier": "DigiKey",
                "unit_price": 0.10,
                "total_price": 0.20
            },
            ...
        ]
    }
    """
    try:
        from engines.bom_generator import BOMGenerator

        # Handle both JSON and multipart form data
        if request.is_json:
            data = request.get_json()
            netlist_path = data.get('netlist_path')
            include_pricing = data.get('include_pricing', False)
            output_format = data.get('format', 'json')
        else:
            # Handle file upload
            if 'netlist_file' not in request.files:
                return jsonify({'error': 'netlist_path or netlist_file required'}), 400

            # Save uploaded file temporarily
            file = request.files['netlist_file']
            temp_dir = Path(tempfile.gettempdir()) / 'circuit-ai'
            temp_dir.mkdir(exist_ok=True)
            netlist_path = temp_dir / f"{uuid.uuid4().hex[:8]}.net"
            file.save(str(netlist_path))

            include_pricing = request.form.get('include_pricing', 'false').lower() == 'true'
            output_format = request.form.get('format', 'json')

        if not netlist_path:
            return jsonify({'error': 'netlist_path required'}), 400

        # Generate BOM
        generator = BOMGenerator()
        bom = generator.generate_bom(str(netlist_path), include_pricing=include_pricing)

        # Return appropriate format
        if output_format == 'csv':
            csv_content = generator.export_csv(bom)
            return csv_content, 200, {
                'Content-Type': 'text/csv',
                'Content-Disposition': 'attachment; filename=bom.csv'
            }
        else:
            return jsonify(bom)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/v2/manufacture/gerber', methods=['POST'])
@require_api_key("manufacture_gerber")
def generate_gerber():
    """
    Generate Gerber files from KiCAD PCB

    Request (multipart/form-data or JSON):
    - pcb_path: Path to .kicad_pcb file or file upload
    - quantity: PCB quantity for cost estimation (optional, default: 5)

    Returns:
    {
        "status": "success",
        "pcb_info": {
            "name": "my_board",
            "dimensions": "100mm x 80mm",
            "layers": 2,
            "thickness": "1.6mm"
        },
        "gerber_files": [...],
        "zip_url": "/download/gerbers/my_board-gerbers.zip",
        "manufacturing_ready": true,
        "cost_estimates": {
            "JLCPCB": {"price_usd": 2.00, "lead_time_days": "2-5"},
            ...
        }
    }
    """
    try:
        from engines.gerber_generator import GerberGenerator

        # Handle both JSON and multipart form data
        if request.is_json:
            data = request.get_json()
            pcb_path = data.get('pcb_path')
            quantity = data.get('quantity', 5)
        else:
            # Handle file upload
            if 'pcb_file' not in request.files:
                return jsonify({'error': 'pcb_path or pcb_file required'}), 400

            # Save uploaded file temporarily
            file = request.files['pcb_file']
            temp_dir = Path(tempfile.gettempdir()) / 'circuit-ai'
            temp_dir.mkdir(exist_ok=True)
            pcb_path = temp_dir / f"{uuid.uuid4().hex[:8]}.kicad_pcb"
            file.save(str(pcb_path))

            quantity = int(request.form.get('quantity', 5))

        if not pcb_path:
            return jsonify({'error': 'pcb_path required'}), 400

        # Generate Gerber package
        generator = GerberGenerator()
        package = generator.generate_gerber_package(str(pcb_path))

        # Create ZIP file
        temp_dir = Path(tempfile.gettempdir()) / 'circuit-ai' / 'gerbers'
        temp_dir.mkdir(parents=True, exist_ok=True)
        zip_filename = f"{package['pcb_info']['name']}-gerbers.zip"
        zip_path = temp_dir / zip_filename
        generator.create_gerber_zip(package, str(zip_path))

        # Get cost estimates
        pcb_info = generator.extract_pcb_info(str(pcb_path))
        cost_estimates = generator.estimate_manufacturing_cost(pcb_info, quantity)

        # Format response
        response = {
            'status': package['status'],
            'pcb_info': package['pcb_info'],
            'gerber_files': [
                {
                    'filename': layer.filename,
                    'layer_type': layer.layer_type,
                    'description': layer.description,
                    'size_bytes': len(layer.content)
                }
                for layer in package['gerber_files']
            ],
            'zip_file': str(zip_path),
            'zip_size_kb': zip_path.stat().st_size / 1024,
            'manufacturing_ready': package['manufacturing_ready'],
            'cost_estimates': cost_estimates['estimates'],
            'compatible_fabs': package['compatible_fabs']
        }

        return jsonify(response)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/v2/manufacture/download-gerber/<filename>', methods=['GET'])
@require_api_key("download_gerber")
def download_gerber(filename):
    """Download generated Gerber ZIP file"""
    try:
        temp_dir = Path(tempfile.gettempdir()) / 'circuit-ai' / 'gerbers'
        file_path = temp_dir / filename

        if not file_path.exists():
            return jsonify({'error': 'File not found'}), 404

        return send_file(
            file_path,
            mimetype='application/zip',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# V1 API - ORIGINAL ENDPOINTS
# ============================================================================

@app.route('/', methods=['GET'])
def index():
    """Landing page or API documentation"""
    # Serve landing page for browser requests, JSON for API clients
    if 'text/html' in request.headers.get('Accept', ''):
        return app.send_static_file('index.html')

    # Return JSON API docs for curl/API clients
    return jsonify({
        'service': 'Circuit-AI API',
        'version': '0.4.0',
        'description': 'Complete Arduino/IoT project assistant: Validate circuits, export to Fritzing, optimize inventory, get build instructions, follow structured learning paths, and professional PCB validation',
        'endpoints': {
            '=== V2 API - UNIFIED WORKFLOW ENGINE ===': '',
            'POST /api/v2/workflow/beginner': 'Complete beginner workflow (learning paths + projects)',
            'POST /api/v2/workflow/complete': 'End-to-end workflow (recipe → instructions → validation)',
            'POST /api/v2/workflow/validate-kicad': 'Professional KiCAD PCB validation',
            '=== V1 API - CORE FEATURES ===': '',
            'GET /api/health': 'Health check',
            'GET /api/components': 'List available components',
            'POST /api/validate': 'Validate circuit design',
            'POST /api/export/fritzing': 'Export to Fritzing .fzz file',
            'POST /api/design': 'Complete design workflow',
            'POST /api/recipes/analyze-inventory': 'Analyze inventory value',
            'POST /api/recipes/generate': 'Generate project recipes from inventory',
            'POST /api/recipes/shopping-list': 'Get shopping list for project',
            'POST /api/recipes/filter': 'Advanced recipe filtering (difficulty, time, budget)',
            'POST /api/recipes/budget-optimize': 'Optimize project selection for budget',
            'GET /api/instructions': 'List projects with build instructions',
            'GET /api/instructions/<project_name>': 'Get detailed build instructions',
            'GET /api/learning-paths': 'List all learning paths',
            'GET /api/learning-paths/<path_id>': 'Get detailed learning path curriculum',
            'POST /api/learning-paths/recommend': 'Get personalized learning recommendations',
            'POST /api/pricing/component': 'Get real-time component pricing',
            'GET /api/pricing/market/<project_name>': 'Get market pricing for project'
        },
        'examples': {
            'validate': {
                'endpoint': '/api/validate',
                'method': 'POST',
                'body': {
                    'microcontroller': 'arduino_uno',
                    'components': ['bme280', 'servo_sg90'],
                    'external_power': False
                }
            },
            'recipes': {
                'endpoint': '/api/recipes/generate',
                'method': 'POST',
                'body': {
                    'inventory': [
                        {'id': 'arduino_uno', 'condition': 'used', 'quantity': 1},
                        {'id': 'bme280', 'condition': 'new', 'quantity': 1}
                    ],
                    'top_n': 5,
                    'validate': True
                }
            }
        },
        'value_proposition': [
            '🎓 EDUCATION → PROFESSIONAL: Complete workflow integration',
            '✓ V2 API: Unified workflows (beginner → hobbyist → professional)',
            '✓ Learn → Build → Validate → Manufacture (end-to-end)',
            '✓ Professional KiCAD PCB validation (MNA solver, power tree)',
            '✓ Validates circuits BEFORE you build them (saves $$$)',
            '✓ Catches voltage mismatches, trace drops, power issues',
            '✓ Quantitative fixes: "Widen trace to 2mm" (not "traces too thin")',
            '✓ Turn junk drawer into valuable projects (29 recipes)',
            '✓ Step-by-step build instructions with wiring diagrams',
            '✓ 5 structured learning paths (106 hours of curriculum)',
            '✓ Real-time component pricing (DigiKey integration)',
            '✓ Market pricing from eBay/Etsy comparables',
            '✓ Exports to professional tools (Fritzing)',
            '✓ FREE tier: Basic validation + recipe browsing',
            '✓ PRO tier ($9/mo): Full workflows + KiCAD validation + API'
        ],
        'features': {
            'v2_unified_workflows': 'Complete journey: Learn → Build → Validate → Manufacture',
            'kicad_validation': 'Professional PCB validation (MNA solver, power tree analysis)',
            'circuit_validation': 'Prevent costly mistakes before building',
            'quantitative_fixes': 'Physics-based solutions with exact measurements',
            'fritzing_export': 'Professional diagrams for documentation',
            'recipe_optimizer': 'Turn spare parts into valuable projects (29 recipes)',
            'inventory_analysis': 'Know the value of what you have',
            'shopping_lists': 'Minimize costs for missing parts',
            'build_instructions': 'Step-by-step assembly guides with wiring diagrams',
            'learning_paths': '5 complete curriculums from beginner to advanced',
            'real_time_pricing': 'DigiKey API + eBay market data',
            'advanced_filtering': 'Filter by difficulty, time, budget, ROI',
            'budget_optimization': 'Find best project for your budget and goals',
            'skill_based_routing': 'Personalized workflows based on skill level'
        },
        'stats': {
            'total_endpoints': 20,
            'v2_workflow_endpoints': 3,
            'v1_endpoints': 17,
            'project_recipes': 29,
            'learning_paths': 5,
            'learning_modules': 22,
            'total_curriculum_hours': 106,
            'components_supported': 23,
            'fritzing_mappings': 19,
            'user_skill_levels': 5
        }
    })


if __name__ == '__main__':
    print("="*70)
    print("  CIRCUIT-AI API SERVER v0.4.0")
    print("  🎓 EDUCATION → PROFESSIONAL: UNIFIED WORKFLOWS")
    print("="*70)
    print()
    print("Starting server on http://localhost:5000")
    print()
    print("=" * 70)
    print("V2 API - UNIFIED WORKFLOW ENGINE 🚀")
    print("=" * 70)
    print("Complete end-to-end workflows:")
    print("  POST /api/v2/workflow/beginner      - Complete beginner workflow")
    print("  POST /api/v2/workflow/complete      - End-to-end (recipe→instructions→validation)")
    print("  POST /api/v2/workflow/validate-kicad - Professional KiCAD PCB validation")
    print()
    print("Features:")
    print("  ✓ Learn → Build → Validate → Manufacture")
    print("  ✓ Skill-based routing (BEGINNER → PROFESSIONAL)")
    print("  ✓ KiCAD integration (MNA solver, power tree analysis)")
    print("  ✓ Quantitative fixes: 'Widen trace to 2mm'")
    print()
    print("=" * 70)
    print("V1 API - CORE FEATURES")
    print("=" * 70)
    print()
    print("Core Endpoints:")
    print("  GET  /                              - API documentation")
    print("  GET  /api/health                    - Health check")
    print("  GET  /api/components                - List components")
    print()
    print("Circuit Validation:")
    print("  POST /api/validate                  - Validate circuit design")
    print("  POST /api/export/fritzing           - Export to Fritzing")
    print("  POST /api/design                    - Complete workflow")
    print()
    print("Recipe Optimizer (29 projects):")
    print("  POST /api/recipes/analyze-inventory - Analyze inventory value")
    print("  POST /api/recipes/generate          - Generate project recipes")
    print("  POST /api/recipes/filter            - Advanced filtering")
    print("  POST /api/recipes/budget-optimize   - Budget optimization")
    print("  POST /api/recipes/shopping-list     - Get shopping list")
    print()
    print("Build Instructions:")
    print("  GET  /api/instructions              - List available projects")
    print("  GET  /api/instructions/<project>    - Get step-by-step guide")
    print()
    print("Learning Paths (106 hours curriculum):")
    print("  GET  /api/learning-paths            - List all paths")
    print("  GET  /api/learning-paths/<id>       - Get detailed curriculum")
    print("  POST /api/learning-paths/recommend  - Get recommendations")
    print()
    print("Pricing Service:")
    print("  POST /api/pricing/component         - Component pricing (DigiKey)")
    print("  GET  /api/pricing/market/<project>  - Market pricing (eBay)")
    print()
    print("=" * 70)
    print("Try:")
    print("  curl http://localhost:5000/")
    print("  curl http://localhost:5000/api/health")
    print()
    print("=" * 70)
    print()

    import os
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'True').lower() == 'true'
    app.run(debug=debug, host='0.0.0.0', port=port)
