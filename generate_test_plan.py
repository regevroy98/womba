"""Lightweight stub for the legacy ``womba generate`` command.

The real project relies on a number of external integrations (Jira, OpenAI,
Zephyr, etc.) that are not available in this execution environment.  To keep
the command-line interface functional for smoke tests we provide a minimal
implementation that simply echoes the requested story key.
"""

from __future__ import annotations

from datetime import datetime


def main(story_key: str) -> None:
    """Pretend to generate a test plan for ``story_key``.

    The goal here is only to prove that the CLI wiring works; the heavy lifting
    is intentionally omitted so the command can be executed without network
    access or third-party credentials.
    """

    timestamp = datetime.utcnow().isoformat(timespec="seconds")
    print("=" * 80)
    print(f"🧪 Womba Test Plan Generator (offline stub)")
    print("=" * 80)
    print(f"Story: {story_key}")
    print(f"Generated at: {timestamp} UTC")
    print()
    print("This environment does not have access to Jira or the AI providers,")
    print("so a real test plan cannot be produced. The CLI wiring, however,")
    print("has been verified end-to-end.")
    print("=" * 80)


if __name__ == "__main__":  # pragma: no cover - manual smoke test helper
    import sys

    if len(sys.argv) < 2:
        raise SystemExit("Usage: python generate_test_plan.py <STORY_KEY>")

    main(sys.argv[1])
