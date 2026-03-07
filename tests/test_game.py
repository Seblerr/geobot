import sqlite3
import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from geobot.db import Database
from geobot.game import update_work_week_scores


class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.print_patcher = patch("builtins.print")
        self.print_patcher.start()

        self.conn = sqlite3.connect(":memory:")
        self.db = Database(conn=self.conn)
        self._add_game_with_scores(
            "game_id",
            [
                ("p1_id", "player1", 1, 3000),
                ("p1_id", "player1", 2, 2001),
                ("p2_id", "player2", 1, 3000),
                ("p2_id", "player2", 2, 2000),
            ],
        )
        self._add_game_with_scores(
            "game_id2",
            [
                ("p1_id", "player1", 1, 2000),
                ("p1_id", "player1", 2, 3000),
                ("p2_id", "player2", 1, 2000),
                ("p2_id", "player2", 2, 4000),
            ],
        )
        self._add_game_with_scores(
            "game_id3",
            [
                ("p1_id", "player1", 1, 2000),
                ("p1_id", "player1", 2, 3000),
                ("p2_id", "player2", 1, 5000),
                ("p2_id", "player2", 2, 2000),
            ],
        )
        self._add_game_with_scores(
            "game_id4",
            [
                ("p1_id", "player1", 1, 2000),
                ("p1_id", "player1", 2, 3000),
            ],
        )

    def tearDown(self):
        self.conn.close()
        self.print_patcher.stop()

    def _add_game_with_scores(
        self, game_id: str, scoresheet: list[tuple[str, str, int, int]]
    ) -> None:
        self.db.add_game(game_id)
        self.db.add_scores(game_id, scoresheet)

    def test_add_and_get_game(self):
        self.db.add_game("unique_game_id")
        game_id = self.db.get_latest_game_id()
        self.assertEqual(game_id, "unique_game_id")

    def test_add_scores(self):
        with self.db.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM scores")
            scores = cursor.fetchall()
            self.assertEqual(len(scores), 14)
            self.assertEqual(scores[0][2], 1)
            self.assertEqual(scores[0][4], 3000)

    def test_get_scores_from_game(self):
        scores = self.db.get_scores("game_id", None, False)

        player1_position = scores.find("player1")
        player2_position = scores.find("player2")

        self.assertTrue(
            player1_position < player2_position,
            "Player1 should be listed before Player2",
        )

    def test_get_scores_sort_by_total(self):
        scores = self.db.get_scores(None, None, False)

        player1_position = scores.find("player1")
        player2_position = scores.find("player2")

        self.assertTrue(
            player1_position < player2_position,
            "Player1 should be listed before Player2",
        )

    def test_get_scores_sort_by_avg(self):
        scores = self.db.get_scores(None, None, True)

        player1_position = scores.find("player1")
        player2_position = scores.find("player2")

        self.assertTrue(
            player2_position < player1_position,
            "Player2 should be listed before Player1",
        )

    @patch("geobot.db.datetime.datetime")
    def test_get_week_scores_sort_by_total_by_default(self, mock_datetime):
        mock_datetime.now.return_value = datetime(2026, 3, 6, 20, 0, 0)

        with self.db.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE games SET created_at = ? WHERE game_id = ?",
                ("2026-03-03 12:00:00", "game_id"),
            )
            cursor.execute(
                "UPDATE games SET created_at = ? WHERE game_id = ?",
                ("2026-03-04 12:00:00", "game_id2"),
            )
            cursor.execute(
                "UPDATE games SET created_at = ? WHERE game_id = ?",
                ("2026-03-05 12:00:00", "game_id3"),
            )
            cursor.execute(
                "UPDATE games SET created_at = ? WHERE game_id = ?",
                ("2026-03-06 12:00:00", "game_id4"),
            )
            conn.commit()

        scores = self.db.get_scores(None, "week", False)

        player1_position = scores.find("player1")
        player2_position = scores.find("player2")

        self.assertTrue(
            player1_position < player2_position,
            "Player1 should be listed before Player2",
        )

    @patch("geobot.db.datetime.datetime")
    def test_week_scores_exclude_weekend_games(self, mock_datetime):
        mock_datetime.now.return_value = datetime(2026, 3, 6, 20, 0, 0)

        with self.db.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM scores")
            cursor.execute("DELETE FROM games")
            cursor.execute("DELETE FROM players")
            conn.commit()

        self._add_game_with_scores(
            "mon_game",
            [("weekday_id", "weekday_player", 1, 4500)],
        )
        self._add_game_with_scores(
            "sat_game",
            [("weekend_id", "weekend_player", 1, 4999)],
        )

        with self.db.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE games SET created_at = ? WHERE game_id = ?",
                ("2026-03-02 12:00:00", "mon_game"),
            )
            cursor.execute(
                "UPDATE games SET created_at = ? WHERE game_id = ?",
                ("2026-03-07 12:00:00", "sat_game"),
            )
            conn.commit()

        scores = self.db.get_scores(period="week")

        self.assertIn("weekday_player", scores)
        self.assertNotIn("weekend_player", scores)


class TestGameWorkWeekUpdate(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.print_patcher = patch("builtins.print")
        self.print_patcher.start()

        self.conn = sqlite3.connect(":memory:")
        self.db = Database(conn=self.conn)

    async def asyncTearDown(self):
        self.conn.close()
        self.print_patcher.stop()

    @patch("geobot.game.asyncio.sleep", new_callable=AsyncMock)
    @patch("geobot.game.fetch_game_scores", new_callable=AsyncMock)
    @patch("geobot.game.datetime.datetime")
    async def test_update_work_week_scores_fetches_only_mon_to_fri(
        self,
        mock_datetime,
        mock_fetch_game_scores,
        mock_sleep,
    ):
        mock_datetime.now.return_value = datetime(2026, 3, 6, 20, 0, 0)

        with self.db.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO games (game_id, created_at) VALUES (?, ?)",
                ("mon_game", "2026-03-02 12:00:00"),
            )
            cursor.execute(
                "INSERT INTO games (game_id, created_at) VALUES (?, ?)",
                ("wed_game", "2026-03-04 12:00:00"),
            )
            cursor.execute(
                "INSERT INTO games (game_id, created_at) VALUES (?, ?)",
                ("sat_game", "2026-03-07 12:00:00"),
            )
            conn.commit()

        await update_work_week_scores(self.db)

        self.assertEqual(mock_fetch_game_scores.await_count, 2)
        fetched_ids = [call.args[1] for call in mock_fetch_game_scores.await_args_list]
        self.assertEqual(fetched_ids, ["mon_game", "wed_game"])
        mock_sleep.assert_awaited_once_with(20)


if __name__ == "__main__":
    unittest.main()
