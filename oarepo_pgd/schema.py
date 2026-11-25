"""Run the profile check whenever the record schema validates a draft.

The record schema runs on draft saves (errors are reported and the draft is
kept), in ``validate_draft()`` (used by community submission and publish
requests) and on publication, where any error blocks it. The check counts the
draft's completed uploads only, as the deposit form does, so a publish request
cannot count a file that is still uploading.

When the schema dumps a record for a user who may not read its files, it leaves
out the file annotations: they name and describe the files, which the
repository hides from that user.
"""

from __future__ import annotations

from typing import Any

from invenio_records_resources.proxies import current_transfer_registry
from invenio_records_resources.services.files.transfer.base import TransferStatus
from marshmallow import ValidationError, post_dump, validates_schema
from marshmallow_utils.context import context_schema
from oarepo_runtime import current_runtime

from .profiles import Configuration
from .rules import check_deposit


def completed_file_keys(draft: Any) -> list[str]:
    """The keys of the draft's files whose upload has completed, checked as RDM does before publishing."""
    service = current_runtime.get_file_service_for_record(draft)
    return [
        key
        for key, file_record in draft.files.entries.items()
        if current_transfer_registry.get_transfer(record=draft, file_record=file_record, file_service=service).status
        == TransferStatus.COMPLETED
    ]


def profile_schema_mixin(configuration: Configuration) -> type:
    """Return a record-schema mixin bound to one model's configuration."""

    class ProfileSchemaMixin:
        @validates_schema(skip_on_field_errors=False)
        def validate_deposition_profile(self, data: dict[str, Any], **kwargs: Any) -> None:
            draft = context_schema.get().get("record")
            if draft is None:
                return
            if not (data.get("files") or {}).get("enabled", draft.files.enabled):
                return
            errors = check_deposit(data.get("metadata") or {}, completed_file_keys(draft), configuration)
            if errors:
                raise ValidationError({"metadata": {"pgd_file_annotations": errors}})

        @post_dump
        def hide_annotations_without_file_access(self, data: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
            try:
                permission_check = context_schema.get().get("field_permission_check")
            except LookupError:
                return data
            metadata = data.get("metadata") or {}
            if permission_check and "pgd_file_annotations" in metadata and not permission_check("read_files"):
                metadata.pop("pgd_file_annotations")
            return data

    return ProfileSchemaMixin
