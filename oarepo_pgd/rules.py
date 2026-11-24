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

from .profiles import Configuration


def check_deposit(metadata: Mapping[str, Any], file_keys: Iterable[str], configuration: Configuration) -> list[str]:
    """Return error messages; an empty list means the files meet the selected profile.

    ``file_keys`` is the repository's current file inventory. Requirement matches
    are derived from the annotated semantic types; each distinct file counts once
    per matching requirement. An annotation whose file is not in the inventory
    is ignored.
    """
    if not configuration.profiles:
        return []
    configuration = configuration.localized()

    selected = metadata.get("pgd_deposition_profile") or {}
    profile = configuration.profile(selected.get("id"))
    if profile is None:
        return [_("Select a deposition profile.")]

    errors = []
    name = profile.dataset_category
    if selected.get("revision") != profile.revision:
        errors.append(_(
            "%(profile)s: the profile has changed since it was selected. "
            "Select it again and review the file meanings.",
            profile=name,
        ))

    inventory = set(file_keys)

    annotations = {}
    for annotation in metadata.get("pgd_file_annotations") or []:
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
            semantic_type = configuration.semantic_type(type_id)
            label = semantic_type.label if semantic_type else type_id
            permitted = profile.permitted(type_id)
            if permitted is None:
                errors.append(_(
                    "%(key)s: %(label)s is not a file meaning in the %(profile)s profile.",
                    key=key, label=label, profile=name,
                ))
                continue
            formats = permitted.formats
            if formats and not any(key.lower().endswith("." + suffix.lower()) for suffix in formats):
                errors.append(_(
                    "%(key)s: %(label)s accepts %(formats)s files.", key=key, label=label, formats=", ".join(formats)
                ))
            described = (annotation.get("description") or "").strip()
            if semantic_type and semantic_type.requires_description and not described:
                errors.append(_("%(key)s: %(label)s needs a description of what the file is.", key=key, label=label))

    for requirement in profile.requirements:
        matching = set(requirement.semantic_types)
        found = sum(1 for annotation in annotations.values()
                    if matching & set(annotation.get("semantic_types") or []))
        label = requirement.label
        minimum, maximum = requirement.min_files, requirement.max_files
        if requirement.level == "required" and found < minimum:
            message = ngettext(
                "%(label)s: %(found)s of at least %(num)s file.",
                "%(label)s: %(found)s of at least %(num)s files.",
                minimum, label=label, found=found,
            )
            errors.append(" ".join(filter(None, [message, requirement.help])))
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
