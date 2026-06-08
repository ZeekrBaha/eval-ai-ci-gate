"""notify.py — optional Slack + PR-comment notifiers.

Both are graceful: with no webhook/token they SKIP (never raise), so the offline core
stays valid and a missing secret degrades to "no notification" rather than a failed run.
Secrets are never returned in result strings or logged. HTTP is dependency-injected so
tests run with no live calls; the defaults wrap `requests` (the optional `notify` extra).
"""

from __future__ import annotations

from typing import Any, Callable, Protocol

PR_COMMENT_MARKER = "<!-- eval-ai-ci-gate -->"

# post(url, json_payload) -> http_status_code
SlackPost = Callable[[str, dict[str, Any]], int]


class HttpClient(Protocol):
    """Minimal GitHub-API surface: each method returns (status_code, parsed_json)."""

    def get(self, url: str, headers: dict[str, str]) -> tuple[int, Any]: ...
    def post(self, url: str, headers: dict[str, str], json: dict[str, Any]) -> tuple[int, Any]: ...
    def patch(self, url: str, headers: dict[str, str], json: dict[str, Any]) -> tuple[int, Any]: ...


def notify_slack(text: str, webhook_url: str | None, *, post: SlackPost | None = None) -> str:
    """Post *text* to a Slack incoming webhook. Skip (no-op) when the webhook is unset."""
    if not webhook_url:
        return "skipped: no webhook"
    sender = post if post is not None else _requests_slack_post
    status = sender(webhook_url, {"text": text})
    if 200 <= status < 300:
        return "sent"
    return f"error: Slack returned HTTP {status}"


def upsert_pr_comment(
    body: str,
    *,
    repo: str | None,
    pr_number: int | None,
    token: str | None,
    marker: str = PR_COMMENT_MARKER,
    client: HttpClient | None = None,
) -> str:
    """Create or update a single sticky PR comment (found by *marker*). Skip when off-PR/token-less."""
    if not token:
        return "skipped: no token"
    if not repo or not pr_number:
        return "skipped: not a pull request"

    http = client if client is not None else _RequestsClient()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    marked_body = f"{marker}\n{body}"

    _status, comments = http.get(
        f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments", headers
    )
    existing_id = _find_marked(comments, marker)
    if existing_id is not None:
        http.patch(
            f"https://api.github.com/repos/{repo}/issues/comments/{existing_id}",
            headers,
            {"body": marked_body},
        )
        return "updated"
    http.post(
        f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments",
        headers,
        {"body": marked_body},
    )
    return "created"


def _find_marked(comments: Any, marker: str) -> int | None:
    if not isinstance(comments, list):
        return None
    for c in comments:
        if isinstance(c, dict) and marker in str(c.get("body", "")):
            return int(c["id"])
    return None


# --- default requests-backed implementations (only used when no client injected) -----------


def _requests_slack_post(url: str, payload: dict[str, Any]) -> int:
    import requests  # local import: optional `notify` extra

    resp = requests.post(url, json=payload, timeout=10)
    return resp.status_code


class _RequestsClient:
    def get(self, url: str, headers: dict[str, str]) -> tuple[int, Any]:
        import requests

        r = requests.get(url, headers=headers, timeout=10)
        return r.status_code, r.json()

    def post(self, url: str, headers: dict[str, str], json: dict[str, Any]) -> tuple[int, Any]:
        import requests

        r = requests.post(url, headers=headers, json=json, timeout=10)
        return r.status_code, r.json()

    def patch(self, url: str, headers: dict[str, str], json: dict[str, Any]) -> tuple[int, Any]:
        import requests

        r = requests.patch(url, headers=headers, json=json, timeout=10)
        return r.status_code, r.json()
