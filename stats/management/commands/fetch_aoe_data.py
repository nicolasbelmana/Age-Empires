import os
import time
from datetime import datetime, timezone as datetime_timezone

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from stats.models import Match, MatchParticipant, Player


class AoE4WorldClient:
    def __init__(self, base_url, timeout=20):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "AoE4Stats/1.0"})

    def get_json(self, path, params=None):
        try:
            response = self.session.get(
                f"{self.base_url}/{path.lstrip('/')}",
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            raise CommandError(f"Error consultando AoE4 World: {exc}") from exc
        except ValueError as exc:
            raise CommandError("AoE4 World devolvió una respuesta JSON inválida.") from exc
        if not isinstance(data, dict):
            raise CommandError("Formato inesperado en la respuesta de AoE4 World.")
        return data


class Command(BaseCommand):
    help = "Sincroniza perfiles y partidas desde la API pública de AoE4 World."

    def add_arguments(self, parser):
        parser.add_argument(
            "--profile-ids",
            default=os.getenv("AOE4_PROFILE_IDS", ""),
            help="IDs separados por coma; por defecto usa AOE4_PROFILE_IDS.",
        )
        parser.add_argument(
            "--leaderboard",
            default="",
            help="Filtra las partidas por leaderboard (por ejemplo: rm_solo).",
        )
        parser.add_argument(
            "--max-pages",
            type=int,
            default=1,
            help="Máximo de páginas de 50 partidas por perfil; usa 0 para todas.",
        )

    def handle(self, *args, **options):
        profile_ids = self.parse_profile_ids(options["profile_ids"])
        if not profile_ids:
            raise CommandError(
                "Indica --profile-ids o configura AOE4_PROFILE_IDS con IDs de perfil."
            )
        if options["max_pages"] < 0:
            raise CommandError("--max-pages debe ser 0 o un número positivo.")

        client = AoE4WorldClient(settings.AOE4_API_BASE_URL)
        saved_matches = set()
        skipped_matches = 0
        for profile_id in profile_ids:
            profile = client.get_json(f"players/{profile_id}")
            self.save_profile(profile, profile_id)
            pages = self.fetch_game_pages(
                client,
                profile_id,
                options["leaderboard"],
                options["max_pages"],
            )
            for game in pages:
                try:
                    match_id = self.save_game(game)
                except CommandError as exc:
                    skipped_matches += 1
                    game_id = (
                        game.get("game_id", "sin ID")
                        if isinstance(game, dict)
                        else "con formato inválido"
                    )
                    self.stderr.write(
                        self.style.WARNING(f"Partida {game_id} omitida: {exc}")
                    )
                    continue
                saved_matches.add(match_id)
            self.stdout.write(
                f"Perfil {profile_id}: leídas {sum(len(page) for page in pages)} partidas."
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Sincronización finalizada: {len(profile_ids)} perfiles y "
                f"{len(saved_matches)} partidas guardadas; "
                f"{skipped_matches} partidas omitidas por datos inválidos."
            )
        )

    @staticmethod
    def parse_profile_ids(raw_ids):
        ids = []
        for value in raw_ids.split(","):
            value = value.strip()
            if not value:
                continue
            try:
                profile_id = int(value)
            except ValueError as exc:
                raise CommandError(f"ID de perfil inválido: {value!r}.") from exc
            if profile_id <= 0:
                raise CommandError(f"ID de perfil inválido: {value!r}.")
            if profile_id not in ids:
                ids.append(profile_id)
        return ids

    @staticmethod
    def save_profile(data, requested_profile_id):
        try:
            profile_id = int(data["profile_id"])
            name = str(data["name"]).strip()
            modes = data.get("modes", {})
        except (KeyError, TypeError, ValueError) as exc:
            raise CommandError(
                f"Respuesta de perfil incompleta para {requested_profile_id}."
            ) from exc
        if profile_id != requested_profile_id or not name or not isinstance(modes, dict):
            raise CommandError(
                f"Respuesta de perfil inválida para {requested_profile_id}."
            )

        rating_mode = modes.get(settings.AOE4_RATING_MODE, {})
        rating = rating_mode.get("rating") if isinstance(rating_mode, dict) else None
        games_count = (
            rating_mode.get("games_count", 0) if isinstance(rating_mode, dict) else 0
        )
        with transaction.atomic():
            Player.objects.update_or_create(
                profile_id=profile_id,
                defaults={
                    "name": name[:150],
                    "rating": rating if isinstance(rating, int) and rating >= 0 else None,
                    "games_count": games_count
                    if isinstance(games_count, int) and games_count >= 0
                    else 0,
                },
            )

    def fetch_game_pages(self, client, profile_id, leaderboard, max_pages):
        pages = []
        page = 1
        while max_pages == 0 or page <= max_pages:
            params = {"page": page}
            if leaderboard:
                params["leaderboard"] = leaderboard
            data = client.get_json(f"players/{profile_id}/games", params=params)
            games = data.get("games")
            if not isinstance(games, list):
                raise CommandError(
                    f"Respuesta de partidas inválida para el perfil {profile_id}."
                )
            pages.append(games)
            next_page = data.get("next_page")
            if not next_page:
                break
            try:
                next_page_number = int(next_page)
            except (TypeError, ValueError) as exc:
                raise CommandError(
                    f"Número de página inválido para el perfil {profile_id}."
                ) from exc
            if next_page_number <= page:
                raise CommandError(
                    f"La API devolvió una página siguiente inválida para {profile_id}."
                )
            page = next_page_number
            time.sleep(0.2)
        return pages

    @staticmethod
    def parse_datetime(value):
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (AttributeError, ValueError) as exc:
            raise CommandError(f"Fecha de partida inválida: {value!r}.") from exc
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed, timezone=datetime_timezone.utc)
        return parsed

    def save_game(self, game):
        if not isinstance(game, dict):
            raise CommandError("el registro de partida no es un objeto JSON.")
        try:
            game_id = int(game["game_id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise CommandError("falta el ID de partida válido (`game_id`).") from exc
        if game_id <= 0:
            raise CommandError("el ID de partida (`game_id`) debe ser positivo.")

        teams = game.get("teams")
        if not isinstance(teams, list):
            state = game.get("state", "desconocido")
            raise CommandError(
                f"la partida {game_id} no contiene equipos válidos "
                f"(estado de AoE4 World: {state})."
            )
        participants = [
            participant["player"]
            for team in teams
            if isinstance(team, list)
            for participant in team
            if isinstance(participant, dict)
            and isinstance(participant.get("player"), dict)
        ]
        if not participants:
            state = game.get("state", "desconocido")
            raise CommandError(
                f"la partida {game_id} no contiene participantes válidos "
                f"(estado de AoE4 World: {state})."
            )

        with transaction.atomic():
            try:
                duration = int(game.get("duration") or 0)
            except (TypeError, ValueError) as exc:
                raise CommandError(
                    f"Duración inválida en la partida {game_id}."
                ) from exc
            match, _ = Match.objects.update_or_create(
                match_id=game_id,
                defaults={
                    "started_at": self.parse_datetime(game.get("started_at")),
                    "duration": max(0, duration),
                    "kind": str(game.get("kind") or "")[:40],
                    "leaderboard": str(game.get("leaderboard") or "")[:40],
                },
            )
            for participant in participants:
                try:
                    profile_id = int(participant["profile_id"])
                    name = str(participant["name"]).strip()
                except (KeyError, TypeError, ValueError) as exc:
                    raise CommandError(
                        f"Participante inválido en la partida {game_id}."
                    ) from exc
                if profile_id <= 0 or not name:
                    raise CommandError(f"Participante inválido en la partida {game_id}.")
                player, _ = Player.objects.get_or_create(
                    profile_id=profile_id,
                    defaults={"name": name[:150]},
                )
                if player.name != name[:150]:
                    player.name = name[:150]
                    player.save(update_fields=("name", "updated_at"))

                result = participant.get("result")
                if result not in MatchParticipant.Result.values:
                    result = MatchParticipant.Result.UNKNOWN
                rating = participant.get("rating")
                if not isinstance(rating, int) or rating < 0:
                    rating = None
                MatchParticipant.objects.update_or_create(
                    match=match,
                    player=player,
                    defaults={
                        "civilization": str(participant.get("civilization") or "")[:80],
                        "result": result,
                        "rating": rating,
                    },
                )
        return game_id
