"""Run the profile check whenever the record schema validates a draft.

The record schema runs on draft saves (errors are reported and the draft is
kept), in ``validate_draft()`` (used by community submission and publish
requests) and on publication, where any error blocks it.
"""

from __future__ import annotations

from typing import Any

from marshmallow import ValidationError, validates_schema
from marshmallow_utils.context import context_schema

from .rules import check_deposit


def profile_schema_mixin(configuration: dict[str, Any]) -> type:
    """Return a record-schema mixin bound to one model's configuration."""

    class ProfileSchemaMixin:
        @validates_schema(skip_on_field_errors=False)
        def validate_deposition_profile(self, data: dict[str, Any], **kwargs: Any) -> None:
            draft = context_schema.get().get("record")
            if draft is None:
                return
            if not (data.get("files") or {}).get("enabled", draft.files.enabled):
                return
            errors = check_deposit(data.get("metadata") or {}, draft.files.entries.keys(), configuration)
            if errors:
                raise ValidationError({"metadata": {"file_annotations": errors}})

    return ProfileSchemaMixin
