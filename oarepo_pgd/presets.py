"""Enable profile-guided deposition on a model.

Add the preset to the model's ``presets`` list::

    from oarepo_pgd import pgd_preset

    presets=[rdm_complete_preset, pgd_preset(__file__)],

It reads the YAML configuration from ``config/`` next to the model module, adds
the ``pgd_deposition_profile`` and ``pgd_file_annotations`` metadata fields, makes
the record schema check every draft against its selected profile, publishes
a record with the annotations of its own files only, and indexes the
annotations only while anyone may read the record's files. An invalid
configuration, a configuration without profiles, or a model that already
defines either field differently from the preset stops the process at startup.
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
from .dumpers import FileAnnotationsDumperExt
from .profiles import Configuration
from .registry import NAMESPACE_KEY
from .schema import profile_schema_mixin
from .services import PublishedFileAnnotationsComponent
from .texts import ConfigurationLabels

PROPERTIES = {
    "pgd_deposition_profile": {
        "type": "object",
        "label": {"en": "Deposition profile", "cs": "Depoziční profil"},
        "properties": {
            "id": {"type": "keyword"},
            "revision": {"type": "keyword", "searchable": False},
        },
    },
    "pgd_file_annotations": {
        "type": "array",
        # Shown with the server's messages in the form's error summary.
        "label": {"en": "File meanings", "cs": "Významy souborů"},
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


def model_properties(configuration: Configuration) -> dict[str, Any]:
    """Return the metadata fields with search filters labelled from the configuration.

    Published and draft records can be filtered by their profile ("Dataset
    category") and by the semantic types of their files ("File types"). The
    filters show the labels from the YAML configuration, in the reader's language. A semantic type with
    ``search_filter: false``, such as a catch-all ``other``, is left out of the
    "File types" filter.
    """
    properties = deepcopy(PROPERTIES)
    properties["pgd_deposition_profile"]["properties"]["id"]["facet-def"] = {
        "facet": TERMS_FACET,
        "field": "metadata.pgd_deposition_profile.id",
        "label": _("Dataset category"),
        # Show every profile; the search engine returns 10 values by default.
        "size": max(len(configuration.profiles), 10),
        "value_labels": ConfigurationLabels({item.id: item.dataset_category for item in configuration.profiles}),
    }
    properties["pgd_file_annotations"]["items"]["properties"]["semantic_types"]["items"]["facet-def"] = {
        "facet": TERMS_FACET,
        "field": "metadata.pgd_file_annotations.semantic_types",
        "label": _("File types"),
        "size": max(len(configuration.semantic_types), 10),
        "value_labels": ConfigurationLabels({item.id: item.label for item in configuration.semantic_types}),
    }
    hidden = [item.id for item in configuration.semantic_types if not item.search_filter]
    if hidden:
        type_filter = properties["pgd_file_annotations"]["items"]["properties"]["semantic_types"]["items"]["facet-def"]
        type_filter["exclude"] = hidden
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
    # A mistyped directory must not fall back to the configuration next to it.
    if not origin.exists():
        raise ConfigurationError(f"No deposition configuration found: {origin} does not exist.")
    config_directory = origin if origin.is_dir() else origin.parent / directory
    if not config_directory.is_dir():
        raise ConfigurationError(
            f"No deposition configuration found: {config_directory} is not a directory. "
            "Put the semantic types and profiles there, or name another directory with directory=."
        )
    configuration = load_configuration(config_directory)
    # An enabled preset without profiles would leave deposits unchecked, so a
    # misplaced configuration must stop the repository instead.
    if not configuration.profiles:
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
                    for field in PROPERTIES:
                        # A definition identical to the preset's own is accepted, so applying it again changes nothing.
                        if field in properties and properties[field] != fields[field]:
                            raise ValueError(
                                f"{model.name}: metadata field {field!r} is already defined, by the model or by "
                                "another package. oarepo-pgd defines this field itself; remove or rename the other "
                                "definition."
                            )
                    properties.update(deepcopy(fields))
                    types[index] = {**collection, name: metadata}
                    break
            else:
                raise ValueError(f"{model.name}: metadata type {name!r} is not among the model's types")

    class DepositionProfileCheck(Preset):
        """Check drafts against the selected profile and keep the configuration on the model."""

        provides = (NAMESPACE_KEY,)
        modifies = ("RecordSchema", "record_service_components", "record_dumper_extensions")

        def apply(self, builder: Any, model: Any, dependencies: Any) -> Iterator[Customization]:
            yield PrependMixin("RecordSchema", profile_schema_mixin(configuration))
            yield AddToList("record_service_components", PublishedFileAnnotationsComponent)
            yield AddToList("record_dumper_extensions", FileAnnotationsDumperExt())
            # Read back per app through OAREPO_MODELS; see registry.py.
            yield AddDictionary(
                NAMESPACE_KEY, {"configuration": configuration, "application_id": application_id}
            )

    return [DepositionProfileFields, DepositionProfileCheck]
