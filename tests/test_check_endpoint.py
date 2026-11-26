"""The draft check at /deposition-profiles/check, against a fake model service.

The service is what OARepo keeps on the model in ``OAREPO_MODELS``; the check
itself is tested against the shared cases in test_rules.py.
"""

from types import SimpleNamespace

import pytest
from flask import Flask, g
from flask_babel import Babel
from invenio_pidstore.errors import PIDDeletedError, PIDDoesNotExistError, PIDMissingObjectError, PIDRedirectedError
from invenio_records_resources.services.errors import PermissionDeniedError
from sqlalchemy.orm.exc import NoResultFound

from oarepo_pgd import views
from oarepo_pgd.profiles import Configuration, PermittedType, Profile, Requirement, SemanticType
from oarepo_pgd.registry import NAMESPACE_KEY
from oarepo_pgd.views import create_api_blueprint

CONFIGURATION = Configuration(
    semantic_types=(
        SemanticType("interview-transcript", label="Interview transcript", definition="A transcription."),
        SemanticType("interview-guide", label="Interview guide", definition="The questions."),
    ),
    profiles=(
        Profile(
            "transcribed-interview",
            revision="1.0",
            dataset_category="Transcribed interview",
            semantic_types=(PermittedType("interview-transcript"), PermittedType("interview-guide")),
            requirements=(
                Requirement("transcripts", label="Transcripts", level="required", min_files=1,
                            semantic_types=("interview-transcript",)),
                Requirement("guides", label="Interview guides", level="recommended", min_files=1,
                            semantic_types=("interview-guide",)),
            ),
        ),
    ),
)

PROFILE = {"id": "transcribed-interview", "revision": "1.0"}


class FakeDraft(dict):
    def __init__(self, metadata, enabled=True):
        super().__init__({"metadata": metadata})
        self.files = SimpleNamespace(enabled=enabled)


def pid(value, pid_type="dsets"):
    return SimpleNamespace(pid_type=pid_type, pid_value=value)


class FakeDraftAnnotations(dict):
    """Draft metadata that fails the test when the check reads the annotations."""

    def get(self, key, default=None):
        assert key != "pgd_file_annotations", "annotations read without permission"
        return super().get(key, default)


class FakeService:
    """read_draft, list_files and check_permission as the record and draft file services offer them."""

    # Errors the PID resolver raises while read_draft resolves an id.
    RESOLVER = {
        "deleted": PIDDeletedError(pid("deleted"), None),
        "merged": PIDRedirectedError(pid("merged"), pid("complete")),
        "merged-elsewhere": PIDRedirectedError(pid("merged-elsewhere"), pid("complete", "recid")),
        "no-object": PIDMissingObjectError("dsets", "no-object"),
        "no-row": NoResultFound(),
    }

    def __init__(self, drafts, denied=(), files_denied=(), annotations_denied=()):
        self.drafts, self.denied = drafts, set(denied)
        self.files_denied, self.annotations_denied = set(files_denied), set(annotations_denied)
        self.listed = []

    def read_draft(self, identity, id_):
        assert identity == "depositor"
        if id_ in self.denied:
            raise PermissionDeniedError("read_draft")
        if id_ in self.RESOLVER:
            raise self.RESOLVER[id_]
        if id_ not in self.drafts:
            raise PIDDoesNotExistError("dsets", id_)
        return SimpleNamespace(_record=self.drafts[id_])

    def list_files(self, identity, id_):
        if id_ in self.files_denied:
            raise PermissionDeniedError("draft_read_files")
        self.listed.append(id_)

    def check_permission(self, identity, action_name, record=None):
        assert action_name == "read_files"
        return not any(record is self.drafts[name] for name in self.annotations_denied)


