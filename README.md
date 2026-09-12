# Next Transportation

## Purpose

Fetches upcoming RATP/IDFM (Île-de-France Mobilités, via the PRIM API) bus/train departure times for a fixed set of lines and stops, and displays them.

The repository contains two things:

- **[nxt_dep_awtrix/](nxt_dep_awtrix/)** — a Home Assistant add-on that polls PRIM on an interval and publishes the next departure for each configured stop to an [AWTRIX NG](https://blueforcer.github.io/awtrix-ng/)/Ulanzi TC001 pixel display over MQTT, as a rotating pushed app per stop.
- **[scripts/check_departures.py](scripts/check_departures.py)** — a standalone debug/reference script that queries the same stops and logs the departures to the console. No MQTT or Home Assistant required; useful for quickly checking the PRIM API or a stop/line reference without deploying the add-on.

The two share the PRIM API client code in [nxt_dep_awtrix/prim_client.py](nxt_dep_awtrix/prim_client.py) (loading/validating the monitored lines/stops, the HTTP call, and the departure-time math).

## Technical requirements

- Python 3.14
- A PRIM API token (free, from the [PRIM developer portal](https://prim.iledefrance-mobilites.fr/)), exposed as `PRIM_API_TOKEN`
- Dependencies from [nxt_dep_awtrix/requirements.txt](nxt_dep_awtrix/requirements.txt): `requests`, `paho-mqtt`, `PyYAML`
- To run the add-on itself: a Home Assistant instance (or plain Docker) and an MQTT broker (e.g. Mosquitto) reachable from it, plus an AWTRIX/Ulanzi display subscribed to that broker
- The monitored lines/stops are configured via the add-on's `lines` option, falling back to the bundled [nxt_dep_awtrix/lines.yaml](nxt_dep_awtrix/lines.yaml) when left empty — see [nxt_dep_awtrix/README.md](nxt_dep_awtrix/README.md) for details

## How to use

### Debug script (`scripts/check_departures.py`)

```
pip install -r nxt_dep_awtrix/requirements.txt
export PRIM_API_TOKEN=your-token-here     # PowerShell: $env:PRIM_API_TOKEN = "your-token-here"
python scripts/check_departures.py
```

Logs the next departures for every configured line/stop to the console and exits.

### Home Assistant add-on (`nxt_dep_awtrix/`)

Runs either as a standalone Docker container (Home Assistant Container, which has no Supervisor/add-on store) or as an installed add-on (Home Assistant OS/Supervised). Full step-by-step instructions for both, the configuration options, and AWTRIX NG's firmware/MQTT compatibility notes are in [nxt_dep_awtrix/README.md](nxt_dep_awtrix/README.md).

## Logging

Both entrypoints load [nxt_dep_awtrix/logging.conf](nxt_dep_awtrix/logging.conf) if present (falling back to basic INFO logging otherwise). Log level and format can be adjusted there.
