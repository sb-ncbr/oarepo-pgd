from pathlib import Path

import pytest
import yaml

from oarepo_pgd.config import ConfigurationError, load_configuration, parse_configuration
from oarepo_pgd.profiles import Configuration

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
    assert [item.id for item in configuration.semantic_types] == ["site-photo", "field-notebook", "other"]
    assert [item.id for item in configuration.profiles] == ["field-survey", "photo-only"]


def test_yml_files_are_read_with_yaml_files_in_name_order(tmp_path):
    write(tmp_path, profiles=[])
    (tmp_path / "profiles" / "b.yaml").write_text(yaml.safe_dump(profile(id="second")))
    (tmp_path / "profiles" / "a.yml").write_text(yaml.safe_dump(profile(id="first")))
    (tmp_path / "profiles" / "notes.txt").write_text("not configuration")
    (tmp_path / "profiles" / ".yaml").write_text(yaml.safe_dump(profile(id="nameless")))
    assert [item.id for item in load_configuration(tmp_path).profiles] == ["nameless", "first", "second"]


def test_a_file_that_cannot_be_read_is_reported_with_the_other_problems(tmp_path):
    write(tmp_path, profiles=[profile(min_file=1)])
    (tmp_path / "profiles" / "latin-1.yaml").write_bytes("dataset_category: Pr\xfczkum\n".encode("latin-1"))
    (tmp_path / "profiles" / "folder.yml").mkdir()
    text = problems(tmp_path)
    assert "profiles/latin-1.yaml: file: The file cannot be read:" in text
    assert "profiles/folder.yml: file: The file cannot be read:" in text
    assert "profiles/profile-0.yaml: min_file: Unknown field." in text


def test_a_folder_that_cannot_be_listed_is_reported(tmp_path, monkeypatch):
    write(tmp_path)
    listing = Path.iterdir

    def iterdir(path):
        if path.name == "profiles":
            raise PermissionError(13, "Permission denied", str(path))
        return listing(path)

    monkeypatch.setattr(Path, "iterdir", iterdir)
    assert "profiles: folder: The folder cannot be read: [Errno 13] Permission denied" in problems(tmp_path)


def test_a_file_in_place_of_a_folder_is_reported(tmp_path):
    write(tmp_path, profiles=[])
    (tmp_path / "profiles").rmdir()
    (tmp_path / "profiles").write_text("")
    assert "profiles: folder: The folder cannot be read:" in problems(tmp_path)


def test_missing_folders_give_an_empty_configuration(tmp_path):
    assert load_configuration(tmp_path) == Configuration()


def test_reports_problems_from_every_file(tmp_path):
    write(tmp_path, profiles=[profile(min_file=1)])
    (tmp_path / "profiles" / "broken.yaml").write_text("id: [unclosed\n")
    text = problems(tmp_path)
    assert "profiles/broken.yaml:" in text
    assert "profiles/profile-0.yaml: min_file: Unknown field." in text


def test_names_the_place_of_a_problem(tmp_path):
    requirement = {"id": "Photos", "label": {"en": ""}, "level": "mandatory", "min_files": "1", "semantic_types": []}
    types = [{"id": "site-photo", "label": "Site photo"}, "site-photo"]
    text = problems(write(tmp_path, types=types, profiles=[profile(requirements=[requirement], revision=1)]))
    assert "semantic-types/types.yaml: 0.definition: Missing data for required field." in text
    assert "semantic-types/types.yaml: 1: Invalid input type." in text
    assert "profiles/profile-0.yaml: revision: Not a valid string." in text
    assert "profiles/profile-0.yaml: requirements.0.id: Must start with a lowercase letter or a digit" in text
    assert "profiles/profile-0.yaml: requirements.0.label: Must be a non-empty text or a mapping" in text
    assert "profiles/profile-0.yaml: requirements.0.level: Must be one of: required, recommended, optional." in text
    assert "profiles/profile-0.yaml: requirements.0.min_files: Must be a whole number of at least 0." in text
    assert "profiles/profile-0.yaml: requirements.0.semantic_types: Shorter than minimum length 1." in text


