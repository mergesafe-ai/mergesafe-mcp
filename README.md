# mergesafe-mcp

MergeSafe's findings for your own coding agent (Claude Code, Cursor, or anything else that speaks MCP over stdio).
Your agent reads what MergeSafe found on a pull request, fixes it on your machine, replies on the thread, and asks for a new review.

| Tool | What it does |
| --- | --- |
| `get_findings(repo, pr_number)` | The latest review's findings, each with a self-contained `agent_prompt` read from its inline comment |
| `request_review(repo, pr_number, tier?, addons?)` | Asks MergeSafe to review the PR's current head |
| `reply(repo, pr_number, comment_id, body)` | Replies on a finding's thread, **as you** |
| `report_reproduction(repo, pr_number, comment_id, command, exit_code, output_tail)` | Posts the result of reproducing a finding (the command, its exit code, the last lines of output) on its thread, **as you** |

## Install

```bash
uvx mergesafe-mcp                 # run without installing
uv tool install mergesafe-mcp     # or install it
```

From source: `uv tool install git+https://github.com/mergesafe-ai/mergesafe-mcp`

## Configure

| Variable | |
| --- | --- |
| `MERGESAFE_API_KEY` | An organization API key from the MergeSafe app (`ms_live_…`) |
| `MERGESAFE_API_URL` | Optional. Defaults to `https://app.mergesafe.ai` |
| `GITHUB_TOKEN` | Optional. Defaults to `gh auth token`. Used to read MergeSafe's comments and to post your replies |

**Claude Code**

```bash
claude mcp add mergesafe --env MERGESAFE_API_KEY=ms_live_... -- mergesafe-mcp
```

**Cursor** (`~/.cursor/mcp.json` or `.cursor/mcp.json`)

```json
{
  "mcpServers": {
    "mergesafe": {
      "command": "mergesafe-mcp",
      "env": { "MERGESAFE_API_KEY": "ms_live_..." }
    }
  }
}
```

Then ask your agent: *"Fix MergeSafe's blocking findings on PR 42 in acme/widgets."*

## What leaves your machine

- **To MergeSafe:** your API key, the repo name and the PR number. MergeSafe's API returns the review's index (severity, title, file, line) and no code.
- **To GitHub:** your own token, to read comments you can already see on github.com and to post your replies.
- Your agent writes the fixes locally, with your tokens. MergeSafe never generates or applies a patch.
