from django.shortcuts import render
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from .serializers import AlbumSerializer
from .models import Album
# Create your views here.
class AlbumListCreateView(generics.ListCreateAPIView):
    serializer_class = AlbumSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Album.objects.filter(owner=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)