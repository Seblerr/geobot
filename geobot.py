import os
import discord
import datetime
from discord.ext import commands, tasks
from dotenv import load_dotenv
from db import Database
from game import create_game, fetch_missing_games_scores

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
    link = create_game()
    channel_id = int(os.getenv("DISCORD_CHANNEL_ID"))
    channel = await bot.fetch_channel(channel_id)
    await channel.send(link)


@tasks.loop(time=set_time(23, 45))
async def fetch_scores_task():
    print("Fetching missing game scores...")
    await fetch_missing_games_scores()


@tasks.loop(time=set_time(23, 59))
async def post_scores_task():
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
    await fetch_missing_games_scores()
    scores = db.get_todays_scores()
    await ctx.send(scores)


@bot.command()
async def leaderboard(ctx):
    scores = db.get_total_scores()
    await ctx.send(scores)


bot.run(os.getenv("DISCORD_TOKEN"))
