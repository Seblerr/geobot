import sqlite3
from contextlib import contextmanager


class Database:
    def __init__(self):
        with self.db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS games (
                game_id TEXT PRIMARY KEY,
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
            cursor.execute("SELECT game_id FROM games ORDER BY created_at DESC LIMIT 1")
            result = cursor.fetchone()
            if result:
                return result[0]
            else:
                return "No games found"

    def add_scores(self, scoresheet):
        with self.db_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(
                "INSERT OR IGNORE INTO scores (game_id, player_name, score) VALUES (?, ?, ?)",
                [
                    (self.get_latest_game(), player, score)
                    for player, score in scoresheet
                ],
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

            res = ""
            if game_id:
                res += "Scores for today's game:\n"
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
                res += "Overall leaderboard:\n"
                cursor.execute(
                    """
                    SELECT player_name, SUM(score) AS total_score
                    FROM scores
                    GROUP BY player_name
                    ORDER BY total_score DESC
                    """
                )
            scores = cursor.fetchall()

            if not scores:
                return "No scores available for today's game."

            res += "\n".join(f"- {player}: {score}" for player, score in scores)
            return res

    def get_todays_scores(self):
        game_id = self.get_latest_game()
        if not game_id:
            return "No game created today."
        return self.get_scores(game_id)

    def get_total_scores(self):
        return self.get_scores()

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
