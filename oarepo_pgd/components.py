"""Give the deposit form its model's deposition configuration.

Add the component to the ``components`` list of the model's UI resource config
class, in ``ui/<model>/__init__.py``, after the entries already there::

    from oarepo_pgd.components import DepositionProfilesComponent


    class DatasetsUIResourceConfig(RDMRecordsUIResourceConfig):
        components = [*RDMRecordsUIResourceConfig.components, DepositionProfilesComponent]

The form then finds the configuration in its form config, as ``deposition_profiles``,
with its texts in the page's language. The record page finds the meanings of the
files it lists in its ``extra_context``, as ``pgd_file_meanings``, for the
template ``oarepo_pgd/record_detail/file_meanings.html``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Any

from flask import current_app
from invenio_app_rdm.records_ui.views.filters import order_entries
from oarepo_ui.resources.components import UIResourceComponent

from .config import ConfigurationError
from .registry import profile_models

if TYPE_CHECKING:
    from .profiles import Configuration

FORM_CONFIG_KEY = "deposition_profiles"
FILE_MEANINGS_KEY = "pgd_file_meanings"


def file_meanings(
    metadata: Mapping[str, Any], file_keys: Iterable[str], configuration: Configuration,
) -> dict[str, Any] | None:
    """The profile and the meanings of the listed files, as the record page shows them.

    Only files in ``file_keys`` appear, each once, in that order, with their first
    annotation. A type missing from the configuration shows its identifier.
    The profile shows its configured name only when the stored revision is the
    configured one; otherwise it shows the stored identifier and revision.
    Returns None when no listed file has an annotation.
    """
    annotations: dict[str, Mapping[str, Any]] = {}
    for annotation in metadata.get("pgd_file_annotations") or []:
        annotations.setdefault(annotation.get("file_key"), annotation)
    files = []
    for key in dict.fromkeys(file_keys):
        if key not in annotations:
            continue
        annotation = annotations[key]
        assigned = dict.fromkeys(annotation.get("semantic_types") or [])
        files.append({
            "key": key,
            "types": [_meaning(type_id, configuration) for type_id in assigned],
            "description": (annotation.get("description") or "").strip() or None,
        })
    if not files:
        return None
    profile = _profile(metadata.get("pgd_deposition_profile") or {}, configuration)
    return {"profile": profile, "files": files}


def _profile(selected: Mapping[str, Any], configuration: Configuration) -> dict[str, Any] | None:
    profile_id, revision = selected.get("id"), selected.get("revision")
    if not profile_id:
        return None
    profile = configuration.profile(profile_id)
    if profile and profile.revision == revision:
        label = profile.dataset_category
    else:
        # The configured name may belong to another revision.
        label = f"{profile_id} ({revision})" if revision else profile_id
    return {"id": profile_id, "revision": revision, "label": label}


def _meaning(type_id: str, configuration: Configuration) -> dict[str, Any]:
    semantic_type = configuration.semantic_type(type_id)
    if semantic_type is None:
        return {"id": type_id, "label": type_id, "definition": None}
    return {"id": type_id, "label": semantic_type.label, "definition": semantic_type.definition}


def _prefix_fix(prefix: Any) -> str:
    """How to make the plugin's override ids match the form's ``prefix``."""
    application_id = prefix.removesuffix(".Form") if isinstance(prefix, str) else ""
    # The preset builds the prefix as oarepo-ui does by default: the capitalized application_id and ".Form".
    if application_id and f"{application_id.capitalize()}.Form" == prefix:
        return f"Pass application_id={application_id!r} to pgd_preset in the model, then run ./run.sh install."
    return "Set OAREPO_PGD_UI_OVERRIDES = False and add the profile controls to the form yourself (see the README)."


class DepositionProfilesComponent(UIResourceComponent):
    """Put the model's configuration into the form config and the file meanings on the record page."""

    def form_config(self, *, form_config: dict[str, Any], **kwargs: Any) -> None:
        """Add the configuration when the resource's model uses profile-guided deposition."""
        entry = profile_models(current_app).get(self.config.model_name)
        if not entry:
            return
        # The plugin's form override is registered under a prefix derived from the
        # preset's application_id. A different prefix on this page would leave the
        # form without profile controls while the server still checks every draft.
        prefix = form_config.get("overridableIdPrefix")
        if current_app.config.get("OAREPO_PGD_UI_OVERRIDES", True) and prefix != entry.form_prefix:
            raise ConfigurationError(
                f"{self.config.model_name}: the deposit form uses the ids {prefix}.*, but oarepo-pgd added its "
                f"profile controls under {entry.form_prefix}.*. {_prefix_fix(prefix)}"
            )
        form_config[FORM_CONFIG_KEY] = entry.configuration.localized().to_dict()

    def before_ui_detail(self, *, api_record: Any, extra_context: dict[str, Any], **kwargs: Any) -> None:
        """Add the meanings of the files the record page lists.

        The page lists files only to a reader who may read them, and of those
        only completed uploads, in the record's file order, while files are
        enabled. The meanings cover the same files in the same order, so a
        reader without file access gets none.
        """
        entry = profile_models(current_app).get(self.config.model_name)
        files = kwargs.get("files")
        # Checked before ordering, as the page's template does: a record with files
        # disabled may keep a files.order naming files it no longer has.
        if not entry or not files or not files.get("enabled", True):
            return
        # As the page's Files list: RDM's order (only the files in files.order, if set), completed uploads only.
        listed = [
            item["key"] for item in order_entries(files) if item.get("key") and item.get("status") == "completed"
        ]
        if not listed:
            return
        meanings = file_meanings(api_record.to_dict().get("metadata") or {}, listed, entry.configuration.localized())
        if meanings:
            extra_context[FILE_MEANINGS_KEY] = meanings
