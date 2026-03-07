import os
from datetime import datetime, time
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

from .db import Database
from .game import (
    create_game,
    fetch_game_scores,
    update_todays_scores,
    update_work_week_scores,
)

PERIODS = ["today", "week", "weekly", "all"]
SORTS = ["avg", "average"]
WEEK_PERIODS = {"week", "weekly"}

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

db = Database()


def _fmt_int(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def _sanitize_cell(value: str) -> str:
    return value.replace("|", "\\|")


def _truncate(value: str, max_len: int) -> str:
    if len(value) <= max_len:
        return value
    return value[: max_len - 1] + "…"


def _build_table_lines(scores: list[tuple], is_daily: bool) -> list[str]:
    if is_daily:
        rows = []
        for index, row in enumerate(scores, start=1):
            rows.append(
                [
                    str(index),
                    _truncate(_sanitize_cell(str(row[0])), 16),
                    _fmt_int(int(row[1])),
                    str(row[2]),
                    str(row[3]),
                ]
            )
        headers = ["#", "Player", "Score", "5k", "0s"]
    else:
        rows = []
        for index, row in enumerate(scores, start=1):
            rows.append(
                [
                    str(index),
                    _truncate(_sanitize_cell(str(row[0])), 16),
                    _fmt_int(int(row[1])),
                    str(row[2]),
                    _fmt_int(int(row[3])),
                    str(row[4]),
                    str(row[5]),
                ]
            )
        headers = ["#", "Player", "Score", "G", "Avg", "5k", "0s"]

    all_rows = [headers] + rows
    col_widths = [
        max(len(str(cell)) for cell in col) for col in zip(*all_rows, strict=False)
    ]

    def _fmt_row(row: list[str]) -> str:
        return "  ".join(
            [
                f"{row[0]:>{col_widths[0]}}",
                f"{row[1]:<{col_widths[1]}}",
            ]
            + [
                f"{cell:>{col_widths[idx]}}"
                for idx, cell in enumerate(row[2:], start=2)
            ]
        )

    header = _fmt_row(headers)
    separator = "-" * len(header)
    body = [_fmt_row(row) for row in rows]
    return [header, separator] + body


def build_leaderboard_embed(
    scores: list[tuple], game_id: str | None = None
) -> discord.Embed:
    is_daily = game_id is not None
    title = "Today's Leaderboard" if is_daily else "Leaderboard"
    embed = discord.Embed(title=title, color=discord.Color.blurple())

    max_rows = 25
    shown_scores = scores[:max_rows]
    table_lines = _build_table_lines(shown_scores, is_daily=is_daily)
    embed.description = "```\n" + "\n".join(table_lines) + "\n```"
    if len(scores) > max_rows:
        hidden_count = len(scores) - max_rows
        embed.set_footer(text=f"Showing top {max_rows}. {hidden_count} more players.")

    return embed


def set_time(hour: int, minute: int) -> time:
    return time(hour=hour, minute=minute, tzinfo=ZoneInfo("Europe/Stockholm"))


@tasks.loop(time=set_time(6, 0))
async def create_game_task() -> None:
    link = create_game(db)
    channel_id_str = os.getenv("DISCORD_CHANNEL_ID")
    if channel_id_str is None:
        print("DISCORD_CHANNEL_ID environment variable not set")
        return

    channel = await bot.fetch_channel(int(channel_id_str))
    if isinstance(channel, discord.TextChannel):
        await channel.send(link or "Couldn't generate challenge game.")


def set_swedish_time(hour: int, minute: int) -> time:
    # Set time in Swedish timezone (CET/CEST)
    swedish_tz = ZoneInfo("Europe/Stockholm")
    return time(hour=hour, minute=minute, tzinfo=swedish_tz)


@tasks.loop(time=set_time(23, 45))
async def fetch_todays_scores_task() -> None:
    print("Fetching today's game scores...")
    await update_todays_scores(db)


@tasks.loop(time=set_time(23, 59))
async def post_daily_scores_task() -> None:
    try:
        game_id = db.get_latest_game_id()
        scores = db.get_scores_rows(game_id=game_id)

        channel_id_str = os.getenv("DISCORD_CHANNEL_ID")
        if channel_id_str is None:
            print("DISCORD_CHANNEL_ID environment variable not set")
            return
        channel_id = int(channel_id_str)
        channel = await bot.fetch_channel(channel_id)

        # Only send to text channels
        if isinstance(channel, discord.TextChannel) and scores:
            await channel.send(embed=build_leaderboard_embed(scores, game_id=game_id))

    except Exception as e:
        print(f"Failed to post scores: {e}")


@tasks.loop(time=set_time(20, 0))
async def post_week_leaderboard() -> None:
    now = datetime.now(ZoneInfo("Europe/Stockholm"))
    if now.weekday() != 4:  # Only post on Fridays
        return
    try:
        channel_id_str = os.getenv("DISCORD_CHANNEL_ID")
        if channel_id_str is None:
            print("DISCORD_CHANNEL_ID environment variable not set")
            return
        channel_id = int(channel_id_str)
        channel = await bot.fetch_channel(channel_id)

        # Only send to text channels
        if not isinstance(channel, discord.TextChannel):
            return

        # Update scores before posting leaderboard
        await update_work_week_scores(db)
        scores = db.get_scores_rows(period="week", sort_by_avg=False)
        if scores:
            await channel.send(embed=build_leaderboard_embed(scores))
        else:
            await channel.send("No scores available for this week.")

    except Exception as e:
        print(f"Failed to post weekly leaderboard: {e}")


@bot.event
async def on_ready() -> None:
    print(f"We have logged in as {bot.user}")

    if os.getenv("DISCORD_CHANNEL_ID"):
        for task in [
            create_game_task,
            fetch_todays_scores_task,
            post_daily_scores_task,
            post_week_leaderboard,
        ]:
            if not task.is_running():
                task.start()


@bot.command()
async def leaderboard(ctx: commands.Context, *args):
    period = None
    sort_by_avg = False
    invalid_args = []

    for arg in args:
        lower = arg.lower()
        if lower in PERIODS:
            period = lower
        elif lower in SORTS:
            sort_by_avg = True
        else:
            invalid_args.append(lower)

    if invalid_args:
        valid_options = f"Valid options: {', '.join(PERIODS + SORTS)}"
        await ctx.send(
            f"Invalid arguments: `{', '.join(invalid_args)}`\n{valid_options}"
        )
        return

    message = await ctx.send("Fetching leaderboard, please wait... 🕐")

    try:
        game_id = None
        if period == "today":
            game_id = db.get_latest_game_id()

        if period in WEEK_PERIODS:
            await update_work_week_scores(db)
        else:
            await update_todays_scores(db)

        scores = db.get_scores_rows(
            game_id=game_id,
            period=period,
            sort_by_avg=sort_by_avg,
        )

        if scores:
            await message.edit(
                content=None,
                embed=build_leaderboard_embed(scores, game_id=game_id),
            )
        else:
            await message.edit(content="No scores found.")
    except Exception as e:
        print(f"Failed to fetch leaderboard: {e}")
        try:
            await message.edit(content=f"Failed to fetch leaderboard: {e}")
        except Exception as edit_error:
            print(f"Failed to edit leaderboard status message: {edit_error}")


@bot.command()
async def add_game(ctx: commands.Context, game_id: str):
    db.add_game(game_id)
    await fetch_game_scores(db, game_id)
    await ctx.send("Game added to the database.")


def main() -> None:
    token = os.getenv("DISCORD_TOKEN")
    if token is None:
        print("DISCORD_TOKEN environment variable not set")
    else:
        bot.run(token)


if __name__ == "__main__":
    main()
