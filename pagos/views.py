import csv
from typing import Type, cast

from django.db.models import QuerySet, Sum
from django.http import StreamingHttpResponse
from django.utils import timezone
from rest_framework import filters, generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.serializers import Serializer
from rest_framework.response import Response

from facturas.models import Factura
from users.permissions import IsGerente, IsVendedor

from .models import Pago
from .serializers import (
    PagoListSerializer,
    PagoDetailSerializer,
    PagoCreateSerializer,
    PagoUpdateSerializer,
    PagoConfirmSerializer,
)
from .services import (
    filtrar_pagos_por_usuario,
    generar_filas_exportacion,
    obtener_estadisticas_dashboard,
    obtener_metodos_pago,
)


class PagoListCreateView(generics.ListCreateAPIView):
    """Vista para listar y crear pagos"""
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['factura__numero_factura', 'factura__cliente__nombre', 'tipo_pago']
    ordering_fields = ['fecha_pago', 'valor_pagado']
    ordering = ['-fecha_pago']

    def get_serializer_class(self) -> Type[Serializer]:  # type: ignore[override]
        if self.request.method == 'POST':
            return PagoCreateSerializer
        return PagoListSerializer

    def get_queryset(self) -> QuerySet[Pago]:  # type: ignore[override]
        request = cast(Request, self.request)
        return filtrar_pagos_por_usuario(request.user, request.query_params)


class PagoDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Vista para ver, actualizar y eliminar pagos individuales"""
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self) -> Type[Serializer]:  # type: ignore[override]
        if self.request.method in ['PUT', 'PATCH']:
            return PagoUpdateSerializer
        return PagoDetailSerializer

    def get_queryset(self) -> QuerySet[Pago]:  # type: ignore[override]
        user = self.request.user
        queryset = Pago.objects.select_related('factura', 'factura__cliente', 'usuario_registro')
        
        # Filtrar según el rol del usuario
        if user.groups.filter(name='Gerente').exists():
            return queryset
        elif user.groups.filter(name='Vendedor').exists():
            return queryset.filter(factura__vendedor=user)
        elif user.groups.filter(name='Distribuidor').exists():
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
            raise PermissionDenied("Solo puede editar pagos que usted mismo registró")
        
        serializer.save()
    
    def perform_destroy(self, instance):
        user = self.request.user
        
        # Solo gerentes o quien registró el pago pueden eliminarlo
        can_delete = (
            user.groups.filter(name='Gerente').exists() or
            instance.usuario_registro == user
        )
        
        if not can_delete:
            raise PermissionDenied("Solo puede eliminar pagos que usted mismo registró")
        
        instance.delete()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def historial_pagos_factura(request, factura_id):
    """Obtener historial de pagos de una factura específica"""
    user = request.user
    
    try:
        factura: Factura = Factura.objects.get(id=factura_id)
        
        # Verificar permisos para ver esta factura
        can_view = False
        if user.groups.filter(name='Gerente').exists():
            can_view = True
        elif user.groups.filter(name='Vendedor').exists():
            can_view = factura.vendedor == user
        elif user.groups.filter(name='Distribuidor').exists():
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
                'id': factura.pk,
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
    
    # Considerar solo pagos confirmados para consistencia con saldos
    pagos = Pago.objects.filter(factura__cliente_id=cliente_id, estado='confirmado')
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
    drf_request = cast(Request, request)
    queryset = filtrar_pagos_por_usuario(drf_request.user, drf_request.query_params)
    data = obtener_estadisticas_dashboard(queryset)
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_metodos_pago(request):
    """Listado de métodos de pago disponibles."""
    return Response(obtener_metodos_pago())


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def registrar_pago_factura(request, factura_id: int):
    """Registra un pago asociado a una factura específica."""
    payload = request.data.copy()
    payload['factura_id'] = factura_id

    serializer = PagoCreateSerializer(data=payload, context={'request': request})
    serializer.is_valid(raise_exception=True)
    pago = serializer.save()

    detalle_serializer = PagoDetailSerializer(pago, context={'request': request})
    return Response(detalle_serializer.data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsGerente])
def confirmar_pago(request, pk: int):
    """Confirma un pago registrado previamente y aplica su efecto en la factura."""
    try:
        pago = Pago.objects.select_related('factura').get(pk=pk)
    except Pago.DoesNotExist:
        return Response({'error': 'Pago no encontrado'}, status=status.HTTP_404_NOT_FOUND)

    # No permitir reconfirmar o confirmar anulados
    if pago.estado == 'confirmado':
        return Response({'detail': 'El pago ya está confirmado'}, status=status.HTTP_400_BAD_REQUEST)
    if pago.estado == 'anulado':
        return Response({'detail': 'No es posible confirmar un pago anulado'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = PagoConfirmSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    # Validar saldo disponible al confirmar
    pago.estado = 'confirmado'
    pago.usuario_confirmacion = request.user
    pago.fecha_confirmacion = timezone.now()

    try:
        pago.save()
    except Exception as exc:  # Validación de exceder saldo, etc.
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    detalle_serializer = PagoDetailSerializer(pago, context={'request': request})
    return Response(detalle_serializer.data, status=status.HTTP_200_OK)


class Echo:
    """Helper para StreamingHttpResponse con csv.writer."""

    @staticmethod
    def write(value):  # pragma: no cover - comportamiento trivial
        return value


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def exportar_pagos(request):
    """Exporta los pagos según filtros aplicados."""
    formato = request.query_params.get('formato', 'excel').lower()
    if formato not in {'excel', 'csv'}:
        return Response({'error': 'Formato no soportado'}, status=status.HTTP_400_BAD_REQUEST)

    drf_request = cast(Request, request)
    queryset = filtrar_pagos_por_usuario(drf_request.user, drf_request.query_params).order_by('-fecha_pago')
    filas = generar_filas_exportacion(queryset)

    pseudo_buffer = Echo()
    writer = csv.writer(pseudo_buffer)

    response = StreamingHttpResponse(
        (writer.writerow(fila) for fila in filas),
        content_type='application/vnd.ms-excel',
    )
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    response['Content-Disposition'] = f'attachment; filename="reporte_pagos_{timestamp}.csv"'
    return response
