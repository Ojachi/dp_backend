from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q, Count, Sum
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from .models import Cliente
from .serializers import (
    ClienteListSerializer,
    ClienteDetailSerializer,
    ClienteCreateUpdateSerializer
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
    
    @action(detail=False, methods=['get'])
    def estadisticas(self, request):
        """Estadísticas generales de clientes"""
        queryset = self.get_queryset()
        
        stats = queryset.aggregate(
            total_clientes=Count('id'),
            clientes_con_facturas=Count('id', filter=Q(facturas__isnull=False)),
            valor_total_facturado=Sum('facturas__valor_total'),
            saldo_pendiente=Sum('facturas__saldo_pendiente',
                               filter=Q(facturas__estado__in=['pendiente', 'parcial']))
        )
        
        # Top 5 clientes por valor facturado
        top_clientes = queryset.annotate(
            valor_facturado=Sum('facturas__valor_total')
        ).filter(
            valor_facturado__gt=0
        ).order_by('-valor_facturado')[:5].values(
            'id', 'nombre', 'valor_facturado'
        )
        
        return Response({
            'estadisticas_generales': {
                'total_clientes': stats['total_clientes'] or 0,
                'clientes_con_facturas': stats['clientes_con_facturas'] or 0,
                'valor_total_facturado': stats['valor_total_facturado'] or 0,
                'saldo_pendiente': stats['saldo_pendiente'] or 0
            },
            'top_clientes': list(top_clientes)
        })
    
    @action(detail=True, methods=['get'])
    def historial_pagos(self, request, pk=None):
        """Historial de pagos de un cliente"""
        cliente = self.get_object()
        
        # Obtener pagos a través de las facturas del cliente
        from pagos.models import Pago
        pagos = Pago.objects.filter(
            factura__cliente=cliente
        ).select_related('factura', 'creador').order_by('-fecha_pago')[:20]
        
        pagos_data = [{
            'id': pago.pk,
            'factura_numero': pago.factura.numero_factura,
            'monto': pago.monto,
            'tipo_pago': pago.get_tipo_pago_display(),
            'fecha_pago': pago.fecha_pago,
            'observaciones': pago.observaciones,
            'creador': pago.creador.get_full_name() if pago.creador else None
        } for pago in pagos]
        
        return Response({
            'cliente': cliente.nombre,
            'historial_pagos': pagos_data
        })
