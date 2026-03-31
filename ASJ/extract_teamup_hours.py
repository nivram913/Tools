import requests
import re
import unicodedata
from datetime import datetime, timedelta
from typing import TypedDict
from enum import Enum, auto
import json
import csv

class Etype(Enum):
    DIVISIONNAIRE = auto()
    PERFECTIONNEMENT = auto()
    CENTRE_BELL = auto()
    CENTRE_BELL_PRIVE = auto()
    AUTRE = auto()

class Event(TypedDict):
    name: str
    start_dt: datetime
    end_dt: datetime
    duration: int
    etype: Etype

class Member(TypedDict):
    #identity: str
    inscriptions: list[str]
    email_hashes: list[str]
    division: str
    events: list[Event]

def compare_inscriptions(insc1: str, insc2: str):
    insc1_tokens = re.findall(r'[a-z-]{2,}', ''.join(c for c in unicodedata.normalize('NFD', insc1) if unicodedata.category(c) != 'Mn').lower())
    insc2_tokens = re.findall(r'[a-z-]{2,}', ''.join(c for c in unicodedata.normalize('NFD', insc2) if unicodedata.category(c) != 'Mn').lower())
    if len(insc1_tokens) < 2 or len(insc2_tokens) < 2:
        return False
    if insc1_tokens[0] == insc2_tokens[0] and insc1_tokens[1] == insc2_tokens[1]:
        return True
    return False

def find_member_by_email_hash(email_hash: str):
    for m in members_list:
        if email_hash in m["email_hashes"]:
            return m
    return None

def find_member_by_inscription(inscription: str):
    for m in members_list:
        for insc in m["inscriptions"]:
            if compare_inscriptions(inscription, insc):
                return m
    return None


print(f"Données extraite le {datetime.now()}")

members_list: list[Member] = []
events_list: list[Event] = []

for month in range(1, 13):
    start_date = datetime(2025, month, 1)
    if month == 12:
        end_date = datetime(2026, 1, 1) - timedelta(days=1)
    else:
        end_date = datetime(2025, month + 1, 1) - timedelta(days=1)

    TEAMUP_SECRET = ""
    TEAMUP_URL = f"https://teamup.com/{TEAMUP_SECRET}/events?startDate={start_date.strftime('%Y-%m-%d')}&endDate={end_date.strftime('%Y-%m-%d')}&tz=America%2FToronto"

    print(f"Traitement de {month:02d}/2025...")
    resp = requests.get(TEAMUP_URL)
    # with open(f"{month:02d}", "r") as f:
    #     events = json.load(f)["events"]
    events = resp.json()["events"]

    for event in events:
        if datetime.fromisoformat(event["start_dt"]).month == month:
            try:
                event_obj: Event = {
                    "name": event["title"],
                    "start_dt": datetime.fromisoformat(event["start_dt"]),
                    "end_dt": datetime.fromisoformat(event["end_dt"]),
                    "duration": int((datetime.fromisoformat(event["end_dt"]) - datetime.fromisoformat(event["start_dt"])).total_seconds() / 3600),
                    "etype": Etype.AUTRE
                }
                if len(event["subcalendar_ids"]) > 1:
                    event_obj["etype"] = Etype.AUTRE
                elif event["subcalendar_id"] == 9616459 and event["title"].startswith("Privé"):
                    event_obj["etype"] = Etype.CENTRE_BELL_PRIVE
                elif event["subcalendar_id"] == 9616459:
                    event_obj["etype"] = Etype.CENTRE_BELL
                elif event["subcalendar_id"] == 11159835 and event["title"].startswith("DIV"):
                    event_obj["etype"] = Etype.DIVISIONNAIRE
                elif event["subcalendar_id"] == 11159835 and event["title"].startswith("Perf."):
                    event_obj["etype"] = Etype.PERFECTIONNEMENT
                else:
                    event_obj["etype"] = Etype.AUTRE
                events_list.append(event_obj)

                for signup in event["signups"]:
                    email_hash: str = signup["email_hash"]
                    inscription: str = signup["name"]
                    match_div = re.search(r'[0-9]{3,4}', inscription)
                    if not match_div:
                        match_div = re.search(r'prov', inscription, re.IGNORECASE)
                    division: str = match_div.group() if match_div else 'Inconnue'
                    if not division in ("452", "0452", "Inconnue"):
                        continue

                    member = find_member_by_email_hash(email_hash)
                    if member:
                        if not inscription in member["inscriptions"]:
                            member["inscriptions"].append(inscription)
                        if member["division"] == "Inconnue":
                            member["division"] = division
                        member["events"].append(event_obj)
                        continue
                    
                    member = find_member_by_inscription(inscription)
                    if member:
                        member["email_hashes"].append(email_hash)
                        if not inscription in member["inscriptions"]:
                            member["inscriptions"].append(inscription)
                        if member["division"] == "Inconnue":
                            member["division"] = division
                        member["events"].append(event_obj)
                        continue

                    members_list.append({
                        "inscriptions": [inscription],
                        "email_hashes": [email_hash],
                        "division": division,
                        "events": [event_obj]
                    })
            except KeyError:
                pass

