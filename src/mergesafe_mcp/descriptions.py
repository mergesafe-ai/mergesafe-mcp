"""The tool descriptions: the only instructions this package gives an agent.

They describe the loop -- read the findings, fix the blocking ones on
the developer's machine, test, reply -- and nothing about how MergeSafe
reviews. Kept apart from the server so a test can hold them to the same
no-recipe rule as every other customer-facing text, without the MCP SDK.
"""

SERVER_INSTRUCTIONS = (
    "MergeSafe reviews pull requests and posts its findings as inline comments. "
    "These tools let you act on them: get_findings, fix each blocking finding in "
    "the local checkout, run the tests, push, reply on the thread, and "
    "request_review to have the new head checked. When a finding's agent_prompt "
    "suggests a test that reproduces it, check the suggestion fits the repository, "
    "and if you run it, report the result with report_reproduction."
)

GET_FINDINGS = (
    "List MergeSafe's findings on the latest review of a pull request. "
    'repo is "owner/name". Each finding has severity (P0 most severe .. P3), '
    "title, problem, file, line, status, blocking, comment_id, comment_url, "
    "agent_prompt (a self-contained instruction for fixing it, read from the "
    "inline comment on GitHub) and comment_status: ok; no_comment (the finding "
    "has no inline comment); no_github_token (set GITHUB_TOKEN or run gh auth "
    "login, then call again); unavailable (the comment could not be read: open "
    "comment_url or the PR on GitHub). "
    "Intended loop: for each finding with blocking=true, check the claim against "
    "the file as it stands now; if it holds, apply the fix the agent_prompt "
    "describes and add a regression test; run the tests; commit and push; then "
    'call reply with "Fixed in <sha>" (or why it is not a real problem) on its '
    "comment_id."
)

REQUEST_REVIEW = (
    "Ask MergeSafe to review the current head of a pull request. "
    'repo is "owner/name" (or the bare name in the key\'s own organization). '
    "tier and addons are optional; leave them out to use the repository's own "
    "settings. Returns MergeSafe's answer unchanged. Call it after pushing fixes; "
    "a head that was already reviewed is refused, not charged twice."
)

REPLY = (
    "Reply on one MergeSafe inline comment thread, as you (with your own GitHub "
    "token, not MergeSafe's). repo is \"owner/name\"; comment_id is the finding's "
    'comment_id from get_findings. Use it to say "Fixed in <sha>" after pushing a '
    "fix, or to explain why a finding is not a real problem."
)

REPORT_REPRODUCTION = (
    "Report the result of reproducing one MergeSafe finding, as a reply on its "
    'thread (with your own GitHub token). repo is "owner/name"; comment_id is the '
    "finding's comment_id from get_findings. Pass the exact command you ran, its "
    "exit code (non-zero when the defect showed) and the tail of its output; the "
    "output is shortened to its last lines; a command over 500 characters is "
    "refused rather than shortened. Run it against the code as it stands, "
    "before fixing, and report what happened rather than what you expected: the "
    "reply records it on the thread as evidence for whoever judges the finding."
)
