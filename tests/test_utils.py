from agents.utils import unwrap_markdown_response


def test_unwrap_markdown_response_strips_outer_markdown_fence() -> None:
    response = """```markdown
# Morning Briefing

Briefing body
```"""

    assert unwrap_markdown_response(response) == "# Morning Briefing\n\nBriefing body"


def test_unwrap_markdown_response_keeps_plain_markdown() -> None:
    response = "# Morning Briefing\n\nBriefing body"

    assert unwrap_markdown_response(response) == response
