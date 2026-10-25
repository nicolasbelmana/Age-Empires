from django.conf import settings
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import render

from .models import LeaderboardEntry, Match, MatchParticipant, Player


def build_statistics():
    current_season = (
        LeaderboardEntry.objects.filter(leaderboard=settings.AOE4_LEADERBOARD)
        .order_by("-season")
        .values_list("season", flat=True)
        .first()
    )
    leaderboard_entries = LeaderboardEntry.objects.none()
    if current_season is not None:
        leaderboard_entries = LeaderboardEntry.objects.filter(
            leaderboard=settings.AOE4_LEADERBOARD,
            season=current_season,
        ).order_by("rank")

    leaderboard_players = list(
        leaderboard_entries.values(
            "profile_id",
            "name",
            "country",
            "rank",
            "rating",
            "games_count",
            "wins_count",
            "losses_count",
            "win_rate",
            "streak",
            "last_game_at",
            "twitch_is_live",
            "synced_at",
        )
    )
    for player in leaderboard_players:
        player["win_rate_display"] = (
            f"{player['win_rate']:.1f}%" if player["win_rate"] is not None else "—"
        )
        player["streak_display"] = (
            f"+{player['streak']}" if player["streak"] > 0 else str(player["streak"])
        )
    best_player = (
        {
            "profile_id": leaderboard_players[0]["profile_id"],
            "name": leaderboard_players[0]["name"],
            "rating": leaderboard_players[0]["rating"],
            "rank": leaderboard_players[0]["rank"],
        }
        if leaderboard_players
        else Player.objects.filter(rating__isnull=False)
        .order_by("-rating", "name")
        .values("profile_id", "name", "rating")
        .first()
    )

    civilizations = list(
        MatchParticipant.objects.exclude(civilization="")
        .values("civilization")
        .annotate(
            games=Count("id"),
            wins=Count("id", filter=Q(result=MatchParticipant.Result.WIN)),
        )
        .order_by("-games", "civilization")
    )

    total_picks = sum(item["games"] for item in civilizations)
    min_games = settings.MIN_CIV_GAMES
    winrates = [
        {
            "civilization": item["civilization"],
            "games": item["games"],
            "wins": item["wins"],
            "win_rate": round(item["wins"] * 100 / item["games"], 1),
        }
        for item in civilizations
        if item["games"] >= min_games
    ]

    return {
        "players_count": Player.objects.count(),
        "best_player": best_player,
        "total_games": Match.objects.count(),
        "leaderboard_key": settings.AOE4_LEADERBOARD,
        "leaderboard_season": current_season,
        "leaderboard_players": leaderboard_players,
        "civilizations": [
            {
                "civilization": item["civilization"],
                "games": item["games"],
                "pick_rate": round(item["games"] * 100 / total_picks, 1)
                if total_picks
                else 0,
            }
            for item in civilizations
        ],
        "winrates": winrates,
        "min_civ_games": min_games,
    }


def dashboard(request):
    return render(request, "stats/index.html", {"stats": build_statistics()})


def stats_json(request):
    return JsonResponse(build_statistics())
