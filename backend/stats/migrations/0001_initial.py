import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Match",
            fields=[
                ("match_id", models.BigIntegerField(primary_key=True, serialize=False)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("duration", models.PositiveIntegerField(default=0, help_text="Duración en segundos")),
                ("kind", models.CharField(blank=True, max_length=40)),
                ("leaderboard", models.CharField(blank=True, max_length=40)),
            ],
        ),
        migrations.CreateModel(
            name="Player",
            fields=[
                ("profile_id", models.BigIntegerField(primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=150)),
                ("rating", models.PositiveIntegerField(blank=True, null=True)),
                ("games_count", models.PositiveIntegerField(default=0)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["-rating", "name"]},
        ),
        migrations.CreateModel(
            name="MatchParticipant",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("civilization", models.CharField(blank=True, db_index=True, max_length=80)),
                ("result", models.CharField(choices=[("win", "Victoria"), ("loss", "Derrota"), ("draw", "Empate"), ("unknown", "Desconocido")], default="unknown", max_length=10)),
                ("rating", models.PositiveIntegerField(blank=True, null=True)),
                ("match", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="participants", to="stats.match")),
                ("player", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="participations", to="stats.player")),
            ],
        ),
        migrations.AddConstraint(
            model_name="matchparticipant",
            constraint=models.UniqueConstraint(fields=("match", "player"), name="unique_player_per_match"),
        ),
        migrations.AddIndex(
            model_name="matchparticipant",
            index=models.Index(fields=["civilization", "result"], name="stats_match_civil_result_idx"),
        ),
    ]
