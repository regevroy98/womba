"""Offline stub for the ``womba upload`` command.

Without network connectivity or Zephyr credentials we cannot perform a real
upload.  This module merely prints a short acknowledgement so the CLI can be
smoke-tested end-to-end.
"""

from __future__ import annotations

from datetime import datetime


def main(story_key: str) -> None:
    """Pretend to upload generated tests to Zephyr Scale."""

    timestamp = datetime.utcnow().isoformat(timespec="seconds")
    print(f"📤 (stub) Would upload tests for {story_key} at {timestamp} UTC")


if __name__ == "__main__":  # pragma: no cover - manual smoke test helper
    import sys

    if len(sys.argv) < 2:
        raise SystemExit("Usage: python upload_to_zephyr.py <STORY_KEY>")

    main(sys.argv[1])
