from django.urls import path

from .views import GoogleCallbackView, GoogleConnectStartView


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
]