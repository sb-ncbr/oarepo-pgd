"""Deposit-form components, imported by hosts through the ``@js/oarepo_pgd`` alias.

The components have no entry point: they reach the page through the UI
overrides bundle or through the host's own deposit form. The only entry builds
the plugin's stylesheet, which the host links from its CSS template.
"""

from invenio_assets.webpack import WebpackThemeBundle

theme = WebpackThemeBundle(
    __name__,
    "assets",
    default="semantic-ui",
    themes={
        "semantic-ui": {
            "entry": {"oarepo_pgd_components": "./js/oarepo_pgd/custom-components.js"},
            "dependencies": {},
            "aliases": {
                "@js/oarepo_pgd": "js/oarepo_pgd",
                "@translations/oarepo_pgd": "translations/oarepo_pgd/i18next.js",
            },
        },
    },
)
