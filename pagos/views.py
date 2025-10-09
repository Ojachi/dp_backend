from rest_framework import generics, status, filters
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Sum
from django.utils import timezone

from .models import Pago
from facturas.models import Factura
from .serializers import (
    PagoListSerializer, PagoDetailSerializer, 
    PagoCreateSerializer, PagoUpdateSerializer
)
from users.permissions import IsGerente, IsVendedor, IsRepartidor


class PagoListCreateView(generics.ListCreateAPIView):
    """Vista para listar y crear pagos"""
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['factura__numero_factura', 'factura__cliente__nombre', 'tipo_pago']
    ordering_fields = ['fecha_pago', 'valor_pagado']
    ordering = ['-fecha_pago']

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return PagoCreateSerializer
        return PagoListSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = Pago.objects.select_related('factura', 'factura__cliente', 'usuario_registro')
        
        # Filtrar según el rol del usuario
        if user.groups.filter(name='Gerente').exists():
            # Los gerentes ven todos los pagos
            pass
        elif user.groups.filter(name='Vendedor').exists():
            # Los vendedores solo ven pagos de sus facturas
            queryset = queryset.filter(factura__vendedor=user)
        elif user.groups.filter(name='Repartidor').exists():
            # Los repartidores solo ven pagos de sus facturas
            queryset = queryset.filter(factura__distribuidor=user)
        else:
            # Sin rol específico, no ve nada
            queryset = queryset.none()
        
        # Filtros adicionales
        factura_id = self.request.query_params.get('factura_id')
        if factura_id:
            queryset = queryset.filter(factura_id=factura_id)
            
        tipo_pago = self.request.query_params.get('tipo_pago')
        if tipo_pago:
            queryset = queryset.filter(tipo_pago=tipo_pago)
            
        fecha_desde = self.request.query_params.get('fecha_desde')
        if fecha_desde:
            queryset = queryset.filter(fecha_pago__date__gte=fecha_desde)
            
        fecha_hasta = self.request.query_params.get('fecha_hasta')
        if fecha_hasta:
            queryset = queryset.filter(fecha_pago__date__lte=fecha_hasta)
        
        return queryset

    def perform_create(self, serializer):
        user = self.request.user
        
        # Verificar permisos para crear pagos
        can_create_payment = (
            user.groups.filter(name='Gerente').exists() or
            user.groups.filter(name='Vendedor').exists() or
            user.groups.filter(name='Repartidor').exists()
        )
        
        if not can_create_payment:
            raise PermissionError("No tiene permisos para registrar pagos")
        
        # Verificar que puede registrar pago para esta factura específica
        factura_id = serializer.validated_data['factura_id']
        try:
            factura = Factura.objects.get(id=factura_id)
            
            # Vendedores solo pueden registrar pagos en sus facturas
            if user.groups.filter(name='Vendedor').exists():
                if factura.vendedor != user:
                    raise PermissionError("Solo puede registrar pagos en facturas asignadas a usted")
            
            # Repartidores solo pueden registrar pagos en sus facturas
            if user.groups.filter(name='Repartidor').exists():
                if factura.distribuidor != user:
                    raise PermissionError("Solo puede registrar pagos en facturas asignadas a usted")
        
        except Factura.DoesNotExist:
            raise ValueError("La factura especificada no existe")
        
        # Asignar el usuario que registra el pago
        serializer.save(usuario_registro=user, factura_id=factura_id)


class PagoDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Vista para ver, actualizar y eliminar pagos individuales"""
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return PagoUpdateSerializer
        return PagoDetailSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = Pago.objects.select_related('factura', 'factura__cliente', 'usuario_registro')
        
        # Filtrar según el rol del usuario
        if user.groups.filter(name='Gerente').exists():
            return queryset
        elif user.groups.filter(name='Vendedor').exists():
            return queryset.filter(factura__vendedor=user)
        elif user.groups.filter(name='Repartidor').exists():
            return queryset.filter(factura__distribuidor=user)
        else:
            return queryset.none()
    
    def perform_update(self, serializer):
        user = self.request.user
        pago = self.get_object()
        
        # Solo el usuario que registró el pago o un gerente pueden editarlo
        can_edit = (
            user.groups.filter(name='Gerente').exists() or
            pago.usuario_registro == user
        )
        
        if not can_edit:
            raise PermissionError("Solo puede editar pagos que usted mismo registró")
        
        serializer.save()
    
    def perform_destroy(self, instance):
        user = self.request.user
        
        # Solo gerentes o quien registró el pago pueden eliminarlo
        can_delete = (
            user.groups.filter(name='Gerente').exists() or
            instance.usuario_registro == user
        )
        
        if not can_delete:
            raise PermissionError("Solo puede eliminar pagos que usted mismo registró")
        
        instance.delete()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def historial_pagos_factura(request, factura_id):
    """Obtener historial de pagos de una factura específica"""
    user = request.user
    
    try:
        factura = Factura.objects.get(id=factura_id)
        
        # Verificar permisos para ver esta factura
        can_view = False
        if user.groups.filter(name='Gerente').exists():
            can_view = True
        elif user.groups.filter(name='Vendedor').exists():
            can_view = factura.vendedor == user
        elif user.groups.filter(name='Repartidor').exists():
            can_view = factura.distribuidor == user
        
        if not can_view:
            return Response(
                {'error': 'No tiene permisos para ver esta factura'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        pagos = Pago.objects.filter(factura=factura).order_by('-fecha_pago')
        serializer = PagoListSerializer(pagos, many=True)
        
        return Response({
            'factura': {
                'id': factura.id,
                'numero_factura': factura.numero_factura,
                'cliente': factura.cliente.nombre,
                'valor_total': factura.valor_total,
                'total_pagado': factura.total_pagado,
                'saldo_pendiente': factura.saldo_pendiente,
                'estado': factura.estado
            },
            'pagos': serializer.data,
            'total_pagos': pagos.count()
        })
        
    except Factura.DoesNotExist:
        return Response(
            {'error': 'Factura no encontrada'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def resumen_pagos_cliente(request, cliente_id):
    """Obtener resumen de pagos por cliente"""
    user = request.user
    
    # Solo gerentes pueden ver resúmenes por cliente
    if not user.groups.filter(name='Gerente').exists():
        return Response(
            {'error': 'Solo los gerentes pueden ver resúmenes por cliente'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Obtener todas las facturas del cliente
    facturas = Factura.objects.filter(cliente_id=cliente_id)
    
    if not facturas.exists():
        return Response(
            {'error': 'Cliente no encontrado o sin facturas'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Calcular estadísticas
    total_facturas = facturas.count()
    valor_total_facturas = facturas.aggregate(Sum('valor_total'))['valor_total__sum'] or 0
    
    pagos = Pago.objects.filter(factura__cliente_id=cliente_id)
    total_pagos = pagos.aggregate(Sum('valor_pagado'))['valor_pagado__sum'] or 0
    
    saldo_pendiente = valor_total_facturas - total_pagos
    
    facturas_por_estado = {
        'pendiente': facturas.filter(estado='pendiente').count(),
        'parcial': facturas.filter(estado='parcial').count(),
        'pagada': facturas.filter(estado='pagada').count(),
        'vencida': facturas.filter(estado='vencida').count(),
    }
    
    # Pagos recientes (últimos 10)
    pagos_recientes = pagos.order_by('-fecha_pago')[:10]
    pagos_serializer = PagoListSerializer(pagos_recientes, many=True)
    
    return Response({
        'cliente_id': cliente_id,
        'resumen': {
            'total_facturas': total_facturas,
            'valor_total_facturas': valor_total_facturas,
            'total_pagos': total_pagos,
            'saldo_pendiente': saldo_pendiente,
            'facturas_por_estado': facturas_por_estado
        },
        'pagos_recientes': pagos_serializer.data
    })


@api_view(['GET'])
@permission_classes([IsGerente])
def dashboard_pagos(request):
    """Dashboard con estadísticas de pagos - Solo para gerentes"""
    
    # Estadísticas generales de pagos
    total_pagos = Pago.objects.count()
    monto_total_pagos = Pago.objects.aggregate(Sum('valor_pagado'))['valor_pagado__sum'] or 0
    
    # Pagos por tipo
    pagos_por_tipo = {}
    for tipo, nombre in Pago.TIPOS_PAGO:
        count = Pago.objects.filter(tipo_pago=tipo).count()
        monto = Pago.objects.filter(tipo_pago=tipo).aggregate(Sum('valor_pagado'))['valor_pagado__sum'] or 0
        pagos_por_tipo[tipo] = {
            'nombre': nombre,
            'cantidad': count,
            'monto_total': monto
        }
    
    # Pagos del mes actual
    hoy = timezone.now()
    inicio_mes = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    pagos_mes = Pago.objects.filter(fecha_pago__gte=inicio_mes)
    
    pagos_mes_count = pagos_mes.count()
    pagos_mes_monto = pagos_mes.aggregate(Sum('valor_pagado'))['valor_pagado__sum'] or 0
    
    return Response({
        'estadisticas_generales': {
            'total_pagos': total_pagos,
            'monto_total_pagos': monto_total_pagos,
        },
        'pagos_mes_actual': {
            'cantidad': pagos_mes_count,
            'monto': pagos_mes_monto
        },
        'pagos_por_tipo': pagos_por_tipo
    })
