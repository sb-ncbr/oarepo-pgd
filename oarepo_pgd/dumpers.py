"""Index the file annotations of a record only while anyone may read its files.

The record schema leaves the annotations out of a record returned to a reader
who may not read its files (see ``schema.py``). Search matches and counts
records in the index before that, so the index must not hold them either:
otherwise a search query or the File types filter would reveal the names,
descriptions and types of restricted files. The selected profile stays indexed.

Whether anyone may read the files is decided by the model's permission policy
for an anonymous reader, which includes OARepo workflows and embargoes. When
that cannot be established, the annotations are left out.

Records found by a search are loaded from the index, so a record with
restricted files has no annotations in search results, also for readers who
may read its files. Its detail page and the record API read the stored record.
"""

from __future__ import annotations

import logging
from typing import Any

from flask_principal import AnonymousIdentity
from invenio_access.permissions import any_user
from invenio_records.dumpers import SearchDumperExt
from oarepo_runtime import current_runtime

log = logging.getLogger(__name__)


def anyone_may_read_files(record: Any) -> bool:
    """Whether the model's permission policy lets a reader who is not logged in read the record's files."""
    # Invenio gives every request's identity the any_user need; AnonymousIdentity alone lacks it.
    identity = AnonymousIdentity()
    identity.provides.add(any_user)
    action = "draft_read_files" if getattr(record, "is_draft", False) else "read_files"
    try:
        service = current_runtime.get_record_service_for_record(record)
        return bool(service.check_permission(identity, action, record=record))
    except Exception:
        # Without an answer the files count as restricted, so nothing about them is indexed.
        # Name the record only by class and id: its repr holds the annotations.
        log.exception(
            "Could not check whether anyone may read the files of %s %s; not indexing its annotations.",
            type(record).__name__,
            getattr(record, "id", None),
        )
        return False


class FileAnnotationsDumperExt(SearchDumperExt):
    """Leave the file annotations out of the indexed document unless anyone may read the files."""

    def dump(self, record: Any, data: dict[str, Any]) -> None:
        """Remove the annotations from the document of a record whose files not everyone may read."""
        metadata = data.get("metadata") or {}
        if "pgd_file_annotations" in metadata and not anyone_may_read_files(record):
            del metadata["pgd_file_annotations"]

    def load(self, data: dict[str, Any], record_cls: Any) -> None:
        """Nothing to restore: the index never held the annotations."""
