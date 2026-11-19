from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from oarepo_pgd.config import ConfigurationError
from oarepo_pgd.presets import PROPERTIES, pgd_preset
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
    assert add_fields([existing])[0]["Metadata"]["properties"] == PROPERTIES


def test_refuses_a_different_existing_definition():
    existing = {"Metadata": {"properties": {"file_annotations": {"type": "keyword"}}}}
    with pytest.raises(ValueError, match="'file_annotations' is already defined"):
        add_fields([existing], name="collision")
