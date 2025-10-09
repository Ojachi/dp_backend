from rest_framework import generics, filters, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Sum, Count

from .models import Distribuidor
from .serializers import (
    DistribuidorListSerializer, DistribuidorDetailSerializer, 
    DistribuidorCreateUpdateSerializer
)
from users.permissions import IsGerente


class DistribuidorListCreateView(generics.ListCreateAPIView):
    """Vista para listar y crear distribuidores - Solo gerentes pueden crear"""
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['codigo', 'zona', 'usuario__name', 'usuario__email']
    ordering_fields = ['codigo', 'zona', 'creado']
    ordering = ['codigo']
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return DistribuidorCreateUpdateSerializer
        return DistribuidorListSerializer
    
    def get_queryset(self):
        user = self.request.user
        queryset = Distribuidor.objects.select_related('usuario')
        
        # Filtrar según permisos
        if user.groups.filter(name='Gerente').exists():
            # Gerentes ven todos los distribuidores
            pass
        elif user.groups.filter(name='Repartidor').exists():
            # Distribuidores solo se ven a sí mismos
            queryset = queryset.filter(usuario=user)
        else:
            # Otros roles no ven distribuidores
            queryset = queryset.none()
        
        # Filtros adicionales
        zona = self.request.query_params.get('zona')
        if zona:
            queryset = queryset.filter(zona__icontains=zona)
        
        return queryset
    
    def perform_create(self, serializer):
        # Solo gerentes pueden crear distribuidores
        if not self.request.user.groups.filter(name='Gerente').exists():
            raise PermissionError("Solo los gerentes pueden crear distribuidores")
        serializer.save()


class DistribuidorDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Vista para ver, actualizar y eliminar distribuidores"""
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return DistribuidorCreateUpdateSerializer
        return DistribuidorDetailSerializer
    
    def get_queryset(self):
        user = self.request.user
        queryset = Distribuidor.objects.select_related('usuario')
        
        # Filtrar según permisos
        if user.groups.filter(name='Gerente').exists():
            return queryset
        elif user.groups.filter(name='Repartidor').exists():
            return queryset.filter(usuario=user)
        else:
            return queryset.none()
    
    def perform_update(self, serializer):
        # Solo gerentes pueden editar distribuidores
        if not self.request.user.groups.filter(name='Gerente').exists():
            raise PermissionError("Solo los gerentes pueden editar distribuidores")
        serializer.save()
    
    def perform_destroy(self, instance):
        # Solo gerentes pueden eliminar distribuidores
        if not self.request.user.groups.filter(name='Gerente').exists():
            raise PermissionError("Solo los gerentes pueden eliminar distribuidores")
        
        # Verificar que no tenga facturas asignadas
        if instance.usuario.facturas_distribuidor.exists():
            raise ValueError("No se puede eliminar un distribuidor que tiene facturas asignadas")
        
        instance.delete()


@api_view(['GET'])
@permission_classes([IsGerente])
def estadisticas_distribuidores(request):
    """Estadísticas de distribuidores - Solo gerentes"""
    
    distribuidores = Distribuidor.objects.annotate(
        total_facturas=Count('usuario__facturas_distribuidor'),
        facturas_pendientes=Count('usuario__facturas_distribuidor', 
                                 filter=Q(usuario__facturas_distribuidor__estado__in=['pendiente', 'parcial'])),
        cartera_total=Sum('usuario__facturas_distribuidor__valor_total',
                         filter=Q(usuario__facturas_distribuidor__estado__in=['pendiente', 'parcial']))
    )
    
    estadisticas = []
    for distribuidor in distribuidores:
        estadisticas.append({
            'id': distribuidor.id,
            'codigo': distribuidor.codigo,
            'nombre': distribuidor.usuario.get_full_name(),
            'zona': distribuidor.zona,
            'total_facturas': distribuidor.total_facturas,
            'facturas_pendientes': distribuidor.facturas_pendientes,
            'cartera_pendiente': distribuidor.cartera_total or 0
        })
    
    return Response({
        'distribuidores': estadisticas,
        'total_distribuidores': len(estadisticas)
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def mi_perfil_distribuidor(request):
    """Obtener perfil del distribuidor autenticado"""
    user = request.user
    
    # Verificar que sea distribuidor
    if not user.groups.filter(name='Repartidor').exists():
        return Response(
            {'error': 'Solo los distribuidores pueden acceder a este endpoint'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        distribuidor = Distribuidor.objects.get(usuario=user)
        serializer = DistribuidorDetailSerializer(distribuidor)
        return Response(serializer.data)
    except Distribuidor.DoesNotExist:
        return Response(
            {'error': 'No tiene un perfil de distribuidor asignado'},
            status=status.HTTP_404_NOT_FOUND
        )
