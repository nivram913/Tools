import re
import json
import csv
import os
import unicodedata
import argparse
import requests
from datetime import datetime, timedelta
from typing import TypedDict
from enum import Enum, auto

class Etype(Enum):
    DIVISIONNAIRE = auto()
    OTHER_EVENT = auto()
    PERFECTIONNEMENT = auto()
    OTHER_TRAINING = auto()
    CENTRE_BELL = auto()
    CENTRE_BELL_PRIVE = auto()
    OTHER = auto()

class Event(TypedDict):
    id: str
    name: str
    start_dt: datetime
    end_dt: datetime
    duration: int
    etype: Etype
    required_members: int
    signups: int

class Member(TypedDict):
    identity: str
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

def extract_teamup(start_dt: datetime, end_dt: datetime):
    TEAMUP_URL = f"https://teamup.com/{TEAMUP_SECRET}/events?startDate={start_dt.strftime('%Y-%m-%d')}&endDate={end_dt.strftime('%Y-%m-%d')}&tz=America%2FToronto"

    resp = requests.get(TEAMUP_URL)
    events = resp.json()["events"]

    for event in events:
        if (datetime.fromisoformat(event["start_dt"]).replace(tzinfo=None) - start_dt).total_seconds() >= 0:
            try:
                event_obj: Event = {
                    "id": event["id"],
                    "name": event["title"],
                    "start_dt": datetime.fromisoformat(event["start_dt"]).replace(tzinfo=None),
                    "end_dt": datetime.fromisoformat(event["end_dt"]).replace(tzinfo=None),
                    "duration": int((datetime.fromisoformat(event["end_dt"]) - datetime.fromisoformat(event["start_dt"])).total_seconds() / 3600),
                    "etype": Etype.OTHER,
                    "required_members": event["custom"].get("nombre_de_membres_ne_cessaires", 0),
                    "signups": event["signup_count"]
                }

                if event["subcalendar_id"] == 9616459 and event["title"].startswith("Privé"):
                    event_obj["etype"] = Etype.CENTRE_BELL_PRIVE
                elif event["subcalendar_id"] == 9616459:
                    event_obj["etype"] = Etype.CENTRE_BELL
                elif event["subcalendar_id"] == 11159835 and event["title"].startswith("DIV"):
                    event_obj["etype"] = Etype.DIVISIONNAIRE
                elif event["subcalendar_id"] == 11159835 and event["title"].startswith("Perf."):
                    event_obj["etype"] = Etype.PERFECTIONNEMENT
                elif "service" in event["custom"].get("cate_gorie_category", []):
                    event_obj["etype"] = Etype.OTHER_EVENT
                elif "formation_training" in event["custom"].get("cate_gorie_category", []):
                    event_obj["etype"] = Etype.OTHER_TRAINING
                else:
                    event_obj["etype"] = Etype.OTHER
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
                    
                    match_inscription = re.fullmatch(r"(?P<identity>([a-z-]+ ){2,})\(.+\) [0-9]{3,4}.*", ''.join(c for c in unicodedata.normalize('NFD', inscription) if unicodedata.category(c) != 'Mn').lower())
                    if not match_inscription:
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
                        "identity": match_inscription.group('identity').strip(),
                        "inscriptions": [inscription],
                        "email_hashes": [email_hash],
                        "division": division,
                        "events": [event_obj]
                    })
            except KeyError:
                pass

def valid_date(s):
    try:
        return datetime.strptime(s, "%d-%m-%Y")
    except ValueError:
        msg = f"Format de date invalide : '{s}'. Le format attendu est JJ-MM-AAAA."
        raise argparse.ArgumentTypeError(msg)

parser = argparse.ArgumentParser(description="Teamup hours extraction tool 452")
parser.add_argument("--secret", action="store", required=True, help="Secret Teamup")
parser.add_argument("--start", action="store", type=valid_date, required=True, help="Date de début au format JJ-MM-AAAA")
parser.add_argument("--end", action="store", type=valid_date, required=True, help="Date de fin au format JJ-MM-AAAA")
parser.add_argument("--write-ld", action="store_true", default=False, help="Write learned data to json file")
args = parser.parse_args()

TEAMUP_SECRET = args.secret

