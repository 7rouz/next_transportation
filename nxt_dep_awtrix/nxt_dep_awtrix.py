import datetime
import json
import math
import logging
import logging.config
import os
import time
from zoneinfo import ZoneInfo

import paho.mqtt.client as mqtt

from prim_client import load_transportations, get_next_departure, time_remaining_until_next_departure

# The active-hours window below is meant in Paris local time regardless of the
# host/container's own timezone configuration (that's what broke last time:
# the Alpine-based image has no system tzdata, so the container silently ran
# on UTC). The `tzdata` package (see requirements.txt) provides the IANA
# database so this resolves correctly even without OS-level tzdata.
LOCAL_TIMEZONE = ZoneInfo("Europe/Paris")

try:
    logging.config.fileConfig('logging.conf')
except FileNotFoundError:
    logging.basicConfig(level=logging.INFO)
    logging.warning("logging.conf not found next to this script, falling back to basicConfig")

logger = logging.getLogger('nxt_dep_ratp')


def load_config():
    """Home Assistant add-ons write the options the user filled in the UI to
    /data/options.json inside the container. Fall back to plain environment
    variables so the script can still be run/tested outside of an add-on."""
    options = {}
    options_path = "/data/options.json"
    if os.path.exists(options_path):
        with open(options_path) as f:
            options = json.load(f)

    def get(key, env_key, default=None, required=False):
        value = options.get(key, os.environ.get(env_key, default))
        if required and not value:
            raise RuntimeError(f"Missing required config value '{key}' (set it in the add-on Configuration tab)")
        return value

    def get_lines():
        """The 'lines' option is a list of objects, not a scalar, so it can't
        go through get() above: options.json already parses it as a list,
        while the env var fallback (for running outside the add-on) is a
        JSON-encoded string that needs decoding."""
        if options.get("lines"):
            return options["lines"]
        env_value = os.environ.get("LINES")
        if env_value:
            try:
                return json.loads(env_value)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"LINES environment variable is not valid JSON: {exc}") from exc
        return None

    return {
        "PRIM_API_TOKEN": get("prim_api_token", "PRIM_API_TOKEN", required=True),
        "MQTT_HOST": get("mqtt_host", "MQTT_HOST", default="core-mosquitto"),
        "MQTT_PORT": int(get("mqtt_port", "MQTT_PORT", default=1883)),
        "MQTT_USER": get("mqtt_user", "MQTT_USER", default=None),
        "MQTT_PASSWORD": get("mqtt_password", "MQTT_PASSWORD", default=None),
        "AWTRIX_PREFIX": get("awtrix_prefix", "AWTRIX_PREFIX", required=True),
        "POLL_INTERVAL_SECONDS": int(get("poll_interval_seconds", "POLL_INTERVAL_SECONDS", default=30)),
        "LINES": get_lines(),
    }


CONFIG = load_config()
PRIM_API_TOKEN = CONFIG["PRIM_API_TOKEN"]
TRANSPORTATIONS = load_transportations(CONFIG["LINES"])


def make_awtrix_appname(line_name, stop_index):
    # AWTRIX app names must not contain spaces; keep them short and stable
    # so each stop always refreshes the same rotating app instead of piling
    # up new ones.
    safe_line = "".join(ch for ch in line_name if ch.isalnum()) or "line"
    return f"bus{safe_line}_{stop_index}"


WHITE = "#ffffff"
SOFT_GREEN = "#2ecc71"
SOFT_RED = "#e74c3c"
NOTICE_ORANGE = "#e67e22"


def wait_time_color(wait_time):
    if not isinstance(wait_time, int):
        return WHITE
    return SOFT_GREEN if wait_time >= 5 else SOFT_RED


def publish_departure(mqtt_client, prefix, appname, text):
    payload = {
        "text": text,
        "durationMs": 8000,
        # If we stop publishing (script crash, network outage) for longer
        # than this, AWTRIX removes the app instead of showing a stale time.
        "lifetimeMs": 90000,
        "lifetimeExpiry": "remove",
    }
    topic = f"{prefix}/cmd/apps/pushed/{appname}"
    mqtt_client.publish(topic, json.dumps(payload), retain=False)
    logger.debug(f"published to {topic}: {payload}")


def clear_app(mqtt_client, prefix, appname):
    # Publishing an empty payload removes a pushed app immediately.
    mqtt_client.publish(f"{prefix}/cmd/apps/pushed/{appname}", "", retain=False)


