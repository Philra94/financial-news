This directory is the shared agent context root for the project.

Use `.agents/skills/` for project-specific skills that should be visible to supported agent CLIs such as Cursor and Codex.

The application also mirrors this `.agents` directory into each spawned agent workspace before running analysis, compile, or claim-research jobs.
