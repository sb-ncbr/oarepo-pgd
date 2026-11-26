"""Check a deposit's files against its deposition profile.

Messages are translated with the request's locale. Their English texts and the
codes must match the form's (``logic.mjs`` and its English catalogue); the
shared cases in ``tests/cases/rules.json`` check both implementations against
the same texts, codes, counts and requirement states. Labels, profile names and
help texts come from the repository's configuration, in the request's language
where the configuration gives several.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from flask_babel import gettext as _
from flask_babel import ngettext

from .profiles import Configuration, Requirement


@dataclass(frozen=True)
class Issue:
    """One problem that blocks publication.

    ``code`` is stable and meant for software; ``message`` is for people, in the
    request's language, without the file key. ``file_key`` names the file the
    problem is about and ``requirement`` the requirement; both are ``None`` for
    a problem with the profile itself.
    """

    code: str
    message: str
    file_key: str | None = None
    requirement: str | None = None

    @property
    def text(self) -> str:
        """The message as the record schema reports it, prefixed with the file key."""
        return self.message if self.file_key is None else f"{self.file_key}: {self.message}"

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "file_key": self.file_key, "requirement": self.requirement, "message": self.message}


@dataclass(frozen=True)
class Check:
    """The result of checking a deposit against its deposition profile.

    ``errors`` block publication. ``counts`` and ``states`` are keyed by
    requirement id and stay empty while no known profile is selected; see
    :func:`requirement_state` for the states.
    """

    errors: list[Issue] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    states: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "errors": [issue.to_dict() for issue in self.errors],
            "counts": dict(self.counts),
            "states": dict(self.states),
        }


def requirement_state(requirement: Requirement, count: int) -> str:
    """What a file count means for a requirement.

    "unmet" blocks publication (a required minimum not reached, or any maximum
    exceeded), "advised" is a recommended minimum not reached, which publication
    ignores, and "met" is everything else. The form's ``requirementState`` is
    the same rule.
    """
    if requirement.max_files is not None and count > requirement.max_files:
        return "unmet"
    if count >= requirement.min_files:
        return "met"
    if requirement.level == "required":
        return "unmet"
    return "advised" if requirement.level == "recommended" else "met"


def check(metadata: Mapping[str, Any], file_keys: Iterable[str], configuration: Configuration) -> Check:
    """Check a deposit's files against its selected profile.

    ``file_keys`` is the repository's current file inventory. Requirement matches
    are derived from the annotated semantic types; each distinct file counts once
    per matching requirement. An annotation whose file is not in the inventory
    is ignored.
    """
    if not configuration.profiles:
        return Check()
    configuration = configuration.localized()

    selected = metadata.get("pgd_deposition_profile") or {}
    profile = configuration.profile(selected.get("id"))
    if profile is None:
        return Check(errors=[Issue("profile_missing", _("Select a deposition profile."))])

    errors: list[Issue] = []
    name = profile.dataset_category
    if selected.get("revision") != profile.revision:
        errors.append(Issue("profile_changed", _(
            "%(profile)s: the profile has changed since it was selected. "
            "Select it again and review the file meanings.",
            profile=name,
        )))

    inventory = set(file_keys)

    annotations = {}
    for annotation in metadata.get("pgd_file_annotations") or []:
        key = annotation.get("file_key")
        if key not in inventory:
            # Not an error: the file may be uploaded later; see annotations_of_files.
            continue
        if key in annotations:
            errors.append(Issue(
                "annotation_repeated", _("the file is annotated more than once. Keep one annotation."), key,
            ))
        else:
            annotations[key] = annotation

    for key in sorted(inventory):
        annotation = annotations.get(key) or {}
        assigned = annotation.get("semantic_types") or []
        if not assigned:
            errors.append(Issue("meaning_missing", _("select at least one file meaning."), key))
            continue
        if len(set(assigned)) < len(assigned):
            errors.append(Issue("meaning_repeated", _("remove the repeated file meaning."), key))
        for type_id in dict.fromkeys(assigned):
            semantic_type = configuration.semantic_type(type_id)
            label = semantic_type.label if semantic_type else type_id
            permitted = profile.permitted(type_id)
            if permitted is None:
                errors.append(Issue("meaning_not_in_profile", _(
                    "%(label)s is not a file meaning in the %(profile)s profile.", label=label, profile=name,
                ), key))
                continue
            formats = permitted.formats
            if formats and not any(key.lower().endswith("." + suffix.lower()) for suffix in formats):
                errors.append(Issue("format_not_accepted", _(
                    "%(label)s accepts %(formats)s files.", label=label, formats=", ".join(formats),
                ), key))
            described = (annotation.get("description") or "").strip()
            if semantic_type and semantic_type.requires_description and not described:
                errors.append(Issue("description_missing", _(
                    "%(label)s needs a description of what the file is.", label=label,
                ), key))

    counts: dict[str, int] = {}
    states: dict[str, str] = {}
    for requirement in profile.requirements:
        matching = set(requirement.semantic_types)
        found = sum(1 for annotation in annotations.values()
                    if matching & set(annotation.get("semantic_types") or []))
        counts[requirement.id] = found
        states[requirement.id] = requirement_state(requirement, found)
        label = requirement.label
        minimum, maximum = requirement.min_files, requirement.max_files
        if requirement.level == "required" and found < minimum:
            message = ngettext(
                "%(label)s: %(found)s of at least %(num)s file.",
                "%(label)s: %(found)s of at least %(num)s files.",
                minimum, label=label, found=found,
            )
            text = " ".join(filter(None, [message, requirement.help]))
            errors.append(Issue("too_few_files", text, requirement=requirement.id))
        if maximum is not None and found > maximum:
            errors.append(Issue("too_many_files", ngettext(
                "%(label)s: %(found)s of at most %(num)s file. Remove or reassign the extra files.",
                "%(label)s: %(found)s of at most %(num)s files. Remove or reassign the extra files.",
                maximum, label=label, found=found,
            ), requirement=requirement.id))
    return Check(errors=errors, counts=counts, states=states)


def check_deposit(metadata: Mapping[str, Any], file_keys: Iterable[str], configuration: Configuration) -> list[str]:
    """Return error messages; an empty list means the files meet the selected profile.

    The messages of :func:`check`'s errors, each prefixed with its file key, as
    the record schema reports them.
    """
    return [issue.text for issue in check(metadata, file_keys, configuration).errors]


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
