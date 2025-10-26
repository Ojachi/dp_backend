from rest_framework import generics, filters
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied

from .models import Distribuidor
from .serializers import (
    DistribuidorListSerializer, DistribuidorDetailSerializer, 
    DistribuidorCreateUpdateSerializer
)


class DistribuidorListCreateView(generics.ListCreateAPIView):
    """Vista para listar y crear distribuidores - Solo gerentes pueden crear"""
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['codigo', 'zona', 'usuario__name', 'usuario__email']
    ordering_fields = ['codigo', 'zona', 'creado']
    ordering = ['codigo']
    
    def get_serializer_class(self):  # type: ignore[override]
        if self.request.method == 'POST':
            return DistribuidorCreateUpdateSerializer
        return DistribuidorListSerializer
    
    def get_queryset(self):  # type: ignore[override]
        user = self.request.user
        queryset = Distribuidor.objects.select_related('usuario')
        
        # Filtrar según permisos
        if user.groups.filter(name='Gerente').exists():
            # Gerentes ven todos los distribuidores
            pass
        elif user.groups.filter(name='Distribuidor').exists():
            # Distribuidores solo se ven a sí mismos
            queryset = queryset.filter(usuario=user)
        else:
            # Otros roles no ven distribuidores
            queryset = queryset.none()
        
        # Filtros adicionales
        params = getattr(self.request, 'query_params', self.request.GET)
        zona = params.get('zona')
        if zona:
            queryset = queryset.filter(zona__icontains=zona)
        
        return queryset
    
    def perform_create(self, serializer):
        # Solo gerentes pueden crear distribuidores
        if not self.request.user.groups.filter(name='Gerente').exists():
            raise PermissionDenied("Solo los gerentes pueden crear distribuidores")
        serializer.save()


class DistribuidorDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Vista para ver, actualizar y eliminar distribuidores"""
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):  # type: ignore[override]
        if self.request.method in ['PUT', 'PATCH']:
            return DistribuidorCreateUpdateSerializer
        return DistribuidorDetailSerializer
    
    def get_queryset(self):  # type: ignore[override]
        user = self.request.user
        queryset = Distribuidor.objects.select_related('usuario')
        
        # Filtrar según permisos
        if user.groups.filter(name='Gerente').exists():
            return queryset
        elif user.groups.filter(name='Distribuidor').exists():
            return queryset.filter(usuario=user)
        else:
            return queryset.none()
    
    def perform_update(self, serializer):
        # Solo gerentes pueden editar distribuidores
        if not self.request.user.groups.filter(name='Gerente').exists():
            raise PermissionDenied("Solo los gerentes pueden editar distribuidores")
        serializer.save()
    
    def perform_destroy(self, instance):
        # Solo gerentes pueden eliminar distribuidores
        if not self.request.user.groups.filter(name='Gerente').exists():
            raise PermissionDenied("Solo los gerentes pueden eliminar distribuidores")
        
        # Verificar que no tenga facturas asignadas
        if instance.usuario.facturas_distribuidor.exists():
            raise PermissionDenied("No se puede eliminar un distribuidor que tiene facturas asignadas")
        
        instance.delete()
 
