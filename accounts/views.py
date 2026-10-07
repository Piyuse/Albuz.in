from django.shortcuts import render
from .serializers import RegistrationSerializer,UserSerializer
from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAuthenticated
# Create your views here.

class RegisterView(generics.CreateAPIView):
    serializer_class=RegistrationSerializer
    permission_classes=[AllowAny]
    
class UserView(generics.RetrieveAPIView):
    serializer_class=UserSerializer
    permission_classes=[IsAuthenticated]
    
    def get_object(self):
        return self.request.user