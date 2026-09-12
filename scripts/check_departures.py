import json
import math
import logging
import logging.config
import os
import sys

# prim_client.py lives in nxt_dep_awtrix/ (it's shipped in the add-on's Docker
# image from there); add that directory to the path so this standalone script
# can reuse it instead of keeping its own copy.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "nxt_dep_awtrix"))
from prim_client import load_transportations, get_next_departure, time_remaining_until_next_departure  # noqa: E402

try:
    logging.config.fileConfig(os.path.join(os.path.dirname(__file__), "..", "nxt_dep_awtrix", "logging.conf"))
except FileNotFoundError:
    logging.basicConfig(level=logging.INFO)
    logging.warning("logging.conf not found, falling back to basicConfig")

logger = logging.getLogger('nxt_dep_ratp')

logger.debug("Environment variables loaded (values not logged for safety)")
PRIM_API_TOKEN = os.environ.get("PRIM_API_TOKEN")
if not PRIM_API_TOKEN:
    logger.error("PRIM_API_TOKEN is not set in the environment - the API calls will fail")
    raise RuntimeError("PRIM_API_TOKEN environment variable is not set")

TRANSPORTATIONS = load_transportations()


if __name__ == '__main__':
    for transportation in TRANSPORTATIONS:
        line_name = transportation["line_name"]
        for stop in transportation["stops"]:
            stop_name = stop["stop_name"]
            destination_name = stop["destination_name"]
            departure_json = get_next_departure(PRIM_API_TOKEN, transportation["line_ref"], stop["stop_ref"])
            if departure_json is None:
                logger.warning(f"Could not get departures for line {line_name} in stop {stop_name} in direction of {destination_name}")
                continue

            logger.debug(json.dumps(departure_json, indent=2))
            if departure_json["Notice"] != "":
                logger.info(f"No departures for line {line_name} in stop {stop_name} in direction of {destination_name}: {departure_json['Notice']}")
            else:
                logger.info(f"next departures for line {line_name} in stop {stop_name} in direction of {destination_name}")
                for i, departure in enumerate(departure_json["next_departures"]):
                    departure["Line"] = line_name
                    departure["Stop"] = stop_name
                    departure["Destination"] = destination_name
                    seconds_remaining = time_remaining_until_next_departure(departure["ExpectedDepartureTime"]).total_seconds()
                    wait_time = max(0, math.floor(seconds_remaining / 60))
                    departure["WaitTime"] = wait_time
                    logger.info(f"Next departure {i + 1} of {line_name} to {destination_name} in {wait_time}")
                logger.debug(json.dumps(departure_json, indent=2))
