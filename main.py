import requests
import json
import datetime
import math
import logging
import logging.config
import os

logging.config.fileConfig('logging.conf')
logger = logging.getLogger('nxt_dep_ratp')

logger.debug(os.environ)
PRIM_API_TOKEN=os.environ.get("PRIM_API_TOKEN")
logger.debug(f"API Token {PRIM_API_TOKEN}")

TRANSPORTATIONS = [ {"line_name": "25","line_ref":"STIF:Line::C02243:", "stops":[{"stop_ref":"STIF:StopPoint:Q:25376:","stop_name":"Jules Vanzuppe","destination_name":"Bibliotheque F.mitterrand"},{"stop_ref":"STIF:StopPoint:Q:23402:","stop_name":"Jules Vanzuppe","destination_name":"V.couturier Lenine"}],"ColourWeb_hexa": "ff1400"},
                    {"line_name": "325","line_ref":"STIF:Line::C01288:", "stops":[{"stop_ref":"STIF:StopPoint:Q:463689:","stop_name":"Jules Vanzuppe","destination_name":"Quai de la Gare"},{"stop_ref":"STIF:StopPoint:Q:463557:","stop_name":"Jules Vanzuppe","destination_name":"Chateau de Vincennes"}],"ColourWeb_hexa": "82c8e6"},
                    {"line_name": "125","line_ref":"STIF:Line::C01154:", "stops":[{"stop_ref":"STIF:StopPoint:Q:15122:","stop_name":"Ivry-sur-Seine RER","destination_name":"Ecole Veterinaire"},{"stop_ref":"STIF:StopPoint:Q:16918:","stop_name":"Ivry-sur-Seine RER","destination_name":"Porte d'Orleans"},{"stop_ref":"STIF:StopPoint:Q:39569:","stop_name":"Jean-Jacques Rousseau","destination_name":"Porte d'Orleans"}],"ColourWeb_hexa": "0055c8"}]

def time_remaining_untill_next_departure(next_departure):
    next_departure_date = datetime.datetime.fromisoformat(next_departure.replace('.000Z', '+00:00'))
    logger.debug(f"next departure {next_departure_date} and now {datetime.datetime.now(datetime.timezone.utc)}")
    date_diff = next_departure_date - datetime.datetime.now(datetime.timezone.utc)
    logger.debug(f"DEBUG diffrence between two times: {date_diff}")

    return date_diff


def get_next_departure(line, stop):
    response = requests.get("https://prim.iledefrance-mobilites.fr/marketplace/stop-monitoring", headers={"apikey": f"{PRIM_API_TOKEN}"}, params={"MonitoringRef": f"{stop}","LineRef": f"{line}"})
    if response.status_code == 200:
        # print(json.dumps(response.json(), indent=2))
        ret = {"next_departures":[],"Notice":""}
        departures = response.json()["Siri"]["ServiceDelivery"]["StopMonitoringDelivery"][0]["MonitoredStopVisit"]
        if len(departures) == 0:
            ret["Notice"] = response.json()["Siri"]["ServiceDelivery"]["StopMonitoringDelivery"][0]["ServiceException"][0]["Notice"][0]["value"]
        else:
            nxt_departures = []
            for departure in departures:
                nxt_departures.append({"ExpectedDepartureTime": departure["MonitoredVehicleJourney"]["MonitoredCall"]["ExpectedDepartureTime"],
                                       "DepartureStatus": departure["MonitoredVehicleJourney"]["MonitoredCall"]["DepartureStatus"]})
            ret["next_departures"] = nxt_departures
        return ret
    else:
        logger.error(f"get depature request returned {response.status_code} : {response.text}")
        return None

if __name__ == '__main__':
    for transportation in TRANSPORTATIONS:
        for stop in transportation["stops"]:
            departure_json = get_next_departure(transportation["line_ref"],stop["stop_ref"])
            logger.debug(json.dumps(departure_json, indent=2))
            if departure_json["Notice"] != "":
                logger.info(f"No departures for line {transportation["line_name"]} in stop {stop["stop_name"]} in direction of {stop["destination_name"]}: {departure_json["Notice"]}")
            else:
                logger.info(f"next departures for line {transportation["line_name"]} in stop {stop["stop_name"]} in direction of {stop["destination_name"]}")
                i = 0
                for departure in departure_json["next_departures"]:
                    departure_json["next_departures"][i]["Line"] = transportation["line_name"]
                    departure_json["next_departures"][i]["Stop"] = stop["stop_name"]
                    departure_json["next_departures"][i]["Destination"] = stop["destination_name"]
                    wait_time = math.floor(time_remaining_untill_next_departure(departure["ExpectedDepartureTime"]).seconds / 60)
                    departure_json["next_departures"][i]["WaitTime"] = wait_time 
                    i+=1
                    logger.info(f"Next departure {i} of {transportation["line_name"]} to {stop["destination_name"]} in {wait_time}")
                logger.debug(json.dumps(departure_json, indent=2))