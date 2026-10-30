from django.urls import path

from . import views


urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("api/stats/", views.stats_json, name="stats_json"),
    path("sync/", views.sync_data, name="sync_data"),
]
