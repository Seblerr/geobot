import os
import discord
import datetime
from discord.ext import commands, tasks
from dotenv import load_dotenv
from db import Database
from game import create_game, update_scores, fetch_game_scores

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

db = Database()


def set_time(hour, minute):
    tz = datetime.datetime.now().astimezone().tzinfo
    return datetime.time(hour=hour, minute=minute, tzinfo=tz)


@tasks.loop(time=set_time(7, 0))
async def create_game_task():
    link = create_game(db)
    channel_id = int(os.getenv("DISCORD_CHANNEL_ID"))
    channel = await bot.fetch_channel(channel_id)

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
        channel_id = int(os.getenv("DISCORD_CHANNEL_ID"))
        channel = await bot.fetch_channel(channel_id)
        scores = db.get_todays_scores()
        await channel.send(scores)
    except Exception as e:
        print(f"Failed to post scores: {e}")
        post_scores_task.cancel()


@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user}")
    if not create_game_task.is_running():
        create_game_task.start()
    if not fetch_scores_task.is_running():
        fetch_scores_task.start()
    if not post_scores_task.is_running():
        post_scores_task.start()


@bot.command()
@commands.cooldown(1, 120, commands.BucketType.user)
async def today(ctx):
    message = await ctx.send("Fetching today's scores, please wait... 🕐")
    await update_scores(db)
    scores = db.get_todays_scores()
    if scores:
        await message.edit(content=scores)


@bot.command()
async def leaderboard(
    ctx: commands.Context, period: str | None = None, sort_by: str | None = None
):
    message = await ctx.send("Fetching leaderboard, please wait... 🕐")
    await update_scores(db)

    period = (period or "all").lower()
    sort_by_avg = (sort_by or "").lower() in {"average", "avg"}

    scores = db.get_scores(None, period, sort_by_avg)

    if scores:
        await message.edit(content=scores)


@bot.command()
async def add_game(ctx: commands.Context, game_id: str):
    db.add_game(game_id)
    await fetch_game_scores(db, game_id)
    await ctx.send("Game added to the database.")


bot.run(os.getenv("DISCORD_TOKEN", ""))
