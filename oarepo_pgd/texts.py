"""Texts from the configuration in the reader's language.

A label, definition, profile name or help text in the YAML is either a string,
used for every language, or a mapping of language codes to strings::

    label: {en: Interview transcript, cs: Přepis rozhovoru}

A mapping is shown in the current locale's language, falling back to English
and then to its first entry.
"""

from __future__ import annotations

from typing import Any


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
