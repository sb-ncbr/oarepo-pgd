"""Load and validate a model's deposition configuration.

Semantic types are read from every ``*.yaml`` file in ``<directory>/semantic-types/``
(each file holds a list) and deposition profiles from every ``*.yaml`` file in
``<directory>/profiles/`` (one profile per file). Files are read in name order.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

SCHEMA = json.loads(Path(__file__).with_name("configuration.schema.json").read_text(encoding="utf-8"))


class ConfigurationError(Exception):
    """The deposition configuration is invalid; the message lists every problem."""


def load_configuration(directory: str | Path) -> dict[str, list[dict[str, Any]]]:
    """Return ``{"semantic_types": [...], "profiles": [...]}`` or raise ConfigurationError."""
    directory = Path(directory)
    problems = []
    semantic_types = [
        (source, item)
        for source, items in _read_files(directory, "semantic-types", "semanticTypes", problems)
        for item in items
    ]
    profiles = _read_files(directory, "profiles", "profile", problems)
    if not problems:
        problems = _check_references(semantic_types, profiles)
    if problems:
        raise ConfigurationError("Invalid deposition configuration:\n" + "\n".join(f"  {p}" for p in problems))
    return {
        "semantic_types": [item for _, item in semantic_types],
        "profiles": [profile for _, profile in profiles],
    }


def _read_files(directory: Path, folder: str, definition: str, problems: list[str]) -> list[tuple[str, Any]]:
    validator = Draft202012Validator({**SCHEMA, "$ref": f"#/$defs/{definition}"})
    results = []
    for path in sorted((directory / folder).glob("*.yaml")):
        source = f"{folder}/{path.name}"
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as error:
            problems.append(f"{source}: {error}")
            continue
        errors = sorted(validator.iter_errors(data), key=lambda error: list(error.absolute_path))
        for error in errors:
            location = ".".join(str(part) for part in error.absolute_path) or "file"
            problems.append(f"{source}: {location}: {error.message}")
        if not errors:
            results.append((source, data))
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
            if requirement.get("max_files") is not None and requirement["max_files"] < requirement["min_files"]:
                problems.append(f"{source}: {name} has max_files below min_files")
    return problems
