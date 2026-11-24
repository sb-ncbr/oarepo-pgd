"""Server rules against the cases shared with the form (cases/rules.json)."""

import json
from pathlib import Path

import pytest

from oarepo_pgd.rules import check_deposit

SHARED = json.loads((Path(__file__).parent / "cases" / "rules.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", SHARED["cases"], ids=lambda case: case["name"])
def test_shared_case(case):
    metadata = {"pgd_deposition_profile": case["profile"], "pgd_file_annotations": case["annotations"]}
    configuration = SHARED["configurations"][case["configuration"]]
    assert check_deposit(metadata, case["file_keys"], configuration) == case["errors"]
