import json
import html
import urllib3
from datetime import datetime, timezone, timedelta

http = urllib3.PoolManager()

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre"
]

def date_iso_to_fr(date_iso):
    dt = datetime.fromisoformat(date_iso)
    jour = JOURS[dt.weekday()]
    mois = MOIS[dt.month - 1]
    return f"{jour} {dt.day} {mois} {dt.strftime('%Hh')}"

utc_now = datetime.now(timezone.utc)
montreal_winter_tz = timezone(timedelta(hours=-5))
montreal_time = utc_now.astimezone(montreal_winter_tz)

TEAMUP_URL = f"https://teamup.com/___SECRET___/events?startDate=2026-02-01&endDate=2026-03-01&tz=America%2FToronto"

SUBCALENDAR_ID = 9616459
TITLE_PREFIX = "Privé : "

def lambda_handler(event, context):
    try:
        # --- Fetch Teamup ---
        resp = http.request("GET", TEAMUP_URL, timeout=urllib3.Timeout(connect=2.0, read=5.0))
        if resp.status != 200:
            return {
                "statusCode": 500,
                "headers": {"Content-Type": "text/html"},
                "body": f"<h1>Erreur Teamup HTTP {resp.status}</h1>"
            }

        data = json.loads(resp.data.decode("utf-8"))
        events = data.get("events", [])

        # --- Filtrage / parsing ---
        services = []
        for event in events:
            if (
                SUBCALENDAR_ID in event.get("subcalendar_ids", []) and
                event.get("title", "").startswith(TITLE_PREFIX)
            ):
                services.append({
                    "date": date_iso_to_fr(event.get("start_dt")),
                    "raw_end_date": datetime.fromisoformat(event.get("end_dt")),
                    "name": event.get("title", "")[8:],
                    "requested_members": int(event.get("custom", {}).get("nombre_de_membres_ne_cessaires", 0)),
                    "members": len(event.get("signups", [])),
                    "members_name": [s.get("name", "") for s in event.get("signups", [])],
                    "link": f"https://teamup.com/___SECRET___/events/{event.get("id", "")}"
                })

        def table_for(services_list):
            rows_html = ""
            for s in services_list:
                if s["members"] == 0 or (s["members"] == 1 and s["requested_members"] > 1):
                    color = "#ffcccc"
                    style = f"background:{color}"
                    status = "Aucun membre ou membre seul"
                elif s["members"] < s["requested_members"]:
                    color = "#fff2cc"
                    style = f"background:{color}"
                    status = "Manque de membres"
                else:
                    color = "#ccffcc"
                    style = f"background:{color}"
                    status = "Complet"
                
                if s["raw_end_date"] < utc_now:
                    style = "background:grey"
                    status += " - Terminé"

                members_name_text = "\n".join(s["members_name"])
                members_name_for_title = html.escape(members_name_text)
                members_name_for_js = json.dumps(members_name_for_title)

                rows_html += f"""
                    <tr title="{members_name_for_title}" style="{style}">
                        <td>{s['date']} <button onclick="window.open('{s['link']}', '_blank');">Teamup</button></td>
                        <td>{s['name']}</td>
                        <td>{s['members']}/{s['requested_members']} <button onclick='alert({members_name_for_js});'>Liste</button></td>
                        <td>{s['requested_members']-s['members']}</td>
                        <td><strong>{status}</strong></td>
                    </tr>
                """

            return f"""
                <table>
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Nom</th>
                            <th>Couverture</th>
                            <th>Membres restants nécessaires</th>
                            <th>État</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>
            """

        # --- HTML final avec onglets ---
        returned_html = f"""
        <!DOCTYPE html>
        <html lang="fr">
        <head>
            <meta charset="UTF-8" />
            <title>Services Privés Centre Bell</title>
            <style>
                body {{ font-family: Arial, sans-serif; padding: 20px; }}
                table {{ text-align: center; width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th, td {{ padding: 10px; border-bottom: 1px solid #ddd; }}
                th {{ background: #f0f0f0; }}

                .tabs {{
                    display: flex;
                    gap: 15px;
                    margin-bottom: 20px;
                }}
                .tab {{
                    padding: 10px 20px;
                    border: 1px solid #888;
                    border-radius: 5px;
                    cursor: pointer;
                    background: #eee;
                }}
                .tab.active {{
                    background: #d0e0ff;
                    font-weight: bold;
                    border-color: #3366ff;
                }}
                .tab-content {{
                    display: none;
                }}
                .tab-content.active {{
                    display: block;
                }}
            </style>
        </head>

        <body>
            <h1>Services Privés Centre Bell</h1>
            <h4>État à {montreal_time.strftime("%Y-%m-%dT%H:%M:%S%z")} (Temps réel)</h4>

            <div id="content" class="tab-content active">
                {table_for(services)}
            </div>
        </body>
        </html>
        """

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "text/html"},
            "body": returned_html
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "text/html"},
            "body": f"<h1>Erreur interne</h1><pre>{str(e)}</pre>"
        }
