from .views import AlbumListCreateView, PhotoReorderView,PhotoUploadView, AlbumPhotoListView, PhotoCopyView,BulkPhotoUploadView,ShareCreateView,ShareRevokeView,SharedAlbumPhotoListView,SharedPhotoCopyView,AlbumDetailView,AlbumPhotoDetailView
from django.urls import path

urlpatterns = [
    path("",AlbumListCreateView.as_view(),name="album-list-create"),
    path("<uuid:album_id>/photos/upload/",PhotoUploadView.as_view(),name="photo-upload"),
    path("<uuid:album_id>/photos/",AlbumPhotoListView.as_view(),name="album-photo-list"),
    path("<uuid:album_id>/photos/copy/", PhotoCopyView.as_view(), name="photo-copy"),
    path("<uuid:album_id>/photos/bulk-upload/", BulkPhotoUploadView.as_view(), name="bulk-photo-upload"),
    path("<uuid:album_id>/shares/",ShareCreateView.as_view(),name="share-create"),
    path("<uuid:album_id>/shares/<uuid:share_id>/",ShareRevokeView.as_view(),name="share-revoke",),
    path("shared/<str:token>/photos/",SharedAlbumPhotoListView.as_view(),name="shared-album-photos",),
    path("shared/<str:token>/photos/copy/",SharedPhotoCopyView.as_view(),name="shared-photo-copy"),
    path("<uuid:album_id>/",AlbumDetailView.as_view(),name="album-detail",)  ,
    path("<uuid:album_id>/photos/<uuid:photo_id>/",AlbumPhotoDetailView.as_view(),name="album-photo-detail",),
    path("<uuid:album_id>/photos/reorder/",PhotoReorderView.as_view(),name="photo-reorder",),
]
