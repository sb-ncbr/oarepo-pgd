from types import SimpleNamespace

import marshmallow
from marshmallow import fields
from marshmallow_utils.context import context_schema

from oarepo_pgd import schema
from oarepo_pgd.profiles import Configuration
from oarepo_pgd.schema import completed_file_keys, profile_schema_mixin

ANNOTATIONS = [{"file_key": "interview.wav", "semantic_types": ["interview-recording"]}]


class RecordSchema(profile_schema_mixin(Configuration()), marshmallow.Schema):
    metadata = fields.Dict()


def dump(allowed_actions):
    record = {"metadata": {"title": "Interview", "pgd_file_annotations": ANNOTATIONS}}
    token = context_schema.set({"field_permission_check": lambda action: action in allowed_actions})
    try:
        return RecordSchema().dump(record)
    finally:
        context_schema.reset(token)


def test_annotations_shown_to_users_who_may_read_the_files():
    assert dump({"read_files"})["metadata"]["pgd_file_annotations"] == ANNOTATIONS


def test_annotations_hidden_from_users_who_may_not_read_the_files():
    assert dump(set())["metadata"] == {"title": "Interview"}


def draft_with_uploads(monkeypatch, statuses):
    """A draft whose files have the given transfer statuses, as RDM's transfer registry reports them."""
    draft = SimpleNamespace(files=SimpleNamespace(enabled=True, entries={key: key for key in statuses}))
    service = object()
    monkeypatch.setattr(schema, "current_runtime", SimpleNamespace(get_file_service_for_record=lambda record: service))

    def get_transfer(record, file_record, file_service):
        assert record is draft and file_service is service
        return SimpleNamespace(status=statuses[file_record])

    monkeypatch.setattr(schema, "current_transfer_registry", SimpleNamespace(get_transfer=get_transfer))
    return draft


def test_only_completed_uploads_count(monkeypatch):
    statuses = {"done.wav": "completed", "uploading.wav": "pending", "broken.wav": "failed"}
    draft = draft_with_uploads(monkeypatch, statuses)
    assert completed_file_keys(draft) == ["done.wav"]


def test_the_check_sees_the_completed_uploads_only(monkeypatch):
    draft = draft_with_uploads(monkeypatch, {"done.wav": "completed", "uploading.wav": "pending"})
    seen = []
    monkeypatch.setattr(schema, "check_deposit", lambda metadata, keys, configuration: seen.extend(keys) or [])
    token = context_schema.set({"record": draft})
    try:
        RecordSchema().load({"metadata": {}})
    finally:
        context_schema.reset(token)
    assert seen == ["done.wav"]
