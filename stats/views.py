from django.conf import settings
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import render

from .models import Match, MatchParticipant, Player


def build_statistics():
    best_player = (
        Player.objects.filter(rating__isnull=False)
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
