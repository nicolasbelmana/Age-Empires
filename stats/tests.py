from io import StringIO
from unittest.mock import patch

from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from .management.commands.fetch_aoe_data import AoE4WorldClient, Command

from .models import LeaderboardEntry, Match, MatchParticipant, Player
from .views import build_statistics


class DashboardStatisticsTests(TestCase):
    def setUp(self):
        Player.objects.create(profile_id=1, name="Alpha", rating=1500)
        Player.objects.create(profile_id=2, name="Beta", rating=1400)
        match = Match.objects.create(match_id=100, duration=600)
        MatchParticipant.objects.create(
            match=match,
            player_id=1,
            civilization="english",
            result=MatchParticipant.Result.WIN,
        )
        MatchParticipant.objects.create(
            match=match,
            player_id=2,
            civilization="french",
            result=MatchParticipant.Result.LOSS,
        )

    def test_counts_players_and_identifies_highest_rating(self):
        stats = build_statistics()

        self.assertEqual(stats["players_count"], 2)
        self.assertEqual(stats["best_player"]["name"], "Alpha")
        self.assertEqual(stats["best_player"]["rating"], 1500)

    def test_pick_rate_uses_all_participant_picks(self):
        stats = build_statistics()

        self.assertEqual(stats["total_games"], 1)
        self.assertEqual({item["pick_rate"] for item in stats["civilizations"]}, {50.0})

    def test_winrate_omits_civilizations_below_minimum_sample(self):
        stats = build_statistics()

        self.assertEqual(stats["winrates"], [])

    @override_settings(
        STORAGES={
            "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
            "staticfiles": {
                "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
            },
        }
    )
    def test_current_leaderboard_is_used_for_best_player(self):
        LeaderboardEntry.objects.create(
            leaderboard="rm_solo",
            season=14,
            rank=1,
            profile_id=3,
            name="Current leader",
            rating=2492,
            win_rate=93.9,
        )

        stats = build_statistics()

        self.assertEqual(stats["best_player"]["name"], "Current leader")
        self.assertEqual(stats["best_player"]["rank"], 1)
        self.assertEqual(len(stats["leaderboard_players"]), 1)
        self.assertContains(self.client.get("/"), "Current leader")
        self.assertEqual(
            self.client.get("/api/stats/").json()["leaderboard_players"][0]["rating"],
            2492,
        )

    @override_settings(
        STORAGES={
            "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
            "staticfiles": {
                "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
            },
        }
    )
    def test_dashboard_and_json_endpoint_return_statistics(self):
        dashboard = self.client.get("/")
        api_response = self.client.get("/api/stats/")

        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(api_response.status_code, 200)
        self.assertEqual(api_response.json()["players_count"], 2)


