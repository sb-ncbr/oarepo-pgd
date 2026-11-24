"""Enable profile-guided deposition on a model.

Add the preset to the model's ``presets`` list::

    from oarepo_pgd import pgd_preset

    presets=[rdm_complete_preset, pgd_preset(__file__)],

It reads the YAML configuration from ``config/`` next to the model module, adds
the ``deposition_profile`` and ``file_annotations`` metadata fields, makes
the record schema check every draft against its selected profile, and publishes
a record with the annotations of its own files only. An invalid
configuration, a configuration without profiles, or a model that already
defines either field differently stops the process at startup.
"""

from __future__ import annotations

from collections.abc import Iterator
from copy import deepcopy
from pathlib import Path
from typing import Any

from invenio_i18n import lazy_gettext as _
from oarepo_model.api import FunctionalPreset
from oarepo_model.customizations import AddDictionary, AddToList, Customization, PrependMixin
from oarepo_model.presets import Preset

from .config import ConfigurationError, load_configuration
from .registry import NAMESPACE_KEY
from .schema import profile_schema_mixin
from .services import PublishedFileAnnotationsComponent
from .texts import ConfigurationLabels

PROPERTIES = {
    "deposition_profile": {
        "type": "object",
        "properties": {
            "id": {"type": "keyword"},
            "revision": {"type": "keyword", "searchable": False},
        },
    },
    "file_annotations": {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "file_key": {"type": "keyword", "searchable": False},
                "semantic_types": {
                    "type": "array",
                    "items": {"type": "keyword"},
                },
                "description": {"type": "fulltext"},
            },
        },
    },
}


TERMS_FACET = "invenio_records_resources.services.records.facets.TermsFacet"


def model_properties(configuration: dict[str, Any]) -> dict[str, Any]:
    """Return the metadata fields with search filters labelled from the configuration.

    Published and draft records can be filtered by their profile ("Dataset
    category") and by the semantic types of their files ("File types"). The
    filters show the labels from the YAML configuration, in the reader's language. A semantic type with
    ``search_filter: false``, such as a catch-all ``other``, is left out of the
    "File types" filter.
    """
    properties = deepcopy(PROPERTIES)
    properties["deposition_profile"]["properties"]["id"]["facet-def"] = {
        "facet": TERMS_FACET,
        "field": "metadata.deposition_profile.id",
        "label": _("Dataset category"),
        # Show every profile; the search engine returns 10 values by default.
        "size": max(len(configuration["profiles"]), 10),
        "value_labels": ConfigurationLabels(
            {profile["id"]: profile["dataset_category"] for profile in configuration["profiles"]}
        ),
    }
    properties["file_annotations"]["items"]["properties"]["semantic_types"]["items"]["facet-def"] = {
        "facet": TERMS_FACET,
        "field": "metadata.file_annotations.semantic_types",
        "label": _("File types"),
        "size": max(len(configuration["semantic_types"]), 10),
        "value_labels": ConfigurationLabels(
            {semantic_type["id"]: semantic_type["label"] for semantic_type in configuration["semantic_types"]}
        ),
    }
    hidden = [item["id"] for item in configuration["semantic_types"] if item.get("search_filter") is False]
    if hidden:
        properties["file_annotations"]["items"]["properties"]["semantic_types"]["items"]["facet-def"]["exclude"] = hidden
    return properties


def pgd_preset(
    origin: str | Path, *, directory: str = "config", application_id: str | None = None
) -> list[type[FunctionalPreset] | type[Preset]]:
    """Return the presets enabling profile-guided deposition on one model.

    :param origin: the model module's ``__file__``; the configuration is read
        from ``directory`` next to it. A directory path is used as it is.
    :param application_id: ``application_id`` of the model's UI resource config,
        when it differs from the model name.
    """
    origin = Path(origin)
    config_directory = origin if origin.is_dir() else origin.parent / directory
    configuration = load_configuration(config_directory)
    # An enabled preset without profiles would leave deposits unchecked, so a
    # misplaced configuration must stop the repository instead.
    if not configuration["profiles"]:
        raise ConfigurationError(
            f"No deposition profiles found: expected profile files in {config_directory / 'profiles'} "
            f"and semantic types in {config_directory / 'semantic-types'}."
        )

    fields = model_properties(configuration)

    class DepositionProfileFields(FunctionalPreset):
        """Add the two metadata fields before the model's types are built."""

        def before_populate_type_registry(self, model: Any, types: list[dict[str, Any]], **kwargs: Any) -> None:
            name = model.metadata_type or "Metadata"
            for index, collection in enumerate(types):
                if name in collection:
                    metadata = deepcopy(collection[name])
                    properties = metadata.setdefault("properties", {})
                    for field, definition in PROPERTIES.items():
                        if field in properties and properties[field] not in (definition, fields[field]):
                            raise ValueError(
                                f"{model.name}: metadata field {field!r} is already defined with a "
                                "different definition. oarepo-pgd defines it; remove it from the model."
                            )
                    properties.update(deepcopy(fields))
                    types[index] = {**collection, name: metadata}
                    break
            else:
                raise ValueError(f"{model.name}: metadata type {name!r} is not among the model's types")

    class DepositionProfileCheck(Preset):
        """Check drafts against the selected profile and keep the configuration on the model."""

        provides = (NAMESPACE_KEY,)
        modifies = ("RecordSchema", "record_service_components")

        def apply(self, builder: Any, model: Any, dependencies: Any) -> Iterator[Customization]:
            yield PrependMixin("RecordSchema", profile_schema_mixin(configuration))
            yield AddToList("record_service_components", PublishedFileAnnotationsComponent)
            # Read back per app through OAREPO_MODELS; see registry.py.
            yield AddDictionary(
                NAMESPACE_KEY, {"configuration": configuration, "application_id": application_id}
            )

    return [DepositionProfileFields, DepositionProfileCheck]
