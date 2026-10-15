"""Versioned prompt registry.

Prompts are files on disk (`<task>/v<N>.md`) so changes are code-reviewed
diffs. Every agent run records which prompt version produced it.
"""

from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent

# Pinned current version per task. Bump deliberately.
CURRENT_VERSIONS: dict[str, int] = {
    "intake_extract": 1,
    "draft_email": 2,
    "draft_follow_up": 2,
    "draft_for_customer": 1,
    "interpret_reply": 1,
}


@lru_cache
def load_prompt(task: str, version: int | None = None) -> tuple[str, str]:
    """Return (prompt_text, version_label) for a task."""
    v = version or CURRENT_VERSIONS[task]
    path = PROMPTS_DIR / task / f"v{v}.md"
    return path.read_text(), f"{task}/v{v}"