if os.path.exists("learned_data.json"):
    with open("learned_data.json") as f:
        learned_data = json.load(f)
        members_list: list[Member] = [{"identity": m["identity"],
                                       "inscriptions": m["inscriptions"],
                                       "division": m["division"],
                                       "email_hashes": m["email_hashes"],
                                       "events": []} for m in learned_data]
        print("Données d'apprentissage chargées")
else:
    print("Pas de données d'apprentissage trouvées")
    members_list: list[Member] = []

start_date: datetime = args.start
end_date: datetime = args.end
delta: timedelta = args.end - args.start
events_list: list[Event] = []

if delta.days < 0:
    print("La date de début doit être antérieure à la date de fin")
    exit(1)

print(f"Données extraite le {datetime.now()}")

current_date = start_date
while current_date < end_date:
    tmp_end_date = min(current_date + timedelta(days=30), end_date)
    
    print(f"Extraction du {current_date.date()} au {tmp_end_date.date()}...")
    extract_teamup(current_date, tmp_end_date)
    
    current_date = tmp_end_date + timedelta(days=1) if tmp_end_date < end_date else end_date


####################
# Ecriture des CSV #
####################

with open('events.csv', mode='w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['ID', 'Nom', 'Type', 'Date', 'Durée', 'Nombre de membres nécessaires', 'Nombre d\'inscrits'])

    for event in events_list:
        if event["etype"] == Etype.DIVISIONNAIRE:
            event_type = "DIVISIONNAIRE"
        elif event["etype"] == Etype.OTHER_EVENT:
            event_type = "AUTRE EVENEMENT"
        elif event["etype"] == Etype.PERFECTIONNEMENT:
            event_type = "PERFECTIONNEMENT"
        elif event["etype"] == Etype.OTHER_TRAINING:
            event_type = "AUTRE FORMATION"
        elif event["etype"] == Etype.CENTRE_BELL:
            event_type = "CENTRE BELL"
        elif event["etype"] == Etype.CENTRE_BELL_PRIVE:
            event_type = "CENTRE BELL PRIVÉ"
        else:
            event_type = "AUTRE"
        writer.writerow([event["id"], event["name"], event_type, event["start_dt"].strftime('%Y-%m-%dT%H:%M'), event["duration"], event["required_members"], event["signups"]])

with open('inscriptions.csv', mode='w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['Identité', 'ID événement', 'Nom', 'Date'])

    for member in members_list:
        for event in member["events"]:
            writer.writerow([member["identity"], event["id"], event["name"], event["start_dt"].strftime('%Y-%m-%dT%H:%M')])

with open('members_hours.csv', mode='w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['Identité', 'Heures totales', 'Heures divisionnaires', 'Heures autres événements', 'Heures perfectionnements', 'Heures autres formations', 'Heures Centre Bell', 'Heures privés', 'Autres heures'])

    for member in members_list:
        if member["division"] in ("452", "0452"):
            hours = 0
            hours_div = 0
            hours_event = 0
            hours_perf = 0
            hours_training = 0
            hours_cb = 0
            hours_prive = 0
            hours_other = 0
            for e in member["events"]:
                hours += e["duration"]
                if e["etype"] == Etype.DIVISIONNAIRE:
                    hours_div += e["duration"]
                elif e["etype"] == Etype.OTHER_EVENT:
                    hours_event += e["duration"]
                elif e["etype"] == Etype.PERFECTIONNEMENT:
                    hours_perf += e["duration"]
                elif e["etype"] == Etype.OTHER_TRAINING:
                    hours_training += e["duration"]
                elif e["etype"] == Etype.CENTRE_BELL:
                    hours_cb += e["duration"]
                elif e["etype"] == Etype.CENTRE_BELL_PRIVE:
                    hours_prive += e["duration"]
                else:
                    hours_other += e["duration"]
            writer.writerow([member["identity"], hours, hours_div, hours_event, hours_perf, hours_training, hours_cb, hours_prive, hours_other])

if args.write_ld:
    with open('learned_data.json', 'w') as f:
        data = [{"identity": m["identity"],
                "inscriptions": m["inscriptions"],
                "division": m["division"],
                "email_hashes": m["email_hashes"]} for m in members_list]
        json.dump(data, f)
        print("Données d'apprentissage sauvegardées")
