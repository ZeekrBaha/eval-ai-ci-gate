"""T6 — Slack + PR-comment notifiers. Mocked HTTP only; no live calls.

Both notifiers must degrade gracefully (skip, never raise) when their token/webhook is
absent, and never leak the secret into their return value.
"""

from typing import Any

from gate.notify import notify_slack, upsert_pr_comment

WEBHOOK = "https://hooks.slack.com/services/T000/B000/xxx"


# --- Slack -------------------------------------------------------------------


def test_slack_skips_without_webhook() -> None:
    calls: list[Any] = []

    def post(url: str, payload: dict[str, Any]) -> int:
        calls.append((url, payload))
        return 200

    result = notify_slack("hello", None, post=post)
    assert result == "skipped: no webhook"
    assert calls == []


def test_slack_posts_with_webhook() -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    def post(url: str, payload: dict[str, Any]) -> int:
        calls.append((url, payload))
        return 200

    result = notify_slack("verdict: BLOCKED", WEBHOOK, post=post)
    assert result == "sent"
    assert calls[0][0] == WEBHOOK
    assert "verdict: BLOCKED" in calls[0][1]["text"]


def test_slack_return_value_has_no_secret() -> None:
    result = notify_slack("x", WEBHOOK, post=lambda url, payload: 200)
    assert "hooks.slack.com" not in result


def test_slack_non_2xx_reported_not_raised() -> None:
    result = notify_slack("x", WEBHOOK, post=lambda url, payload: 500)
    assert result.startswith("error")


# --- PR comment --------------------------------------------------------------


class FakeClient:
    """Minimal GitHub-API stand-in capturing calls."""

    def __init__(self, existing: list[dict[str, Any]] | None = None) -> None:
        self.existing = existing or []
        self.posted: list[dict[str, Any]] = []
        self.patched: list[tuple[int, dict[str, Any]]] = []

    def get(self, url: str, headers: dict[str, str]) -> tuple[int, Any]:
        return 200, self.existing

    def post(self, url: str, headers: dict[str, str], json: dict[str, Any]) -> tuple[int, Any]:
        self.posted.append(json)
        return 201, {"id": 999}

    def patch(self, url: str, headers: dict[str, str], json: dict[str, Any]) -> tuple[int, Any]:
        cid = int(url.rstrip("/").split("/")[-1])
        self.patched.append((cid, json))
        return 200, {"id": cid}


MARKER = "<!-- eval-ai-ci-gate -->"


def test_pr_comment_skips_without_token() -> None:
    c = FakeClient()
    result = upsert_pr_comment("body", repo="o/r", pr_number=1, token=None, client=c)
    assert result == "skipped: no token"
    assert c.posted == [] and c.patched == []


def test_pr_comment_skips_without_pr_number() -> None:
    c = FakeClient()
    result = upsert_pr_comment("body", repo="o/r", pr_number=None, token="t", client=c)
    assert result == "skipped: not a pull request"


def test_pr_comment_creates_when_none_exists() -> None:
    c = FakeClient(existing=[])
    result = upsert_pr_comment("the body", repo="o/r", pr_number=7, token="t", client=c)
    assert result == "created"
    assert len(c.posted) == 1
    assert MARKER in c.posted[0]["body"]
    assert "the body" in c.posted[0]["body"]


def test_pr_comment_updates_existing_sticky_comment() -> None:
    c = FakeClient(existing=[{"id": 42, "body": f"{MARKER}\nold content"}])
    result = upsert_pr_comment("new content", repo="o/r", pr_number=7, token="t", client=c)
    assert result == "updated"
    assert c.patched[0][0] == 42
    assert c.posted == []  # upsert, not append


def test_pr_comment_ignores_unrelated_comments() -> None:
    c = FakeClient(existing=[{"id": 1, "body": "a human comment"}])
    result = upsert_pr_comment("body", repo="o/r", pr_number=7, token="t", client=c)
    assert result == "created"
    assert len(c.posted) == 1
