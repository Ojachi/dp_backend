from rest_framework import generics, filters
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied

from .models import Vendedor
from .serializers import (
    VendedorListSerializer, VendedorDetailSerializer, 
    VendedorCreateUpdateSerializer
)


class VendedorListCreateView(generics.ListCreateAPIView):
    """Vista para listar y crear vendedores - Solo gerentes pueden crear"""
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['codigo', 'zona', 'usuario__name', 'usuario__email']
    ordering_fields = ['codigo', 'zona', 'creado']
    ordering = ['codigo']
    
    def get_serializer_class(self):  # type: ignore[override]
        if self.request.method == 'POST':
            return VendedorCreateUpdateSerializer
        return VendedorListSerializer
    
    def get_queryset(self):  # type: ignore[override]
        user = self.request.user
        queryset = Vendedor.objects.select_related('usuario')
        
        # Filtrar según permisos
        if user.groups.filter(name='Gerente').exists():
            # Gerentes ven todos los vendedores
            pass
        elif user.groups.filter(name='Vendedor').exists():
            # Vendedores solo se ven a sí mismos
            queryset = queryset.filter(usuario=user)
        else:
            # Otros roles no ven vendedores
            queryset = queryset.none()
        
        # Filtros adicionales
        params = getattr(self.request, 'query_params', self.request.GET)
        zona = params.get('zona')
        if zona:
            queryset = queryset.filter(zona__icontains=zona)
        
        return queryset
    
    def perform_create(self, serializer):
        # Solo gerentes pueden crear vendedores
        if not self.request.user.groups.filter(name='Gerente').exists():
            raise PermissionDenied("Solo los gerentes pueden crear vendedores")
        serializer.save()


class VendedorDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Vista para ver, actualizar y eliminar vendedores"""
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):  # type: ignore[override]
        if self.request.method in ['PUT', 'PATCH']:
            return VendedorCreateUpdateSerializer
        return VendedorDetailSerializer
    
    def get_queryset(self):  # type: ignore[override]
        user = self.request.user
        queryset = Vendedor.objects.select_related('usuario')
        
        # Filtrar según permisos
        if user.groups.filter(name='Gerente').exists():
            return queryset
        elif user.groups.filter(name='Vendedor').exists():
            return queryset.filter(usuario=user)
        else:
            return queryset.none()
    
    def perform_update(self, serializer):
        # Solo gerentes pueden editar vendedores
        if not self.request.user.groups.filter(name='Gerente').exists():
            raise PermissionDenied("Solo los gerentes pueden editar vendedores")
        serializer.save()
    
    def perform_destroy(self, instance):
        # Solo gerentes pueden eliminar vendedores
        if not self.request.user.groups.filter(name='Gerente').exists():
            raise PermissionDenied("Solo los gerentes pueden eliminar vendedores")
        
        # Verificar que no tenga facturas asignadas
        if instance.usuario.facturas_vendedor.exists():
            raise PermissionDenied("No se puede eliminar un vendedor que tiene facturas asignadas")
        
        instance.delete()


 
