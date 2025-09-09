import sqlite3
import unittest
from datetime import time
from zoneinfo import ZoneInfo
from db import Database
from geobot import set_time


class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.db = Database(conn=self.conn)
        self._create_tables()
        self._add_game_with_scores(
            "game_id",
            [
                ("player1", 1, 3000),
                ("player1", 2, 2000),
                ("player2", 1, 1000),
                ("player2", 2, 2000),
            ],
        )
        self._add_game_with_scores(
            "game_id2",
            [
                ("player1", 1, 2000),
                ("player1", 2, 3000),
                ("player2", 1, 2000),
                ("player2", 2, 4000),
            ],
        )
        self._add_game_with_scores(
            "game_id3",
            [
                ("player1", 1, 2000),
                ("player1", 2, 3000),
                ("player2", 1, 5000),
                ("player2", 2, 2000),
            ],
        )

    def tearDown(self):
        self.conn.close()

    def _create_tables(self):
        with self.db.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id TEXT UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id TEXT,
                player_name TEXT,
                round_number INTEGER,
                score INTEGER,
                UNIQUE(game_id, player_name, round_number),
                FOREIGN KEY (game_id) REFERENCES games(game_id)
            )
            """)
            conn.commit()

    def _add_game_with_scores(self, game_id: str, scoresheet: list[tuple]):
        self.db.add_game(game_id)
        self.db.add_scores(game_id, scoresheet)

    def test_set_time(self):
        t = set_time(6, 0)
        assert isinstance(t, time)
        assert t.hour == 6
        assert t.minute == 0
        assert t.tzinfo is not None
        assert isinstance(t.tzinfo, ZoneInfo)
        assert t.tzinfo.key == "Europe/Stockholm"

    def test_add_and_get_game(self):
        """Test that a game can be added and retrieved."""
        self.db.add_game("unique_game_id")
        game_id = self.db.get_latest_game_id()
        self.assertEqual(game_id, "unique_game_id")

    def test_add_scores(self):
        """Test that scores can be added for a game."""

        with self.db.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM scores")
            scores = cursor.fetchall()
            self.assertEqual(len(scores), 12)
            self.assertEqual(scores[0][2], "player1")
            self.assertEqual(scores[0][4], 3000)

    def test_get_scores_from_game(self):
        """Test that get_scores can fetch score from specific game"""

        scores = self.db.get_scores("game_id", None, False)

        player1_position = scores.find("player1")
        player2_position = scores.find("player2")

        self.assertTrue(
            player1_position < player2_position,
            "Player1 should be listed before Player2",
        )

    def test_get_scores_sort_by_total(self):
        """Test that get_scores correctly sorts players by total score (default)."""

        scores = self.db.get_scores(None, None, False)

        player1_position = scores.find("player1")
        player2_position = scores.find("player2")

        self.assertTrue(
            player2_position < player1_position,
            "Player2 should be listed before Player1",
        )

    def test_get_scores_sort_by_avg(self):
        """Get scores and sort by avg."""

        scores = self.db.get_scores(None, None, True)

        player1_position = scores.find("player1")
        player2_position = scores.find("player2")

        self.assertTrue(
            player2_position < player1_position,
            "Player2 should be listed before Player1",
        )

    def test_get_week_scores_sorted_by_avg(self):
        """Get scores by week and sort by avg."""

        scores = self.db.get_scores(None, "week", True)

        player1_position = scores.find("player1")
        player2_position = scores.find("player2")

        self.assertTrue(
            player2_position < player1_position,
            "Player2 should be listed before Player1",
        )


if __name__ == "__main__":
    unittest.main()
