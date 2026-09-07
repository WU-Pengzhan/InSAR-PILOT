"""One active browser document per local service; tasks do not own this lease."""

import secrets
import time
from collections.abc import Callable


class WindowLease:
    def __init__(self, ttl: float = 15, clock: Callable[[], float] = time.monotonic):
        self.ttl = ttl
        self.clock = clock
        self.owner = ""
        self.deadline = 0.0

    def acquire(self) -> str | None:
        if self.owner and self.clock() < self.deadline:
            return None
        self.owner = secrets.token_urlsafe(32)
        self.deadline = self.clock() + self.ttl
        return self.owner

    def valid(self, owner: str) -> bool:
        return bool(owner and self.owner and secrets.compare_digest(owner, self.owner) and self.clock() < self.deadline)

    def renew(self, owner: str) -> bool:
        if not self.valid(owner):
            return False
        self.deadline = self.clock() + self.ttl
        return True

    def release(self, owner: str) -> None:
        if self.owner and secrets.compare_digest(owner, self.owner):
            self.owner = ""
            self.deadline = 0.0
