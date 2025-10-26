from rest_framework import viewsets, permissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from .models import Cliente, Poblacion, ClienteSucursal
from .serializers import (
    ClienteListSerializer,
    ClienteDetailSerializer,
    ClienteCreateUpdateSerializer,
    PoblacionSerializer,
    ClienteSucursalSerializer,
)

class ClienteViewSet(viewsets.ModelViewSet):
    queryset = Cliente.objects.select_related('creador').prefetch_related('facturas')
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['creado']
    search_fields = ['nombre', 'direccion', 'telefono', 'email']
    ordering_fields = ['nombre', 'creado', 'actualizado']
    ordering = ['-creado']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ClienteListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return ClienteCreateUpdateSerializer
        else:
            return ClienteDetailSerializer
    
    def get_permissions(self):
        """Permisos basados en grupos"""
        permission_classes = [permissions.IsAuthenticated]
        
        if self.action in ['destroy']:
            # Solo administradores pueden eliminar
            from users.permissions import IsAdministrador
            permission_classes.append(IsAdministrador)
        elif self.action in ['create', 'update', 'partial_update']:
            # Administradores y vendedores pueden crear/editar
            from users.permissions import IsAdministradorOrVendedor
            permission_classes.append(IsAdministradorOrVendedor)
        
        return [permission() for permission in permission_classes]
    
    def perform_create(self, serializer):
        """Asignar creador al crear cliente"""
        serializer.save(creador=self.request.user)


class PoblacionViewSet(viewsets.ModelViewSet):
    queryset = Poblacion.objects.select_related('vendedor', 'distribuidor')
    serializer_class = PoblacionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['nombre']
    ordering_fields = ['nombre']
    ordering = ['nombre']


class ClienteSucursalViewSet(viewsets.ModelViewSet):
    queryset = ClienteSucursal.objects.select_related('cliente', 'poblacion')
    serializer_class = ClienteSucursalSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['cliente', 'poblacion', 'activo', 'condicion_pago']
    search_fields = ['codigo', 'cliente__nombre', 'poblacion__nombre']
    ordering_fields = ['codigo', 'creado']
    ordering = ['-creado']
