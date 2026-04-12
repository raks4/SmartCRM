from django.urls import path

from .views import (
    dashboard_view,
    lead_note_create_view,
    lead_update_view,
    leads_collection_view,
    login_view,
    logout_view,
    session_view,
)

urlpatterns = [
    path("auth/login/", login_view, name="login"),
    path("auth/logout/", logout_view, name="logout"),
    path("auth/session/", session_view, name="session"),
    path("dashboard/", dashboard_view, name="dashboard"),
    path("leads/", leads_collection_view, name="leads"),
    path("leads/<int:lead_id>/", lead_update_view, name="lead-update"),
    path("leads/<int:lead_id>/notes/", lead_note_create_view, name="lead-note-create"),
]
