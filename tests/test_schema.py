import marshmallow
from marshmallow import fields
from marshmallow_utils.context import context_schema

from oarepo_pgd.schema import profile_schema_mixin

ANNOTATIONS = [{"file_key": "interview.wav", "semantic_types": ["interview-recording"]}]


class RecordSchema(profile_schema_mixin({"profiles": [], "semantic_types": []}), marshmallow.Schema):
    metadata = fields.Dict()


def dump(allowed_actions):
    record = {"metadata": {"title": "Interview", "file_annotations": ANNOTATIONS}}
    token = context_schema.set({"field_permission_check": lambda action: action in allowed_actions})
    try:
        return RecordSchema().dump(record)
    finally:
        context_schema.reset(token)


def test_annotations_shown_to_users_who_may_read_the_files():
    assert dump({"read_files"})["metadata"]["file_annotations"] == ANNOTATIONS


def test_annotations_hidden_from_users_who_may_not_read_the_files():
    assert dump(set())["metadata"] == {"title": "Interview"}
