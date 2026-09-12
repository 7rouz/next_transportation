# Next Bus/Train to Awtrix

## Purpose

This is a Home Assistant add-on that fetches upcoming RATP/IDFM (Île-de-France Mobilités, via the [PRIM](https://prim.iledefrance-mobilites.fr/) API) departure times for a fixed set of bus/train lines and stops, and displays them on an [AWTRIX NG](https://blueforcer.github.io/awtrix-ng/)/Ulanzi TC001 pixel display over MQTT.

It runs continuously: every `poll_interval_seconds`, it queries PRIM for each configured stop and publishes a custom AWTRIX app showing the line, destination, and minutes until the next departure (e.g. `25 > Bibliotheque F.mitterrand: 4min`), colored per line. A stop with no upcoming departure clears its app instead of showing a stale time. If the add-on stops publishing for more than 90 seconds (crash, network outage), AWTRIX removes the app on its own rather than leaving stale data on screen.

The monitored lines and stops are configured via the add-on's `lines` option (see below); if left empty, it falls back to the bundled [lines.yaml](lines.yaml).

## How to use

### Prerequisites

- A running Home Assistant instance — either Home Assistant OS/Supervised (add-on support), or Home Assistant Container (plain Docker), which has no Supervisor/add-on store and needs to run this as its own container instead (see Installation below)
- An MQTT broker Home Assistant can reach — the [Mosquitto broker add-on](https://github.com/home-assistant/addons/tree/master/mosquitto) (Supervised) or the [eclipse-mosquitto](https://hub.docker.com/_/eclipse-mosquitto) image (Container) are the simplest options and are assumed by the defaults below
- An AWTRIX/Ulanzi TC001 device flashed with [AWTRIX NG](https://blueforcer.github.io/awtrix-ng/), connected to the same MQTT broker — **not AWTRIX 3**, see [AWTRIX firmware compatibility](#awtrix-firmware-compatibility) below
- A PRIM API token: register for free at the [PRIM developer portal](https://prim.iledefrance-mobilites.fr/) and create a token
- The `MonitoringRef` (stop) and `LineRef` (line) identifiers for the stops you want to track — look these up via the PRIM `stop-monitoring` API or IDFM's [open data](https://prim.iledefrance-mobilites.fr/) stop reference

### Installation

#### Home Assistant Container (plain Docker, no Supervisor)

Home Assistant Container has no add-on store, so run this as a standalone container next to it instead:

```
docker build -t nxt-dep-awtrix nxt_dep_awtrix/
docker run -d \
  --name nxt-dep-awtrix \
  --restart=unless-stopped \
  -e PRIM_API_TOKEN=your-token \
  -e AWTRIX_PREFIX=ulanzi_xxxxxx \
  -e MQTT_HOST=localhost \
  --network=host \
  nxt-dep-awtrix
```

`MQTT_HOST=localhost` assumes your MQTT broker container also runs with `--network=host`; otherwise use its container name or IP. The full set of environment variables mirrors the add-on options in the table below (`MQTT_PORT`, `MQTT_USER`, `MQTT_PASSWORD`, `POLL_INTERVAL_SECONDS`) — see `load_config()` in [nxt_dep_awtrix.py](nxt_dep_awtrix.py). To override the bundled [lines.yaml](lines.yaml), set `LINES` to a JSON-encoded version of the `lines` option described under "Changing the tracked lines/stops".

#### Home Assistant OS / Supervised (add-on store)

1. In Home Assistant, go to **Settings → Add-ons → Add-on Store**.
2. Click the **⋮** menu (top right) → **Repositories**, and add the URL of this git repository.
3. The add-on **"Next Bus/Train to Awtrix"** should now appear in the store (you may need to refresh). Click it, then **Install**.
4. Open the **Configuration** tab and fill in the options (see table below).
5. Go to the **Info** tab and click **Start**. Enable **Start on boot** if you want it to survive Home Assistant restarts.
6. Check the **Log** tab to confirm it connected to MQTT and is publishing departures without errors.

### Configuration options

| Option | Required | Default | Description |
|---|---|---|---|
| `prim_api_token` | yes | — | Your PRIM API token |
| `awtrix_prefix` | yes | — | MQTT topic prefix your AWTRIX device listens on (its MQTT settings show this, typically `ulanzi_xxxxxx`) |
| `mqtt_host` | no | `core-mosquitto` | MQTT broker hostname (default matches the Mosquitto add-on) |
| `mqtt_port` | no | `1883` | MQTT broker port |
| `mqtt_user` | no | *(none)* | MQTT username, if your broker requires auth |
| `mqtt_password` | no | *(none)* | MQTT password, if your broker requires auth |
| `poll_interval_seconds` | no | `30` | How often to query PRIM and refresh the display, in seconds |
| `lines` | no | *(empty — uses [lines.yaml](lines.yaml))* | The bus/train lines and stops to monitor (see below) |

### Changing the tracked lines/stops

Set the `lines` option from the add-on's Configuration tab — no rebuild or file editing needed. Each entry needs a `line_name` (display label), a `line_ref`, an optional `color` (hex, used for the AWTRIX app's text color), and a `stops` list, where each stop needs a `stop_ref`, `stop_name`, and `destination_name`:

```yaml
lines:
  - line_name: "25"
    line_ref: "STIF:Line::C02243:"
    color: "ff1400"
    stops:
      - stop_ref: "STIF:StopPoint:Q:25376:"
        stop_name: "Jules Vanzuppe"
        destination_name: "Bibliotheque F.mitterrand"
```

Leave `lines` empty to use the bundled [lines.yaml](lines.yaml) instead — that's also what `scripts/check_departures.py` always uses, since it has no add-on options of its own. If a configured line or stop is missing a required field, the add-on raises a clear error at startup naming the exact line/stop and field, rather than failing silently or with a raw `KeyError`.

### AWTRIX firmware compatibility

This add-on targets **AWTRIX NG**, not the older AWTRIX 3. The two are not wire-compatible — AWTRIX NG changed the MQTT topic for pushed apps, renamed several payload fields, and now strictly rejects payloads with unknown or invalid fields instead of silently ignoring them. If your device is still running AWTRIX 3, either reflash it to AWTRIX NG or you'll need to adapt `publish_departure()`/`clear_app()` in [nxt_dep_awtrix.py](nxt_dep_awtrix.py) back to the AWTRIX 3 format.

| | AWTRIX 3 | AWTRIX NG |
|---|---|---|
| Custom/pushed app topic | `<prefix>/custom/<name>` | `<prefix>/cmd/apps/pushed/<name>` |
| Text color field | `color` | `textColor` |
| Duration | `duration` (seconds) | `durationMs` (milliseconds) |
| Lifetime | `lifetime` (seconds) | `lifetimeMs` (milliseconds) |
| Lifetime behavior | `lifetimeMode` (`0`/`1`) | `lifetimeExpiry` (`"remove"`/`"mark"`) |
| Removing an app | empty payload to the topic | empty payload to the topic (unchanged) |

References:
- [AWTRIX NG — MQTT topics reference](https://blueforcer.github.io/awtrix-ng/reference/mqtt/)
- [AWTRIX NG — Migrating from AWTRIX 3](https://blueforcer.github.io/awtrix-ng/guides/migrating-from-awtrix3/)

### Logging

Log level and format are controlled by [logging.conf](logging.conf) (INFO by default); if the file is missing at runtime it falls back to basic INFO logging.

### Troubleshooting

- **Add-on won't start / "Missing required config value"**: `prim_api_token` or `awtrix_prefix` isn't set in the Configuration tab.
- **Log shows repeated "could not connect to MQTT broker"**: check `mqtt_host`/`mqtt_port`/credentials, and that the broker add-on is running.
- **Log shows "get departure request returned 401"**: the PRIM API token is invalid or expired.
- **Nothing shows up on the display but no errors in the log**: double-check `awtrix_prefix` matches the MQTT prefix configured on the AWTRIX device itself, and that the device is subscribed to that broker.
- **Nothing shows up and the device is on AWTRIX 3, not AWTRIX NG**: see [AWTRIX firmware compatibility](#awtrix-firmware-compatibility) — the two firmwares use different MQTT topics and payload fields.
