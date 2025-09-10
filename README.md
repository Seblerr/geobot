# GeoBot

A Discord bot for generating GeoGuessr challenges with persistent scoring and leaderboards.

## Features

- Posts a daily challenge link at 6:00 Swedish time
- Automatically posts daily leaderboards each night
- Track scores with persistent leaderboard system using SQLite database
- View all-time or weekly leaderboards, sorted by total or average score

## Commands

### `!leaderboard [period] [sort]`
Display the leaderboard with optional filters.

**Options:**
- **Period**: `week`, `weekly`, `all` - Filter by time period
- **Sort**: `avg`, `average` - Sort by average score instead of total

**Examples:**
```
!leaderboard                # Show default leaderboard (all-time, sorted by total score)
!leaderboard avg            # Show all-time, sorted by average scores
!leaderboard week           # Show weekly (Mon-Fri) leaderboard
!leaderboard week avg       # Show weekly average scores
```

### `!add_game [game_id]`
Adds an already existing game_id to the database.

## Setup

### Prerequisites
- GeoGuessr Pro
- Python 3.10+
- Discord bot token

### Installation

1. Clone the repository:
```bash
git clone https://github.com/Seblerr/geobot.git
cd geobot
```

2. Install dependencies using uv:
```bash
uv sync
```

3. Create a `.env` file with your Discord bot token, channel ID (can be found in the url in browser) and NCFA token from GeoGuessr.
```env
DISCORD_TOKEN=xxx
DISCORD_CHANNEL_ID=yyy
GEOGUESSR_NCFA=zzz
```

4. Run the bot:
```bash
uv run geobot.py
```

