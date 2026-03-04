import unittest
from datetime import datetime, time
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import geobot


class FakeTextChannel:
    def __init__(self) -> None:
        self.send = AsyncMock()


class TestGeoBotTasks(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.print_patcher = patch("builtins.print")
        self.print_patcher.start()

    async def asyncTearDown(self):
        self.print_patcher.stop()

    def test_set_time(self):
        result = geobot.set_time(6, 0)
        tzinfo = result.tzinfo

        self.assertIsInstance(result, time)
        self.assertEqual(result.hour, 6)
        self.assertEqual(result.minute, 0)
        self.assertIsNotNone(tzinfo)
        self.assertIsInstance(tzinfo, ZoneInfo)
        if isinstance(tzinfo, ZoneInfo):
            self.assertEqual(tzinfo.key, "Europe/Stockholm")

    @patch("geobot.update_work_week_scores", new_callable=AsyncMock)
    @patch("geobot.datetime")
    async def test_weekly_post_skips_on_non_friday(
        self,
        mock_datetime,
        mock_update_work_week_scores,
    ):
        mock_datetime.now.return_value = datetime(2026, 3, 5, 20, 0, 0)

        await geobot.post_week_leaderboard.coro()

        mock_update_work_week_scores.assert_not_awaited()

    @patch("geobot.discord.TextChannel", FakeTextChannel)
    @patch("geobot.update_work_week_scores", new_callable=AsyncMock)
    @patch("geobot.datetime")
    @patch("geobot.os.getenv", return_value="123")
    async def test_weekly_post_refreshes_then_posts_scores(
        self,
        _mock_getenv,
        mock_datetime,
        mock_update_work_week_scores,
    ):
        mock_datetime.now.return_value = datetime(2026, 3, 6, 20, 0, 0)

        channel = FakeTextChannel()
        events: list[str] = []

        async def refresh_side_effect(_db):
            events.append("refresh")

        def get_scores_side_effect(*_args, **_kwargs):
            events.append("scores")
            return "weekly leaderboard"

        async def send_side_effect(_message):
            events.append("send")

        mock_update_work_week_scores.side_effect = refresh_side_effect
        channel.send.side_effect = send_side_effect

        fake_db = MagicMock()
        fake_db.get_scores.side_effect = get_scores_side_effect

        with (
            patch.object(geobot, "db", fake_db),
            patch.object(
                geobot.bot,
                "fetch_channel",
                AsyncMock(return_value=channel),
            ),
        ):
            await geobot.post_week_leaderboard.coro()

        mock_update_work_week_scores.assert_awaited_once_with(fake_db)
        fake_db.get_scores.assert_called_once_with(period="week", sort_by_avg=True)
        channel.send.assert_awaited_once_with("weekly leaderboard")
        self.assertEqual(events, ["refresh", "scores", "send"])

    @patch("geobot.update_todays_scores", new_callable=AsyncMock)
    async def test_fetch_todays_task_updates_today_only(
        self, mock_update_todays_scores
    ):
        await geobot.fetch_todays_scores_task.coro()

        mock_update_todays_scores.assert_awaited_once_with(geobot.db)


if __name__ == "__main__":
    unittest.main()
