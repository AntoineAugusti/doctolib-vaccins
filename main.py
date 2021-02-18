import os
import json
import datetime

import requests


class Notification(object):
    FILENAME = "notifications.json"
    DELAY_HOURS = 3

    def __init__(self, id):
        self.id = str(id)
        self.data = json.loads(open(self.FILENAME).read())

    def should_warn(self):
        if self.id not in self.data:
            return True
        previous = datetime.datetime.fromisoformat(self.data[self.id])
        now = datetime.datetime.utcnow()
        return previous + datetime.timedelta(hours=self.DELAY_HOURS) < now

    def register_notification(self):
        now = datetime.datetime.utcnow().isoformat()
        self.data[self.id] = now

        with open(self.FILENAME, "w") as f:
            f.write(json.dumps(self.data))

    def post_notification(self, message):
        if not self.should_warn():
            return

        requests.post(
            "https://smsapi.free-mobile.fr/sendmsg",
            params={
                "user": os.environ["FREE_USER"],
                "pass": os.environ["FREE_PASS"],
                "msg": message,
            },
        ).raise_for_status()

        self.register_notification()


SLUGS = os.environ["SLUGS"].split(",")

for slug in SLUGS:
    data = requests.get(f"https://www.doctolib.fr/booking/{slug}.json").json()["data"]
    id = data["profile"]["id"]
    center = data["profile"]["name_with_title_and_determiner"]

    has_availability = [a for a in data["agendas"] if not a["booking_disabled"]]

    if not has_availability:
        print(f"No open agendas at {center}")
        continue

    try:
        visit_motive_id = [
            v["id"]
            for v in data["visit_motives"]
            if v["name"].startswith("1ère injection")
            and "astrazeneca" not in v["name"].lower()
        ][0]
    except IndexError:
        continue

    agendas_id = "-".join([str(a["id"]) for a in data["agendas"]])

    r = requests.get(
        "https://www.doctolib.fr/availabilities.json",
        params={
            "start_date": datetime.datetime.today().date().isoformat(),
            "visit_motive_ids": visit_motive_id,
            "agenda_ids": agendas_id,
        },
    )
    r.raise_for_status()
    total = r.json()["total"]

    print(f"Found {total} availabilities at {center}")

    if total >= 3:
        Notification(id).post_notification(f"RDV disponible à {center}")