def build_mqtt_client(config):
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, protocol=mqtt.MQTTv311)
    if config["MQTT_USER"]:
        client.username_pw_set(config["MQTT_USER"], config["MQTT_PASSWORD"])
    client.reconnect_delay_set(min_delay=1, max_delay=30)

    while True:
        try:
            client.connect(config["MQTT_HOST"], config["MQTT_PORT"], keepalive=60)
            break
        except (OSError, ConnectionRefusedError) as exc:
            logger.error(f"could not connect to MQTT broker {config['MQTT_HOST']}:{config['MQTT_PORT']} ({exc}), retrying in 10s")
            time.sleep(10)

    client.loop_start()
    return client


def run_once(mqtt_client):
    for transportation in TRANSPORTATIONS:
        line_name = transportation["line_name"]
        color = f"#{transportation.get('color', 'ffffff')}"
        for stop_index, stop in enumerate(transportation["stops"]):
            stop_name = stop["stop_name"]
            destination_name = stop["destination_name"]
            destination_name_short = stop.get("destination_name_short", destination_name)
            appname = make_awtrix_appname(line_name, stop_index)

            departure_json = get_next_departure(PRIM_API_TOKEN, transportation["line_ref"], stop["stop_ref"])
            if departure_json is None:
                logger.warning(f"Could not get departures for line {line_name} in stop {stop_name} in direction of {destination_name}")
                continue

            if departure_json["Notice"] != "":
                logger.info(f"No departures for line {line_name} in stop {stop_name} in direction of {destination_name}: {departure_json['Notice']}")
                text = [
                    {"text": f"{line_name}", "color": color},
                    {"text": f": {destination_name_short}: {departure_json['Notice']}", "color": NOTICE_ORANGE},
                ]
                # clear_app(mqtt_client, CONFIG["AWTRIX_PREFIX"], appname)
                publish_departure(mqtt_client, CONFIG["AWTRIX_PREFIX"], appname, text)
                continue

            next_departures = departure_json["next_departures"]
            next_departure = next_departures[0]
            seconds_remaining = time_remaining_until_next_departure(next_departure["ExpectedDepartureTime"]).total_seconds()
            wait_time = max(0, math.floor(seconds_remaining / 60))
            if len(next_departures) > 1:
                next_departure_2 = next_departures[1]
                seconds_remaining_2 = time_remaining_until_next_departure(next_departure_2["ExpectedDepartureTime"]).total_seconds()
                wait_time_2 = max(0, math.floor(seconds_remaining_2 / 60))
            else:
                wait_time_2 = "-"
            logger.info(f"{line_name} to {destination_name} from {stop_name}: {wait_time} min")
            text = [
                {"text": f"{line_name}", "color": color},
                {"text": f": {destination_name_short}: ", "color": WHITE},
                {"text": str(wait_time), "color": wait_time_color(wait_time)},
                {"text": " , ", "color": WHITE},
                {"text": str(wait_time_2), "color": wait_time_color(wait_time_2)},
            ]
            publish_departure(mqtt_client, CONFIG["AWTRIX_PREFIX"], appname, text)


ACTIVE_WINDOW_START_MINUTES = 7 * 60
ACTIVE_WINDOW_END_MINUTES = 8 * 60 + 30


def seconds_until_active_window(now):
    """0 if `now` falls in the Mon-Fri 07:00-08:30 commute window this add-on
    only polls during; otherwise seconds to sleep until that window next
    opens. Covers every case (early morning, past today's window, weekends)
    so the caller always has a positive duration to sleep for instead of
    spinning the loop with no delay when a case is missed."""
    minutes_since_midnight = now.hour * 60 + now.minute
    if now.isoweekday() <= 5 and ACTIVE_WINDOW_START_MINUTES <= minutes_since_midnight < ACTIVE_WINDOW_END_MINUTES:
        return 0

    target = now.replace(hour=7, minute=0, second=0, microsecond=0)
    if minutes_since_midnight >= ACTIVE_WINDOW_END_MINUTES:
        target += datetime.timedelta(days=1)
    while target.isoweekday() > 5:
        target += datetime.timedelta(days=1)

    return max(1, (target - now).total_seconds())


if __name__ == '__main__':
    logger.info(f"Starting nxt_dep_awtrix, publishing to prefix '{CONFIG['AWTRIX_PREFIX']}' every {CONFIG['POLL_INTERVAL_SECONDS']}s")
    mqtt_client = build_mqtt_client(CONFIG)
    try:
        while True:
            now = datetime.datetime.now(LOCAL_TIMEZONE)
            wait_seconds = seconds_until_active_window(now)
            if wait_seconds == 0:
                run_once(mqtt_client)
                time.sleep(CONFIG["POLL_INTERVAL_SECONDS"])
            else:
                logger.info(f"{now} is outside the Mon-Fri 07:00-08:30 window, sleeping {wait_seconds:.0f}s")
                time.sleep(wait_seconds)
    finally:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
