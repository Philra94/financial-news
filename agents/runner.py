from __future__ import annotations

import asyncio
import os
import shutil
from abc import ABC, abstractmethod
from pathlib import Path

from agents.models import AgentBackend
from agents.paths import ROOT_DIR
from agents.storage import write_text


class AgentRunner(ABC):
    def __init__(self, workspace: Path, timeout_seconds: int) -> None:
        self.workspace = workspace
        self.timeout_seconds = timeout_seconds

    @abstractmethod
    async def run(self, task_prompt: str, skills: list[Path]) -> str:
        raise NotImplementedError

    def prepare_workspace(self, task_prompt: str, skills: list[Path]) -> None:
        self.workspace.mkdir(parents=True, exist_ok=True)
        self._attach_project_agents_dir()
        write_text(self.workspace / "TASK.md", task_prompt)
        skill_sections = []
        for skill in skills:
            if not skill.exists():
                continue
            skill_sections.append(f"# {skill.parent.name}\n\n{skill.read_text(encoding='utf-8')}")
        write_text(self.workspace / "AGENTS.md", "\n\n".join(skill_sections))

    def _attach_project_agents_dir(self) -> None:
        project_agents_dir = ROOT_DIR / ".agents"
        workspace_agents_dir = self.workspace / ".agents"
        if not project_agents_dir.exists() or workspace_agents_dir.exists():
            return
        try:
            workspace_agents_dir.symlink_to(project_agents_dir, target_is_directory=True)
        except OSError:
            shutil.copytree(project_agents_dir, workspace_agents_dir)

    async def _run_command(self, command: list[str], task_prompt: str) -> str:
        process = await asyncio.create_subprocess_exec(
            *command,
            task_prompt,
            cwd=str(self.workspace),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=self.timeout_seconds)
        if process.returncode != 0:
            raise RuntimeError(stderr.decode("utf-8", errors="ignore") or "Agent CLI failed")
        return stdout.decode("utf-8", errors="ignore").strip()


class SubprocessRunner(AgentRunner):
    env_var_name: str
    default_command: list[str]

    async def run(self, task_prompt: str, skills: list[Path]) -> str:
        self.prepare_workspace(task_prompt, skills)
        command = self._resolve_command()
        return await self._run_command(command, task_prompt)

    def _resolve_command(self) -> list[str]:
        override = os.getenv(self.env_var_name)
        if override:
            return override.split()
        binary = self.default_command[0]
        if shutil.which(binary) is None:
            raise FileNotFoundError(
                f"Required agent CLI '{binary}' was not found. Set {self.env_var_name} to override."
            )
        return self.default_command


class ClaudeCodeRunner(SubprocessRunner):
    env_var_name = "FINNEWS_CLAUDE_CODE_CMD"
    default_command = ["claude", "--print", "--dangerously-skip-permissions"]


class CodexRunner(SubprocessRunner):
    env_var_name = "FINNEWS_CODEX_CMD"
    default_command = ["codex", "exec", "--skip-git-repo-check"]


class CursorRunner(SubprocessRunner):
    env_var_name = "FINNEWS_CURSOR_CMD"
    default_command = ["cursor-agent", "--print"]


class CopilotRunner(SubprocessRunner):
    env_var_name = "FINNEWS_COPILOT_CMD"
    default_command = ["gh", "copilot", "suggest"]


def build_runner(backend: AgentBackend, workspace: Path, timeout_seconds: int) -> AgentRunner:
    if backend == "claude-code":
        return ClaudeCodeRunner(workspace, timeout_seconds)
    if backend == "cursor":
        return CursorRunner(workspace, timeout_seconds)
    if backend == "copilot":
        return CopilotRunner(workspace, timeout_seconds)
    return CodexRunner(workspace, timeout_seconds)
