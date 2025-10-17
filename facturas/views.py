from datetime import timedelta
from typing import Any, Type, cast

from django.db.models import QuerySet
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import Serializer

from .models import Factura, FacturaImportacion
from .serializers import (
    FacturaCreateSerializer,
    FacturaDetailSerializer,
    FacturaImportacionSerializer,
    FacturaListSerializer,
    FacturaUpdateSerializer,
)
from .services import (
    confirmar_importacion_facturas,
    generar_vista_previa,
    obtener_historial_importaciones,
    validar_archivo_facturas,
)
from users.permissions import IsGerente, IsVendedor, IsRepartidor


class FacturaPendientesPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 200


class FacturaListCreateView(generics.ListCreateAPIView):
    """Vista para listar y crear facturas"""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['estado', 'cliente', 'vendedor', 'distribuidor', 'tipo', 'valor_total']
    search_fields = ['numero_factura', 'cliente__nombre', 'observaciones']
    ordering_fields = ['fecha_emision', 'fecha_vencimiento', 'valor_total', 'estado']
    ordering = ['-fecha_emision']

    def get_serializer_class(self) -> Type[Serializer]:  # type: ignore[override]
        if self.request.method == 'POST':
            return FacturaCreateSerializer
        return FacturaListSerializer

    def get_queryset(self) -> QuerySet[Factura]:  # type: ignore[override]
        request = cast(Request, self.request)
        user = request.user
        
        # Actualizar automáticamente facturas vencidas antes de consultar
        Factura.actualizar_estados_vencidas()
        
        queryset = Factura.objects.select_related('cliente', 'vendedor', 'distribuidor')
        
        # Filtrar según el rol del usuario
        if user.groups.filter(name='Gerente').exists():
            # Los gerentes ven todas las facturas
            pass
        elif user.groups.filter(name='Vendedor').exists():
            # Los vendedores solo ven sus facturas asignadas
            queryset = queryset.filter(vendedor=user)
        elif user.groups.filter(name='Distribuidor').exists():
            # Los distribuidores solo ven sus facturas asignadas
            queryset = queryset.filter(distribuidor=user)
        else:
            # Sin rol específico, no ve nada
            queryset = queryset.none()
        
        # Filtros adicionales por parámetros de query
        estado = request.query_params.get('estado')
        if estado:
            queryset = queryset.filter(estado=estado)
            
        fecha_desde = request.query_params.get('fecha_desde')
        if fecha_desde:
            queryset = queryset.filter(fecha_emision__gte=fecha_desde)
            
        fecha_hasta = request.query_params.get('fecha_hasta')
        if fecha_hasta:
            queryset = queryset.filter(fecha_emision__lte=fecha_hasta)
        
        # Filtros por fecha de vencimiento (soporte para UI)
        fecha_venc_desde = request.query_params.get('fecha_vencimiento__gte')
        if fecha_venc_desde:
            queryset = queryset.filter(fecha_vencimiento__gte=fecha_venc_desde)
        fecha_venc_hasta = request.query_params.get('fecha_vencimiento__lte')
        if fecha_venc_hasta:
            queryset = queryset.filter(fecha_vencimiento__lte=fecha_venc_hasta)

        vencidas = request.query_params.get('vencidas')
        if vencidas and vencidas.lower() == 'true':
            queryset = queryset.filter(
                fecha_vencimiento__lt=timezone.now().date(),
                estado__in=['pendiente', 'parcial']
            )
        
        return queryset

    def perform_create(self, serializer):
        # Solo los gerentes pueden crear facturas
        if not self.request.user.groups.filter(name='Gerente').exists():
            raise PermissionDenied("Solo los gerentes pueden crear facturas")
        serializer.save()


class FacturaDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Vista para ver, actualizar y eliminar facturas individuales"""
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self) -> Type[Serializer]:  # type: ignore[override]
        if self.request.method in ['PUT', 'PATCH']:
            return FacturaUpdateSerializer
        return FacturaDetailSerializer

    def get_queryset(self) -> QuerySet[Factura]:  # type: ignore[override]
        request = cast(Request, self.request)
        user = request.user
        
        # Actualizar automáticamente facturas vencidas antes de consultar
        Factura.actualizar_estados_vencidas()
        
        queryset = Factura.objects.select_related('cliente', 'vendedor', 'distribuidor')
        
        # Filtrar según el rol del usuario
        if user.groups.filter(name='Gerente').exists():
            return queryset
        elif user.groups.filter(name='Vendedor').exists():
            return queryset.filter(vendedor=user)
        elif user.groups.filter(name='Distribuidor').exists():
            return queryset.filter(distribuidor=user)
        else:
            return queryset.none()
    
    def perform_update(self, serializer):
        # Solo los gerentes pueden editar facturas
        if not self.request.user.groups.filter(name='Gerente').exists():
            raise PermissionDenied("Solo los gerentes pueden editar facturas")
        serializer.save()
    
    def perform_destroy(self, instance):
        # Solo los gerentes pueden eliminar facturas
        if not self.request.user.groups.filter(name='Gerente').exists():
            raise PermissionDenied("Solo los gerentes pueden eliminar facturas")
        
        # No permitir eliminar facturas que ya tienen pagos
        if instance.pagos.exists():
            raise ValueError("No se puede eliminar una factura que ya tiene pagos registrados")
        
        instance.delete()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def facturas_vencidas(request):
    """Endpoint para obtener facturas vencidas"""
    user = request.user
    
    # Construir queryset base según permisos
    queryset = Factura.objects.select_related('cliente', 'vendedor', 'distribuidor')
    
    if user.groups.filter(name='Gerente').exists():
        pass  # Ve todas
    elif user.groups.filter(name='Vendedor').exists():
        queryset = queryset.filter(vendedor=user)
    elif user.groups.filter(name='Distribuidor').exists():
        queryset = queryset.filter(distribuidor=user)
    else:
        queryset = queryset.none()
    
    # Filtrar solo facturas vencidas
    facturas_vencidas = queryset.filter(
        fecha_vencimiento__lt=timezone.now().date(),
        estado__in=['pendiente', 'parcial', 'vencida']  # Incluye 'vencida' ya en BD
    ).order_by('fecha_vencimiento')
    
    serializer = FacturaListSerializer(facturas_vencidas, many=True)
    
    return Response({
        'count': facturas_vencidas.count(),
        'facturas': serializer.data
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_facturas(request):
    """Dashboard con estadísticas de facturas"""
    user = request.user
    
    # Solo gerentes pueden ver el dashboard completo
    if not user.groups.filter(name='Gerente').exists():
        return Response(
            {'error': 'Solo los gerentes pueden acceder al dashboard'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    queryset = Factura.objects.all()
    
    # Estadísticas generales
    total_facturas = queryset.count()
    facturas_pendientes = queryset.filter(estado='pendiente').count()
    facturas_parciales = queryset.filter(estado='parcial').count()
    facturas_pagadas = queryset.filter(estado='pagada').count()
    facturas_vencidas = queryset.filter(
        fecha_vencimiento__lt=timezone.now().date(),
        estado__in=['pendiente', 'parcial']
    ).count()
    
    # Montos
    from django.db.models import Sum, Case, When, DecimalField
    montos = queryset.aggregate(
        total_cartera=Sum('valor_total'),
        total_pendiente=Sum(
            Case(
                When(estado__in=['pendiente', 'parcial'], then='valor_total'),
                default=0,
                output_field=DecimalField()
            )
        )
    )
    
    return Response({
        'estadisticas': {
            'total_facturas': total_facturas,
            'facturas_pendientes': facturas_pendientes,
            'facturas_parciales': facturas_parciales,
            'facturas_pagadas': facturas_pagadas,
            'facturas_vencidas': facturas_vencidas,
        },
        'montos': {
            'total_cartera': montos['total_cartera'] or 0,
            'total_pendiente': montos['total_pendiente'] or 0,
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def facturas_pendientes(request: Request):
    """Facturas pendientes o vencidas con filtros de días y cliente."""

    queryset = Factura.objects.select_related('cliente', 'vendedor', 'distribuidor')
    user = request.user

    if user.groups.filter(name='Gerente').exists():
        pass
    elif user.groups.filter(name='Vendedor').exists():
        queryset = queryset.filter(vendedor=user)
    elif user.groups.filter(name='Distribuidor').exists():
        queryset = queryset.filter(distribuidor=user)
    else:
        queryset = queryset.none()

    hoy = timezone.now().date()
    queryset = queryset.filter(estado__in=['pendiente', 'parcial', 'vencida'])

    cliente_id = request.query_params.get('cliente_id')
    if cliente_id:
        queryset = queryset.filter(cliente_id=cliente_id)

    dias_min = request.query_params.get('dias_vencimiento_min')
    if dias_min:
        try:
            dias = int(dias_min)
            fecha_limite = hoy - timedelta(days=dias)
            queryset = queryset.filter(fecha_vencimiento__lte=fecha_limite)
        except ValueError:  # pragma: no cover - validación básica
            pass

    dias_max = request.query_params.get('dias_vencimiento_max')
    if dias_max:
        try:
            dias = int(dias_max)
            fecha_limite = hoy - timedelta(days=dias)
            queryset = queryset.filter(fecha_vencimiento__gte=fecha_limite)
        except ValueError:  # pragma: no cover - validación básica
            pass

    paginator = FacturaPendientesPagination()
    page = paginator.paginate_queryset(queryset.order_by('fecha_vencimiento'), request)
    serializer = FacturaListSerializer(page, many=True)
    return paginator.get_paginated_response(serializer.data)


@api_view(['POST'])
@permission_classes([IsGerente])
def validar_importacion_facturas(request: Request):
    files = cast(Any, request.FILES)
    archivo = files.get('archivo')
    if archivo is None:
        return Response({'error': 'Debe adjuntar un archivo'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        resultado = validar_archivo_facturas(archivo)
    except ValueError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return Response({
        'valido': resultado.invalidos == 0,
        'total_registros': resultado.total,
        'filas_validas': resultado.validos,
        'filas_invalidas': resultado.invalidos,
        'errores': resultado.errores,
    })


@api_view(['POST'])
@permission_classes([IsGerente])
def vista_previa_importacion(request: Request):
    files = cast(Any, request.FILES)
    archivo = files.get('archivo')
    if archivo is None:
        return Response({'error': 'Debe adjuntar un archivo'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        preview = generar_vista_previa(archivo)
    except ValueError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return Response({'total': len(preview), 'registros': preview})


@api_view(['POST'])
@permission_classes([IsGerente])
def confirmar_importacion(request: Request):
    files = cast(Any, request.FILES)
    archivo = files.get('archivo')
    if archivo is None:
        return Response({'error': 'Debe adjuntar un archivo'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        registro, resumen = confirmar_importacion_facturas(archivo, request.user)
    except ValueError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    status_code = status.HTTP_201_CREATED if resumen.get('estado') == 'completado' else status.HTTP_200_OK
    return Response(resumen, status=status_code)


@api_view(['GET'])
@permission_classes([IsGerente])
def estado_importacion(request: Request, pk: int):
    try:
        registro = FacturaImportacion.objects.get(pk=pk)
    except FacturaImportacion.DoesNotExist:
        return Response({'error': 'Proceso no encontrado'}, status=status.HTTP_404_NOT_FOUND)

    serializer = FacturaImportacionSerializer(registro)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsGerente])
def historial_importaciones(request: Request):
    registros = obtener_historial_importaciones()
    serializer = FacturaImportacionSerializer(registros, many=True)
    return Response(serializer.data)
