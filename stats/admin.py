from django.contrib import admin

from .models import LeaderboardEntry, Match, MatchParticipant, Player


class MatchParticipantInline(admin.TabularInline):
    model = MatchParticipant
    extra = 0


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ("profile_id", "name", "rating", "games_count", "updated_at")
    search_fields = ("name", "profile_id")
    ordering = ("-rating",)


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ("match_id", "started_at", "duration", "kind", "leaderboard")
    inlines = (MatchParticipantInline,)


@admin.register(MatchParticipant)
class MatchParticipantAdmin(admin.ModelAdmin):
    list_display = ("match", "player", "civilization", "result", "rating")
    list_filter = ("civilization", "result")
    search_fields = ("player__name", "player__profile_id", "match__match_id")


@admin.register(LeaderboardEntry)
class LeaderboardEntryAdmin(admin.ModelAdmin):
    list_display = (
        "rank",
        "name",
        "rating",
        "win_rate",
        "leaderboard",
        "season",
        "synced_at",
    )
    list_filter = ("leaderboard", "season", "twitch_is_live")
    search_fields = ("name", "profile_id")
    ordering = ("leaderboard", "season", "rank")
