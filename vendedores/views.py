from rest_framework import generics, filters, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Sum, Count

from .models import Vendedor
from .serializers import (
    VendedorListSerializer, VendedorDetailSerializer, 
    VendedorCreateUpdateSerializer
)
from users.permissions import IsGerente


class VendedorListCreateView(generics.ListCreateAPIView):
    """Vista para listar y crear vendedores - Solo gerentes pueden crear"""
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['codigo', 'zona', 'usuario__name', 'usuario__email']
    ordering_fields = ['codigo', 'zona', 'creado']
    ordering = ['codigo']
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return VendedorCreateUpdateSerializer
        return VendedorListSerializer
    
    def get_queryset(self):
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
        zona = self.request.query_params.get('zona')
        if zona:
            queryset = queryset.filter(zona__icontains=zona)
        
        return queryset
    
    def perform_create(self, serializer):
        # Solo gerentes pueden crear vendedores
        if not self.request.user.groups.filter(name='Gerente').exists():
            raise PermissionError("Solo los gerentes pueden crear vendedores")
        serializer.save()


class VendedorDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Vista para ver, actualizar y eliminar vendedores"""
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return VendedorCreateUpdateSerializer
        return VendedorDetailSerializer
    
    def get_queryset(self):
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
            raise PermissionError("Solo los gerentes pueden editar vendedores")
        serializer.save()
    
    def perform_destroy(self, instance):
        # Solo gerentes pueden eliminar vendedores
        if not self.request.user.groups.filter(name='Gerente').exists():
            raise PermissionError("Solo los gerentes pueden eliminar vendedores")
        
        # Verificar que no tenga facturas asignadas
        if instance.usuario.facturas_vendedor.exists():
            raise ValueError("No se puede eliminar un vendedor que tiene facturas asignadas")
        
        instance.delete()


@api_view(['GET'])
@permission_classes([IsGerente])
def estadisticas_vendedores(request):
    """Estadísticas de vendedores - Solo gerentes"""
    
    vendedores = Vendedor.objects.annotate(
        total_facturas=Count('usuario__facturas_vendedor'),
        facturas_pendientes=Count('usuario__facturas_vendedor', 
                                 filter=Q(usuario__facturas_vendedor__estado__in=['pendiente', 'parcial'])),
        cartera_pendiente=Sum('usuario__facturas_vendedor__saldo_pendiente',
                             filter=Q(usuario__facturas_vendedor__estado__in=['pendiente', 'parcial']))
    )
    
    estadisticas = []
    for vendedor in vendedores:
        estadisticas.append({
            'id': vendedor.id,
            'codigo': vendedor.codigo,
            'nombre': vendedor.usuario.get_full_name(),
            'zona': vendedor.zona,
            'total_facturas': vendedor.total_facturas,
            'facturas_pendientes': vendedor.facturas_pendientes,
            'cartera_pendiente': vendedor.cartera_pendiente or 0
        })
    
    return Response({
        'vendedores': estadisticas,
        'total_vendedores': len(estadisticas)
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def mi_perfil_vendedor(request):
    """Obtener perfil del vendedor autenticado"""
    user = request.user
    
    # Verificar que sea vendedor
    if not user.groups.filter(name='Vendedor').exists():
        return Response(
            {'error': 'Solo los vendedores pueden acceder a este endpoint'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        vendedor = Vendedor.objects.get(usuario=user)
        serializer = VendedorDetailSerializer(vendedor)
        return Response(serializer.data)
    except Vendedor.DoesNotExist:
        return Response(
            {'error': 'No tiene un perfil de vendedor asignado'},
            status=status.HTTP_404_NOT_FOUND
        )
