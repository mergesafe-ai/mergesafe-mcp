"""What each MCP tool does, without the MCP SDK (so it is testable alone).

Two parties, two credentials. MergeSafe's API is called with the org's
API key: it returns the review's index -- severity, title, file, line,
the inline comment's id -- and no code. The fix text lives in those
inline comments on GitHub, which are read, and replied to, with the
developer's own GitHub token: nothing is exposed that they cannot
already read on github.com, and a reply is theirs, not MergeSafe's.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlsplit

import httpx

from mergesafe_mcp.prompt import extract_agent_prompt

DEFAULT_API_URL = "https://app.mergesafe.ai"
GITHUB_API = "https://api.github.com"
TIMEOUT_SECONDS = 30.0
# The fields of each finding handed to the agent; the API row's
# ``comment_id`` becomes ``comment_url`` plus ``agent_prompt``.
FINDING_FIELDS = ("severity", "title", "problem", "file", "line", "status", "blocking")
# GitHub comment reads in flight at once for one get_findings call.
COMMENT_FETCH_WORKERS = 8
# Where the API key may be sent. MERGESAFE_API_URL can come from a
# project-level config a repository ships (.cursor/mcp.json), so any other
# origin would hand the org's key to whoever wrote that file.
_TRUSTED_SUFFIX = ".mergesafe.ai"
_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


class ToolError(Exception):
    """A failure to report to the calling agent as the tool's result."""


@dataclass(frozen=True)
class Config:
    api_key: str
    api_url: str
    github_token: str | None

    @classmethod
    def from_env(cls) -> Config:
        api_key = os.environ.get("MERGESAFE_API_KEY", "").strip()
        if not api_key:
            raise ToolError("MERGESAFE_API_KEY is not set; create one in the MergeSafe app")
        api_url = os.environ.get("MERGESAFE_API_URL", "").strip() or DEFAULT_API_URL
        return cls(api_key, trusted_api_url(api_url), _github_token())


def trusted_api_url(url: str) -> str:
    """``url`` without a trailing slash if the API key may go there:
    https on mergesafe.ai or a subdomain, or any scheme on localhost."""
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower()
    trusted = parts.scheme == "https" and (host == "mergesafe.ai" or host.endswith(_TRUSTED_SUFFIX))
    local = parts.scheme in ("http", "https") and host in _LOCAL_HOSTS
    if not (trusted or local) or parts.username or parts.password:
        raise ToolError(
            "MERGESAFE_API_URL must be https://*.mergesafe.ai (or localhost); "
            "the API key is never sent anywhere else"
        )
    return url.strip().rstrip("/")


