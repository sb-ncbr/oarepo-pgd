"""A published record keeps the annotations of its own files only."""

from types import SimpleNamespace

from oarepo_pgd.rules import annotations_of_files
from oarepo_pgd.services import PublishedFileAnnotationsComponent

KEPT = {"file_key": "interview.txt", "semantic_types": ["interview-transcript"]}
ABSENT = {"file_key": "removed.wav", "semantic_types": ["interview-recording"]}


class FakeRecord(dict):
    """A record as the component sees it: a mapping with a file manager."""

    def __init__(self, annotations, file_keys=(), enabled=True):
        super().__init__({"metadata": {"pgd_file_annotations": annotations}})
        self.files = SimpleNamespace(enabled=enabled, entries=dict.fromkeys(file_keys))


def published(record):
    """Run the component as publication does, once the record has its metadata and files."""
    PublishedFileAnnotationsComponent(service=None).publish(None, draft=FakeRecord([]), record=record)
    return record["metadata"]["pgd_file_annotations"]


def test_annotations_of_absent_files_are_left_out():
    assert annotations_of_files([ABSENT, KEPT], ["interview.txt", "notes.md"]) == [KEPT]


def test_published_record_keeps_the_annotations_of_its_files():
    assert published(FakeRecord([KEPT, ABSENT], ["interview.txt"])) == [KEPT]


def test_a_metadata_only_record_keeps_no_annotations():
    assert published(FakeRecord([KEPT], enabled=False)) == []
