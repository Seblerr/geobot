import sqlite3
import unittest
from db import Database


class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.db = Database(conn=self.conn)

    def tearDown(self):
        self.conn.close()

    def test_add_and_get_game(self):
        """Test that a game can be added and retrieved."""
        with self.db.db_connection() as conn:
            cursor = conn.cursor()
            # Manually create tables in the in-memory database
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id TEXT UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            conn.commit()

        self.db.add_game("game_id")
        game_id = self.db.get_latest_game_id()
        self.assertEqual(game_id, "game_id")

    def test_add_scores(self):
        """Test that scores can be added for a game."""
        with self.db.db_connection() as conn:
            cursor = conn.cursor()
            # Manually create tables in the in-memory database
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

        self.db.add_game("game_id")

        scoresheet = [
            ("player1", 1, 5000),
            ("player1", 2, 3000),
            ("player2", 1, 4500),
        ]
        self.db.add_scores("game_id", scoresheet)

        with self.db.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM scores")
            scores = cursor.fetchall()
            self.assertEqual(len(scores), 3)
            self.assertEqual(scores[0][2], "player1")
            self.assertEqual(scores[0][4], 5000)

    def test_get_scores_sorts_correctly(self):
        """Test that get_scores correctly sorts players by total score."""
        with self.db.db_connection() as conn:
            cursor = conn.cursor()
            # Manually create tables in the in-memory database
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

        game_id = "game_id"
        self.db.add_game(game_id)

        player1_scores = [
            ("player1", 1, 1000),
            ("player1", 2, 2000),
        ]
        player2_scores = [
            ("player2", 1, 5000),
            ("player2", 2, 4500),
        ]
        self.db.add_scores(game_id, player1_scores + player2_scores)

        scores = self.db.get_scores()

        player1_position = scores.find("player1")
        player2_position = scores.find("player2")

        self.assertTrue(
            player2_position < player1_position,
            "Player2 should be listed before Player1",
        )


if __name__ == "__main__":
    unittest.main()
