from pathlib import Path

import agents.runner as runner_module
from agents.runner import AgentRunner, ClaudeCodeRunner, KimiRunner, build_runner


class DummyRunner(AgentRunner):
    async def run(self, task_prompt: str, skills: list[Path]) -> str:
        self.prepare_workspace(task_prompt, skills)
        return ""


def test_prepare_workspace_attaches_project_agents_dir(tmp_path, monkeypatch) -> None:
    project_root = tmp_path / "project"
    project_agents_dir = project_root / ".agents"
    project_agents_dir.mkdir(parents=True)
    (project_agents_dir / "README.md").write_text("agent rules", encoding="utf-8")
    monkeypatch.setattr(runner_module, "ROOT_DIR", project_root)

    workspace = tmp_path / "workspace"
    runner = DummyRunner(workspace=workspace, timeout_seconds=5)

    runner.prepare_workspace("Do a thing", [])

    linked_agents_dir = workspace / ".agents"
    assert linked_agents_dir.exists()
    assert (linked_agents_dir / "README.md").read_text(encoding="utf-8") == "agent rules"


def test_prepare_workspace_skips_missing_project_agents_dir(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(runner_module, "ROOT_DIR", tmp_path / "project")
    workspace = tmp_path / "workspace"
    runner = DummyRunner(workspace=workspace, timeout_seconds=5)

    runner.prepare_workspace("Do a thing", [])

    assert not (workspace / ".agents").exists()


def test_claude_runner_defaults_to_bypass_permissions() -> None:
    runner = ClaudeCodeRunner(workspace=Path("/tmp/workspace"), timeout_seconds=5)

    assert runner.default_command == ["claude", "--print", "--dangerously-skip-permissions"]
    assert runner.pass_prompt_via_stdin is True


def test_claude_runner_appends_model_flag(monkeypatch) -> None:
    monkeypatch.setattr(runner_module.shutil, "which", lambda binary: f"/usr/bin/{binary}")
    runner = ClaudeCodeRunner(workspace=Path("/tmp/workspace"), timeout_seconds=5, model="opus")

    assert runner._resolve_command() == [
        "claude",
        "--print",
        "--dangerously-skip-permissions",
        "--model",
        "opus",
    ]


def test_kimi_runner_defaults_pipe_stdin() -> None:
    runner = KimiRunner(workspace=Path("/tmp/workspace"), timeout_seconds=5)

    assert runner.default_command == ["kimi-cli", "--print"]
    assert runner.pass_prompt_via_stdin is True


def test_kimi_runner_appends_model_flag(monkeypatch) -> None:
    monkeypatch.setattr(runner_module.shutil, "which", lambda binary: f"/usr/bin/{binary}")
    runner = KimiRunner(workspace=Path("/tmp/workspace"), timeout_seconds=5, model="kimi-k2-0905-preview")

    assert runner._resolve_command() == ["kimi-cli", "--print", "--model", "kimi-k2-0905-preview"]


def test_kimi_runner_command_override(monkeypatch) -> None:
    monkeypatch.setenv("FINNEWS_KIMI_CMD", "/opt/kimi --print --json")
    runner = KimiRunner(workspace=Path("/tmp/workspace"), timeout_seconds=5)

    assert runner._resolve_command() == ["/opt/kimi", "--print", "--json"]


def test_build_runner_dispatches_kimi() -> None:
    runner = build_runner("kimi", Path("/tmp/workspace"), 10)

    assert isinstance(runner, KimiRunner)
