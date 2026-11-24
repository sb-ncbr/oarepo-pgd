"""Marshmallow schemas of the YAML deposition configuration.

A file in ``semantic-types/`` holds a list of semantic types and a file in
``profiles/`` one deposition profile. Each schema validates an entry and builds
its object from ``profiles.py``.
"""

from __future__ import annotations

import re
from typing import Any

from marshmallow import Schema, ValidationError, fields, post_load, validate

from .profiles import PermittedType, Profile, Requirement, SemanticType

LEVELS = ("required", "recommended", "optional")
LANGUAGE = re.compile(r"^[a-z]{2,3}$")


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


class String(fields.String):
    """A YAML string. Marshmallow's own field would also decode binary values."""

    def _deserialize(self, value: Any, attr: str | None, data: Any, **kwargs: Any) -> str:
        if not isinstance(value, str):
            raise self.make_error("invalid")
        return super()._deserialize(value, attr, data, **kwargs)


class List(fields.List):
    """A YAML sequence. Marshmallow's own field would also take a set."""

    def _deserialize(self, value: Any, attr: str | None, data: Any, **kwargs: Any) -> list[Any]:
        if not isinstance(value, list):
            raise self.make_error("invalid")
        return super()._deserialize(value, attr, data, **kwargs)


class Text(fields.Field):
    """A text for every language, or a mapping of language codes to texts.

    For example ``Interview transcript`` or ``{en: Interview transcript, cs: Přepis rozhovoru}``.
    """

    default_error_messages = {
        "invalid": "Must be a non-empty text or a mapping of language codes, such as en and cs, to non-empty texts."
    }

    def _deserialize(self, value: Any, attr: str | None, data: Any, **kwargs: Any) -> str | dict[str, str]:
        if _nonempty(value):
            return value
        if isinstance(value, dict) and value:
            if all(isinstance(code, str) and LANGUAGE.match(code) and _nonempty(text) for code, text in value.items()):
                # A copy, so later changes to the input do not reach the configuration.
                return dict(value)
        raise self.make_error("invalid")


class Flag(fields.Field):
    """``true`` or ``false``; YAML has already parsed it."""

    default_error_messages = {"invalid": "Must be true or false."}

    def _deserialize(self, value: Any, attr: str | None, data: Any, **kwargs: Any) -> bool:
        if not isinstance(value, bool):
            raise self.make_error("invalid")
        return value


class Count(fields.Field):
    """A whole number of files, at least ``minimum``."""

    default_error_messages = {"invalid": "Must be a whole number of at least {minimum}."}

    def __init__(self, minimum: int, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.minimum = minimum

    def _deserialize(self, value: Any, attr: str | None, data: Any, **kwargs: Any) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < self.minimum:
            raise self.make_error("invalid", minimum=self.minimum)
        return value


def identifier(**kwargs: Any) -> String:
    """An identifier such as ``interview-transcript``."""
    pattern = validate.Regexp(
        r"^[a-z0-9][a-z0-9_-]*$",
        error="Must start with a lowercase letter or a digit and contain only lowercase letters, digits, '-' and '_'.",
    )
    return String(validate=pattern, **kwargs)


def string(**kwargs: Any) -> String:
    """A non-empty string."""
    return String(validate=validate.Length(min=1), **kwargs)


def _distinct(values: list[str]) -> None:
    if len(set(values)) != len(values):
        raise ValidationError("Must not repeat a value.")


class SemanticTypeSchema(Schema):
    """One semantic type."""

    id = identifier(required=True)
    label = Text(required=True)
    definition = Text(required=True)
    uri = String(validate=validate.Regexp(r"^https?://", error="Must be an http or https address."))
    requires_description = Flag()
    search_filter = Flag()

    @post_load
    def build(self, data: dict[str, Any], **kwargs: Any) -> SemanticType:
        """Return the semantic type."""
        return SemanticType(**data)


class PermittedTypeSchema(Schema):
    """A semantic type as one profile permits it."""

    id = identifier(required=True)
    filename_patterns = List(string())
    formats = List(
        String(
            validate=validate.Regexp(r"^[A-Za-z0-9][A-Za-z0-9.+-]*$", error="Must be a file extension such as txt.")
        ),
        validate=validate.Length(min=1),
    )

    @post_load
    def build(self, data: dict[str, Any], **kwargs: Any) -> PermittedType:
        """Return the permitted type."""
        return PermittedType(**_tuples(data))


class RequirementSchema(Schema):
    """One file requirement of a profile."""

    id = identifier(required=True)
    label = Text(required=True)
    level = String(required=True, validate=validate.OneOf(LEVELS))
    min_files = Count(0, required=True)
    max_files = Count(1)
    semantic_types = List(identifier(), required=True, validate=[validate.Length(min=1), _distinct])
    help = Text()

    @post_load
    def build(self, data: dict[str, Any], **kwargs: Any) -> Requirement:
        """Return the requirement."""
        return Requirement(**_tuples(data))


class ProfileSchema(Schema):
    """One deposition profile."""

    id = identifier(required=True)
    revision = string(required=True)
    dataset_category = Text(required=True)
    semantic_types = List(fields.Nested(PermittedTypeSchema), required=True, validate=validate.Length(min=1))
    requirements = List(fields.Nested(RequirementSchema), required=True)

    @post_load
    def build(self, data: dict[str, Any], **kwargs: Any) -> Profile:
        """Return the profile."""
        return Profile(**_tuples(data))


def _tuples(data: dict[str, Any]) -> dict[str, Any]:
    """The loaded data with its lists as tuples, as the objects keep them."""
    return {key: tuple(value) if isinstance(value, list) else value for key, value in data.items()}


class ConfigurationSchema(Schema):
    """A whole configuration given as plain data."""

    semantic_types = List(fields.Nested(SemanticTypeSchema), required=True)
    profiles = List(fields.Nested(ProfileSchema), required=True)


# What one file holds: a list of semantic types, or one profile.
SEMANTIC_TYPES = List(fields.Nested(SemanticTypeSchema))
PROFILE = fields.Nested(ProfileSchema)


def problems(error: ValidationError) -> list[str]:
    """Turn marshmallow's nested messages into lines such as ``requirements.0.level: Must be one of: ...``."""
    return list(_lines(error.messages, ()))


def _lines(messages: Any, path: tuple[Any, ...]) -> Any:
    if isinstance(messages, dict):
        for key, value in messages.items():
            # "_schema" holds messages about the whole value, not a field of it.
            yield from _lines(value, path if key == "_schema" else (*path, key))
    elif isinstance(messages, list):
        for message in messages:
            yield from _lines(message, path)
    else:
        yield f"{'.'.join(str(part) for part in path) or 'file'}: {messages}"
