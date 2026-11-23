from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from oarepo_pgd.config import ConfigurationError, load_configuration
from oarepo_pgd.presets import PROPERTIES, model_properties, pgd_preset
from oarepo_pgd.registry import NAMESPACE_KEY

TEST_CONFIG = Path(__file__).parent / "config"


def model(name="survey"):
    return SimpleNamespace(name=name, metadata_type="Metadata", configuration={})


def add_fields(types, configuration=TEST_CONFIG, name="survey"):
    fields, _ = pgd_preset(configuration)
    fields().before_populate_type_registry(model(name), types)
    return types


def test_missing_configuration_stops_startup(tmp_path):
    with pytest.raises(ConfigurationError, match="No deposition profiles found"):
        pgd_preset(tmp_path / "config")


def test_configuration_without_profiles_stops_startup(tmp_path):
    (tmp_path / "semantic-types").mkdir()
    (tmp_path / "semantic-types" / "types.yaml").write_text("- {id: photo, label: Photo, definition: A photo.}\n")
    with pytest.raises(ConfigurationError, match=str(tmp_path / "profiles")):
        pgd_preset(tmp_path)


def test_adds_the_fields():
    types = add_fields([{"Metadata": {"properties": {"title": {"type": "fulltext"}}}}])
    assert set(types[0]["Metadata"]["properties"]) == {"title", *PROPERTIES}


def test_keeps_the_configuration_on_the_model():
    _, check = pgd_preset(TEST_CONFIG, application_id="surveys")
    names = {customization.name: customization for customization in check().apply(None, model(), {})}
    assert set(names) == {"RecordSchema", NAMESPACE_KEY}
    stored = names[NAMESPACE_KEY].default
    assert stored["application_id"] == "surveys"
    assert [profile["id"] for profile in stored["configuration"]["profiles"]] == ["field-survey", "photo-only"]


def test_accepts_an_identical_existing_definition():
    existing = {"Metadata": {"properties": deepcopy(PROPERTIES)}}
    expected = model_properties(load_configuration(TEST_CONFIG))
    assert add_fields([existing])[0]["Metadata"]["properties"] == expected


def test_search_filters_use_the_configured_labels():
    configuration = load_configuration(TEST_CONFIG)
    properties = add_fields([{"Metadata": {"properties": {}}}])[0]["Metadata"]["properties"]
    profile_filter = properties["deposition_profile"]["properties"]["id"]["facet-def"]
    type_filter = properties["file_annotations"]["items"]["properties"]["semantic_types"]["items"]["facet-def"]
    assert profile_filter["field"] == "metadata.deposition_profile.id"
    assert profile_filter["value_labels"].texts == {
        profile["id"]: profile["dataset_category"] for profile in configuration["profiles"]
    }
    assert type_filter["field"] == "metadata.file_annotations.semantic_types"
    assert type_filter["size"] >= len(configuration["semantic_types"])
    assert profile_filter["size"] >= len(configuration["profiles"])
    assert type_filter["value_labels"].texts == {item["id"]: item["label"] for item in configuration["semantic_types"]}


def test_refuses_a_different_existing_definition():
    existing = {"Metadata": {"properties": {"file_annotations": {"type": "keyword"}}}}
    with pytest.raises(ValueError, match="'file_annotations' is already defined"):
        add_fields([existing], name="collision")


def test_a_type_can_stay_out_of_the_file_types_filter():
    configuration = load_configuration(TEST_CONFIG)
    configuration["semantic_types"][0] = {**configuration["semantic_types"][0], "search_filter": False}
    hidden = configuration["semantic_types"][0]["id"]
    type_filter = model_properties(configuration)["file_annotations"]["items"]["properties"]["semantic_types"]["items"]
    assert type_filter["facet-def"]["exclude"] == [hidden]
    assert "exclude" not in model_properties(load_configuration(TEST_CONFIG))["file_annotations"]["items"][
        "properties"
    ]["semantic_types"]["items"]["facet-def"]
