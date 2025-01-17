import os
import asyncio
import schedule
import discord
from discord.ext import commands
from dotenv import load_dotenv
from db import Database
from game import create_game, fetch_missing_games_scores

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


async def scheduler_loop():
    while True:
        schedule.run_pending()
        await asyncio.sleep(1)


db = Database()


async def post_todays_scores():
    scores = db.get_todays_scores()
    channel = bot.get_channel(os.getenv("DISCORD_CHANNEL_ID"))
    await channel.send(scores)


@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user}")
    bot.loop.create_task(scheduler_loop())


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


schedule.every().day.at("07:00").do(create_game)
schedule.every().day.at("23:30").do(fetch_missing_games_scores)
schedule.every().day.at("23:45").do(post_todays_scores)

bot.run(os.getenv("DISCORD_TOKEN"))