class AoE4SyncTests(TestCase):
    @override_settings(AOE4_RATING_MODE="rm_solo")
    def test_save_profile_uses_configured_rating_mode(self):
        Command.save_profile(
            {
                "profile_id": 42,
                "name": "Player 42",
                "modes": {"rm_solo": {"rating": 1234, "games_count": 56}},
            },
            42,
        )

        player = Player.objects.get(profile_id=42)
        self.assertEqual(player.rating, 1234)
        self.assertEqual(player.games_count, 56)

    def test_save_game_is_idempotent_and_stores_participants(self):
        command = Command()
        game = {
            "game_id": 9001,
            "started_at": "2026-10-25T12:00:00.000Z",
            "duration": 900,
            "kind": "rm_1v1",
            "leaderboard": "rm_solo",
            "teams": [
                [
                    {
                        "player": {
                            "profile_id": 11,
                            "name": "Alpha",
                            "result": "win",
                            "civilization": "english",
                        }
                    }
                ],
                [
                    {
                        "player": {
                            "profile_id": 12,
                            "name": "Beta",
                            "result": "loss",
                            "civilization": "french",
                        }
                    }
                ],
            ],
        }

        command.save_game(game)
        command.save_game(game)

        self.assertEqual(Match.objects.count(), 1)
        self.assertEqual(MatchParticipant.objects.count(), 2)
        self.assertEqual(
            MatchParticipant.objects.get(player_id=11).civilization,
            "english",
        )

    def test_save_game_reports_when_api_omits_teams(self):
        command = Command()

        with self.assertRaisesMessage(
            CommandError,
            "la partida 9002 no contiene equipos válidos",
        ):
            command.save_game({"game_id": 9002, "state": "pending"})

    @override_settings(AOE4_LEADERBOARD_SIZE=2, AOE4_LEADERBOARD="rm_solo")
    def test_save_leaderboard_replaces_entries_with_configured_top_n(self):
        data = {
            "key": "rm_solo",
            "season": 14,
            "players": [
                {
                    "profile_id": 31,
                    "name": "First",
                    "rank": 1,
                    "rating": 2000,
                    "games_count": 80,
                    "wins_count": 50,
                    "losses_count": 30,
                    "win_rate": 62.5,
                    "streak": 3,
                    "twitch_is_live": True,
                },
                {
                    "profile_id": 32,
                    "name": "Second",
                    "rank": 2,
                    "rating": 1900,
                },
                {
                    "profile_id": 33,
                    "name": "Third",
                    "rank": 3,
                    "rating": 1800,
                },
            ],
        }

        saved_count = Command.save_leaderboard(data)

        self.assertEqual(saved_count, 2)
        self.assertEqual(LeaderboardEntry.objects.count(), 2)
        first = LeaderboardEntry.objects.get(rank=1)
        self.assertEqual(first.rating, 2000)
        self.assertEqual(first.win_rate, 62.5)
        self.assertTrue(first.twitch_is_live)

    @patch.object(Command, "fetch_game_pages")
    @patch.object(Command, "save_profile")
    @patch.object(AoE4WorldClient, "get_json")
    def test_handle_saves_games_inside_each_page(
        self,
        get_json,
        save_profile,
        fetch_game_pages,
    ):
        game = {
            "game_id": 9003,
            "teams": [
                [
                    {
                        "player": {
                            "profile_id": 21,
                            "name": "Alpha",
                            "result": "win",
                            "civilization": "english",
                        }
                    }
                ]
            ],
        }
        fetch_game_pages.return_value = [[game]]
        get_json.side_effect = [
            {
                "profile_id": 21,
                "name": "Alpha",
                "modes": {},
            },
            {
                "key": "rm_solo",
                "season": 14,
                "players": [
                    {
                        "profile_id": 31,
                        "name": "Current leader",
                        "rank": 1,
                        "rating": 2000,
                    }
                ],
            },
        ]
        command = Command(stdout=StringIO(), stderr=StringIO())

        command.handle(profile_ids="21", leaderboard="", max_pages=1)

        self.assertTrue(Match.objects.filter(match_id=9003).exists())
        self.assertEqual(MatchParticipant.objects.count(), 1)
        self.assertTrue(LeaderboardEntry.objects.filter(profile_id=31, rank=1).exists())
        self.assertIn("1 partidas guardadas", command.stdout.getvalue())
        self.assertEqual(command.stderr.getvalue(), "")

    @patch.object(AoE4WorldClient, "get_json")
    def test_handle_can_sync_leaderboard_without_profile_ids(self, get_json):
        get_json.return_value = {
            "key": "rm_solo",
            "season": 14,
            "players": [
                {
                    "profile_id": 41,
                    "name": "Ranked player",
                    "rank": 1,
                    "rating": 2100,
                }
            ],
        }
        command = Command(stdout=StringIO(), stderr=StringIO())

        command.handle(profile_ids="", leaderboard="", max_pages=1)

        self.assertTrue(LeaderboardEntry.objects.filter(profile_id=41).exists())
        get_json.assert_called_once_with("leaderboards/rm_solo", params={"page": 1})
