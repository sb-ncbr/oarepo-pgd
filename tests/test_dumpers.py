"""The file annotations reach the search index only while anyone may read the record's files."""

from types import SimpleNamespace

import pytest
from invenio_access.permissions import any_user

from oarepo_pgd import dumpers
from oarepo_pgd.dumpers import FileAnnotationsDumperExt

ANNOTATIONS = [{"file_key": "interview.wav", "semantic_types": ["interview-recording"], "description": "Session 1"}]
PROFILE = {"id": "recorded-interview", "revision": "1.0"}


class Service:
    """A service whose policy lets anonymous readers do the actions in `allowed`."""

    def __init__(self, allowed=()):
        self.allowed = set(allowed)
        self.checked = []

    def check_permission(self, identity, action, record=None):
        # The dumper asks as a reader who is not logged in.
        assert identity.id is None and any_user in identity.provides
        self.checked.append(action)
        return action in self.allowed


@pytest.fixture
def service(monkeypatch):
    def use(service):
        runtime = SimpleNamespace(get_record_service_for_record=lambda record: service)
        monkeypatch.setattr(dumpers, "current_runtime", runtime)
        return service

    return use


def indexed(record):
    data = {"metadata": {"title": "Interviews", "pgd_deposition_profile": PROFILE, "pgd_file_annotations": ANNOTATIONS}}
    FileAnnotationsDumperExt().dump(record, data)
    return data["metadata"]


# RDM's protection field says the files are public; only the policy decides.
PUBLIC_FILES = SimpleNamespace(is_draft=False, access=SimpleNamespace(protection=SimpleNamespace(files="public")))


def test_files_anyone_may_read_are_indexed_with_their_annotations(service):
    used = service(Service(allowed={"read_files"}))
    assert indexed(PUBLIC_FILES)["pgd_file_annotations"] == ANNOTATIONS
    assert used.checked == ["read_files"]


def test_files_marked_public_that_the_policy_restricts_are_indexed_without_them(service):
    service(Service(allowed={"read"}))
    metadata = indexed(PUBLIC_FILES)
    assert "pgd_file_annotations" not in metadata
    # The profile and the other metadata stay searchable.
    assert metadata["pgd_deposition_profile"] == PROFILE
    assert metadata["title"] == "Interviews"


def test_a_draft_is_checked_with_the_draft_file_permission(service):
    used = service(Service())
    assert "pgd_file_annotations" not in indexed(SimpleNamespace(is_draft=True))
    assert used.checked == ["draft_read_files"]


class Record(dict):
    """Like an OARepo record: a dict, whose repr shows the metadata, with an id."""

    id = "3f2a"
    is_draft = False


def test_without_an_answer_from_the_policy_the_annotations_are_left_out_and_not_logged(monkeypatch, caplog):
    def no_model(record):
        raise KeyError("No model found for record class 'Record'.")

    monkeypatch.setattr(dumpers, "current_runtime", SimpleNamespace(get_record_service_for_record=no_model))
    record = Record(metadata={"pgd_file_annotations": ANNOTATIONS})
    assert "pgd_file_annotations" not in indexed(record)
    assert "Record 3f2a" in caplog.text
    assert "interview.wav" not in caplog.text
    assert "Session 1" not in caplog.text


def test_a_document_without_annotations_needs_no_check(service):
    used = service(Service())
    data = {"metadata": {"title": "Interviews"}}
    FileAnnotationsDumperExt().dump(PUBLIC_FILES, data)
    assert data == {"metadata": {"title": "Interviews"}}
    assert used.checked == []
