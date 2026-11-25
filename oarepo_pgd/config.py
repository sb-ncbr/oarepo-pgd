"""Load and validate a model's deposition configuration.

Semantic types are read from every YAML file (``*.yaml`` or ``*.yml``) in
``<directory>/semantic-types/`` (each file holds a list) and deposition profiles
from every YAML file in ``<directory>/profiles/`` (one profile per file). Files
are read in name order. A folder or file that cannot be read, or a file that
cannot be parsed or repeats a key within a mapping, is reported with the other
problems.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from marshmallow import ValidationError, fields

from .config_schema import PROFILE, SEMANTIC_TYPES, ConfigurationSchema, problems
from .profiles import Configuration, Profile, Requirement, SemanticType

YAML_SUFFIXES = (".yaml", ".yml")


class UniqueKeyLoader(yaml.SafeLoader):
    """A safe YAML loader that refuses a key repeated within one mapping.

    YAML requires unique keys, but PyYAML keeps the last value, so a second
    ``requirements:`` would silently replace the first. Each mapping is checked
    once, as written, when PyYAML composes it; ``<<`` merges are resolved later,
    so a mapping may hold one ``<<`` and its own keys may override merged values.
    """

    def compose_mapping_node(self, anchor: str | None) -> yaml.MappingNode:
        """Compose the mapping and check its keys."""
        node = super().compose_mapping_node(anchor)
        keys = set()
        for key_node, _ in node.value:
            # Scalar keys are compared as written, with their resolved tag; "<<" is a key like any other here.
            key = (key_node.tag, key_node.value) if isinstance(key_node, yaml.ScalarNode) else key_node
            if key in keys:
                raise yaml.composer.ComposerError(
                    problem=f"line {key_node.start_mark.line + 1}: the key {key_node.value!r} appears more than once "
                    "in this mapping"
                )
            keys.add(key)
        return node


class ConfigurationError(Exception):
    """The deposition configuration is invalid; the message lists every problem."""


def load_configuration(directory: str | Path) -> Configuration:
    """Return the configuration read from ``directory`` or raise ConfigurationError."""
    directory = Path(directory)
    found: list[str] = []
    semantic_types = [
        (source, item)
        for source, items in _read_files(directory, "semantic-types", SEMANTIC_TYPES, found)
        for item in items
    ]
    profiles = _read_files(directory, "profiles", PROFILE, found)
    return _configuration(semantic_types, profiles, found)


def parse_configuration(data: dict[str, Any]) -> Configuration:
    """Return the configuration given as plain data, such as parsed JSON, or raise ConfigurationError."""
    try:
        loaded = ConfigurationSchema().load(data)
    except ValidationError as error:
        raise ConfigurationError(_report(problems(error))) from error
    semantic_types = [("semantic_types", item) for item in loaded["semantic_types"]]
    profiles = [("profiles", profile) for profile in loaded["profiles"]]
    return _configuration(semantic_types, profiles, [])


def _configuration(
    semantic_types: list[tuple[str, SemanticType]], profiles: list[tuple[str, Profile]], found: list[str],
) -> Configuration:
    """Build the configuration from entries that loaded without problems, after checking their references."""
    found = found or _check_references(semantic_types, profiles)
    if found:
        raise ConfigurationError(_report(found))
    return Configuration(
        semantic_types=tuple(item for _, item in semantic_types),
        profiles=tuple(profile for _, profile in profiles),
    )


def _report(found: list[str]) -> str:
    return "Invalid deposition configuration:\n" + "\n".join(f"  {problem}" for problem in found)


def _read_files(directory: Path, folder: str, content: fields.Field, found: list[str]) -> list[tuple[str, Any]]:
    results = []
    try:
        paths = sorted(path for path in (directory / folder).iterdir() if path.name.lower().endswith(YAML_SUFFIXES))
    except FileNotFoundError:
        # A missing folder is an empty one; the preset refuses a configuration without profiles.
        return results
    except OSError as error:
        found.append(f"{folder}: folder: The folder cannot be read: {error}")
        return results
    for path in paths:
        source = f"{folder}/{path.name}"
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            found.append(f"{source}: file: The file cannot be read: {error}")
            continue
        try:
            # UniqueKeyLoader is a SafeLoader.
            data = yaml.load(text, Loader=UniqueKeyLoader)
        except yaml.YAMLError as error:
            found.append(f"{source}: {error}")
            continue
        if data is None:
            found.append(f"{source}: file: The file is empty.")
            continue
        try:
            results.append((source, content.deserialize(data)))
        except ValidationError as error:
            found.extend(f"{source}: {problem}" for problem in problems(error))
    return results


def _check_references(semantic_types: list[tuple[str, SemanticType]], profiles: list[tuple[str, Profile]]) -> list[str]:
    problems = []
    defined: dict[str, str] = {}
    for source, item in semantic_types:
        if item.id in defined:
            problems.append(f"{source}: semantic type '{item.id}' is already defined in {defined[item.id]}")
        defined.setdefault(item.id, source)

    profile_sources: dict[str, str] = {}
    for source, profile in profiles:
        if profile.id in profile_sources:
            problems.append(f"{source}: profile '{profile.id}' is already defined in {profile_sources[profile.id]}")
        profile_sources.setdefault(profile.id, source)

        permitted = [entry.id for entry in profile.semantic_types]
        for type_id in sorted(set(permitted)):
            if type_id not in defined:
                problems.append(f"{source}: permits semantic type '{type_id}', which is not defined")
            if permitted.count(type_id) > 1:
                problems.append(f"{source}: permits semantic type '{type_id}' more than once")

        requirement_ids = [requirement.id for requirement in profile.requirements]
        for requirement_id in sorted(set(requirement_ids)):
            if requirement_ids.count(requirement_id) > 1:
                problems.append(f"{source}: requirement '{requirement_id}' is defined more than once")
        for requirement in profile.requirements:
            name = f"requirement '{requirement.id}'"
            for type_id in requirement.semantic_types:
                if type_id not in permitted:
                    problems.append(
                        f"{source}: {name} uses semantic type '{type_id}', which the profile does not permit"
                    )
            if requirement.level == "optional" and requirement.min_files != 0:
                problems.append(f"{source}: {name} is optional, so min_files must be 0")
            if requirement.level == "recommended" and requirement.min_files == 0:
                problems.append(f"{source}: {name} is recommended, so min_files must be at least 1")
            if requirement.max_files is not None and requirement.max_files < requirement.min_files:
                problems.append(f"{source}: {name} has max_files below min_files")
        problems.extend(f"{source}: {problem}" for problem in _contradictory_counts(profile.requirements))
    return problems


def _contradictory_counts(requirements: tuple[Requirement, ...]) -> list[str]:
    """Requirements over the same meanings whose counts no deposit can meet together.

    Such requirements count the same files. A count above ``max_files`` is an
    error at every level and a count below ``min_files`` one for a required
    requirement, so a required minimum above another requirement's maximum
    blocks every deposit.
    """
    groups: dict[frozenset[str], list[Requirement]] = {}
    for requirement in requirements:
        groups.setdefault(frozenset(requirement.semantic_types), []).append(requirement)
    problems = []
    for group in groups.values():
        capped = [item for item in group if item.max_files is not None]
        required = [item for item in group if item.level == "required"]
        if not capped or not required:
            continue
        lowest = min(capped, key=lambda item: item.max_files)
        highest = max(required, key=lambda item: item.min_files)
        # A single requirement with max_files below min_files is reported on its own.
        if highest is not lowest and highest.min_files > lowest.max_files:
            problems.append(
                f"requirement '{highest.id}' needs at least {highest.min_files} files, but requirement "
                f"'{lowest.id}' allows at most {lowest.max_files} of the same file meanings"
            )
    return problems
