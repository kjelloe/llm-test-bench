"""Task.requires: a task whose programs are missing is skipped as SKIPPED_ENV, an infrastructure skip (not a failure)."""
from lib.reporting import _INFRA_ERROR_KINDS
from lib.tasks import Task, missing_requirements


def _task(requires):
    return Task(id="t", description="", subdir="t", editable_files=[], context_files=[], test_cmd=["true"], requires=requires)


def test_missing_programs_are_reported():
    assert missing_requirements(_task(("sh", "no-such-program-xyz"))) == ["no-such-program-xyz"]


def test_no_requirements_or_all_present():
    assert missing_requirements(_task(())) == []
    assert missing_requirements(_task(("sh",))) == []


def test_skipped_env_counts_as_infrastructure():
    assert "SKIPPED_ENV" in _INFRA_ERROR_KINDS
