from datetime import date, timedelta
from io import StringIO

from django.conf import settings
from django.contrib import messages
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models import Count, Max, Min, Q
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import DataSyncStatus, LeaderboardEntry, Match, MatchParticipant, Player


SYNC_STATUS_ID = 1
SYNC_COOLDOWN = timedelta(minutes=1)
SYNC_STALE_AFTER = timedelta(minutes=10)

CIVILIZATION_NAMES = {
    "abbasid_dynasty": "Abbasid Dynasty",
    "ayyubids": "Ayyubids",
    "byzantines": "Byzantines",
    "delhi_sultanate": "Delhi Sultanate",
    "holy_roman_empire": "Holy Roman Empire",
    "order_of_the_dragon": "Order of the Dragon",
    "zhuxi_legacy": "Zhu Xi's Legacy",
}


def civilization_display_name(civilization):
    return CIVILIZATION_NAMES.get(
        civilization,
        civilization.replace("_", " ").title(),
    )


def get_dashboard_filters(params):
    leaderboard_options = sorted(
        set(
            LeaderboardEntry.objects.exclude(leaderboard="")
            .values_list("leaderboard", flat=True)
            .distinct()
        )
        | {settings.AOE4_LEADERBOARD}
    )
    game_mode_options = sorted(
        set(
            Match.objects.exclude(leaderboard="")
            .values_list("leaderboard", flat=True)
            .distinct()
        )
    )
    civilization_options = [
        {
            "key": civilization,
            "name": civilization_display_name(civilization),
        }
        for civilization in MatchParticipant.objects.exclude(civilization="")
        .values_list("civilization", flat=True)
        .distinct()
        .order_by("civilization")
    ]
    errors = []

    leaderboard = params.get("leaderboard", settings.AOE4_LEADERBOARD).strip()
    if leaderboard not in leaderboard_options:
        errors.append("El modo de clasificación seleccionado no está disponible.")
        leaderboard = settings.AOE4_LEADERBOARD

    season_options = list(
        LeaderboardEntry.objects.filter(leaderboard=leaderboard)
        .values_list("season", flat=True)
        .distinct()
        .order_by("-season")
    )
    selected_season = params.get("season", "").strip()
    if selected_season:
        try:
            selected_season_number = int(selected_season)
        except ValueError:
            selected_season_number = None
        if selected_season_number not in season_options:
            errors.append("La temporada seleccionada no está disponible.")
            selected_season = str(season_options[0]) if season_options else ""
        else:
            selected_season = str(selected_season_number)
    elif season_options:
        selected_season = str(season_options[0])

    game_mode = params.get("game_mode", "all").strip()
    if game_mode != "all" and game_mode not in game_mode_options:
        errors.append("El modo de partidas seleccionado no está disponible.")
        game_mode = "all"

    civilization = params.get("civilization", "").strip()
    available_civilizations = {item["key"] for item in civilization_options}
    if civilization and civilization not in available_civilizations:
        errors.append("La civilización seleccionada no está disponible.")
        civilization = ""

    date_from = params.get("date_from", "").strip()
    date_to = params.get("date_to", "").strip()
    parsed_date_from = None
    parsed_date_to = None
    try:
        if date_from:
            parsed_date_from = date.fromisoformat(date_from)
        if date_to:
            parsed_date_to = date.fromisoformat(date_to)
    except ValueError:
        errors.append("Usa fechas válidas para filtrar las partidas.")
        date_from = ""
        date_to = ""
        parsed_date_from = None
        parsed_date_to = None

    if parsed_date_from and parsed_date_to and parsed_date_from > parsed_date_to:
        errors.append("La fecha inicial no puede ser posterior a la fecha final.")
        date_from = ""
        date_to = ""
        parsed_date_from = None
        parsed_date_to = None

    return {
        "leaderboard": leaderboard,
        "leaderboard_options": leaderboard_options,
        "season": selected_season,
        "season_options": season_options,
        "game_mode": game_mode,
        "game_mode_options": game_mode_options,
        "civilization": civilization,
        "civilization_options": civilization_options,
        "date_from": date_from,
        "date_to": date_to,
        "parsed_date_from": parsed_date_from,
        "parsed_date_to": parsed_date_to,
        "filter_errors": errors,
    }


