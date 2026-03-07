import datetime
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from zoneinfo import ZoneInfo


class Database:
    def __init__(self, conn: sqlite3.Connection | None = None):
        # To re-use connection for in-memory database
        self.conn = conn

        with self.db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL
            )
            """)

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
                player_id INTEGER,
                round_number INTEGER,
                score INTEGER,
                UNIQUE(game_id, player_id, round_number),
                FOREIGN KEY (game_id) REFERENCES games(game_id),
                FOREIGN KEY (player_id) REFERENCES players(id)
            )
            """)
            conn.commit()

    @contextmanager
    def db_connection(self) -> Iterator[sqlite3.Connection]:
        if self.conn is not None:
            yield self.conn
        else:
            conn = sqlite3.connect("database.db")
            try:
                yield conn
            finally:
                conn.close()

    def upsert_player(self, account_id: str, name: str) -> int:
        with self.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO players (account_id, name)
                VALUES (?, ?)
                ON CONFLICT(account_id) DO UPDATE SET name = excluded.name
                """,
                (account_id, name),
            )
            cursor.execute("SELECT id FROM players WHERE account_id = ?", (account_id,))
            player_id = cursor.fetchone()[0]
            conn.commit()
            return player_id

    def add_game(self, game_id: str) -> None:
        with self.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO games (game_id) VALUES (?)",
                (game_id,),
            )
            conn.commit()
            print(f"Game {game_id} added to the database.")

    def get_latest_game_id(self) -> str | None:
        with self.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT game_id FROM games ORDER BY id DESC LIMIT 1")
            result = cursor.fetchone()
            if result:
                return result[0]
            else:
                return None

    def add_scores(self, game_id: str, scoresheet: list[tuple[str, str, int, int]]) -> None:
        with self.db_connection() as conn:
            player_ids = {account_id: self.upsert_player(account_id, name) for account_id, name, _, _ in scoresheet}

            cursor = conn.cursor()
            cursor.executemany(
                "INSERT OR IGNORE INTO scores (game_id, player_id, round_number, score) VALUES (?, ?, ?, ?)",
                [(game_id, player_ids[account_id], round_num, score) for account_id, _, round_num, score in scoresheet],
            )
            conn.commit()
            if cursor.rowcount > 0:
                print("Scores added to the database.")

    def get_scores_rows(
        self,
        game_id: str | None = None,
        period: str | None = None,
        sort_by_avg: bool = False,
    ) -> list[tuple]:
        with self.db_connection() as conn:
            cursor = conn.cursor()

            if game_id:
                query = self._get_game_scores_query()
                cursor.execute(query, (game_id,))
            else:
                query, date = self._get_scores_query(period, sort_by_avg)
                cursor.execute(query, date)
            scores = cursor.fetchall()
        return scores

    def _get_game_scores_query(self) -> str:
        return """
            SELECT
                p.name,
                SUM(s.score) as total_score,
                COUNT(CASE WHEN s.score = 5000 THEN 1 END) as perfect_scores,
                COUNT(CASE WHEN s.score = 0 THEN 1 END) as missed_scores
            FROM scores s
            JOIN players p ON s.player_id = p.id
            WHERE s.game_id = ?
            GROUP BY p.id, p.name
            ORDER BY total_score DESC
        """

    def _get_scores_query(self, period: str | None, sort_by_avg: bool) -> tuple[str, tuple]:
        query = """
            SELECT
                p.name,
                SUM(s.score) AS total_score,
                COUNT(DISTINCT s.game_id) AS games_played,
                SUM(s.score) / COUNT(DISTINCT s.game_id) AS average_score,
                COUNT(CASE WHEN s.score = 5000 THEN 1 END) AS perfect_scores,
                COUNT(CASE WHEN s.score = 0 THEN 1 END) AS missed_scores
            FROM scores s
            JOIN games g ON s.game_id = g.game_id
            JOIN players p ON s.player_id = p.id
        """

        date_range: tuple = ()
        if period in {"week", "weekly"}:
            today = datetime.datetime.now(ZoneInfo("Europe/Stockholm")).date()
            monday = today - datetime.timedelta(days=today.weekday())
            friday = monday + datetime.timedelta(days=4)

            query += "WHERE DATE(g.created_at, 'localtime') BETWEEN ? AND ?"
            date_range = (monday.isoformat(), friday.isoformat())

        order_by = "average_score DESC" if sort_by_avg else "total_score DESC"
        query += f"""
            GROUP BY p.id, p.name
            ORDER BY {order_by}
        """

        return (query, date_range)

    def print_table(self, table_name: str) -> None:
        with self.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {table_name}")
            rows = cursor.fetchall()
            print(f"Contents of the '{table_name}' table:")
            for row in rows:
                print(row)