nb_event = len(events_list)
nb_event_div = 0
nb_event_perf = 0
nb_event_cb = 0
nb_event_prive = 0
nb_event_other = 0
with open('events.csv', mode='w', newline='', encoding='utf-8-sig') as f:
    writer = csv.writer(f)
    writer.writerow(['Nom', 'Type', 'Date', 'Durée'])

    for event in events_list:
        if event["etype"] == Etype.DIVISIONNAIRE:
            event_type = "DIVISIONNAIRE"
            nb_event_div += 1
        elif event["etype"] == Etype.PERFECTIONNEMENT:
            event_type = "PERFECTIONNEMENT"
            nb_event_perf += 1
        elif event["etype"] == Etype.CENTRE_BELL:
            event_type = "CENTRE BELL"
            nb_event_cb += 1
        elif event["etype"] == Etype.CENTRE_BELL_PRIVE:
            event_type = "CENTRE BELL PRIVÉ"
            nb_event_prive += 1
        else:
            event_type = "AUTRE"
            nb_event_other += 1
        writer.writerow([event["name"], event_type, event["start_dt"], event["duration"]])

print(f"Nombre d'événements au total: {nb_event}")
print(f"Nombre d'événements divisionnaires: {nb_event_div}")
print(f"Nombre d'événements de perfectionnements: {nb_event_perf}")
print(f"Nombre d'événements Centre Bell: {nb_event_cb}")
print(f"Nombre d'événements privés: {nb_event_prive}")
print(f"Nombre d'événements autres: {nb_event_other}")

with open('members.csv', mode='w', newline='', encoding='utf-8-sig') as f:
    writer = csv.writer(f)
    writer.writerow(['Nom', 'Division', 'Heures totales', 'Heures divisionnaires', 'Heures perfectionnements', 'Heures Centre Bell', 'Heures privés', 'Autres heures'])

    for member in members_list:
        if member["division"] in ("452", "0452"):
            shortest_name = min(zip([len(n) for n in member["inscriptions"]], member["inscriptions"]), key=lambda x: x[0])[1]
            hours = 0
            hours_div = 0
            hours_perf = 0
            hours_cb = 0
            hours_prive = 0
            hours_other = 0
            for e in member["events"]:
                hours += e["duration"]
                if e["etype"] == Etype.DIVISIONNAIRE:
                    hours_div += e["duration"]
                elif e["etype"] == Etype.PERFECTIONNEMENT:
                    hours_perf += e["duration"]
                elif e["etype"] == Etype.CENTRE_BELL:
                    hours_cb += e["duration"]
                elif e["etype"] == Etype.CENTRE_BELL_PRIVE:
                    hours_prive += e["duration"]
                else:
                    hours_other += e["duration"]
            writer.writerow([shortest_name, member["division"], hours, hours_div, hours_perf, hours_cb, hours_prive, hours_other])

