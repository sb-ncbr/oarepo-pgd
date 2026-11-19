from pathlib import Path

import pytest
import yaml

from oarepo_pgd.config import ConfigurationError, load_configuration

TEST_CONFIG = Path(__file__).parent / "config"

TYPES = [
    {"id": "site-photo", "label": "Site photo", "definition": "A photograph taken at the study site."},
    {"id": "field-notebook", "label": "Field notebook", "definition": "Notes written during fieldwork."},
]


def profile(**changes):
    data = {
        "id": "survey",
        "revision": "1",
        "dataset_category": "Survey",
        "semantic_types": [{"id": "site-photo"}, {"id": "field-notebook"}],
        "requirements": [
            {"id": "photos", "label": "Photos", "level": "required", "min_files": 1, "semantic_types": ["site-photo"]},
        ],
    }
    return {**data, **changes}


def write(directory, types=TYPES, profiles=None):
    profiles = (profile(),) if profiles is None else profiles
    (directory / "semantic-types").mkdir()
    (directory / "profiles").mkdir()
    (directory / "semantic-types" / "types.yaml").write_text(yaml.safe_dump(types))
    for index, item in enumerate(profiles):
        (directory / "profiles" / f"profile-{index}.yaml").write_text(yaml.safe_dump(item))
    return directory


def problems(directory):
    with pytest.raises(ConfigurationError) as error:
        load_configuration(directory)
    return str(error.value)


def test_loads_all_files_in_name_order():
    configuration = load_configuration(TEST_CONFIG)
    assert [item["id"] for item in configuration["semantic_types"]] == ["site-photo", "field-notebook", "other"]
    assert [item["id"] for item in configuration["profiles"]] == ["field-survey", "photo-only"]


def test_missing_folders_give_an_empty_configuration(tmp_path):
    assert load_configuration(tmp_path) == {"semantic_types": [], "profiles": []}


def test_reports_problems_from_every_file(tmp_path):
    write(tmp_path, profiles=[profile(min_file=1)])
    (tmp_path / "profiles" / "broken.yaml").write_text("id: [unclosed\n")
    text = problems(tmp_path)
    assert "profiles/broken.yaml:" in text
    assert "profiles/profile-0.yaml: file: Additional properties are not allowed ('min_file' was unexpected)" in text


def test_reports_duplicate_and_undefined_types(tmp_path):
    second = profile(semantic_types=[{"id": "site-photo"}, {"id": "site-photo"}, {"id": "drone-video"}])
    text = problems(write(tmp_path, types=TYPES + TYPES[:1], profiles=[profile(), second]))
    assert "semantic type 'site-photo' is already defined in semantic-types/types.yaml" in text
    assert "profile 'survey' is already defined in profiles/profile-0.yaml" in text
    assert "permits semantic type 'drone-video', which is not defined" in text
    assert "permits semantic type 'site-photo' more than once" in text


def test_reports_requirement_problems(tmp_path):
    requirements = [
        {"id": "photos", "label": "Photos", "level": "required", "min_files": 3, "max_files": 2,
         "semantic_types": ["site-photo"]},
        {"id": "photos", "label": "Photos again", "level": "optional", "min_files": 1,
         "semantic_types": ["drone-video"]},
    ]
    text = problems(write(tmp_path, profiles=[profile(requirements=requirements)]))
    assert "requirement 'photos' is defined more than once" in text
    assert "requirement 'photos' has max_files below min_files" in text
    assert "requirement 'photos' is optional, so min_files must be 0" in text
    assert "requirement 'photos' uses semantic type 'drone-video', which the profile does not permit" in text
