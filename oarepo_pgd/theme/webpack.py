"""Deposit-form components, imported by hosts through the ``@js/oarepo_pgd`` alias.

The components have no entry point: they reach the page through the UI
overrides bundle or through the host's own deposit form. They are styled with
the classes of the host's theme, so the plugin ships no stylesheet.
"""

from invenio_assets.webpack import WebpackThemeBundle

theme = WebpackThemeBundle(
    __name__,
    "assets",
    default="semantic-ui",
    themes={
        "semantic-ui": {
            "entry": {},
            "dependencies": {},
            "aliases": {
                "@js/oarepo_pgd": "js/oarepo_pgd",
                "@translations/oarepo_pgd": "translations/oarepo_pgd/i18next.js",
            },
        },
    },
)
