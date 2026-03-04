import sys
from pathlib import Path


def main() -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

    from geobot.bot import main as bot_main

    bot_main()


if __name__ == "__main__":
    main()
