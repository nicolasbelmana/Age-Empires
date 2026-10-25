from django.test import TestCase, override_settings

from .management.commands.fetch_aoe_data import Command

from .models import Match, MatchParticipant, Player
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
