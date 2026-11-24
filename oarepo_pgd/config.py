"""Load and validate a model's deposition configuration.

Semantic types are read from every ``*.yaml`` file in ``<directory>/semantic-types/``
(each file holds a list) and deposition profiles from every ``*.yaml`` file in
``<directory>/profiles/`` (one profile per file). Files are read in name order.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from marshmallow import ValidationError, fields

from .config_schema import PROFILE, SEMANTIC_TYPES, problems


class ConfigurationError(Exception):
    """The deposition configuration is invalid; the message lists every problem."""


def load_configuration(directory: str | Path) -> dict[str, list[dict[str, Any]]]:
    """Return ``{"semantic_types": [...], "profiles": [...]}`` or raise ConfigurationError."""
    directory = Path(directory)
    found: list[str] = []
    semantic_types = [
        (source, item)
        for source, items in _read_files(directory, "semantic-types", SEMANTIC_TYPES, found)
        for item in items
    ]
    profiles = _read_files(directory, "profiles", PROFILE, found)
    if not found:
        found = _check_references(semantic_types, profiles)
    if found:
        raise ConfigurationError("Invalid deposition configuration:\n" + "\n".join(f"  {p}" for p in found))
    return {
        "semantic_types": [item for _, item in semantic_types],
        "profiles": [profile for _, profile in profiles],
    }


def _read_files(directory: Path, folder: str, content: fields.Field, found: list[str]) -> list[tuple[str, Any]]:
    results = []
    for path in sorted((directory / folder).glob("*.yaml")):
        source = f"{folder}/{path.name}"
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
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


def _check_references(
    semantic_types: list[tuple[str, dict[str, Any]]], profiles: list[tuple[str, dict[str, Any]]]
) -> list[str]:
    problems = []
    defined = {}
    for source, item in semantic_types:
        if item["id"] in defined:
            problems.append(f"{source}: semantic type '{item['id']}' is already defined in {defined[item['id']]}")
        defined.setdefault(item["id"], source)

    profile_sources = {}
    for source, profile in profiles:
        if profile["id"] in profile_sources:
            first = profile_sources[profile["id"]]
            problems.append(f"{source}: profile '{profile['id']}' is already defined in {first}")
        profile_sources.setdefault(profile["id"], source)

        permitted = [entry["id"] for entry in profile["semantic_types"]]
        for type_id in sorted(set(permitted)):
            if type_id not in defined:
                problems.append(f"{source}: permits semantic type '{type_id}', which is not defined")
            if permitted.count(type_id) > 1:
                problems.append(f"{source}: permits semantic type '{type_id}' more than once")

        requirement_ids = [requirement["id"] for requirement in profile["requirements"]]
        for requirement_id in sorted(set(requirement_ids)):
            if requirement_ids.count(requirement_id) > 1:
                problems.append(f"{source}: requirement '{requirement_id}' is defined more than once")
        for requirement in profile["requirements"]:
            name = f"requirement '{requirement['id']}'"
            for type_id in requirement["semantic_types"]:
                if type_id not in permitted:
                    problems.append(
                        f"{source}: {name} uses semantic type '{type_id}', which the profile does not permit"
                    )
            if requirement["level"] == "optional" and requirement["min_files"] != 0:
                problems.append(f"{source}: {name} is optional, so min_files must be 0")
            if requirement["level"] == "recommended" and requirement["min_files"] == 0:
                problems.append(f"{source}: {name} is recommended, so min_files must be at least 1")
            if requirement.get("max_files") is not None and requirement["max_files"] < requirement["min_files"]:
                problems.append(f"{source}: {name} has max_files below min_files")
    return problems
