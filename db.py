import sqlite3
import datetime
from contextlib import contextmanager


class Database:
    def __init__(self):
        with self.db_connection() as conn:
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

    def add_game(self, game_id):
        with self.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO games (game_id) VALUES (?)",
                (game_id,),
            )
            conn.commit()
            print(f"Game {game_id} added to the database.")

    def get_latest_game(self):
        with self.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT game_id FROM games ORDER BY id DESC LIMIT 1")
            result = cursor.fetchone()
            if result:
                return result[0]
            else:
                return "No games found"

    def add_scores(self, game_id, scoresheet):
        with self.db_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(
                "INSERT OR IGNORE INTO scores (game_id, player_name, round_number, score) VALUES (?, ?, ?, ?)",
                [
                    (game_id, player, round_num, score)
                    for player, round_num, score in scoresheet
                ],
            )
            conn.commit()
            if cursor.rowcount > 0:
                print("Scores added to the database.")

    def get_missing_game_ids(self):
        with self.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT g.game_id
                FROM games g
                LEFT JOIN scores s ON g.game_id = s.game_id
                WHERE s.game_id IS NULL
                """
            )
            return [row[0] for row in cursor.fetchall()]

    def get_scores(self, game_id=None, sorted_by_avg=None):
        with self.db_connection() as conn:
            cursor = conn.cursor()

            if game_id:
                query = self._get_game_scores_query()
                cursor.execute(query, (game_id,))
            else:
                query = self._get_overall_scores_query(sorted_by_avg)
                cursor.execute(query)
            scores = cursor.fetchall()

            if not scores:
                return "No scores available."

            table = self._format_table(scores, game_id=game_id)
            return table

    def _get_game_scores_query(self):
        return """
            SELECT
                player_name,
                SUM(score) as total_score,
                COUNT(CASE WHEN score = 5000 THEN 1 END) as perfect_scores,
                COUNT(CASE WHEN score = 0 THEN 1 END) as missed_scores
            FROM scores
            WHERE game_id = ?
            GROUP BY player_name
            ORDER BY total_score DESC
        """

    def _get_overall_scores_query(self, sorted_by_avg=False):
        order_by = "average_score DESC" if sorted_by_avg else "total_score DESC"
        return f"""
            SELECT
                player_name,
                SUM(score) AS total_score,
                COUNT(DISTINCT game_id) AS games_played,
                SUM(score) / COUNT(DISTINCT game_id) AS average_score,
                COUNT(CASE WHEN score = 5000 THEN 1 END) AS perfect_scores,
                COUNT(CASE WHEN score = 0 THEN 1 END) AS missed_scores
            FROM scores
            GROUP BY player_name
            ORDER BY {order_by}
        """

    def get_week_scores(self):
        with self.db_connection() as conn:
            cursor = conn.cursor()

            today = datetime.date.today()
            monday = today - datetime.timedelta(days=today.weekday())
            friday = monday + datetime.timedelta(days=4)

            cursor.execute(
                """
                SELECT
                    player_name,
                    SUM(score) AS total_score,
                    COUNT(DISTINCT scores.game_id) AS games_played,
                    SUM(score) / COUNT(DISTINCT scores.game_id) AS average_score,
                    COUNT(CASE WHEN score = 5000 THEN 1 END) as perfect_scores,
                    COUNT(CASE WHEN score = 0 THEN 1 END) as missed_scores
                FROM scores
                JOIN games ON scores.game_id = games.game_id
                WHERE DATE(games.created_at) BETWEEN ? AND ?
                GROUP BY player_name
                ORDER BY total_score DESC
                """,
                (monday, friday),
            )

            scores = cursor.fetchall()

            if not scores:
                return "No scores available for this week's games."

            table = self._format_table(scores, weekly=True)
            return table

    def get_todays_scores(self):
        game_id = self.get_latest_game()
        return self.get_scores(game_id)

    def get_total_scores(self, sorted_by_avg=None):
        return self.get_scores(game_id=None, sorted_by_avg=sorted_by_avg)

    def _format_table(self, scores, game_id=None, weekly=None):
        if game_id:
            title = "Today's Leaderboard"
            header = f"{'Player':<20}{'Score':>10}{'5000s':>10}{'0s':>10}\n"
            separator = "-" * 50 + "\n"

            rows = "\n".join(
                f"{player:<20}{score:>10,}{perfect:>10,}{missed:>10}".replace(",", " ")
                for player, score, perfect, missed in scores
            )
        else:
            title = "Work Week Leaderboard" if weekly else "Overall Leaderboard"
            header = f"{'Player':<20}{'Score':>10}{'# Games':>15}{'Avg Score':>10}{'5000s':>10}{'0s':>10}\n"
            separator = "-" * 75 + "\n"

            rows = "\n".join(
                f"{player:<20}{score:>10,}{games:>15,}{average:>10,}{perfect:>10,}{missed:>10}".replace(
                    ",", " "
                )
                for player, score, games, average, perfect, missed in scores
            )

        return f"**{title}**\n\n```\n{header}{separator}{rows}\n```"

    def print_table(self, table_name):
        with self.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {table_name}")
            rows = cursor.fetchall()
            print(f"Contents of the '{table_name}' table:")
            for row in rows:
                print(row)

    @staticmethod
    @contextmanager
    def db_connection():
        con = sqlite3.connect("database.db")
        try:
            yield con
        finally:
            con.close()
