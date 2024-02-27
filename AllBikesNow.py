import requests
import argparse
import json
import re
from lxml import html

def get_trips_details(name, login, password, nb_days):
    session = requests.Session()
    resp = session.get("https://abo-marseille.cyclocity.fr/service/login")
    data={"Name": name, "Login": login, "Password": password, "LoginButton": "Connexion", "RedirectURI": "service/myaccount"}
    resp = session.post("https://abo-marseille.cyclocity.fr/service/login", data=data)
    if "is_logged_in" not in resp.cookies or resp.cookies["is_logged_in"]!="true":
        return None
    
    resp = session.post("https://abo-marseille.cyclocity.fr/service/myaccount/(tab)/use", data={"seedetails": nb_days})
    tree = html.fromstring(resp.content)
    table = tree.xpath("//table[@class='detail_consommation']")[0]
    table_rows = table.getchildren()[1:]
    trips = []
    for row in table_rows:
        cols = row.getchildren()
        trips.append({"date": cols[0].text, "trip_number": cols[1].text.strip(), "label": cols[2].text, "duration": cols[3].text, "price": cols[4].text})
    
    session.get("https://abo-marseille.cyclocity.fr/service/logout")
    session.close()
    
    return trips

def get_token():
    headers = {"X-Requested-With": "com.jcdecaux.allbikesnow", "Content-Type": "application/json"}
    resp = requests.get("https://gw.cyclocity.fr/3311a6cea2e49b10/token/key/b9e3c203de99c588c37bd8cf8d36750a", headers=headers)
    if resp.status_code != 200:
        return None
    return resp.json()["token"]

def get_client_info(name, login, password):
    token = get_token()
    if token is None:
        return None
    
    headers = {"X-Requested-With": "com.jcdecaux.allbikesnow", "Content-Type": "application/json"}
    resp = requests.get("https://gw.cyclocity.fr/3311a6cea2e49b10/client/marseille/info/{}?token={}&cltNm={}&cltPin={}&lng=en".format(login, token, name, password), headers=headers)
    if resp.status_code != 200:
        return None
    
    return resp.json()

def get_last_trips(login, nb_trips):
    token = get_token()
    if token is None:
        return None
    
    headers = {"X-Requested-With": "com.jcdecaux.allbikesnow", "Content-Type": "application/json"}
    resp = requests.get("https://gw.cyclocity.fr/3311a6cea2e49b10/client/marseille/lastTrips/{}?token={}&tripsNumber={}".format(login, token, nb_trips), headers=headers)
    if resp.status_code != 200:
        return None
    
    return resp.json()

def get_stations(lat, lng, max_stations):
    token = get_token()
    if token is None:
        return None
    
    headers = {"X-Requested-With": "com.jcdecaux.allbikesnow", "Content-Type": "application/json"}
    resp = requests.get("https://gw.cyclocity.fr/3311a6cea2e49b10/availability/marseille/stations/proximity/?token={}&lat={}&lng={}&min=0&maxRes={}".format(token, lat, lng, max_stations), headers=headers)
    if resp.status_code != 200:
        return None
    
    return resp.json()

def get_station_state(station_number):
    token = get_token()
    if token is None:
        return None
    
    headers = {"X-Requested-With": "com.jcdecaux.allbikesnow", "Content-Type": "application/json"}
    resp = requests.get("https://gw.cyclocity.fr/3311a6cea2e49b10/availability/marseille/stations/state/{}?token={}".format(station_number, token), headers=headers)
    if resp.status_code != 200:
        return None
    
    return resp.json()

def get_station_state_from_tdgfr(station_number):
    resp = requests.get("https://transport.data.gouv.fr/gbfs/marseille/station_information.json")
    if resp.status_code != 200:
        return None
    
    stations = resp.json()
    for station in stations["data"]["stations"]:
        if int(station["station_id"]) == station_number:
            return station
    
    return None

