"""Post messages to a GroupMe group through a bot.

Create the bot at https://dev.groupme.com/bots (it needs a GroupMe account
that is a member of the target group). The bot id is all that is needed.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

POST_URL = "https://api.groupme.com/v3/bots/post"
MAX_LEN = 1000  # GroupMe's message length limit


class GroupMeError(RuntimeError):
    pass


def send(bot_id: str, text: str, retries: int = 3, timeout: float = 10.0) -> None:
    if not bot_id:
        raise GroupMeError("No GroupMe bot id configured (set STLFRC_GROUPME_BOT_ID)")
    if len(text) > MAX_LEN:
        text = text[: MAX_LEN - 1] + "…"
    body = json.dumps({"bot_id": bot_id, "text": text}).encode()
    req = urllib.request.Request(
        POST_URL, data=body, headers={"Content-Type": "application/json"}
    )
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if 200 <= resp.status < 300:
                    return
                last_err = GroupMeError(f"HTTP {resp.status}")
        except urllib.error.HTTPError as e:
            # 4xx means a bad bot id or request; retrying won't help.
            if 400 <= e.code < 500:
                raise GroupMeError(f"GroupMe rejected the message: HTTP {e.code}") from e
            last_err = e
        except (urllib.error.URLError, TimeoutError) as e:
            last_err = e
        time.sleep(2**attempt)
    raise GroupMeError(f"Could not reach GroupMe: {last_err}")
