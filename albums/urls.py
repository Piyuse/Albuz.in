from .views import AlbumListCreateView, PhotoUploadView, AlbumPhotoListView, PhotoCopyView,BulkPhotoUploadView
from django.urls import path

urlpatterns = [
    path("",AlbumListCreateView.as_view(),name="album-list-create"),
    path("<uuid:album_id>/photos/upload/",PhotoUploadView.as_view(),name="photo-upload"),
    path("<uuid:album_id>/photos/",AlbumPhotoListView.as_view(),name="album-photo-list"),
    path("<uuid:album_id>/photos/copy/", PhotoCopyView.as_view(), name="photo-copy"),
    path("<uuid:album_id>/photos/bulk-upload/", BulkPhotoUploadView.as_view(), name="bulk-photo-upload"),
]
