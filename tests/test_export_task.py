import pytest

from lib.tasks import TASK_MAP, export_task


def test_export_writes_task_md_and_prompt(tmp_path):
    dest = tmp_path / "out"
    export_task(TASK_MAP["python_safe_div"], dest)
    assert (dest / "TASK.md").exists()
    assert (dest / "PROMPT.txt").exists()
    assert "python_safe_div" in (dest / "TASK.md").read_text()


def test_export_includes_editable_and_context_files(tmp_path):
    dest = tmp_path / "out"
    task = TASK_MAP["node_paratrooper"]
    export_task(task, dest)
    for rel in task.editable_files + task.context_files:
        assert (dest / rel).exists(), f"missing {rel}"


def test_export_excludes_reference_solution(tmp_path):
    dest = tmp_path / "out"
    export_task(TASK_MAP["node_paratrooper"], dest)
    assert not (dest / "src" / "game.reference.js").exists()
    assert not any(dest.rglob("*.reference.*"))


def test_export_refuses_nonempty_destination(tmp_path):
    dest = tmp_path / "out"
    export_task(TASK_MAP["python_safe_div"], dest)
    with pytest.raises(FileExistsError):
        export_task(TASK_MAP["python_safe_div"], dest)


def test_export_prompt_matches_harness_prompt(tmp_path):
    """PROMPT.txt must be byte-identical to what the harness actually sends a model."""
    from lib.tasks import build_prompt

    dest = tmp_path / "out"
    task = TASK_MAP["python_safe_div"]
    export_task(task, dest)
    assert (dest / "PROMPT.txt").read_text() == build_prompt(task, dest)


def _section(md: str, heading: str) -> list[str]:
    lines = md.splitlines()
    start = lines.index(heading) + 1
    out = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        out.append(line)
    return out


@pytest.mark.parametrize("task_id", sorted(TASK_MAP))
def test_task_md_contract_used_by_llm_service_provider(tmp_path, task_id):
    """~/GIT/llm-service-provider/bin/selftest.sh --bench parses TASK.md: the `- `file`` bullets under
    '## Files you may edit' (its allowed-edit list) and the first fenced line under '## Check your
    work' (the command that decides pass/fail). Changing these headings or formats breaks it."""
    task = TASK_MAP[task_id]
    dest = tmp_path / "out"
    export_task(task, dest)
    md = (dest / "TASK.md").read_text()
    edits = [l[3:-1] for l in _section(md, "## Files you may edit") if l.startswith("- `")]
    assert edits == list(task.editable_files)
    check = _section(md, "## Check your work")
    fence = check.index("```")
    assert check[fence + 1] == " ".join(task.test_cmd)
    assert ("**Setup:**" in md) == bool(task.setup_cmd)
