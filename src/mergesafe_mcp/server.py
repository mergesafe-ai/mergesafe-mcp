"""The stdio MCP server: four tools over ``mergesafe_mcp.tools``."""

from __future__ import annotations

from typing import Any

import httpx
from mcp.server.mcpserver import MCPServer

from mergesafe_mcp import descriptions, tools

mcp = MCPServer("mergesafe", instructions=descriptions.SERVER_INSTRUCTIONS)


def _call(fn: Any, *args: Any, **kwargs: Any) -> dict:
    try:
        config = tools.Config.from_env()
        with httpx.Client() as client:
            return fn(config, client, *args, **kwargs)
    except tools.ToolError as error:
        return {"error": str(error)}
    except httpx.HTTPError as error:
        return {"error": f"network error: {type(error).__name__}"}


@mcp.tool(description=descriptions.GET_FINDINGS)
def get_findings(repo: str, pr_number: int) -> dict:
    return _call(tools.get_findings, repo, pr_number)


@mcp.tool(description=descriptions.REQUEST_REVIEW)
def request_review(
    repo: str, pr_number: int, tier: str | None = None, addons: list[str] | None = None
) -> dict:
    return _call(tools.request_review, repo, pr_number, tier, addons)


@mcp.tool(description=descriptions.REPLY)
def reply(repo: str, pr_number: int, comment_id: int, body: str) -> dict:
    return _call(tools.reply, repo, pr_number, comment_id, body)


@mcp.tool(description=descriptions.REPORT_REPRODUCTION)
def report_reproduction(
    repo: str, pr_number: int, comment_id: int, command: str, exit_code: int, output_tail: str
) -> dict:
    return _call(
        tools.report_reproduction, repo, pr_number, comment_id, command, exit_code, output_tail
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
