from django.db import transaction
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import GoogleDriveConnection, GoogleOAuthState


class GoogleConnectionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        connected = GoogleDriveConnection.objects.filter(
            user=request.user,
        ).exists()

        response = Response({
            "connected": connected,
        })
        response["Cache-Control"] = "no-store"
        return response

    def delete(self, request):
        with transaction.atomic():
            # Cancel OAuth attempts started before disconnecting.
            GoogleOAuthState.objects.filter(
                user=request.user,
            ).delete()

            # Remove this user's encrypted Google credentials.
            GoogleDriveConnection.objects.filter(
                user=request.user,
            ).delete()

        response = Response({
            "connected": False,
        })
        response["Cache-Control"] = "no-store"
        return response