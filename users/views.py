from rest_framework.views import APIView
from rest_framework.generics import RetrieveUpdateDestroyAPIView
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from django.contrib.auth import logout
from .serializers import (
    CustomUserSerializer,
)
from .models import CustomUser
from .permissions import IsGerente
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q

from rest_framework.generics import ListCreateAPIView
from django.core.exceptions import ValidationError as DjangoValidationError
from django.contrib.auth.password_validation import validate_password

class CustomUserListView(ListCreateAPIView):
    serializer_class = CustomUserSerializer
    queryset = CustomUser.objects.all()
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsGerente]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        # Buscar por texto en nombre, username, email, first_name, last_name
        buscar = params.get('buscar')
        if buscar:
            buscar = buscar.strip()
            qs = qs.filter(
                Q(name__icontains=buscar) |
                Q(username__icontains=buscar) |
                Q(email__icontains=buscar) |
                Q(first_name__icontains=buscar) |
                Q(last_name__icontains=buscar)
            )

        # Filtrar por estado activo
        is_active = params.get('is_active')
        if is_active in ('true', 'false', 'True', 'False', '1', '0'):
            qs = qs.filter(is_active=is_active.lower() in ('true', '1'))

        # Filtrar por rol (grupo): gerente | vendedor | distribuidor
        rol = params.get('rol')
        if rol:
            mapa = {
                'gerente': 'Gerente',
                'vendedor': 'Vendedor',
                'distribuidor': 'Distribuidor'
            }
            nombre_grupo = mapa.get(rol.lower())
            if nombre_grupo:
                qs = qs.filter(groups__name=nombre_grupo)

        return qs

class CustomUserRetrieveUpdateDestroyView(RetrieveUpdateDestroyAPIView):
    serializer_class = CustomUserSerializer
    queryset = CustomUser.objects.all()
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsGerente]

    def destroy(self, request, *args, **kwargs):  # type: ignore[override]
        instance = self.get_object()
        # Evitar que un usuario se elimine a sí mismo
        if getattr(request.user, 'pk', None) == getattr(instance, 'pk', None):
            return Response({
                'detail': 'No puede eliminar su propio usuario.'
            }, status=status.HTTP_400_BAD_REQUEST)
        return super().destroy(request, *args, **kwargs)

    

class ValidateEmailView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsGerente]

    def get(self, request):
        email = request.query_params.get('email', '').strip()
        exclude_id = request.query_params.get('exclude_id')
        if not email:
            return Response({"valid": False, "message": "Email es requerido"}, status=status.HTTP_400_BAD_REQUEST)
        qs = CustomUser.objects.filter(email__iexact=email)
        if exclude_id:
            qs = qs.exclude(pk=exclude_id)
        if qs.exists():
            return Response({"valid": False, "message": "El email ya está en uso"}, status=status.HTTP_200_OK)
        return Response({"valid": True, "message": "Disponible"}, status=status.HTTP_200_OK)

class ValidateUsernameView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsGerente]

    def get(self, request):
        username = request.query_params.get('username', '').strip()
        exclude_id = request.query_params.get('exclude_id')
        if not username:
            return Response({"valid": False, "message": "Username es requerido"}, status=status.HTTP_400_BAD_REQUEST)
        qs = CustomUser.objects.filter(username__iexact=username)
        if exclude_id:
            qs = qs.exclude(pk=exclude_id)
        if qs.exists():
            return Response({"valid": False, "message": "El nombre de usuario ya está en uso"}, status=status.HTTP_200_OK)
        return Response({"valid": True, "message": "Disponible"}, status=status.HTTP_200_OK)

class ResetUserPasswordView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsGerente]

    def post(self, request, pk):
        user = get_object_or_404(CustomUser, pk=pk)
        password = request.data.get('password', '')
        if not password:
            return Response({"error": "La contraseña es requerida"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            validate_password(password, user)
        except DjangoValidationError as e:
            return Response({"error": e.messages}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(password)
        user.save()
        return Response({"message": "Contraseña restablecida correctamente"}, status=status.HTTP_200_OK)

    

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def current_user_view(request):
    """
    Vista simple para obtener información básica del usuario logueado
    """
    user = request.user
    
    # Obtener roles del usuario
    roles = []
    if user.groups.exists():
        roles = [group.name for group in user.groups.all()]
    
    return Response({
        'id': user.id,
        'email': user.email,
        'username': user.username,
        'name': getattr(user, 'name', ''),
        'first_name': user.first_name,
        'last_name': user.last_name,
        'full_name': user.get_full_name(),
        'roles': roles,
        'is_gerente': 'Gerente' in roles,
        'is_vendedor': 'Vendedor' in roles,
        'is_distribuidor': 'Distribuidor' in roles,
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """
    Vista para cerrar sesión del usuario
    """
    try:
        # Si usa tokens, eliminar el token
        if hasattr(request.user, 'auth_token'):
            request.user.auth_token.delete()
        
        # Cerrar sesión de Django
        logout(request)
        
        return Response(
            {"message": "Sesión cerrada exitosamente"}, 
            status=status.HTTP_200_OK
        )
    except Exception as e:
        return Response(
            {"error": f"Error al cerrar sesión: {str(e)}"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