def pretty_print_client_infos(client_infos):
    print("First name:", client_infos["firstname"])
    print("Last name:", client_infos["lastname"])
    print("Email:", client_infos["email"])
    print("End of validity:", client_infos["endValidity"])
    #print("Auto renew:", client_infos["resub"]) # not sure of this
    print("")
    
    print("Account:", client_infos["account"], client_infos["currency"])
    print("Bonus:", client_infos["bonus"], "min")
    print("In trip:", client_infos["inTrip"])
    print("")
    
    print("Last trip date:", client_infos["lastTripDate"])
    print("Last trip duration:", client_infos["lastTripDuration"], "min")
    print("Last trip cost:", client_infos["lastTripAmount"], client_infos["currency"])

def merge_trips(trips_details, last_trips):
    merged_trips = []
    station_code_regex = re.compile("[0-9]{4}")
    for lt, td in zip(last_trips, trips_details):
        mt = {"date": lt["date"], "duration": lt["duration"], "cost": lt["amount"], "bonus": lt["bonus"], "label": td["label"], "trip_number": td["trip_number"]}
        if mt["label"] != " -> ":
            start_station = mt["label"].split(" -> ")[0]
            end_station = mt["label"].split(" -> ")[1]
            mt["start_station_label"] = start_station
            mt["end_station_label"] = end_station
            mt["start_station_code"] = station_code_regex.match(start_station).group(0)
            mt["end_station_code"] = station_code_regex.match(end_station).group(0)
        merged_trips.append(mt)
    
    return merged_trips

def print_merged_trips(merged_trips, only_cost=False, only_bonus=False):
    print("Displaying {} trips\n".format(len(merged_trips)))
    for trip in merged_trips:
        if only_cost and trip["cost"] == 0 and trip["bonus"] >= 0:
            continue
        if only_bonus and trip["bonus"] <= 0:
            continue
        print("Date:", trip["date"])
        print("Duration:", trip["duration"], "min")
        print("Cost:", trip["cost"], "EUR")
        print("Bonus:", trip["bonus"], "min")
        if "start_station_label" in trip:
            print("From {} to {}".format(trip["start_station_label"], trip["end_station_label"]))
        print("")

