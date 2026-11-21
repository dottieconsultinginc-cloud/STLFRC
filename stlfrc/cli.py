"""Command line entry point: `stlfrc watch | test-alert | transcribe | match`."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime

from . import groupme
from .config import load_config
from .matcher import find_matches


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="stlfrc", description="Scanner-to-GroupMe alerts for the fire canteen")
    p.add_argument("-c", "--config", default="/etc/stlfrc/config.toml")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("watch", help="Run continuously: transcribe new calls and send alerts")
    t = sub.add_parser("test-alert", help="Send a test message to GroupMe")
    t.add_argument("message", nargs="?", default=None)
    tr = sub.add_parser("transcribe", help="Transcribe an audio file and show any rule matches")
    tr.add_argument("audio")
    tr.add_argument("--talkgroup", type=int, default=0)
    m = sub.add_parser("match", help="Check a sentence against the rules (no audio)")
    m.add_argument("text")
    m.add_argument("--talkgroup", type=int, default=0)

    args = p.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    cfg = load_config(args.config)

    if args.cmd == "test-alert":
        msg = args.message or f"✅ STLFRC test alert – {datetime.now():%Y-%m-%d %H:%M}. No action needed."
        groupme.send(cfg.groupme_bot_id, msg)
        print("Sent.")
        return 0

    if args.cmd == "match":
        _print_matches(find_matches(args.text, args.talkgroup, cfg.rules))
        return 0

    from .transcribe import Transcriber

    transcriber = Transcriber(cfg.whisper_model, cfg.whisper_device, cfg.whisper_prompt)

    if args.cmd == "transcribe":
        text = transcriber.transcribe(args.audio)
        print(text)
        _print_matches(find_matches(text, args.talkgroup, cfg.rules))
        return 0

    from .pipeline import Processor, Watcher

    Watcher(cfg, Processor(cfg, transcriber)).run()
    return 0


def _print_matches(matches) -> None:
    if not matches:
        print("No alert rules matched.")
    for mt in matches:
        print(f"MATCH {mt.rule}: {mt.phrase!r}")


if __name__ == "__main__":
    sys.exit(main())
