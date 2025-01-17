import os
import requests
import time
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


def fetch_game_scores(game_id):
    load_dotenv()
    session = requests.Session()

    try:
        token = os.getenv("GEOGUESSR_NCFA")
        session.cookies.set("_ncfa", token, domain="www.geoguessr.com")

        db = Database()
        res = session.get(
            f"https://www.geoguessr.com/api/v3/results/highscores/{game_id}"
        )
        assert res.status_code == 200
        items = res.json()["items"]
        scores = [(item["playerName"], item["totalScore"]) for item in items]

        db.add_scores(scores)
    finally:
        session.close()


def fetch_missing_games_scores():
    db = Database()
    game_ids = db.get_missing_game_ids()
    for game_id in game_ids:
        fetch_game_scores(game_id)
        time.sleep(30)
