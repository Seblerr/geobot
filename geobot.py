import os
import asyncio
import discord
from datetime import datetime
from zoneinfo import ZoneInfo
from discord.ext import commands, tasks
from dotenv import load_dotenv
from db import Database
from game import create_game, fetch_missing_games_scores

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


db = Database()


def get_swedish_time():
    return datetime.now(ZoneInfo("Europe/Stockholm"))


@tasks.loop(hours=24)
async def create_game_task():
    now = get_swedish_time()
    if now.hour == 7 and now.minute == 0:
        link = create_game()
        print(f"Game created: {link}")


@tasks.loop(hours=24)
async def fetch_scores_task():
    now = get_swedish_time()
    if now.hour == 23 and now.minute == 30:
        print("Fetching missing game scores...")
        await asyncio.to_thread(fetch_missing_games_scores)


@tasks.loop(hours=24)
async def post_scores_task():
    now = get_swedish_time()
    if now.hour == 23 and now.minute == 45:
        print("Posting scores...")
        channel_id = int(os.getenv("DISCORD_CHANNEL_ID"))
        channel = await bot.fetch_channel(channel_id)
        scores = db.get_todays_scores()
        await channel.send(scores)


@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user}")
    create_game_task.start()
    fetch_scores_task.start()
    post_scores_task.start()


@bot.command()
async def generate(ctx):
    link = create_game()
    await ctx.send(link)


@bot.command()
async def today(ctx):
    scores = db.get_todays_scores()
    await ctx.send(scores)


@bot.command()
async def leaderboard(ctx):
    scores = db.get_total_scores()
    await ctx.send(scores)


bot.run(os.getenv("DISCORD_TOKEN"))
