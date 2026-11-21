import json
import os
import time
from pathlib import Path

import pytest

from stlfrc.config import load_config
from stlfrc.matcher import Cooldown, find_matches
from stlfrc.pipeline import Processor, Watcher, load_call

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def cfg(tmp_path):
    c = load_config(ROOT / "config.example.toml")
    c.capture_dir = tmp_path / "audio"
    c.capture_dir.mkdir()
    c.state_file = tmp_path / "state" / "processed.txt"
    c.groupme_bot_id = "test-bot"
    return c


@pytest.mark.parametrize(
    "text,rule",
    [
        ("Engine 1712 requesting the canteen to the scene", "canteen request"),
        ("go ahead and send the can teen", "canteen request"),
        ("Canteen 2 responding", "canteen request"),
        ("command requesting rehab on side alpha", "rehab request"),
        ("battalion 17 going to a second alarm", "multiple alarm"),
        ("we have a 3rd-alarm", "multiple alarm"),
        ("we have a working house fire", "working fire"),
    ],
)
def test_rules_match(cfg, text, rule):
    assert rule in {m.rule for m in find_matches(text, 0, cfg.rules)}


@pytest.mark.parametrize(
    "text",
    ["medic 1 en route to a fall", "fire alarm activation, nothing showing", "engine 12 back in quarters"],
)
def test_rules_ignore_routine_traffic(cfg, text):
    assert find_matches(text, 0, cfg.rules) == []


def test_cooldown():
    now = [0.0]
    cd = Cooldown(120, clock=lambda: now[0])
    assert cd.allow("canteen", 1)
    assert not cd.allow("canteen", 1)
    assert cd.allow("canteen", 2)  # different talkgroup
    now[0] = 121
    assert cd.allow("canteen", 1)


class FakeTranscriber:
    def __init__(self, text):
        self.text = text

    def transcribe(self, path):
        return self.text


def write_call(dirpath, name, talkgroup=1234, length=5.0):
    d = dirpath / "stlco" / "2026" / "11" / "21"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.m4a").write_bytes(b"fake")
    j = d / f"{name}.json"
    j.write_text(json.dumps({"talkgroup": talkgroup, "start_time": time.time(), "call_length": length}))
    return j


def test_processor_sends_alert(cfg):
    sent = []
    cfg.talkgroups = {1234: "County Fire Dispatch"}
    cfg.audio_base_url = "https://example.org/audio"
    j = write_call(cfg.capture_dir, "call1")
    proc = Processor(cfg, FakeTranscriber("Command requesting the canteen"), sender=lambda b, t: sent.append((b, t)))
    proc.process(load_call(j, cfg))
    assert len(sent) == 1
    bot, text = sent[0]
    assert bot == "test-bot"
    assert "CANTEEN REQUEST" in text and "County Fire Dispatch" in text
    assert "https://example.org/audio/stlco/2026/11/21/call1.m4a" in text


def test_processor_skips_other_talkgroups_and_short_calls(cfg):
    sent = []
    cfg.talkgroups = {1234: "County Fire Dispatch"}
    proc = Processor(cfg, FakeTranscriber("requesting the canteen"), sender=lambda b, t: sent.append(t))
    proc.process(load_call(write_call(cfg.capture_dir, "a", talkgroup=9999), cfg))
    proc.process(load_call(write_call(cfg.capture_dir, "b", length=0.5), cfg))
    assert sent == []


def test_watcher_processes_new_calls_once_and_skips_backlog(cfg):
    sent = []
    cfg.talkgroups = {}  # transcribe everything
    old = write_call(cfg.capture_dir, "old")
    past = time.time() - 3600
    os.utime(old, (past, past))
    proc = Processor(cfg, FakeTranscriber("requesting the canteen"), sender=lambda b, t: sent.append(t))
    w = Watcher(cfg, proc)
    write_call(cfg.capture_dir, "new")
    w.scan_once()
    w.scan_once()
    assert len(sent) == 1
    # A restarted watcher must not re-alert.
    Watcher(cfg, proc).scan_once()
    assert len(sent) == 1
