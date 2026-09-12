# Next Transportation

## Purpose

Fetches upcoming RATP/IDFM (Île-de-France Mobilités, via the PRIM API) bus/train departure times for a fixed set of lines and stops, and displays them.

The repository contains two things:

- **[nxt_dep_awtrix/](nxt_dep_awtrix/)** — a Home Assistant add-on that polls PRIM on an interval and publishes the next departure for each configured stop to an [AWTRIX](https://blueforcer.github.io/awtrix3/)/Ulanzi TC001 pixel display over MQTT, as a rotating custom app per stop.
- **[scripts/check_departures.py](scripts/check_departures.py)** — a standalone debug/reference script that queries the same stops and logs the departures to the console. No MQTT or Home Assistant required; useful for quickly checking the PRIM API or a stop/line reference without deploying the add-on.

The two share the PRIM API client code in [nxt_dep_awtrix/prim_client.py](nxt_dep_awtrix/prim_client.py) (the list of monitored lines/stops, the HTTP call, and the departure-time math).

## Technical requirements

- Python 3.12
- A PRIM API token (free, from the [PRIM developer portal](https://prim.iledefrance-mobilites.fr/)), exposed as `PRIM_API_TOKEN`
- Dependencies from [nxt_dep_awtrix/requirements.txt](nxt_dep_awtrix/requirements.txt): `requests`, `paho-mqtt`
- To run the add-on itself: a Home Assistant instance (or plain Docker) and an MQTT broker (e.g. Mosquitto) reachable from it, plus an AWTRIX/Ulanzi display subscribed to that broker
- The monitored lines/stops are hardcoded in `prim_client.py` (`TRANSPORTATIONS`) — editing them requires changing that file, there's no runtime configuration for it

## How to use

### Debug script (`scripts/check_departures.py`)

```
pip install -r nxt_dep_awtrix/requirements.txt
export PRIM_API_TOKEN=your-token-here     # PowerShell: $env:PRIM_API_TOKEN = "your-token-here"
python scripts/check_departures.py
```

Logs the next departures for every configured line/stop to the console and exits.

### Home Assistant add-on (`nxt_dep_awtrix/`)

1. Add this repository as an add-on repository in Home Assistant (Settings → Add-ons → Add-on Store → ⋮ → Repositories), then install "Next Bus/Train to Awtrix" from the store.
2. In the add-on's Configuration tab, set:
   - `prim_api_token` (required)
   - `awtrix_prefix` (required) — the MQTT topic prefix your AWTRIX device listens on
   - `mqtt_host` / `mqtt_port` / `mqtt_user` / `mqtt_password` — defaults assume the Mosquitto add-on (`core-mosquitto`)
   - `poll_interval_seconds` (default 30)
3. Start the add-on. It publishes one MQTT custom-app payload per configured stop, refreshed every poll interval; a stop with no upcoming departures clears its app instead of showing a stale time.

### Running the add-on outside Home Assistant

The same options can be set as environment variables (`PRIM_API_TOKEN`, `MQTT_HOST`, `AWTRIX_PREFIX`, etc. — see `load_config()` in `nxt_dep_awtrix.py`) instead of `/data/options.json`:

```
cd nxt_dep_awtrix
docker build -t nxt-dep-awtrix .
docker run --rm -e PRIM_API_TOKEN=... -e AWTRIX_PREFIX=... -e MQTT_HOST=... nxt-dep-awtrix
```

## Logging

Both entrypoints load [nxt_dep_awtrix/logging.conf](nxt_dep_awtrix/logging.conf) if present (falling back to basic INFO logging otherwise). Log level and format can be adjusted there.
