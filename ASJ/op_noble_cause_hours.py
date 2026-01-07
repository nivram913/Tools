import requests
import re
import unicodedata
import difflib
from datetime import datetime
from typing import TypedDict

class Member(TypedDict):
    names: list[str]
    email_hashes: list[str]
    hours: float
    division: str

def normalize(id_str: str):
    text_ascii = ''.join(c for c in unicodedata.normalize('NFD', id_str) if unicodedata.category(c) != 'Mn')
    return text_ascii.lower()

def filter_keywords(array: list[str]):
    filtered = [s for s in array if s not in ('sg', 'pr', 'sgm', 'sg-m', 'prm', 'pr-m')]
    return filtered

def tokenize(id_str: str):
    return re.findall(r'[a-z-]{2,}', id_str)

def standardize(inscription: str):
    standardized = filter_keywords(tokenize(normalize(inscription)))
    return standardized.copy()

def find_similar(ref: str, into: list[str]):
    ratios = [difflib.SequenceMatcher(None, ref, s).ratio() for s in into]
    max_ratio = max(ratios)
    if max_ratio > 0.8:
        return ratios.index(max_ratio)
    else:
        return -1

def compare_std_inscriptions(std_insc1: list[str], std_insc2: list[str]):
    if len(std_insc1) < len(std_insc2):
        matching = [find_similar(r, std_insc2) for r in std_insc1]
    else:
        matching = [find_similar(r, std_insc1) for r in std_insc2]
    
    score = 0
    for i in range(len(matching[:4])):
        distance = abs(matching[i] - i) if matching[i] >= 0 else -1
        if distance >= 0 and distance <= 2:
            score += 2
        else:
            score += 1

    return score / (2 * min(len(matching), 4))

def compare_inscriptions(insc1: str, insc2: str):
    return compare_std_inscriptions(standardize(insc1), standardize(insc2)) > 0.8

def find_member_by_email_hash(email_hash: str):
    for m in members:
        if email_hash in m["email_hashes"]:
            return m
    return None

def find_member_by_inscription(inscription: str):
    for m in members:
        for insc in m["names"]:
            if compare_inscriptions(inscription, insc):
                return m
    return None

TEAMUP_URL = f"https://teamup.com/___SECRET___/events?startDate=2025-12-01&endDate=2026-01-15&tz=America%2FToronto"

resp = requests.get(TEAMUP_URL)
events = resp.json()["events"]
print(f"Données extraite le {datetime.now()}")

members: list[Member] = []

for event in events:
    if 14169839 in event["subcalendar_ids"] and event["title"].startswith("OPÉRATION NOBLE CAUSE"):
        for signup in event["signups"]:
            email_hash = signup["email_hash"]
            inscription = signup["name"]
            match_div = re.search(r'[0-9]{3,4}', signup["name"])
            if not match_div:
                match_div = re.search(r'prov', signup["name"], re.IGNORECASE)
            division = match_div.group() if match_div else 'Inconnue'

            member = find_member_by_email_hash(email_hash)
            if member:
                member["hours"] += (datetime.fromisoformat(event["end_dt"]) - datetime.fromisoformat(event["start_dt"])).total_seconds() / 3600
                if not inscription in member["names"]:
                    member["names"].append(inscription)
                if member["division"] == "Inconnue":
                    member["division"] = division
                continue
            
            member = find_member_by_inscription(inscription)
            if member:
                member["hours"] += (datetime.fromisoformat(event["end_dt"]) - datetime.fromisoformat(event["start_dt"])).total_seconds() / 3600
                member["email_hashes"].append(email_hash)
                if not inscription in member["names"]:
                    member["names"].append(inscription)
                if member["division"] == "Inconnue":
                    member["division"] = division
                continue

            members.append({
                "hours": (datetime.fromisoformat(event["end_dt"]) - datetime.fromisoformat(event["start_dt"])).total_seconds() / 3600,
                "names": [inscription],
                "email_hashes": [email_hash],
                "division": division
            })

print("Nom\tDivision\tHeures")
for member in members:
    shortest_name = min(zip([len(n) for n in member["names"]], member["names"]), key=lambda x: x[0])[1]
    print(shortest_name, member["division"], f"{member['hours']}".replace('.', ','), sep='\t')

    #details
    if True:
        print('', member["names"], sep='\t')
        print('', member["email_hashes"], sep='\t')
        print('')
