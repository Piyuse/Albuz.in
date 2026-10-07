from django.urls import path

from .views import GoogleCallbackView, GoogleConnectStartView,DriveFolderPhotoListView


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
    DriveFolderPhotoListView.as_view(),
    name="google-folder-photos",
),
]