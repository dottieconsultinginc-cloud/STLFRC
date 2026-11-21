"""Watch trunk-recorder output, transcribe calls, and alert on matches.

trunk-recorder writes each call as an audio file plus a JSON sidecar with
the same name, under <captureDir>/<system>/<year>/<month>/<day>/.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import groupme
from .config import Config
from .matcher import Cooldown, Match, find_matches

log = logging.getLogger("stlfrc")

AUDIO_EXTS = (".m4a", ".wav", ".mp3")


@dataclass
class Call:
    json_path: Path
    audio_path: Path
    talkgroup: int
    talkgroup_name: str
    start_time: float
    length: float


def load_call(json_path: Path, config: Config) -> Call | None:
    try:
        meta = json.loads(json_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None  # still being written; try again next scan
    audio = next(
        (json_path.with_suffix(ext) for ext in AUDIO_EXTS if json_path.with_suffix(ext).exists()),
        None,
    )
    if audio is None:
        return None
    tg = int(meta.get("talkgroup", 0))
    name = (
        config.talkgroups.get(tg)
        or meta.get("talkgroup_tag")
        or meta.get("talkgroup_description")
        or f"TG {tg}"
    )
    return Call(
        json_path=json_path,
        audio_path=audio,
        talkgroup=tg,
        talkgroup_name=name,
        start_time=float(meta.get("start_time", time.time())),
        length=float(meta.get("call_length", 0)),
    )


def format_alert(call: Call, matches: list[Match], text: str, config: Config) -> str:
    when = datetime.fromtimestamp(call.start_time).strftime("%H:%M:%S")
    rules = ", ".join(sorted({m.rule for m in matches}))
    lines = [
        f"🚒 {rules.upper()} – {call.talkgroup_name} at {when}",
        f'"{text}"',
    ]
    if config.audio_base_url:
        rel = call.audio_path.relative_to(config.capture_dir).as_posix()
        lines.append(f"Audio: {config.audio_base_url.rstrip('/')}/{rel}")
    lines.append("(Auto-transcribed – listen before responding)")
    return "\n".join(lines)


class Processor:
    def __init__(self, config: Config, transcriber, sender=groupme.send):
        self.config = config
        self.transcriber = transcriber
        self.sender = sender
        self.cooldown = Cooldown(config.cooldown_seconds)

    def process(self, call: Call) -> str | None:
        """Handle one call. Returns the alert text if one was sent."""
        cfg = self.config
        if cfg.talkgroups and call.talkgroup not in cfg.talkgroups:
            return None
        if call.length and call.length < cfg.min_call_seconds:
            return None
        text = self.transcriber.transcribe(str(call.audio_path))
        log.info("[%s] %s", call.talkgroup_name, text)
        if not text:
            return None
        matches = [
            m for m in find_matches(text, call.talkgroup, cfg.rules)
            if self.cooldown.allow(m.rule, call.talkgroup)
        ]
        if not matches:
            return None
        alert = format_alert(call, matches, text, cfg)
        try:
            self.sender(cfg.groupme_bot_id, alert)
            log.warning("ALERT sent: %s", alert.splitlines()[0])
        except groupme.GroupMeError:
            log.exception("Failed to send GroupMe alert")
        return alert


class Watcher:
    """Polls the capture directory for new calls. Survives restarts via a state file."""

    def __init__(self, config: Config, processor: Processor, poll_seconds: float = 1.0):
        self.config = config
        self.processor = processor
        self.poll_seconds = poll_seconds
        self.seen: set[str] = set()
        if config.state_file.exists():
            self.seen = set(config.state_file.read_text().split())
        config.state_file.parent.mkdir(parents=True, exist_ok=True)
        self._started = time.time()

    def scan_once(self) -> int:
        handled = 0
        for json_path in sorted(self.config.capture_dir.rglob("*.json")):
            key = str(json_path)
            if key in self.seen:
                continue
            # Skip the backlog from before we started, so a restart doesn't
            # re-alert on old calls.
            if json_path.stat().st_mtime < self._started - 60:
                self._mark(key)
                continue
            call = load_call(json_path, self.config)
            if call is None:
                continue
            try:
                self.processor.process(call)
            except Exception:
                log.exception("Error processing %s", json_path)
            self._mark(key)
            handled += 1
        return handled

    def _mark(self, key: str) -> None:
        self.seen.add(key)
        with open(self.config.state_file, "a") as f:
            f.write(key + "\n")

    def run(self) -> None:
        log.info("Watching %s", self.config.capture_dir)
        while True:
            self.scan_once()
            time.sleep(self.poll_seconds)
