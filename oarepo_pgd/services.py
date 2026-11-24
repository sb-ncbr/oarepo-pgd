"""Publish a record with the annotations of its own files only.

A draft may hold annotations of files it does not have (see
``rules.annotations_of_files``). The profile check ignores them, and this
component leaves them out of the published record.
"""

from __future__ import annotations

from typing import Any

from invenio_records_resources.services.records.components import ServiceComponent

from .rules import annotations_of_files


class PublishedFileAnnotationsComponent(ServiceComponent):
    """Drop the annotations of absent files when a draft is published."""

    # Run after the components that copy the draft's metadata and files to the
    # record: only then does the record hold what is being published.
    depends_on = "*"

    def publish(self, identity: Any, draft: Any = None, record: Any = None, **kwargs: Any) -> None:
        """Keep the annotations of the record's own files."""
        metadata = record.get("metadata") or {}
        if metadata.get("file_annotations"):
            file_keys = record.files.entries.keys() if record.files.enabled else ()
            metadata["file_annotations"] = annotations_of_files(metadata["file_annotations"], file_keys)
