"""Check a deposit's files against its deposition profile.

Messages are translated with the request's locale. Their English texts must
match the form's (``logic.mjs`` and its English catalogue); the shared cases in
``tests/cases/rules.json`` check both implementations against the same texts.
Labels, profile names and help texts come from the repository's configuration,
in the request's language where the configuration gives several.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from flask_babel import gettext as _
from flask_babel import ngettext

from .texts import localized_configuration


def check_deposit(metadata: Mapping[str, Any], file_keys: Iterable[str], configuration: Mapping[str, Any]) -> list[str]:
    """Return error messages; an empty list means the files meet the selected profile.

    ``file_keys`` is the repository's current file inventory. Requirement matches
    are derived from the annotated semantic types; each distinct file counts once
    per matching requirement. An annotation whose file is not in the inventory
    is ignored.
    """
    if not configuration["profiles"]:
        return []
    configuration = localized_configuration(configuration)

    selected = metadata.get("deposition_profile") or {}
    profile = next((item for item in configuration["profiles"] if item["id"] == selected.get("id")), None)
    if profile is None:
        return [_("Select a deposition profile.")]

    errors = []
    name = profile["dataset_category"]
    if selected.get("revision") != profile["revision"]:
        errors.append(_(
            "%(profile)s: the profile has changed since it was selected. "
            "Select it again and review the file meanings.",
            profile=name,
        ))

    types = {item["id"]: item for item in configuration["semantic_types"]}
    permitted = {item["id"]: item for item in profile["semantic_types"]}
    inventory = set(file_keys)

    annotations = {}
    for annotation in metadata.get("file_annotations") or []:
        key = annotation.get("file_key")
        if key not in inventory:
            # Not an error: the file may be uploaded later; see annotations_of_files.
            continue
        if key in annotations:
            errors.append(_("%(key)s: the file is annotated more than once. Keep one annotation.", key=key))
        else:
            annotations[key] = annotation

    for key in sorted(inventory):
        annotation = annotations.get(key) or {}
        assigned = annotation.get("semantic_types") or []
        if not assigned:
            errors.append(_("%(key)s: select at least one file meaning.", key=key))
            continue
        if len(set(assigned)) < len(assigned):
            errors.append(_("%(key)s: remove the repeated file meaning.", key=key))
        for type_id in dict.fromkeys(assigned):
            label = types.get(type_id, {}).get("label", type_id)
            if type_id not in permitted:
                errors.append(_(
                    "%(key)s: %(label)s is not a file meaning in the %(profile)s profile.",
                    key=key, label=label, profile=name,
                ))
                continue
            formats = permitted[type_id].get("formats")
            if formats and not any(key.lower().endswith("." + suffix.lower()) for suffix in formats):
                errors.append(_(
                    "%(key)s: %(label)s accepts %(formats)s files.", key=key, label=label, formats=", ".join(formats)
                ))
            if types[type_id].get("requires_description") and not (annotation.get("description") or "").strip():
                errors.append(_("%(key)s: %(label)s needs a description of what the file is.", key=key, label=label))

    for requirement in profile["requirements"]:
        matching = set(requirement["semantic_types"])
        found = sum(1 for annotation in annotations.values()
                    if matching & set(annotation.get("semantic_types") or []))
        label = requirement["label"]
        minimum, maximum = requirement["min_files"], requirement.get("max_files")
        if requirement["level"] == "required" and found < minimum:
            message = ngettext(
                "%(label)s: %(found)s of at least %(num)s file.",
                "%(label)s: %(found)s of at least %(num)s files.",
                minimum, label=label, found=found,
            )
            errors.append(" ".join(filter(None, [message, requirement.get("help")])))
        if maximum is not None and found > maximum:
            errors.append(ngettext(
                "%(label)s: %(found)s of at most %(num)s file. Remove or reassign the extra files.",
                "%(label)s: %(found)s of at most %(num)s files. Remove or reassign the extra files.",
                maximum, label=label, found=found,
            ))
    return errors


def annotations_of_files(annotations: Iterable[Mapping[str, Any]], file_keys: Iterable[str]) -> list[Mapping[str, Any]]:
    """Return the annotations whose file is in the inventory, in their order.

    A draft may hold annotations of files it does not have: a client can save
    the annotations before uploading the files, and a draft of a new version
    starts with the previous version's annotations and no files. They take
    effect once a file of that name is there. A published record keeps only
    the annotations of its own files.
    """
    inventory = set(file_keys)
    return [annotation for annotation in annotations if annotation.get("file_key") in inventory]
