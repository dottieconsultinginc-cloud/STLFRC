"""Load STLFRC settings from a TOML file."""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Rule:
    name: str
    patterns: list[re.Pattern]
    talkgroups: set[int] = field(default_factory=set)  # empty = any talkgroup


@dataclass
class Config:
    groupme_bot_id: str
    capture_dir: Path
    state_file: Path
    talkgroups: dict[int, str]  # talkgroups to transcribe -> display name
    rules: list[Rule]
    whisper_model: str = "small.en"
    whisper_device: str = "auto"
    whisper_prompt: str = ""
    cooldown_seconds: int = 120
    audio_base_url: str = ""  # optional public URL prefix for clip links
    min_call_seconds: float = 1.0


def load_config(path: str | Path) -> Config:
    with open(path, "rb") as f:
        raw = tomllib.load(f)

    gm = raw.get("groupme", {})
    # Prefer the environment variable so the bot id never has to live in git.
    bot_id = os.environ.get("STLFRC_GROUPME_BOT_ID") or gm.get("bot_id", "")

    tr = raw.get("trunk_recorder", {})
    wh = raw.get("whisper", {})
    al = raw.get("alerts", {})

    talkgroups = {int(k): v for k, v in raw.get("talkgroups", {}).items()}

    rules = []
    for r in raw.get("rules", []):
        rules.append(
            Rule(
                name=r["name"],
                patterns=[re.compile(p, re.IGNORECASE) for p in r["patterns"]],
                talkgroups={int(t) for t in r.get("talkgroups", [])},
            )
        )

    return Config(
        groupme_bot_id=bot_id,
        capture_dir=Path(tr.get("capture_dir", "/var/lib/trunk-recorder/audio")),
        state_file=Path(tr.get("state_file", "/var/lib/stlfrc/processed.txt")),
        talkgroups=talkgroups,
        rules=rules,
        whisper_model=wh.get("model", "small.en"),
        whisper_device=wh.get("device", "auto"),
        whisper_prompt=wh.get("prompt", ""),
        cooldown_seconds=int(al.get("cooldown_seconds", 120)),
        audio_base_url=al.get("audio_base_url", ""),
        min_call_seconds=float(tr.get("min_call_seconds", 1.0)),
    )