def build_statistics(filters=None):
    filters = filters or get_dashboard_filters({})
    selected_season = int(filters["season"]) if filters["season"] else None
    leaderboard_entries = LeaderboardEntry.objects.filter(
        leaderboard=filters["leaderboard"],
    )
    if selected_season is not None:
        leaderboard_entries = leaderboard_entries.filter(season=selected_season)
    else:
        leaderboard_entries = LeaderboardEntry.objects.none()
    leaderboard_entries = leaderboard_entries.order_by("rank")

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
    best_player = None
    if leaderboard_players:
        best_player = {
            "profile_id": leaderboard_players[0]["profile_id"],
            "name": leaderboard_players[0]["name"],
            "rating": leaderboard_players[0]["rating"],
            "rank": leaderboard_players[0]["rank"],
        }

    matches = Match.objects.all()
    if filters["game_mode"] != "all":
        matches = matches.filter(leaderboard=filters["game_mode"])
    if filters["parsed_date_from"]:
        matches = matches.filter(started_at__date__gte=filters["parsed_date_from"])
    if filters["parsed_date_to"]:
        matches = matches.filter(started_at__date__lte=filters["parsed_date_to"])

    if filters["civilization"]:
        matches = matches.filter(
            participants__civilization=filters["civilization"],
        ).distinct()
    participants = MatchParticipant.objects.filter(match__in=matches)
    if filters["civilization"]:
        participants = participants.filter(civilization=filters["civilization"])

    civilizations = list(
        participants.exclude(civilization="")
        .values("civilization")
        .annotate(
            games=Count("id"),
            wins=Count("id", filter=Q(result=MatchParticipant.Result.WIN)),
        )
        .order_by("-games", "civilization")
    )

    total_picks = sum(item["games"] for item in civilizations)
    min_games = settings.MIN_CIV_GAMES
    configured_profile_ids = settings.AOE4_PROFILE_IDS
    synced_profiles = Player.objects.filter(
        profile_id__in=configured_profile_ids,
        profile_synced_at__isnull=False,
    )
    match_dates = matches.aggregate(
        period_start=Min("started_at"),
        period_end=Max("started_at"),
        last_synced_at=Max("synced_at"),
    )
    leaderboard_last_synced_at = leaderboard_entries.aggregate(
        last_synced_at=Max("synced_at")
    )["last_synced_at"]
    winrates = [
        {
            "civilization": item["civilization"],
            "name": civilization_display_name(item["civilization"]),
            "games": item["games"],
            "wins": item["wins"],
            "win_rate": round(item["wins"] * 100 / item["games"], 1),
        }
        for item in civilizations
        if item["games"] >= min_games
    ]

    return {
        "players_count": participants.values("player_id").distinct().count(),
        "all_players_count": MatchParticipant.objects.values("player_id").distinct().count(),
        "configured_profiles_count": len(configured_profile_ids),
        "synced_profiles_count": synced_profiles.count(),
        "profiles_last_synced_at": synced_profiles.aggregate(
            last_synced_at=Max("profile_synced_at")
        )["last_synced_at"],
        "best_player": best_player,
        "total_games": matches.count(),
        "matches_period_start": match_dates["period_start"],
        "matches_period_end": match_dates["period_end"],
        "matches_last_synced_at": match_dates["last_synced_at"],
        "leaderboard_key": filters["leaderboard"],
        "leaderboard_season": selected_season,
        "leaderboard_last_synced_at": leaderboard_last_synced_at,
        "leaderboard_players": leaderboard_players,
        "civilizations": [
            {
                "civilization": item["civilization"],
                "name": civilization_display_name(item["civilization"]),
                "games": item["games"],
                "pick_rate": round(item["games"] * 100 / total_picks, 1)
                if total_picks
                else 0,
            }
            for item in civilizations
        ],
        "winrates": winrates,
        "winrates_period_start": match_dates["period_start"],
        "winrates_period_end": match_dates["period_end"],
        "min_civ_games": min_games,
        "filters": {
            "leaderboard": filters["leaderboard"],
            "season": filters["season"],
            "game_mode": filters["game_mode"],
            "civilization": filters["civilization"],
            "date_from": filters["date_from"],
            "date_to": filters["date_to"],
        },
        "leaderboard_options": filters["leaderboard_options"],
        "season_options": filters["season_options"],
        "game_mode_options": filters["game_mode_options"],
        "civilization_options": filters["civilization_options"],
        "filter_errors": filters["filter_errors"],
    }


def dashboard(request):
    data_sync = DataSyncStatus.objects.filter(pk=SYNC_STATUS_ID).first()
    sync_running = (
        data_sync is not None
        and data_sync.status == DataSyncStatus.Status.RUNNING
        and data_sync.started_at is not None
        and data_sync.started_at > timezone.now() - SYNC_STALE_AFTER
    )
    return render(
        request,
        "stats/index.html",
        {
            "stats": build_statistics(get_dashboard_filters(request.GET)),
            "data_sync": data_sync,
            "sync_running": sync_running,
        },
    )


def stats_json(request):
    return JsonResponse(build_statistics(get_dashboard_filters(request.GET)))


@require_POST
def sync_data(request):
    now = timezone.now()
    with transaction.atomic():
        status = DataSyncStatus.objects.get(pk=SYNC_STATUS_ID)
        available = DataSyncStatus.objects.filter(pk=SYNC_STATUS_ID).filter(
            Q(status__in=[
                DataSyncStatus.Status.IDLE,
                DataSyncStatus.Status.SUCCEEDED,
                DataSyncStatus.Status.FAILED,
            ])
            | Q(
                status=DataSyncStatus.Status.RUNNING,
                started_at__lte=now - SYNC_STALE_AFTER,
            )
        )
        if status.started_at is not None:
            available = available.filter(started_at__lte=now - SYNC_COOLDOWN)
        claimed = available.update(
            status=DataSyncStatus.Status.RUNNING,
            started_at=now,
            finished_at=None,
            error="",
        )

    if not claimed:
        if status.status == DataSyncStatus.Status.RUNNING:
            messages.info(request, "La actualización ya está en curso.")
        else:
            messages.info(
                request,
                "Espera un minuto desde la última actualización para volver a sincronizar.",
            )
        return redirect("dashboard")

    output = StringIO()
    errors = StringIO()
    try:
        call_command("fetch_aoe_data", stdout=output, stderr=errors)
    except CommandError as exc:
        DataSyncStatus.objects.filter(pk=SYNC_STATUS_ID).update(
            status=DataSyncStatus.Status.FAILED,
            finished_at=timezone.now(),
            error=str(exc),
        )
        messages.error(request, f"No se pudieron actualizar los datos: {exc}")
    else:
        DataSyncStatus.objects.filter(pk=SYNC_STATUS_ID).update(
            status=DataSyncStatus.Status.SUCCEEDED,
            finished_at=timezone.now(),
            error="",
        )
        messages.success(request, "Los datos se actualizaron correctamente.")
    return redirect("dashboard")
