from .views import AlbumListCreateView
from django.urls import path

urlpatterns = [
    path("",AlbumListCreateView.as_view(),name="album-list-create"),
]
