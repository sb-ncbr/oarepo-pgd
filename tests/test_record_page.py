"""The file meanings on the record page: the data the component prepares and the template."""

from types import SimpleNamespace

from flask import Flask

from oarepo_pgd.components import DepositionProfilesComponent, file_meanings
from oarepo_pgd.profiles import Configuration, PermittedType, Profile, SemanticType
from oarepo_pgd.registry import NAMESPACE_KEY
from oarepo_pgd.views import create_ui_blueprint

TEMPLATE = "oarepo_pgd/record_detail/file_meanings.html"

CONFIGURATION = Configuration(
    semantic_types=(
        SemanticType(
            "interview-recording",
            label={"en": "Interview recording", "cs": "Nahrávka rozhovoru"},
            definition="An audio recording of an interview.",
        ),
        SemanticType("interview-transcript", label="Interview transcript", definition="A written transcription."),
    ),
    profiles=(
        Profile(
            "recorded-interview",
            revision="1.0",
            dataset_category={"en": "Recorded interview", "cs": "Nahraný rozhovor"},
            semantic_types=(PermittedType("interview-recording"), PermittedType("interview-transcript")),
            requirements=(),
        ),
    ),
)

METADATA = {
    "pgd_deposition_profile": {"id": "recorded-interview", "revision": "1.0"},
    "pgd_file_annotations": [
        {"file_key": "interview.wav", "semantic_types": ["interview-recording"], "description": " Session 1 "},
        {"file_key": "interview.txt", "semantic_types": ["interview-transcript", "retired-type"]},
        {"file_key": "not-uploaded.wav", "semantic_types": ["interview-recording"]},
    ],
}


def test_the_meanings_cover_the_listed_files_in_annotation_order():
    meanings = file_meanings(METADATA, ["interview.txt", "interview.wav"], CONFIGURATION.localized("en"))

    assert meanings == {
        "profile": {"id": "recorded-interview", "revision": "1.0", "label": "Recorded interview"},
        "files": [
            {
                "key": "interview.wav",
                "types": [{
                    "id": "interview-recording",
                    "label": "Interview recording",
                    "definition": "An audio recording of an interview.",
                }],
                "description": "Session 1",
            },
            {
                "key": "interview.txt",
                "types": [
                    {
                        "id": "interview-transcript",
                        "label": "Interview transcript",
                        "definition": "A written transcription.",
                    },
                    # A type no longer in the configuration shows its identifier.
                    {"id": "retired-type", "label": "retired-type", "definition": None},
                ],
                "description": None,
            },
        ],
    }


def test_the_meanings_follow_the_language():
    meanings = file_meanings(METADATA, ["interview.wav"], CONFIGURATION.localized("cs"))

    assert meanings["profile"]["label"] == "Nahraný rozhovor"
    assert meanings["files"][0]["types"][0]["label"] == "Nahrávka rozhovoru"


def test_a_duplicated_annotation_shows_once_and_an_unknown_profile_by_its_identifier():
    metadata = {
        "pgd_deposition_profile": {"id": "retired-profile"},
        "pgd_file_annotations": [
            {"file_key": "a.txt", "semantic_types": ["interview-transcript"]},
            {"file_key": "a.txt", "semantic_types": ["interview-recording"]},
        ],
    }
    meanings = file_meanings(metadata, ["a.txt"], CONFIGURATION)

    assert meanings["profile"] == {"id": "retired-profile", "revision": None, "label": "retired-profile"}
    assert [file["types"][0]["id"] for file in meanings["files"]] == ["interview-transcript"]


def test_a_retired_revision_shows_its_identifier_and_revision_not_the_current_name():
    metadata = {**METADATA, "pgd_deposition_profile": {"id": "recorded-interview", "revision": "0.9"}}
    meanings = file_meanings(metadata, ["interview.wav"], CONFIGURATION.localized("en"))

    assert meanings["profile"] == {"id": "recorded-interview", "revision": "0.9", "label": "recorded-interview (0.9)"}


def test_there_are_no_meanings_without_an_annotated_listed_file():
    assert file_meanings(METADATA, ["other.pdf"], CONFIGURATION) is None
    assert file_meanings({}, ["interview.wav"], CONFIGURATION) is None


def detail_context(models, model_name, files):
    app = Flask(__name__)
    app.config["OAREPO_MODELS"] = models
    resource = SimpleNamespace(config=SimpleNamespace(model_name=model_name))
    record = SimpleNamespace(to_dict=lambda: {"metadata": METADATA})
    extra_context = {}
    with app.app_context():
        DepositionProfilesComponent(resource).before_ui_detail(
            api_record=record, record={}, identity=None, ui_links={}, extra_context=extra_context,
            render_kwargs={}, files=files,
        )
    return extra_context


PROFILE_MODEL = SimpleNamespace(namespace=SimpleNamespace(**{NAMESPACE_KEY: {"configuration": CONFIGURATION}}),
                                ui_blueprint_name="datasets_ui")
OTHER_MODEL = SimpleNamespace(namespace=None, ui_blueprint_name=None)


def completed(key):
    return {"key": key, "status": "completed"}


def test_the_record_page_gets_the_meanings_of_the_files_it_lists():
    files = {"enabled": True, "entries": [completed("interview.wav")]}
    context = detail_context({"datasets": PROFILE_MODEL}, "datasets", files)

    assert [file["key"] for file in context["pgd_file_meanings"]["files"]] == ["interview.wav"]


def test_a_draft_preview_leaves_out_uploads_the_page_does_not_list():
    # The record page lists only completed uploads.
    files = {"enabled": True, "entries": [completed("interview.wav"), {"key": "interview.txt", "status": "pending"}]}
    context = detail_context({"datasets": PROFILE_MODEL}, "datasets", files)

    assert [file["key"] for file in context["pgd_file_meanings"]["files"]] == ["interview.wav"]


def test_a_reader_who_gets_no_file_list_gets_no_meanings():
    # The record page passes files=None when the reader may not read the files.
    assert detail_context({"datasets": PROFILE_MODEL}, "datasets", None) == {}
    assert detail_context({"datasets": PROFILE_MODEL}, "datasets", {"enabled": True, "entries": []}) == {}


def test_a_record_with_files_disabled_gets_no_meanings():
    files = {"enabled": False, "entries": [completed("interview.wav")]}
    assert detail_context({"datasets": PROFILE_MODEL}, "datasets", files) == {}


def test_other_models_get_no_meanings():
    files = {"enabled": True, "entries": [completed("a")]}
    assert detail_context({"vocabularies": OTHER_MODEL}, "vocabularies", files) == {}


def render(extra_context):
    app = Flask(__name__)
    app.register_blueprint(create_ui_blueprint(app))
    app.jinja_env.globals["_"] = lambda text: text
    with app.app_context():
        return app.jinja_env.get_template(TEMPLATE).render(extra_context=extra_context)


def test_the_template_renders_a_row_per_file():
    meanings = file_meanings(METADATA, ["interview.wav", "interview.txt"], CONFIGURATION.localized("en"))
    meanings["files"][0]["description"] = "<b>Session 1</b>"
    html = render({"pgd_file_meanings": meanings})

    assert "File meanings" in html
    assert "<strong>Recorded interview</strong>" in html
    assert html.count("<tr>") == 3  # the header and two files
    assert 'title="An audio recording of an interview."' in html
    # Texts from the record are escaped.
    assert "&lt;b&gt;Session 1&lt;/b&gt;" in html


def test_the_template_renders_nothing_without_meanings():
    assert render({}).strip() == ""
    assert render(None).strip() == ""
