import shutil
from copy import deepcopy
from dataclasses import replace
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
    with pytest.raises(ConfigurationError, match=f"No deposition configuration found: {tmp_path / 'config'} does not"):
        pgd_preset(tmp_path / "config")


def test_a_mistyped_directory_does_not_fall_back_to_the_configuration_next_to_it(tmp_path):
    shutil.copytree(TEST_CONFIG, tmp_path / "config")
    with pytest.raises(ConfigurationError, match="does not exist"):
        pgd_preset(tmp_path / "confg")


def test_a_model_file_without_a_configuration_directory_stops_startup(tmp_path):
    (tmp_path / "model.py").write_text("")
    with pytest.raises(ConfigurationError, match=f"{tmp_path / 'config'} is not a directory"):
        pgd_preset(tmp_path / "model.py")


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
    assert set(names) == {"RecordSchema", "record_service_components", "record_dumper_extensions", NAMESPACE_KEY}
    stored = names[NAMESPACE_KEY].default
    assert stored["application_id"] == "surveys"
    assert [profile.id for profile in stored["configuration"].profiles] == ["field-survey", "photo-only"]


def test_adding_the_fields_again_changes_nothing():
    types = add_fields([{"Metadata": {"properties": {}}}])
    expected = model_properties(load_configuration(TEST_CONFIG))
    assert add_fields(types)[0]["Metadata"]["properties"] == expected


def test_refuses_an_existing_definition_without_the_search_filters():
    existing = {"Metadata": {"properties": deepcopy(PROPERTIES)}}
    with pytest.raises(ValueError, match="'pgd_deposition_profile' is already defined"):
        add_fields([existing])


def test_search_filters_use_the_configured_labels():
    configuration = load_configuration(TEST_CONFIG)
    properties = add_fields([{"Metadata": {"properties": {}}}])[0]["Metadata"]["properties"]
    profile_filter = properties["pgd_deposition_profile"]["properties"]["id"]["facet-def"]
    type_filter = properties["pgd_file_annotations"]["items"]["properties"]["semantic_types"]["items"]["facet-def"]
    assert profile_filter["field"] == "metadata.pgd_deposition_profile.id"
    assert profile_filter["value_labels"].texts == {item.id: item.dataset_category for item in configuration.profiles}
    assert type_filter["field"] == "metadata.pgd_file_annotations.semantic_types"
    assert type_filter["size"] >= len(configuration.semantic_types)
    assert profile_filter["size"] >= len(configuration.profiles)
    assert type_filter["value_labels"].texts == {item.id: item.label for item in configuration.semantic_types}


def test_refuses_a_different_existing_definition():
    existing = {"Metadata": {"properties": {"pgd_file_annotations": {"type": "keyword"}}}}
    with pytest.raises(ValueError, match="'pgd_file_annotations' is already defined"):
        add_fields([existing], name="collision")


def test_a_type_can_stay_out_of_the_file_types_filter():
    configuration = load_configuration(TEST_CONFIG)
    first, *others = configuration.semantic_types
    configuration = replace(configuration, semantic_types=(replace(first, search_filter=False), *others))
    hidden = first.id

    def type_filter(properties):
        return properties["pgd_file_annotations"]["items"]["properties"]["semantic_types"]["items"]["facet-def"]

    assert type_filter(model_properties(configuration))["exclude"] == [hidden]
    assert "exclude" not in type_filter(model_properties(load_configuration(TEST_CONFIG)))
