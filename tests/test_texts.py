import pytest
import yaml

from oarepo_pgd.config import ConfigurationError, load_configuration
from oarepo_pgd.rules import check_deposit
from oarepo_pgd.texts import ConfigurationLabels, localized, localized_configuration

TRANSCRIPT = {"en": "Interview transcript", "cs": "Přepis rozhovoru"}


def test_a_string_is_used_for_every_language():
    assert localized("Interview transcript", "cs") == "Interview transcript"


def test_a_mapping_gives_the_requested_language():
    assert localized(TRANSCRIPT, "cs") == "Přepis rozhovoru"


def test_a_mapping_falls_back_to_english_then_to_its_first_entry():
    assert localized(TRANSCRIPT, "de") == "Interview transcript"
    assert localized({"cs": "Přepis rozhovoru"}, "de") == "Přepis rozhovoru"


def test_outside_a_request_texts_are_english():
    assert localized(TRANSCRIPT) == "Interview transcript"


def bilingual_configuration(tmp_path):
    (tmp_path / "semantic-types").mkdir()
    (tmp_path / "profiles").mkdir()
    (tmp_path / "semantic-types" / "types.yaml").write_text(yaml.safe_dump([{
        "id": "interview-transcript",
        "label": TRANSCRIPT,
        "definition": {"en": "A written transcription.", "cs": "Písemný přepis."},
    }], allow_unicode=True), encoding="utf-8")
    (tmp_path / "profiles" / "transcribed.yaml").write_text(yaml.safe_dump({
        "id": "transcribed-interview",
        "revision": "1",
        "dataset_category": {"en": "Transcribed interview", "cs": "Přepsaný rozhovor"},
        "semantic_types": [{"id": "interview-transcript"}],
        "requirements": [{
            "id": "transcripts", "label": {"en": "Transcripts", "cs": "Přepisy"}, "level": "required",
            "min_files": 1, "semantic_types": ["interview-transcript"],
            "help": {"en": "Provide a transcript.", "cs": "Přiložte přepis."},
        }],
    }, allow_unicode=True), encoding="utf-8")
    return load_configuration(tmp_path)


def test_the_configuration_accepts_texts_in_several_languages(tmp_path):
    configuration = localized_configuration(bilingual_configuration(tmp_path), "cs")
    assert configuration["semantic_types"][0]["label"] == "Přepis rozhovoru"
    assert configuration["semantic_types"][0]["definition"] == "Písemný přepis."
    profile = configuration["profiles"][0]
    assert profile["dataset_category"] == "Přepsaný rozhovor"
    assert profile["requirements"][0]["label"] == "Přepisy"
    assert profile["requirements"][0]["help"] == "Přiložte přepis."


def test_the_check_reports_configured_texts_in_one_language(tmp_path):
    configuration = bilingual_configuration(tmp_path)
    metadata = {"deposition_profile": {"id": "transcribed-interview", "revision": "1"}, "file_annotations": []}
    assert check_deposit(metadata, [], configuration) == ["Transcripts: 0 of at least 1 file. Provide a transcript."]


def test_an_empty_text_mapping_is_refused(tmp_path):
    (tmp_path / "semantic-types").mkdir()
    (tmp_path / "semantic-types" / "types.yaml").write_text("- {id: photo, label: {}, definition: A photo.}\n")
    with pytest.raises(ConfigurationError, match="semantic-types/types.yaml: 0.label"):
        load_configuration(tmp_path)


def test_filter_labels_follow_the_language():
    labels = ConfigurationLabels({"interview-transcript": TRANSCRIPT})
    assert labels(["interview-transcript", "unknown"]) == {
        "interview-transcript": "Interview transcript",
        "unknown": "unknown",
    }
