"""
Scraper modules for Circuit-AI
Extracts data from tutorials, component databases, and verified projects
"""

try:
    from .code_library_scraper import CodeLibraryScraper, CodeExample
except ImportError:
    CodeLibraryScraper = None
    CodeExample = None

__all__ = ['CodeLibraryScraper', 'CodeExample']
