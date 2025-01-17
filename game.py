import os
import requests
from db import Database
from dotenv import load_dotenv


def create_game():
    load_dotenv()
    MAP = "5cfda2c9bc79e16dd866104d"

    session = requests.Session()

    try:
        token = os.getenv("GEOGUESSR_NCFA")
        session.cookies.set("_ncfa", token, domain="www.geoguessr.com")
        print

        res = session.post(
            "https://www.geoguessr.com/api/v3/challenges",
            json={
                "forbidMoving": True,
                "forbidRotating": False,
                "forbidZooming": False,
                "map": MAP,
                "rounds": 5,
                "timeLimit": 60,
            },
        )
        assert res.status_code == 200
        game_id = res.json()["token"]
        db = Database()
        db.add_game(game_id)
        return f"https://www.geoguessr.com/challenge/{game_id}"
    finally:
        session.close()


def fetch_scores(game_id=None):
    load_dotenv()
    session = requests.Session()

    try:
        token = os.getenv("GEOGUESSR_NCFA")
        session.cookies.set("_ncfa", token, domain="www.geoguessr.com")

        print(token)

        db = Database()
        if game_id is None:
            game_id = db.get_latest_game()
        url = f"https://www.geoguessr.com/api/v3/results/highscores/{game_id}"
        print(url)
        res = session.get(
            f"https://www.geoguessr.com/api/v3/results/highscores/{game_id}"
        )
        print(res)
        assert res.status_code == 200
        items = res.json()["items"]
        scores = [(item["playerName"], item["totalScore"]) for item in items]

        db.add_game(game_id)
        db.add_scores(scores)
    finally:
        session.close()
