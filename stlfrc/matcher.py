"""Decide whether a transcribed call should trigger an alert."""

from __future__ import annotations

import time
from dataclasses import dataclass

from .config import Rule


@dataclass
class Match:
    rule: str
    phrase: str


def find_matches(text: str, talkgroup: int, rules: list[Rule]) -> list[Match]:
    matches = []
    for rule in rules:
        if rule.talkgroups and talkgroup not in rule.talkgroups:
            continue
        for pat in rule.patterns:
            m = pat.search(text)
            if m:
                matches.append(Match(rule=rule.name, phrase=m.group(0)))
                break
    return matches


class Cooldown:
    """Suppress repeat alerts for the same rule on the same talkgroup."""

    def __init__(self, seconds: int, clock=time.monotonic):
        self.seconds = seconds
        self.clock = clock
        self._last: dict[tuple[str, int], float] = {}

    def allow(self, rule: str, talkgroup: int) -> bool:
        if self.seconds <= 0:
            return True
        now = self.clock()
        key = (rule, talkgroup)
        last = self._last.get(key)
        if last is not None and now - last < self.seconds:
            return False
        self._last[key] = now
        return True
