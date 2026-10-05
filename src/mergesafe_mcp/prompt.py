"""The "Prompt for AI agents" block, read back out of an inline comment.

MergeSafe's inline comments end with a collapsed ``Details & AI prompt``
block whose inner ``Prompt for AI agents`` holds a fenced ``text`` block:
a self-contained hand-off for a coding agent. The fence is hard-wrapped
for GitHub, so the lines of each paragraph are joined back here; it is
at least three backticks and one longer than any run inside it.
"""

from __future__ import annotations

import re

_SUMMARY = "<summary>Prompt for AI agents</summary>"
_OPEN = re.compile(r"^\s*(`{3,})text\s*$")


def extract_agent_prompt(body: str) -> str | None:
    """The agent prompt in ``body``, unwrapped, or None when it has none."""
    lines = body.splitlines()
    start = next((i for i, line in enumerate(lines) if _SUMMARY in line), None)
    if start is None:
        return None
    fence = None
    paragraphs: list[list[str]] = [[]]
    for line in lines[start + 1 :]:
        if fence is None:
            opened = _OPEN.match(line)
            if opened:
                fence = opened.group(1)
            elif "</details>" in line:
                return None
            continue
        if line.strip() == fence:
            text = "\n\n".join(" ".join(p) for p in paragraphs if p)
            return text or None
        if line.strip():
            paragraphs[-1].append(line.strip())
        elif paragraphs[-1]:
            paragraphs.append([])
    return None
