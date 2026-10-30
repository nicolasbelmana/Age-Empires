from django.db import models


class Player(models.Model):
    profile_id = models.BigIntegerField(primary_key=True)
    name = models.CharField(max_length=150)
    rating = models.PositiveIntegerField(null=True, blank=True)
    games_count = models.PositiveIntegerField(default=0)
    profile_synced_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-rating", "name"]

    def __str__(self):
        return self.name


class Match(models.Model):
    match_id = models.BigIntegerField(primary_key=True)
    started_at = models.DateTimeField(null=True, blank=True)
    duration = models.PositiveIntegerField(default=0, help_text="Duración en segundos")
    kind = models.CharField(max_length=40, blank=True)
    leaderboard = models.CharField(max_length=40, blank=True)
    synced_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Partida {self.match_id}"


class MatchParticipant(models.Model):
    class Result(models.TextChoices):
        WIN = "win", "Victoria"
        LOSS = "loss", "Derrota"
        DRAW = "draw", "Empate"
        UNKNOWN = "unknown", "Desconocido"

    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name="participants")
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="participations")
    civilization = models.CharField(max_length=80, blank=True, db_index=True)
    result = models.CharField(max_length=10, choices=Result.choices, default=Result.UNKNOWN)
    rating = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("match", "player"),
                name="unique_player_per_match",
            )
        ]
        indexes = [
            models.Index(
                fields=("civilization", "result"),
                name="stats_match_civil_result_idx",
            )
        ]

    def __str__(self):
        return f"{self.player} - {self.match}"


class LeaderboardEntry(models.Model):
    leaderboard = models.CharField(max_length=40)
    season = models.PositiveSmallIntegerField()
    rank = models.PositiveIntegerField()
    profile_id = models.BigIntegerField()
    name = models.CharField(max_length=150)
    country = models.CharField(max_length=2, blank=True)
    rating = models.PositiveIntegerField(null=True, blank=True)
    games_count = models.PositiveIntegerField(default=0)
    wins_count = models.PositiveIntegerField(default=0)
    losses_count = models.PositiveIntegerField(default=0)
    win_rate = models.FloatField(null=True, blank=True)
    streak = models.IntegerField(default=0)
    last_game_at = models.DateTimeField(null=True, blank=True)
    twitch_is_live = models.BooleanField(default=False)
    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["rank"]
        constraints = [
            models.UniqueConstraint(
                fields=("leaderboard", "season", "rank"),
                name="unique_leaderboard_season_rank",
            ),
            models.UniqueConstraint(
                fields=("leaderboard", "season", "profile_id"),
                name="unique_leaderboard_season_player",
            ),
        ]
        indexes = [
            models.Index(fields=("leaderboard", "season", "rank")),
        ]

    def __str__(self):
        return f"#{self.rank} {self.name} ({self.leaderboard})"


class DataSyncStatus(models.Model):
    class Status(models.TextChoices):
        IDLE = "idle", "Sin iniciar"
        RUNNING = "running", "En curso"
        SUCCEEDED = "succeeded", "Completada"
        FAILED = "failed", "Fallida"

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.IDLE,
    )
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)

    class Meta:
        verbose_name = "estado de sincronización"
        verbose_name_plural = "estado de sincronización"

    def __str__(self):
        return f"Sincronización {self.get_status_display()}"
