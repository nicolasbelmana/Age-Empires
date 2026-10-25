from django.db import models


class Player(models.Model):
    profile_id = models.BigIntegerField(primary_key=True)
    name = models.CharField(max_length=150)
    rating = models.PositiveIntegerField(null=True, blank=True)
    games_count = models.PositiveIntegerField(default=0)
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
