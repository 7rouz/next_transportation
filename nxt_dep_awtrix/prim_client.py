import datetime
import logging

import requests

logger = logging.getLogger('nxt_dep_ratp')

TRANSPORTATIONS = [ {"line_name": "25","line_ref":"STIF:Line::C02243:", "stops":[{"stop_ref":"STIF:StopPoint:Q:25376:","stop_name":"Jules Vanzuppe","destination_name":"Bibliotheque F.mitterrand"},{"stop_ref":"STIF:StopPoint:Q:23402:","stop_name":"Jules Vanzuppe","destination_name":"V.couturier Lenine"}],"ColourWeb_hexa": "ff1400"},
                    {"line_name": "325","line_ref":"STIF:Line::C01288:", "stops":[{"stop_ref":"STIF:StopPoint:Q:463689:","stop_name":"Jules Vanzuppe","destination_name":"Quai de la Gare"},{"stop_ref":"STIF:StopPoint:Q:463557:","stop_name":"Jules Vanzuppe","destination_name":"Chateau de Vincennes"}],"ColourWeb_hexa": "82c8e6"},
                    {"line_name": "125","line_ref":"STIF:Line::C01154:", "stops":[{"stop_ref":"STIF:StopPoint:Q:15122:","stop_name":"Ivry-sur-Seine RER","destination_name":"Ecole Veterinaire"},{"stop_ref":"STIF:StopPoint:Q:16918:","stop_name":"Ivry-sur-Seine RER","destination_name":"Porte d'Orleans"},{"stop_ref":"STIF:StopPoint:Q:39569:","stop_name":"Jean-Jacques Rousseau","destination_name":"Porte d'Orleans"}],"ColourWeb_hexa": "0055c8"}]


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