def test_a_file_of_the_wrong_shape_is_reported(tmp_path):
    write(tmp_path)
    (tmp_path / "semantic-types" / "empty.yaml").write_text("")
    (tmp_path / "semantic-types" / "set.yaml").write_text("!!set {}\n")
    (tmp_path / "semantic-types" / "mapping.yaml").write_text("id: site-photo\n")
    (tmp_path / "profiles" / "list.yaml").write_text("- id: survey\n")
    text = problems(tmp_path)
    assert "semantic-types/empty.yaml: file: The file is empty." in text
    assert "semantic-types/set.yaml: file: Not a valid list." in text
    assert "semantic-types/mapping.yaml: file: Not a valid list." in text
    assert "profiles/list.yaml: file: Invalid input type." in text


def test_texts_in_several_languages_and_flags_are_accepted(tmp_path):
    types = [{"id": "site-photo", "label": {"en": "Site photo", "cs": "Fotografie"}, "definition": "A photo.",
              "uri": "https://example.org/photo", "requires_description": True, "search_filter": False},
             TYPES[1]]
    configuration = load_configuration(write(tmp_path, types=types))
    assert configuration.semantic_type("site-photo").requires_description is True
    assert configuration.semantic_type("site-photo").search_filter is False
    assert configuration.semantic_type("field-notebook").search_filter is True
    # As plain data, an entry keeps what the YAML set and leaves out the defaults.
    assert configuration.to_dict()["semantic_types"] == types
    assert configuration.to_dict()["profiles"] == [profile()]


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
        {"id": "notes", "label": "Notes", "level": "recommended", "min_files": 0,
         "semantic_types": ["field-notebook"]},
    ]
    text = problems(write(tmp_path, profiles=[profile(requirements=requirements)]))
    assert "requirement 'photos' is defined more than once" in text
    assert "requirement 'photos' has max_files below min_files" in text
    assert "requirement 'photos' is optional, so min_files must be 0" in text
    assert "requirement 'notes' is recommended, so min_files must be at least 1" in text
    assert "requirement 'photos' uses semantic type 'drone-video', which the profile does not permit" in text


def test_values_of_other_yaml_types_are_refused(tmp_path):
    write(tmp_path)
    (tmp_path / "semantic-types" / "binary.yaml").write_text(
        "- {id: !!binary cGhvdG9z, label: Photos, definition: Photos.}\n"
    )
    (tmp_path / "profiles" / "set.yaml").write_text(yaml.safe_dump(profile(id="sets")).replace(
        "semantic_types:\n  - site-photo", "semantic_types: !!set {site-photo: null}"
    ))
    text = problems(tmp_path)
    assert "semantic-types/binary.yaml: 0.id: Not a valid string." in text
    assert "profiles/set.yaml: requirements.0.semantic_types: Not a valid list." in text


def test_plain_data_gives_the_same_configuration_as_the_files(tmp_path):
    data = {"semantic_types": TYPES, "profiles": [profile()]}
    assert parse_configuration(data) == load_configuration(write(tmp_path))


@pytest.mark.parametrize(
    ("data", "problem"),
    [
        ({"semantic_types": [], "profiles": {}}, "profiles: Not a valid list."),
        ({"semantic_types": []}, "profiles: Missing data for required field."),
        ({"semantic_types": [], "profiles": None}, "profiles: Field may not be null."),
        ({"semantic_types": "site-photo", "profiles": []}, "semantic_types: Not a valid list."),
        ([], "file: Invalid input type."),
        ({"semantic_types": TYPES, "profiles": [profile(level="required")]}, "profiles.0.level: Unknown field."),
        ({"semantic_types": TYPES[:1], "profiles": [profile()]}, "semantic type 'field-notebook', which is not"),
    ],
)
def test_malformed_plain_data_is_refused(data, problem):
    with pytest.raises(ConfigurationError, match=problem):
        parse_configuration(data)
