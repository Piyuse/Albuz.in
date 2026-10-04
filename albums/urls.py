from .views import AlbumListCreateView, PhotoUploadView
from django.urls import path

urlpatterns = [
    path("",AlbumListCreateView.as_view(),name="album-list-create"),
    path("<uuid:album_id>/photos/upload/",PhotoUploadView.as_view(),name="photo-upload"),
]
