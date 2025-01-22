import os
import discord
import datetime
from discord.ext import commands, tasks
from dotenv import load_dotenv
from db import Database
from game import create_game, update_scores

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

    pinned_messages = await channel.pins()
    if pinned_messages:
        await pinned_messages[0].unpin()

    message = await channel.send("Game link pinned! 📌")
    await message.pin()


@tasks.loop(time=set_time(23, 45))
async def fetch_scores_task():
    print("Fetching missing game scores...")
    await update_scores()


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
@commands.cooldown(1, 120, commands.BucketType.user)
async def today(ctx):
    message = await ctx.send("Fetching today's scores, please wait... 🕐")
    await update_scores()
    scores = db.get_todays_scores()
    await message.edit(content=scores)


@bot.command()
async def week(ctx):
    message = await ctx.send("Fetching this week's scores, please wait... 🕐")
    await update_scores()
    scores = db.get_week_scores()
    await message.edit(content=scores)


@bot.command()
async def leaderboard(ctx, sort_by="total"):
    message = await ctx.send("Fetching leaderboard, please wait... 🕐")
    await update_scores()

    sort_by = sort_by.lower()
    leaderboard_options = {"average": True, "avg": True, "total": False}
    sort_by_avg = leaderboard_options[sort_by]

    scores = db.get_total_scores(sorted_by_avg=sort_by_avg)
    await message.edit(content=scores)


bot.run(os.getenv("DISCORD_TOKEN"))
