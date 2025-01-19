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
                score INTEGER,
                UNIQUE(game_id, player_name),
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
                "INSERT OR IGNORE INTO scores (game_id, player_name, score) VALUES (?, ?, ?)",
                [(game_id, player, score) for player, score in scoresheet],
            )
            conn.commit()
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

    def get_scores(self, game_id=None):
        with self.db_connection() as conn:
            cursor = conn.cursor()

            if game_id:
                cursor.execute(
                    """
                    SELECT player_name, score
                    FROM scores
                    WHERE game_id = ?
                    ORDER BY score DESC
                    """,
                    (game_id,),
                )
            else:
                cursor.execute(
                    """
                    SELECT player_name, SUM(score) AS total_score, count (DISTINCT game_id) as games_played
                    FROM scores
                    GROUP BY player_name
                    ORDER BY total_score DESC
                    """
                )
            scores = cursor.fetchall()

            if not scores:
                return "No scores available for today's game."

            table = self.format_table(scores, game_id)
            return table

    def get_week_scores(self):
        with self.db_connection() as conn:
            cursor = conn.cursor()

            today = datetime.date.today()
            monday = today - datetime.timedelta(days=today.weekday())
            friday = monday + datetime.timedelta(days=4)

            cursor.execute(
                """
                SELECT player_name, SUM(score) AS total_score, COUNT(DISTINCT scores.game_id) AS games_played
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

            table = self.format_table(scores)
            return table

    def get_todays_scores(self):
        game_id = self.get_latest_game()
        return self.get_scores(game_id)

    def get_total_scores(self):
        return self.get_scores()

    def format_table(self, scores, game_id=None):
        if not game_id:
            title = "Overall Leaderboard"
            header = f"{'Player':<20}{'Score':>10}{'Games Played':>15}{'Average Score':>15}\n"
            separator = "-" * 62 + "\n"

            rows = "\n".join(
                f"{player:<20}{score:>10,}{games:>15,}{score // games:>15,}".replace(
                    ",", " "
                )
                for player, score, games in scores
            )
        else:
            title = "Today's Leaderboard"
            header = f"{'Player':<20}{'Score':>10}\n"
            separator = "-" * 32 + "\n"

            rows = "\n".join(
                f"{player:<20}{score:>10,}".replace(",", " ")
                for player, score in scores
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
