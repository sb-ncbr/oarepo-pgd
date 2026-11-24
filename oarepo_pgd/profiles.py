"""The deposition configuration as objects.

``load_configuration`` builds these from the YAML. A text (label, definition,
profile name, help) is a string, or a mapping of language codes to strings.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass, replace
from typing import Any

from .texts import current_language, localized

Text = str | dict[str, str]


@dataclass(frozen=True)
class SemanticType:
    """What a file means, such as an interview transcript."""

    id: str
    label: Text
    definition: Text
    uri: str | None = None
    requires_description: bool = False
    search_filter: bool = True

    def localized(self, language: str) -> SemanticType:
        """The type with its texts in one language."""
        return replace(self, label=localized(self.label, language), definition=localized(self.definition, language))


@dataclass(frozen=True)
class PermittedType:
    """A semantic type as one profile permits it."""

    id: str
    filename_patterns: tuple[str, ...] = ()
    formats: tuple[str, ...] | None = None


@dataclass(frozen=True)
class Requirement:
    """How many files of some semantic types a profile asks for."""

    id: str
    label: Text
    level: str
    min_files: int
    semantic_types: tuple[str, ...]
    max_files: int | None = None
    help: Text | None = None

    def localized(self, language: str) -> Requirement:
        """The requirement with its texts in one language."""
        return replace(self, label=localized(self.label, language), help=localized(self.help, language))


@dataclass(frozen=True)
class Profile:
    """A deposition profile: the permitted semantic types and the file requirements."""

    id: str
    revision: str
    dataset_category: Text
    semantic_types: tuple[PermittedType, ...]
    requirements: tuple[Requirement, ...]

    def permitted(self, type_id: str) -> PermittedType | None:
        """The profile's entry for a semantic type, if it permits the type."""
        return next((item for item in self.semantic_types if item.id == type_id), None)

    def localized(self, language: str) -> Profile:
        """The profile with its texts in one language."""
        return replace(
            self,
            dataset_category=localized(self.dataset_category, language),
            requirements=tuple(requirement.localized(language) for requirement in self.requirements),
        )


@dataclass(frozen=True)
class Configuration:
    """One model's semantic types and deposition profiles."""

    semantic_types: tuple[SemanticType, ...] = ()
    profiles: tuple[Profile, ...] = ()

    def semantic_type(self, type_id: str) -> SemanticType | None:
        """The semantic type with this identifier, if it is defined."""
        return next((item for item in self.semantic_types if item.id == type_id), None)

    def profile(self, profile_id: str | None) -> Profile | None:
        """The profile with this identifier, if it is defined."""
        return next((item for item in self.profiles if item.id == profile_id), None)

    def localized(self, language: str | None = None) -> Configuration:
        """The configuration with every text in one language (default: the current locale's)."""
        language = language or current_language()
        return Configuration(
            semantic_types=tuple(item.localized(language) for item in self.semantic_types),
            profiles=tuple(profile.localized(language) for profile in self.profiles),
        )

    def to_dict(self) -> dict[str, Any]:
        """The configuration as JSON-compatible data, for the deposit form and the API.

        An entry leaves out the fields that have their default value, as the YAML does.
        """
        return {"semantic_types": _plain(self.semantic_types), "profiles": _plain(self.profiles)}


def _plain(value: Any) -> Any:
    if is_dataclass(value):
        return {
            field.name: _plain(getattr(value, field.name))
            for field in fields(value)
            if getattr(value, field.name) != field.default
        }
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    if isinstance(value, dict):
        # A text in several languages: a copy, so the caller cannot change the configuration.
        return dict(value)
    return value
