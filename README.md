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

## Finding line and stop identifiers

Each entry under `lines` (in the add-on option or [nxt_dep_awtrix/lines.yaml](nxt_dep_awtrix/lines.yaml)) needs IDFM's own identifiers, not just a station name: a `line_ref` (e.g. `STIF:Line::C01288:`) and a `stop_ref` (e.g. `STIF:StopPoint:Q:463689:`), which the PRIM `stop-monitoring` API expects as `LineRef`/`MonitoringRef`. Two sources, used together, reliably find them:

1. **[IDFM open data stop search](https://data.iledefrance-mobilites.fr/)** (the `arrets` dataset) — searchable by stop name, returns candidate numeric stop IDs. This only has static stop metadata, no line or direction info, and a station can have several physical stop points (one per platform/direction, plus separate ones for bus poles vs. rail platforms at the same station) — so a name match here is a *candidate* `stop_ref`, not a confirmed one.

2. **PRIM's live `stop-monitoring` endpoint, queried with only `MonitoringRef` and no `LineRef` filter** — returns every line and direction actually serving that stop right now, which is what confirms a candidate ID and gives you the exact `LineRef` and `DestinationName` to use:

   ```bash
   curl -s "https://prim.iledefrance-mobilites.fr/marketplace/stop-monitoring?MonitoringRef=STIF:StopPoint:Q:<candidate-id>:" \
     -H "apikey: $PRIM_API_TOKEN" \
   | jq '.Siri.ServiceDelivery.StopMonitoringDelivery[0].MonitoredStopVisit[].MonitoredVehicleJourney | {LineRef, PublishedLineName, DirectionName, DestinationName}'
   ```

   PowerShell equivalent:
   ```powershell
   $resp = Invoke-RestMethod -Uri "https://prim.iledefrance-mobilites.fr/marketplace/stop-monitoring?MonitoringRef=STIF:StopPoint:Q:<candidate-id>:" -Headers @{apikey=$env:PRIM_API_TOKEN}
   $resp.Siri.ServiceDelivery.StopMonitoringDelivery.MonitoredStopVisit | ForEach-Object {
       $_.MonitoredVehicleJourney | Select-Object LineRef, PublishedLineName, DirectionName, DestinationName
   }
   ```

   If `jq` isn't available, a dependency-free Python fallback:
   ```bash
   curl -s "https://prim.iledefrance-mobilites.fr/marketplace/stop-monitoring?MonitoringRef=STIF:StopPoint:Q:<candidate-id>:" \
     -H "apikey: $PRIM_API_TOKEN" \
   | python3 -c "
   import json, sys
   data = json.load(sys.stdin)
   visits = data['Siri']['ServiceDelivery']['StopMonitoringDelivery'][0].get('MonitoredStopVisit', [])
   for v in visits:
       j = v['MonitoredVehicleJourney']
       print({k: j.get(k) for k in ('LineRef', 'PublishedLineName', 'DirectionName', 'DestinationName')})
   "
   ```

A well-formed but empty result (`"Status": "true"`, `"MonitoredStopVisit": []`, `"ServiceException": []`) is normal outside service hours — it means nothing is running right now (e.g. querying at 1 AM), not that the ID is wrong. Re-run the query during the line's actual service hours to get real entries back.

## Logging

Both entrypoints load [nxt_dep_awtrix/logging.conf](nxt_dep_awtrix/logging.conf) if present (falling back to basic INFO logging otherwise). Log level and format can be adjusted there.
