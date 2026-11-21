# trunk-recorder setup for SLATER

Source: RadioReference database, system id 1085 (SLATER, St. Louis County),
page updated Aug 7 2026. Re-check it before deploying, since frequencies change.

| | |
|---|---|
| Type | P25 Phase I, simulcast |
| System ID / WACN | 4F2 / BEE00 |

## Files

| File | Use |
|---|---|
| `config.example.json` | **Two RTL-SDRs** (default) |
| `config.airspy.example.json` | **One Airspy Mini/R2** instead |
| `talkgroups.csv` | Fire talkgroups to record (RadioReference CSV column layout) |

Copy the one you use to `/etc/trunk-recorder/config.json`, and copy
`talkgroups.csv` to `/etc/trunk-recorder/talkgroups.csv`.

## Choosing a site

Use the simulcast site that covers where the receiver sits. Both carry the
same talkgroups. The configs default to Site 002.

| Site | Name | NAC | Control channels (MHz) |
|---|---|---|---|
| 1-002 | StL Co. Urban South Simulcast | 4F2 | 853.4625, 853.6875, 853.7875, 853.9375 |
| 1-001 | StL Co. Urban North Simulcast | 4F1 | 853.5125, 853.725, 853.825, 853.9125 |

To use Site 001, replace `control_channels` with
`[853512500, 853725000, 853825000, 853912500]`. Then check that site's voice
frequencies on RadioReference and confirm they fall inside the source ranges
below. If they don't, move the `center` values.

## Why two RTL-SDRs

Site 002's channels run from 851.0375 MHz (lowest voice) to 853.9375 MHz
(highest control), a span of about 2.9 MHz. An RTL-SDR at 2.4 MSPS covers
2.4 MHz, and only about the middle 2 MHz is reliable. So the default config
uses two dongles that overlap:

| Source | Center | Usable range (approx.) | Covers |
|---|---|---|---|
| A (`rtl=stlfrc-a`) | 851.850 MHz | 850.85–852.85 | lower voice channels |
| B (`rtl=stlfrc-b`) | 853.250 MHz | 852.25–854.25 | upper voice + all control channels |

Both centers sit between channels, so the dongle's DC spike doesn't land on one.

**Give each dongle a unique serial** so they don't swap after a reboot. Plug
in one dongle at a time:

```bash
rtl_eeprom -s stlfrc-a   # first dongle, then unplug/replug
rtl_eeprom -s stlfrc-b   # second dongle
```

**Single-SDR alternative:** an Airspy Mini at 6 MSPS (center 852.5 MHz) covers
849.5–855.5 MHz, the whole site, with one device. For an Airspy R2, set `rate`
to 10000000 (it doesn't support 6 MSPS). Use `config.airspy.example.json`.

## Tuning

- Start with gain 40 (RTL) / 15 (Airspy) and watch trunk-recorder's log. You
  want control-channel decode rates near 40 msgs/sec. Lower the gain if decode
  is poor near the towers, which usually means overload.
- RTL-SDR Blog V4 dongles have a TCXO, so `error` can stay 0. For older
  dongles, measure the ppm offset and set `error` in Hz.
- `modulation: "qpsk"` is correct for simulcast sites.

## Talkgroups

`recordUnknown` is false, so trunk-recorder records **only** what is in
`talkgroups.csv`. To stop recording a talkgroup, delete its line. To add the
Fire Tac channels later (54700, 54703–54747, 54760–54762), add lines in the
same format with the alpha tags from RadioReference. Priority 1 = most
important, which trunk-recorder keeps when it runs out of recorders.

Not included:
- **FireNet 54101** is encrypted and can't be decoded.
- **City of St. Louis Fire** is on MOSWIN, not SLATER.
