"""Best-effort public release checks without sending project data or credentials."""
import json
import re
from urllib.request import Request, urlopen
import threading
import time

from . import __version__


def stable_version(value):
    if not isinstance(value, str) or not re.fullmatch(r"v?\d+\.\d+\.\d+", value):
        return None
    return tuple(int(part) for part in value.removeprefix("v").split("."))


class UpdateChecker:
    """Cache successes and failures for six hours, including concurrent requests."""

    def __init__(self):
        self._lock = threading.Lock()
        self._checked_at = None
        self._latest = None

    def check(self):
        with self._lock:
            now = time.monotonic()
            if self._checked_at is not None and now - self._checked_at < 6 * 60 * 60:
                return self._latest
            self._checked_at = now
            self._latest = None
            try:
                request = Request(
                    "https://api.github.com/repos/shaheedazaad/meta-coder/releases/latest",
                    headers={"Accept": "application/vnd.github+json", "User-Agent": f"meta-coder/{__version__}"},
                )
                with urlopen(request, timeout=5) as response:
                    payload = json.load(response)
                if not isinstance(payload, dict) or payload.get("draft") or payload.get("prerelease"):
                    return None
                candidate = stable_version(payload.get("tag_name"))
                current = stable_version(__version__)
                if candidate is not None and current is not None and candidate > current:
                    self._latest = ".".join(map(str, candidate))
            except (OSError, ValueError, TypeError):
                pass  # Offline, rate limited, or malformed feed: keep the app usable.
            return self._latest
