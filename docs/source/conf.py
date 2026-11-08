# Configuration file for the Sphinx documentation builder.
#
# For a full list of options see:
# http://www.sphinx-doc.org/en/master/config

# -- Path setup ---------------------------------------------------------
#
# dofjson is installed editable by the builds that render these docs
# (.readthedocs.yaml, test.yml) rather than reached via sys.path manipulation
# here, so conf.py only needs to import the already-installed package to read
# its __version__.

import dofjson

# -- Project information -------------------------------------------------

project = "dofjson"
copyright = "2026, legistlan"
author = "legistlan"

# The repository is the package, so there is a single version here -- kept as
# the same |dofjson_version| substitution the page used while it was one page
# of the LegalIA monorepo's site.
rst_epilog = f"""
.. |dofjson_version| replace:: {dofjson.__version__}
"""

# -- General configuration ------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx.ext.doctest",
]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "requests": ("https://requests.readthedocs.io/en/latest/", None),
}

source_suffix = ".rst"
master_doc = "index"
language = "en"
exclude_patterns = []

pygments_style = "sphinx"
highlight_language = "python"
autodoc_member_order = "bysource"
autodoc_class_signature = "separated"
add_function_parentheses = False
add_module_names = False

# -- Options for HTML output ----------------------------------------------

html_theme = "furo"
htmlhelp_basename = "dofjsondoc"
