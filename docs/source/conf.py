import os
import sys
import re
import tomllib  # Python 3.11+; use 'tomli' for earlier versions

sys.path.insert(0, os.path.abspath(".."))

# -- Project metadata from pyproject.toml ------------------------------------

def get_metadata():
    pyproject_path = os.path.join(os.path.dirname(__file__), "..", "..", "pyproject.toml")
    pyproject_path = os.path.abspath(pyproject_path)
    with open(pyproject_path, "rb") as f:
        pyproject_data = tomllib.load(f)
    project = pyproject_data.get("project", {})
    authors = project.get("authors", [])
    author_names = ", ".join(a.get("name", "") for a in authors if "name" in a)

    init_path = os.path.join(os.path.dirname(__file__), "..", "..", "mapchete_eo", "__init__.py")
    init_path = os.path.abspath(init_path)
    with open(init_path, "r", encoding="utf-8") as f:
        content = f.read()
    version_match = re.search(r'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]', content, re.MULTILINE)
    version = version_match.group(1) if version_match else "0.0.0"

    return version, author_names

release, author = get_metadata()

# -- General configuration ---------------------------------------------------


version, author = get_metadata()

project = "mapchete-eo"
author = author

release = version

version, author = get_metadata()

rst_prolog = f"""
.. |author| replace:: {author}
.. |version| replace:: {version}
"""


extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.autosummary",
]

autosummary_generate = True

# Optional: include tests folder on path (if you want to import tests modules)
sys.path.insert(0, os.path.abspath("../.."))


templates_path = ["_templates"]
exclude_patterns = []

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
