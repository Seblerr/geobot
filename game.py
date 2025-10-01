import os
import requests
import asyncio
from db import Database
from dotenv import load_dotenv

# Map IDs
I_SAW_THE_SIGN_2 = "5cfda2c9bc79e16dd866104d"
A_COMMUNITY_WORLD = "62a44b22040f04bd36e8a914"

load_dotenv()


def _get_authenticated_session() -> requests.Session | None:
    token = os.getenv("GEOGUESSR_NCFA")
    if token is None:
        print("NCFA token missing")
        return None

    session = requests.Session()
    session.cookies.set("_ncfa", token or "", domain="www.geoguessr.com")
    return session


def create_game(db: Database) -> str | None:
    session = _get_authenticated_session()
    if session is None:
        return None

    try:
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
        res.raise_for_status()

        game_id = res.json()["token"]
        db.add_game(game_id)
        return f"https://www.geoguessr.com/challenge/{game_id}"

    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return None
    finally:
        session.close()


async def fetch_game_scores(db: Database, game_id: str) -> None:
    session = _get_authenticated_session()
    if not session:
        return None

    try:
        res = session.get(
            f"https://www.geoguessr.com/api/v3/results/highscores/{game_id}"
        )
        res.raise_for_status()

        for item in res.json().get("items", []):
            player = item.get("game").get("player")
            nick = player.get("nick")
            account_id = player.get("id")
            guesses = player.get("guesses")

            if not nick or not guesses or not account_id:
                print(f"Incomplete data for game {game_id}, skipping item.")
                continue

            round_scores = [round.get("roundScoreInPoints") for round in guesses]
            scores = [
                (account_id, nick, i + 1, score) for i, score in enumerate(round_scores)
            ]

            db.add_scores(game_id, scores)

    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")

    finally:
        session.close()


async def update_missing_games_scores(db: Database) -> None:
    game_ids = db.get_missing_game_ids()
    for i, game_id in enumerate(game_ids):
        await fetch_game_scores(db, game_id)

        if i < len(game_ids) - 1:
            await asyncio.sleep(10)


async def update_todays_scores(db: Database) -> None:
    game_id = db.get_latest_game_id()
    if game_id is not None:
        await fetch_game_scores(db, game_id)


async def update_scores(db: Database) -> None:
    await update_missing_games_scores(db)
    await update_todays_scores(db)
