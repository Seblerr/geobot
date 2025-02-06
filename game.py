import os
import requests
import asyncio
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


async def fetch_game_scores(game_id):
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
        for item in res.json().get("items", []):
            try:
                nick = item["game"]["player"]["nick"]
                round_scores = [
                    round["roundScoreInPoints"]
                    for round in item["game"]["player"]["guesses"]
                ]

                scores = [(nick, i + 1, score) for i, score in enumerate(round_scores)]

                db.add_scores(game_id, scores)
            except KeyError as e:
                print(f"KeyError: Missing {e.args[0]} in JSON response")
    finally:
        session.close()


async def fetch_missing_games_scores():
    db = Database()
    game_ids = db.get_missing_game_ids()
    for game_id in game_ids:
        await fetch_game_scores(game_id)
        if len(game_ids) > 1:
            await asyncio.sleep(10)


async def fetch_todays_scores():
    db = Database()
    game_id = db.get_latest_game()
    await fetch_game_scores(game_id)


async def update_scores():
    await fetch_missing_games_scores()
    await fetch_todays_scores()
