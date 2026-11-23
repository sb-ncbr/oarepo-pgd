"""Texts from the configuration in the reader's language.

A label, definition, profile name or help text in the YAML is either a string,
used for every language, or a mapping of language codes to strings::

    label: {en: Interview transcript, cs: Přepis rozhovoru}

A mapping is shown in the current locale's language, falling back to English
and then to its first entry.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

TEXT_FIELDS = {
    "semantic_types": ("label", "definition"),
    "profiles": ("dataset_category",),
    "requirements": ("label", "help"),
}


def current_language() -> str:
    """The language of the current request's locale, or English where there is none."""
    try:
        from flask_babel import get_locale

        locale = get_locale()
    except (RuntimeError, KeyError):  # no application context, or an app without Flask-Babel
        locale = None
    return locale.language if locale else "en"


def localized(text: Any, language: str | None = None) -> Any:
    """The text in ``language`` (default: the current locale's language)."""
    if not isinstance(text, dict):
        return text
    language = language or current_language()
    return text.get(language) or text.get("en") or next(iter(text.values()), "")


def localized_configuration(configuration: dict[str, Any], language: str | None = None) -> dict[str, Any]:
    """A copy of the configuration with every text in one language."""
    language = language or current_language()
    result = deepcopy(configuration)
    for item in result.get("semantic_types", []):
        _localize(item, TEXT_FIELDS["semantic_types"], language)
    for profile in result.get("profiles", []):
        _localize(profile, TEXT_FIELDS["profiles"], language)
        for requirement in profile.get("requirements", []):
            _localize(requirement, TEXT_FIELDS["requirements"], language)
    return result


def _localize(item: dict[str, Any], fields: tuple[str, ...], language: str) -> None:
    for field in fields:
        if field in item:
            item[field] = localized(item[field], language)


class ConfigurationLabels:
    """Facet value labels from the configuration, in the current locale's language."""

    def __init__(self, texts: dict[str, Any]) -> None:
        """Keep the texts by identifier."""
        self.texts = texts

    def __call__(self, ids: list[str]) -> dict[str, str]:
        """Return the labels of the given identifiers."""
        language = current_language()
        return {id_: localized(self.texts.get(id_, id_), language) for id_ in ids}

    def __eq__(self, other: object) -> bool:
        """Compare by texts, so identical model definitions compare equal."""
        return isinstance(other, ConfigurationLabels) and other.texts == self.texts

    __hash__ = None  # type: ignore[assignment]
