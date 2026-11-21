# STLFRC – Scanner-to-GroupMe alerts for the fire canteen

Replaces "someone always has to be listening to a scanner." A small always-on
computer with a software-defined radio (SDR) records St. Louis County fire
dispatch, transcribes every call, and posts to GroupMe when it hears a canteen
request, rehab request, multiple alarm, or working fire.

```
 St. Louis County P25 radio
          │
   RTL-SDR / Airspy  ──►  trunk-recorder  ──►  audio + JSON per call
                                                     │
                                         stlfrc watch (this project)
                                           ├─ Whisper speech-to-text (local)
                                           ├─ keyword rules (config.toml)
                                           └─ GroupMe bot post
```

Example alert:

```
🚒 CANTEEN REQUEST – County Fire Dispatch at 14:32:05
"Command to dispatch, requesting the canteen to 123 Main Street"
(Auto-transcribed – listen before responding)
```

> Transcription isn't perfect. The rules lean toward alerting too often
> rather than missing a call, and every alert says it was auto-transcribed.
> Keep a human in the loop for anything that matters.

## Hardware (about $150–$400)

| Item | Notes |
|---|---|
| SDR | RTL-SDR Blog V4 (~$40) works. An Airspy Mini/R2 (~$130–$200) covers more of the band and handles strong signals better. A P25 site usually needs one SDR if its frequencies fit within ~2 MHz, otherwise two. |
| Antenna | A tuned 700/800 MHz antenna mounted high (attic or roof) beats the stock whip by a lot. |
| Computer | Mini PC (Intel N100 or better, 8–16 GB RAM, ~$150–$250) is recommended. A Raspberry Pi 5 can run trunk-recorder, but Whisper is slow on it, so use the `base.en` model. |
| Power | A small UPS so alerts survive power blips. |

## Setup

### 1. Radio: trunk-recorder

1. Install [trunk-recorder](https://github.com/robotastic/trunk-recorder) (Docker image or packages).
2. On [RadioReference](https://www.radioreference.com), open the St. Louis County
   P25 system. Pick the site closest to you and note its **control channels**
   and the **talkgroup IDs** for fire dispatch and fireground ops.
3. Copy `trunk-recorder/config.example.json` to `/etc/trunk-recorder/config.json`,
   fill in `control_channels` and `center`, and list your talkgroups in `talkgroups.csv`.
4. Start it and confirm audio files appear under `/var/lib/trunk-recorder/audio`.

### 2. GroupMe bot

1. Sign in at <https://dev.groupme.com/bots> with an account that is in the target group.
2. **Create Bot**, choose the group, name it (e.g. "Canteen Scanner"), and leave the callback URL blank.
3. Copy the **Bot ID**.

### 3. STLFRC

```bash
sudo useradd -r -s /usr/sbin/nologin stlfrc
sudo mkdir -p /opt/stlfrc /etc/stlfrc /var/lib/stlfrc
sudo chown stlfrc /var/lib/stlfrc
sudo git clone https://github.com/dottieconsultinginc-cloud/STLFRC /opt/stlfrc
sudo python3 -m venv /opt/stlfrc/.venv
sudo /opt/stlfrc/.venv/bin/pip install /opt/stlfrc
sudo cp /opt/stlfrc/config.example.toml /etc/stlfrc/config.toml
echo 'STLFRC_GROUPME_BOT_ID=paste-bot-id-here' | sudo tee /etc/stlfrc/env
sudo chmod 600 /etc/stlfrc/env
```

Edit `/etc/stlfrc/config.toml`: add your talkgroups and adjust the rules.

Send a test message:

```bash
sudo -u stlfrc env $(sudo cat /etc/stlfrc/env) /opt/stlfrc/.venv/bin/stlfrc -c /etc/stlfrc/config.toml test-alert
```

Run it as a service:

```bash
sudo cp /opt/stlfrc/deploy/stlfrc.service /etc/systemd/system/
sudo systemctl enable --now stlfrc
journalctl -u stlfrc -f
```

The log shows every transcription, which is handy for tuning rules.

## Commands

| Command | What it does |
|---|---|
| `stlfrc watch` | Run continuously: transcribe new calls and send alerts |
| `stlfrc test-alert ["message"]` | Send a test message to GroupMe |
| `stlfrc transcribe file.m4a` | Transcribe a recording and show which rules match |
| `stlfrc match "some text"` | Check a sentence against the rules without audio |

## Tuning rules

Rules live in `config.toml` as case-insensitive regular expressions. Whisper
often mishears radio words, so after running for a few days, check the logs
for how it actually writes "canteen" and add those spellings. Add frequent
street and unit names to `[whisper] prompt` too. Limit a rule to specific
talkgroups with `talkgroups = [1234]`.

## Development

```bash
pip install -e '.[test]'
pytest
```

## Roadmap

- Web page with recent calls, transcripts, audio playback, and a test button
- Tone-out (two-tone / QC-II) detection, if dispatch tones the canteen
- Backup alert channel (SMS or push) and a daily "still alive" heartbeat
- Pull incident addresses from CAD if access becomes available