def print_stations(stations, min_bikes=0, min_docks=0):
    for station in stations:
        if station["station"]["ststate"]["freebk"] < min_bikes or station["station"]["ststate"]["freebs"] < min_docks:
            continue
        if  min_bikes == 0 and min_docks == 0 and station["station"]["ststate"]["state"] != "open":
            continue
        print("Station ID:", station["station"]["nb"])
        print("Station label:", station["station"]["lb"])
        print("Distance:", station["dst"], "m")
        print("Coordinates:", station["station"]["lat"], station["station"]["lng"])
        print("State:", station["station"]["ststate"]["state"], station["station"]["ststate"]["connstate"])
        print("Last checked:", station["station"]["ststate"]["lastCheck"])
        print("Available bikes:", station["station"]["ststate"]["freebk"])
        print("Available docks:", station["station"]["ststate"]["freebs"])
        print("Total docks:", station["station"]["ststate"]["freebk"] + station["station"]["ststate"]["freebs"])
        print("Bonus:", station["station"]["bonus"])
        print("")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AllBikesNow command line tool")
    subparsers = parser.add_subparsers(dest='action')
    subparsers.required = True
    client_info_parser = subparsers.add_parser("clientinfo", help="Get client information")
    trips_parser = subparsers.add_parser("trips", help="Get trips information")
    station_state_parser = subparsers.add_parser("station-state", help="Get single station information")
    find_stations_parser = subparsers.add_parser("find-stations", help="Find stations around coordinates")
    find_bike_parser = subparsers.add_parser("find-bike", help="Find station with available bikes around coordinates")
    find_dock_parser = subparsers.add_parser("find-dock", help="Find station with available docks around coordinates")

    client_info_parser.add_argument("--name", action="store", type=str, required=True)
    client_info_parser.add_argument("--login", action="store", type=int, required=True)
    client_info_parser.add_argument("--pin", action="store", type=int, required=True)

    trips_parser.add_argument("--name", action="store", type=str, required=True)
    trips_parser.add_argument("--login", action="store", type=int, required=True)
    trips_parser.add_argument("--pin", action="store", type=int, required=True)
    trips_parser.add_argument("--nb-trips", action="store", type=int, default=5, help="Max number of trips to fetch (default: 5)")
    trips_parser.add_argument("--nb-days", action="store", type=int, default=7, help="Max number of days in past to fetch (default: 7)")
    trips_parser.add_argument("--only-costing", action="store_true", default=False, help="Display only trips that cost you money or bonus")
    trips_parser.add_argument("--only-bonus", action="store_true", default=False, help="Display only trips that gave you bonus")
    
    station_state_parser.add_argument("--id", action="store", type=int, required=True)
    
    find_stations_parser.add_argument("--lat", action="store", type=float, required=True)
    find_stations_parser.add_argument("--lng", action="store", type=float, required=True)
    find_stations_parser.add_argument("--max", action="store", type=int, default=5, help="Max number of stations to fetch (default: 5)")
    
    find_bike_parser.add_argument("--lat", action="store", type=float, required=True)
    find_bike_parser.add_argument("--lng", action="store", type=float, required=True)
    find_bike_parser.add_argument("--max", action="store", type=int, default=5, help="Max number of stations to fetch (default: 5)")
    find_bike_parser.add_argument("--min-bikes", action="store", type=int, default=1, help="Display only stations that has 'MIN_BIKES' available bikes (default: 1)")
    
    find_dock_parser.add_argument("--lat", action="store", type=float, required=True)
    find_dock_parser.add_argument("--lng", action="store", type=float, required=True)
    find_dock_parser.add_argument("--max", action="store", type=int, default=5, help="Max number of stations to fetch (default: 5)")
    find_dock_parser.add_argument("--min-docks", action="store", type=int, default=1, help="Display only stations that has 'MIN_DOCKS' available docks (default: 1)")

    args = parser.parse_args()
    if args.action == "clientinfo":
        client_infos = get_client_info(args.name, args.login, args.pin)
        if client_infos is None:
            print("Error fetching client info")
            exit(1)
        pretty_print_client_infos(client_infos)
    elif args.action == "trips":
        trips_details = get_trips_details(args.name, args.login, args.pin, args.nb_days)
        last_trips = get_last_trips(args.login, args.nb_trips)
        if trips_details is None or last_trips is None:
            print("Error fetching trips info")
            exit(1)
        print_merged_trips(merge_trips(trips_details, last_trips), args.only_costing, args.only_bonus)
    elif args.action == "station-state":
        station_state = get_station_state(args.id)
        station_state2 = get_station_state_from_tdgfr(args.id)
        if station_state is None or station_state2 is None:
            print("Error fetching station info")
            exit(1)
        station_state = station_state["ststates"][0]
        print("Coordinates:", station_state2["lat"], station_state2["lon"])
        print("State:", station_state["state"], station_state["connstate"])
        print("Last checked:", station_state["lastCheck"])
        print("Available bikes:", station_state["freebk"])
        print("Available docks:", station_state["freebs"])
        print("Total docks:", station_state["freebk"] + station_state["freebs"])
    elif args.action == "find-stations":
        stations = get_stations(args.lat, args.lng, args.max)
        if stations is None:
            print("Error fetching stations")
            exit(1)
        print_stations(stations)
    elif args.action == "find-bike":
        stations = get_stations(args.lat, args.lng, args.max)
        if stations is None:
            print("Error fetching stations")
            exit(1)
        print_stations(stations, min_bikes=args.min_bikes)
    elif args.action == "find-dock":
        stations = get_stations(args.lat, args.lng, args.max)
        if stations is None:
            print("Error fetching stations")
            exit(1)
        print_stations(stations, min_docks=args.min_docks)

