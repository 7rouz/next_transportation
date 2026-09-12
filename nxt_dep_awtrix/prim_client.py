import datetime
import logging
import os

import requests
import yaml

logger = logging.getLogger('nxt_dep_ratp')

DEFAULT_LINES_PATH = os.path.join(os.path.dirname(__file__), "lines.yaml")


class TransportationConfigError(ValueError):
    """Raised when a 'lines' configuration (from the add-on option or the
    bundled default file) doesn't have the shape get_next_departure() and
    run_once() expect, so the problem is clear immediately instead of surfacing
    as a KeyError deep inside the polling loop."""


def _require_fields(item, fields, source, what):
    missing = [field for field in fields if field not in item]
    if missing:
        raise TransportationConfigError(f"{source}: {what} is missing required field(s) {missing}: {item}")


def _validate_transportations(lines, source):
    if not isinstance(lines, list) or not lines:
        raise TransportationConfigError(f"{source} must contain a non-empty list of lines")

    for i, line in enumerate(lines):
        _require_fields(line, ("line_name", "line_ref", "stops"), source, f"line #{i + 1}")
        if not isinstance(line["stops"], list) or not line["stops"]:
            raise TransportationConfigError(f"{source}: line '{line['line_name']}' must have a non-empty list of stops")
        for j, stop in enumerate(line["stops"]):
            _require_fields(stop, ("stop_ref", "stop_name", "destination_name"), source,
                             f"line '{line['line_name']}', stop #{j + 1}")

    return lines


def load_transportations(configured_lines=None):
    """Returns configured_lines if given (the add-on's 'lines' option),
    otherwise falls back to the bundled lines.yaml (also always used by
    scripts/check_departures.py, which has no add-on options of its own)."""
    if configured_lines:
        return _validate_transportations(configured_lines, "configured 'lines' option")

    with open(DEFAULT_LINES_PATH) as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict) or "lines" not in data:
        raise TransportationConfigError(f"{DEFAULT_LINES_PATH} must contain a top-level 'lines' key")

    return _validate_transportations(data["lines"], DEFAULT_LINES_PATH)


def time_remaining_until_next_departure(next_departure):
    # SIRI timestamps end in "Z" (UTC); milliseconds aren't always ".000" so
    # replace the trailing Z rather than a fixed ".000Z" literal.
    next_departure_date = datetime.datetime.fromisoformat(next_departure.replace('Z', '+00:00'))
    now = datetime.datetime.now(datetime.timezone.utc)
    date_diff = next_departure_date - now
    logger.debug(f"next departure {next_departure_date} and now {now}, difference: {date_diff}")
    return date_diff


def get_next_departure(api_token, line, stop):
    try:
        response = requests.get(
            "https://prim.iledefrance-mobilites.fr/marketplace/stop-monitoring",
            headers={"apikey": f"{api_token}"},
            params={"MonitoringRef": f"{stop}", "LineRef": f"{line}"},
            timeout=10,
        )
    except requests.exceptions.RequestException as exc:
        logger.error(f"get departure request failed: {exc}")
        return None

    if response.status_code == 200:
        data = response.json()
        ret = {"next_departures": [], "Notice": ""}
        try:
            delivery = data["Siri"]["ServiceDelivery"]["StopMonitoringDelivery"][0]
            departures = delivery["MonitoredStopVisit"]
        except (KeyError, IndexError) as exc:
            logger.error(f"unexpected response shape from stop-monitoring API: {exc}")
            return None

        if len(departures) == 0:
            try:
                ret["Notice"] = delivery["ServiceException"][0]["Notice"][0]["value"]
            except (KeyError, IndexError):
                ret["Notice"] = "No departures found"
        else:
            nxt_departures = []
            for departure in departures:
                nxt_departures.append({"ExpectedDepartureTime": departure["MonitoredVehicleJourney"]["MonitoredCall"]["ExpectedDepartureTime"],
                                       "DepartureStatus": departure["MonitoredVehicleJourney"]["MonitoredCall"]["DepartureStatus"]})
            ret["next_departures"] = nxt_departures
        return ret
    else:
        logger.error(f"get departure request returned {response.status_code} : {response.text}")
        return None