@pytest.fixture
def service():
    return FakeService({
        "incomplete": FakeDraft({"pgd_deposition_profile": PROFILE, "pgd_file_annotations": [
            {"file_key": "notes.txt", "semantic_types": []},
            {"file_key": "uploading.txt", "semantic_types": ["interview-transcript"]},
        ]}),
        "complete": FakeDraft({"pgd_deposition_profile": PROFILE, "pgd_file_annotations": [
            {"file_key": "interview.txt", "semantic_types": ["interview-transcript"]},
        ]}),
        "metadata-only": FakeDraft({}, enabled=False),
        "no-file-access": FakeDraft({"pgd_deposition_profile": PROFILE}),
        # The workflow lets the caller list the files but not read their annotations.
        "no-annotation-access": FakeDraft(FakeDraftAnnotations({
            "pgd_deposition_profile": PROFILE,
            "pgd_file_annotations": [{"file_key": "interview.txt", "semantic_types": ["interview-transcript"]}],
        })),
    }, denied={"someone-else"}, files_denied={"no-file-access"}, annotations_denied={"no-annotation-access"})


@pytest.fixture
def client(service, monkeypatch):
    # Completed uploads only: "uploading.txt" is still being uploaded.
    completed = {"incomplete": ["notes.txt"], "complete": ["interview.txt"], "no-file-access": [],
                 "no-annotation-access": ["interview.txt"]}
    monkeypatch.setattr(views, "completed_file_keys", lambda draft: next(
        keys for name, keys in completed.items() if service.drafts.get(name) is draft
    ))
    model = SimpleNamespace(
        namespace=SimpleNamespace(**{NAMESPACE_KEY: {"configuration": CONFIGURATION}}),
        ui_blueprint_name="datasets_ui",
        service=service,
        draft_file_service=service,
    )
    app = Flask(__name__)
    app.config.update(OAREPO_MODELS={"datasets": model})
    Babel(app)  # as invenio-i18n sets up the repository's apps
    app.before_request(lambda: setattr(g, "identity", "depositor"))
    app.register_blueprint(create_api_blueprint(app))
    return app.test_client()


def checked(client, query):
    response = client.get(f"/deposition-profiles/check{query}")
    return response.status_code, response.get_json()


def test_an_incomplete_draft_gets_codes_counts_and_states(client, service):
    status, body = checked(client, "?draft=incomplete")

    assert status == 200
    assert body == {
        "model": "datasets",
        "draft": "incomplete",
        "files_enabled": True,
        "file_keys": ["notes.txt"],
        "errors": [
            {"code": "meaning_missing", "file_key": "notes.txt", "requirement": None,
             "message": "select at least one file meaning."},
            {"code": "too_few_files", "file_key": None, "requirement": "transcripts",
             "message": "Transcripts: 0 of at least 1 file."},
        ],
        "counts": {"transcripts": 0, "guides": 0},
        "states": {"transcripts": "unmet", "guides": "advised"},
    }
    assert service.listed == ["incomplete"]


def test_a_complete_draft_has_no_errors_and_shows_missing_recommended_files(client):
    status, body = checked(client, "?model=datasets&draft=complete")

    assert status == 200
    assert body["errors"] == []
    assert body["states"] == {"transcripts": "met", "guides": "advised"}


def test_a_draft_without_files_is_not_checked(client, service):
    status, body = checked(client, "?draft=metadata-only")

    assert status == 200
    assert body["files_enabled"] is False
    assert (body["errors"], body["counts"], body["states"], body["file_keys"]) == ([], {}, {}, [])
    assert service.listed == []


@pytest.mark.parametrize(("query", "expected"), [
    ("?draft=someone-else", 403),
    ("?draft=no-file-access", 403),
    ("?draft=no-annotation-access", 403),
    ("?draft=missing", 404),
    ("?draft=no-object", 404),
    ("?draft=no-row", 404),
    ("?draft=merged-elsewhere", 404),
    ("?draft=deleted", 410),
    ("", 400),
    ("?model=vocabularies&draft=complete", 404),
])
def test_refusals(client, query, expected):
    status, body = checked(client, query)

    assert status == expected
    assert body["status"] == expected
    assert body["message"]


@pytest.mark.parametrize("query", ["?draft=merged", "?model=datasets&draft=merged"])
def test_a_redirected_id_redirects_to_the_check_of_its_destination(client, query):
    response = client.get(f"/deposition-profiles/check{query}")

    assert response.status_code == 301
    location = "/deposition-profiles/check?model=datasets&draft=complete"
    assert response.headers["Location"] == location
    assert response.get_json() == {"status": 301, "message": "Moved Permanently.", "location": location}
    assert checked(client, location.removeprefix("/deposition-profiles/check"))[1]["draft"] == "complete"
