from importlib import resources
from pathlib import Path

from jinja2 import Environment, FileSystemLoader


def _templates_dir() -> Path:
    source_templates = Path(__file__).parents[2] / "templates"
    if source_templates.exists():
        return source_templates

    try:
        return Path(str(resources.files("templates")))
    except ModuleNotFoundError as exc:
        raise FileNotFoundError("Could not locate 3d-splicer templates.") from exc


def render_template(name: str, context: dict) -> str:
    """Render a Jinja2 template with the given context."""
    env = Environment(
        loader=FileSystemLoader(str(_templates_dir())),
        trim_blocks=True,
        lstrip_blocks=True
    )
    tpl = env.get_template(name)
    return tpl.render(**context)
