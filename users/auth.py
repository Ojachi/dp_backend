from rest_framework.views import APIView
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.models import Group
from .models import CustomUser
from .serializers import (
    CustomUserSerializer,
    CustomUserLoginSerializer,
    ChangePasswordSerializer
)
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated, AllowAny

class CustomUserRegisterView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = CustomUserSerializer

    def post(self, request):
        data = request.data.copy()
        # Si no se envía ningún rol explícito, por defecto asignar Vendedor
        role_flags = [
            data.get('is_gerente'),
            data.get('is_vendedor'),
            data.get('is_distribuidor')
        ]
        if not any(str(v).lower() in ('true', '1') for v in role_flags):
            data['is_vendedor'] = True

        serializer = CustomUserSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        # Si serializer.save() retorna una lista, tomar el primer usuario
        if isinstance(user, list):
            user = user[0]
        # El serializer ya asigna el grupo basado en las banderas de rol
        return Response(CustomUserSerializer(user).data, status=status.HTTP_201_CREATED)

class CustomUserLoginView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = CustomUserLoginSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]
        user = authenticate(request, username=email, password=password)
        if user:
            token, created = Token.objects.get_or_create(user=user)
            return Response({
                "message": "Login successful",
                "token": token.key,
                "userid": user.id,
                "email": user.email
            }, status=status.HTTP_200_OK)
        return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)

class ChangePasswordView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ChangePasswordSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        if not user.check_password(serializer.validated_data["old_password"]):
            return Response({"error": "Old password is incorrect"}, status=status.HTTP_400_BAD_REQUEST)
        validate_password(serializer.validated_data["new_password"], user)
        user.set_password(serializer.validated_data["new_password"])
        user.save()
        return Response({"message": "Password changed successfully"}, status=status.HTTP_200_OK)
