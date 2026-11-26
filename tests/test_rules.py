"""Server rules against the cases shared with the form (cases/rules.json)."""

import json
from pathlib import Path

import pytest

from oarepo_pgd.config import parse_configuration
from oarepo_pgd.rules import check, check_deposit

SHARED = json.loads((Path(__file__).parent / "cases" / "rules.json").read_text(encoding="utf-8"))


def arguments(case):
    metadata = {"pgd_deposition_profile": case["profile"], "pgd_file_annotations": case["annotations"]}
    return metadata, case["file_keys"], parse_configuration(SHARED["configurations"][case["configuration"]])


@pytest.mark.parametrize("case", SHARED["cases"], ids=lambda case: case["name"])
def test_shared_case(case):
    assert check_deposit(*arguments(case)) == case["errors"]


@pytest.mark.parametrize("case", SHARED["cases"], ids=lambda case: case["name"])
def test_shared_case_structure(case):
    result = check(*arguments(case))
    assert [
        {"code": issue.code, "file_key": issue.file_key, "requirement": issue.requirement}
        for issue in result.errors
    ] == case["issues"]
    assert [issue.text for issue in result.errors] == case["errors"]
    assert result.counts == case["counts"]
    assert result.states == case["states"]