def _github_token() -> str | None:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        return token
    gh = shutil.which("gh")
    if gh is None:
        return None
    try:
        out = subprocess.run(
            [gh, "auth", "token"], capture_output=True, text=True, timeout=10, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() or None


def _split_repo(repo: str) -> tuple[str, str]:
    owner, _, name = repo.strip().partition("/")
    if not owner or not name or "/" in name:
        raise ToolError('repo must be "owner/name"')
    return owner, name


def _api(config: Config, client: httpx.Client, method: str, path: str, **kw: Any) -> Any:
    response = client.request(
        method,
        f"{config.api_url}/api/v1/reviews{path}",
        headers={"Authorization": f"Bearer {config.api_key}"},
        timeout=TIMEOUT_SECONDS,
        **kw,
    )
    try:
        body = response.json()
    except ValueError:
        body = {"error": response.text[:200]}
    if response.status_code >= 400:
        raise ToolError(f"MergeSafe API {response.status_code}: {body.get('error', body)}")
    return body


def _github(config: Config, client: httpx.Client, method: str, path: str, **kw: Any):
    if not config.github_token:
        raise ToolError("no GitHub token: set GITHUB_TOKEN or run `gh auth login`")
    return client.request(
        method,
        f"{GITHUB_API}{path}",
        headers={
            "Authorization": f"Bearer {config.github_token}",
            "Accept": "application/vnd.github+json",
        },
        timeout=TIMEOUT_SECONDS,
        **kw,
    )


def get_findings(config: Config, client: httpx.Client, repo: str, pr_number: int) -> dict:
    owner, name = _split_repo(repo)
    review = _api(config, client, "GET", f"/{quote(owner)}/{quote(name)}/{int(pr_number)}")
    rows = review.get("findings") or []

    def one(row: dict) -> dict:
        finding = {field: row.get(field) for field in FINDING_FIELDS}
        finding |= {"comment_id": row.get("comment_id"), "comment_url": None, "agent_prompt": None}
        if not row.get("comment_id"):
            return finding | {"comment_status": "no_comment"}
        if not config.github_token:
            return finding | {"comment_status": "no_github_token"}
        return finding | _comment(config, client, owner, name, row["comment_id"])

    with ThreadPoolExecutor(max_workers=COMMENT_FETCH_WORKERS) as pool:
        findings = list(pool.map(one, rows))
    return {
        "repo": f"{owner}/{name}",
        "pr_number": int(pr_number),
        "head_sha": review.get("head_sha"),
        "findings": findings,
        "findings_truncated": bool(review.get("findings_truncated")),
    }


def _comment(config: Config, client: httpx.Client, owner: str, name: str, comment_id: Any):
    """``comment_url``, ``agent_prompt`` and ``comment_status`` from the
    inline comment: ``unavailable`` when it could not be read (deleted, the
    token cannot see it, or GitHub failed), so the agent can tell that from
    a finding that has no comment."""
    path = f"/repos/{quote(owner)}/{quote(name)}/pulls/comments/{int(comment_id)}"
    try:
        response = _github(config, client, "GET", path)
    except httpx.HTTPError:
        return {"comment_status": "unavailable"}
    if response.status_code != 200:
        return {"comment_status": "unavailable"}
    comment = response.json()
    return {
        "comment_url": comment.get("html_url"),
        "agent_prompt": extract_agent_prompt(comment.get("body") or ""),
        "comment_status": "ok",
    }


def request_review(
    config: Config,
    client: httpx.Client,
    repo: str,
    pr_number: int,
    tier: str | None = None,
    addons: list[str] | None = None,
) -> dict:
    body: dict[str, Any] = {"repo": repo, "pr_number": int(pr_number)}
    if tier is not None:
        body["tier"] = tier
    if addons is not None:
        body["addons"] = addons
    return _api(config, client, "POST", "", json=body)


def reply(
    config: Config, client: httpx.Client, repo: str, pr_number: int, comment_id: int, body: str
) -> dict:
    owner, name = _split_repo(repo)
    if not body.strip():
        raise ToolError("reply body is empty")
    path = (
        f"/repos/{quote(owner)}/{quote(name)}/pulls/{int(pr_number)}"
        f"/comments/{int(comment_id)}/replies"
    )
    response = _github(config, client, "POST", path, json={"body": body})
    if response.status_code != 201:
        raise ToolError(f"GitHub {response.status_code}: could not reply on that thread")
    return {"comment_url": response.json().get("html_url")}


# The marker and bounds of a reproduction report. MergeSafe reads the
# reply back by this marker, so its format is a contract with the server.
REPRO_MARKER = "<!-- mergesafe:repro -->"
MAX_COMMAND_CHARS = 500
MAX_OUTPUT_CHARS = 4000
MAX_OUTPUT_LINES = 60


def _fenced(text: str) -> list[str]:
    """``text`` in a ``text`` fence one backtick longer than any run in it,
    so output that prints a fence cannot close ours early."""
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    fence = "`" * max(3, longest + 1)
    return [f"{fence}text", text, fence]


def repro_body(command: str, exit_code: int, output_tail: str) -> str:
    """The reply ``report_reproduction`` posts: marker, exit code, then
    the command and the bounded output tail, each fenced."""
    # Verbatim: collapsing whitespace inside a quoted argument would post a
    # different command from the one that produced this exit code.
    command = command.strip()
    if len(command) > MAX_COMMAND_CHARS:
        # Refused, not clipped: a clipped command is not the one that ran.
        raise ToolError(f"command is longer than {MAX_COMMAND_CHARS} characters")
    # Cut to the character cap before splitting, so a huge output costs
    # no more than the part that is posted.
    tail = "\n".join(output_tail[-MAX_OUTPUT_CHARS:].splitlines()[-MAX_OUTPUT_LINES:])
    lines = [REPRO_MARKER, f"Exit code: {int(exit_code)}", "", "Command:", *_fenced(command)]
    lines += [
        "",
        f"Output tail (last {MAX_OUTPUT_LINES} lines, {MAX_OUTPUT_CHARS} characters at most):",
        *_fenced(tail),
    ]
    return "\n".join(lines)


def report_reproduction(
    config: Config,
    client: httpx.Client,
    repo: str,
    pr_number: int,
    comment_id: int,
    command: str,
    exit_code: int,
    output_tail: str,
) -> dict:
    if not command.strip():
        raise ToolError("command is empty")
    body = repro_body(command, exit_code, output_tail)
    return reply(config, client, repo, pr_number, comment_id, body)
