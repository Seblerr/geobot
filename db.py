import sqlite3
import datetime
from contextlib import contextmanager


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

    def add_scores(
        self, game_id: str, scoresheet: list[tuple[str, str, int, int]]
    ) -> None:
        with self.db_connection() as conn:
            player_ids = {
                account_id: self.upsert_player(account_id, name)
                for account_id, name, _, _ in scoresheet
            }

            cursor = conn.cursor()
            cursor.executemany(
                "INSERT OR IGNORE INTO scores (game_id, player_id, round_number, score) VALUES (?, ?, ?, ?)",
                [
                    (game_id, player_ids[account_id], round_num, score)
                    for account_id, _, round_num, score in scoresheet
                ],
            )
            conn.commit()
            if cursor.rowcount > 0:
                print("Scores added to the database.")

    def get_missing_game_ids(self) -> list[str]:
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

    def get_scores(
        self,
        game_id: str | None = None,
        period: str | None = None,
        sort_by_avg: bool = False,
    ) -> str | None:
        with self.db_connection() as conn:
            cursor = conn.cursor()

            if game_id:
                query = self._get_game_scores_query()
                cursor.execute(query, (game_id,))
            else:
                query, date = self._get_scores_query(period, sort_by_avg)
                cursor.execute(query, date)
            scores = cursor.fetchall()

            if not scores:
                return None

            return self._format_table(scores, game_id=game_id)

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
            GROUP BY p.name
            ORDER BY total_score DESC
        """

    def _get_scores_query(
        self, period: str | None, sort_by_avg: bool
    ) -> tuple[str, tuple]:
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
            today = datetime.date.today()
            monday = today - datetime.timedelta(days=today.weekday())
            friday = monday + datetime.timedelta(days=4)

            query += "WHERE DATE(g.created_at) BETWEEN ? AND ?"
            date_range = (monday.isoformat(), friday.isoformat())

        order_by = "average_score DESC" if sort_by_avg else "total_score DESC"
        query += f"""
            GROUP BY p.name
            ORDER BY {order_by}
        """

        return (query, date_range)

    def _format_table(self, scores: list[tuple], game_id: str | None = None) -> str:
        if game_id:
            title = "Today's Leaderboard"
            columns = ["Player", "Score", "5000s", "0s"]
        else:
            title = "Leaderboard"
            columns = ["Player", "Score", "# Games", "Avg Score", "5000s", "0s"]

        str_rows = [[self._fmt_num(value) for value in row] for row in scores]
        all_rows = [columns] + str_rows

        padding = 2
        col_widths = [
            max(len(str(cell)) for cell in col) + padding for col in zip(*all_rows)
        ]

        format_specs = (
            [
                f"{{:<{col_widths[0]}}}"  # Left-align player names
            ]
            + [
                f"{{:>{width}}}"
                for width in col_widths[1:]  # Right-align numbers
            ]
        )
        fmt = "".join(format_specs)

        header = fmt.format(*columns)
        separator = "-" * len(header)
        data_rows = [fmt.format(*row) for row in str_rows]

        table_content = "\n".join([header, separator] + data_rows)
        return f"**{title}**\n\n```\n{table_content}\n```"

    def _fmt_num(self, value):
        if isinstance(value, int):
            return f"{value:,}".replace(",", " ")
        return value

    def print_table(self, table_name: str) -> None:
        with self.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {table_name}")
            rows = cursor.fetchall()
            print(f"Contents of the '{table_name}' table:")
            for row in rows:
                print(row)

    @contextmanager
    def db_connection(self):
        if self.conn:
            yield self.conn
        else:
            conn = sqlite3.connect("database.db")
            try:
                yield conn
            finally:
                conn.close()
