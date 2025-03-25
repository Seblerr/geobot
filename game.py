import os
import requests
import asyncio
from db import Database
from dotenv import load_dotenv
from typing import Optional

# Map IDs
I_SAW_THE_SIGN_2 = "5cfda2c9bc79e16dd866104d"
A_COMMUNITY_WORLD = "62a44b22040f04bd36e8a914"


def create_game() -> Optional[str]:
    load_dotenv()

    session = requests.Session()

    try:
        token = os.getenv("GEOGUESSR_NCFA")
        session.cookies.set("_ncfa", token, domain="www.geoguessr.com")

        res = session.post(
            "https://www.geoguessr.com/api/v3/challenges",
            json={
                "accessLevel": 1,
                "forbidMoving": True,
                "forbidRotating": False,
                "forbidZooming": False,
                "map": A_COMMUNITY_WORLD,
                "timeLimit": 60,
            },
        )
        if res.status_code != 200:
            return None

        game_id = res.json()["token"]
        db = Database()
        db.add_game(game_id)
        return f"https://www.geoguessr.com/challenge/{game_id}"
    finally:
        session.close()


async def fetch_game_scores(game_id) -> None:
    load_dotenv()
    session = requests.Session()

    try:
        token = os.getenv("GEOGUESSR_NCFA")
        session.cookies.set("_ncfa", token, domain="www.geoguessr.com")

        db = Database()
        res = session.get(
            f"https://www.geoguessr.com/api/v3/results/highscores/{game_id}"
        )
        if res.status_code != 200:
            raise Exception(f"Failed to fetch scores: HTTP {res.status_code}")

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


async def update_missing_games_scores() -> None:
    db = Database()
    game_ids = db.get_missing_game_ids()
    for game_id in game_ids:
        try:
            await fetch_game_scores(game_id)
        except Exception as e:
            print(f"Failed to fetch scores for game {game_id}: {e}")

        if len(game_ids) > 1:
            await asyncio.sleep(10)


async def update_todays_scores() -> None:
    db = Database()
    game_id = db.get_latest_game_id()
    try:
        await fetch_game_scores(game_id)
    except Exception as e:
        print(f"Failed to fetch scores for game {game_id}: {e}")


async def update_scores() -> None:
    await update_missing_games_scores()
    await update_todays_scores()
