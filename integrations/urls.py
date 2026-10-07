from django.urls import path

from .views import GoogleCallbackView, GoogleConnectStartView,GoogleDriveFolderListView
from .connection_views import GoogleConnectionView

urlpatterns = [
    
     path(
        "google/connect/",
        GoogleConnectStartView.as_view(),
        name="google-connect",
    ),
     path(
        "google/callback/",
        GoogleCallbackView.as_view(),
        name="google-callback",
    ),
     path(
    "google/folder-photos/",
    GoogleDriveFolderListView.as_view(),
    name="google-folder-photos",
),
     path(
    "google/connection/",
    GoogleConnectionView.as_view(),
    name="google-connection",
),
]