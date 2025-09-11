import os
import discord
from datetime import datetime, time
from zoneinfo import ZoneInfo
from discord.ext import commands, tasks
from dotenv import load_dotenv
from db import Database
from game import create_game, update_scores, fetch_game_scores

PERIODS = ["today", "week", "weekly", "all"]
SORTS = ["avg", "average"]

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

db = Database()


def set_time(hour: int, minute: int) -> time:
    return time(hour=hour, minute=minute, tzinfo=ZoneInfo("Europe/Stockholm"))


@tasks.loop(time=set_time(6, 0))
async def create_game_task():
    link = create_game(db)
    channel = getattr(bot, "channel", None)

    if link is None:
        await channel.send("Couldn't generate challenge game.")
    else:
        await channel.send(link)


@tasks.loop(time=set_time(23, 45))
async def fetch_scores_task():
    print("Fetching missing game scores...")
    await update_scores(db)


@tasks.loop(time=set_time(23, 59))
async def post_scores_task():
    try:
        channel = getattr(bot, "channel", None)
        scores = db.get_todays_scores()
        await channel.send(scores)
    except Exception as e:
        print(f"Failed to post scores: {e}")
        post_scores_task.cancel()


@tasks.loop(time=set_time(17, 0))
async def post_week_leaderboard():
    now = datetime.now(ZoneInfo("Europe/Stockholm"))
    if now.weekday() != 4:
        return

    channel = getattr(bot, "channel", None)
    try:
        scores = db.get_scores(period="week", sort_by_avg=True)
        if scores:
            await channel.send(scores)
        else:
            await channel.send("No scores available for this week.")
    except Exception as e:
        print(f"Failed to post weekly leaderboard: {e}")
        post_week_leaderboard.cancel()


@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user}")

    channel_id = int(os.getenv("DISCORD_CHANNEL_ID"))
    bot.channel = await bot.fetch_channel(channel_id)

    if not create_game_task.is_running():
        create_game_task.start()
    if not fetch_scores_task.is_running():
        fetch_scores_task.start()
    if not post_scores_task.is_running():
        post_scores_task.start()


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

    game_id = None
    if period == "today":
        game_id = db.get_latest_game_id()

    await update_scores(db)
    scores = db.get_scores(game_id=game_id, period=period, sort_by_avg=sort_by_avg)

    if scores:
        await message.edit(content=scores)
    else:
        await message.edit(content="No scores found.")


@bot.command()
async def add_game(ctx: commands.Context, game_id: str):
    db.add_game(game_id)
    await fetch_game_scores(db, game_id)
    await ctx.send("Game added to the database.")


if __name__ == "__main__":
    bot.run(os.getenv("DISCORD_TOKEN", ""))
