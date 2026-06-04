"""
Setup script for 3d-splicer package.

Allows installation via pip for production deployment.
"""

from setuptools import setup, find_namespace_packages
from pathlib import Path

# Read README for long description
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text() if readme_file.exists() else ""

# Read requirements
requirements_file = Path(__file__).parent / "requirements-core.txt"
requirements = []
if requirements_file.exists():
    requirements = [
        line.strip()
        for line in requirements_file.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]

setup(
    name="splicer3d",
    version="0.1.0",
    description="3D case generation service for PCBs with Circuit.AI integration",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="3d-splicer Team",
    author_email="dev@example.com",
    url="https://github.com/yourorg/3d-splicer",

    # Package discovery
    packages=find_namespace_packages(include=["services", "services.*", "src", "src.*", "templates"]),
    py_modules=["circuit_ai_adapter", "circuit_ai_client", "cli"],

    # Dependencies
    install_requires=requirements,

    # Python version requirement
    python_requires=">=3.11",

    # Entry points for CLI tools
    entry_points={
        "console_scripts": [
            "splicer=cli:main",
        ],
    },

    # Package data
    package_data={
        "templates": ["*.j2"],
        "": ["*.txt", "*.md", "*.json", "*.yaml"],
    },

    # Classifiers
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],

    # Extras for development
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-asyncio>=0.21",
            "pytest-cov>=4.0",
            "black>=23.0",
            "flake8>=6.0",
            "mypy>=1.0",
        ],
    },
)
