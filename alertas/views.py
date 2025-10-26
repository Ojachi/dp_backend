from rest_framework import generics, status, filters
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers as rf_serializers

from .models import Alerta, TipoAlerta, ConfiguracionAlerta
from .serializers import (
    AlertaListSerializer, AlertaDetailSerializer, AlertaUpdateSerializer,
    TipoAlertaSerializer, ConfiguracionAlertaSerializer,
    EstadisticasAlertasSerializer
)
from .services import ServicioAlertas
from users.permissions import IsGerente


class AlertaListView(generics.ListAPIView):
    """Vista para listar alertas del usuario autenticado"""
    serializer_class = AlertaListSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['fecha_generacion', 'prioridad']
    ordering = ['-fecha_generacion']
    
    def get_queryset(self):  # type: ignore[override]
        user = self.request.user
        queryset = ServicioAlertas.obtener_alertas_usuario(user)

        params = getattr(self.request, 'query_params', self.request.GET)

        # Filtros adicionales por parámetros de query
        estado = params.get('estado')
        if estado:
            queryset = queryset.filter(estado=estado)
            
        prioridad = params.get('prioridad')
        if prioridad:
            queryset = queryset.filter(prioridad=prioridad)
            
        solo_nuevas = params.get('solo_nuevas')
        if solo_nuevas and solo_nuevas.lower() == 'true':
            queryset = queryset.filter(estado='nueva')
        
        # Filtro por tipo de alerta
        tipo = params.get('tipo')
        if tipo:
            queryset = queryset.filter(tipo_alerta__tipo=tipo)

        # Filtro por subtipo (por_vencer | vencida)
        subtipo = params.get('subtipo')
        if subtipo:
            queryset = queryset.filter(subtipo=subtipo)

        # Búsqueda por texto (título, mensaje o número de factura)
        buscar = params.get('buscar')
        if buscar:
            queryset = queryset.filter(
                Q(titulo__icontains=buscar) |
                Q(mensaje__icontains=buscar) |
                Q(factura__numero_factura__icontains=buscar)
            )
        
        return queryset


class AlertaDetailView(generics.RetrieveUpdateAPIView):
    """Vista para ver y actualizar alertas individuales"""
    serializer_class = AlertaDetailSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):  # type: ignore[override]
        user = self.request.user
        queryset = Alerta.objects.filter(usuario_destinatario=user)
        return queryset
    
    def get_serializer_class(self):  # type: ignore[override]
        if self.request.method in ['PUT', 'PATCH']:
            return AlertaUpdateSerializer
        return AlertaDetailSerializer
    
    def perform_update(self, serializer):
        alerta = serializer.save()
        
        # Actualizar fechas según el nuevo estado
        if alerta.estado == 'leida' and not alerta.fecha_leida:
            alerta.fecha_leida = timezone.now()
            alerta.save(update_fields=['fecha_leida'])
        elif alerta.estado == 'procesada' and not alerta.fecha_procesada:
            alerta.fecha_procesada = timezone.now()
            alerta.usuario_procesado = self.request.user
            alerta.save(update_fields=['fecha_procesada', 'usuario_procesado'])


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
@extend_schema(
    methods=['PATCH'],
    request=AlertaUpdateSerializer,
    responses=AlertaDetailSerializer,
)
def marcar_alerta_estado(request, pk):
    """Marcar una alerta como leída o no leída"""
    leida = request.data.get('leida', True)
    alerta = ServicioAlertas.cambiar_estado_alerta(
        request.user,
        alerta_id=pk,
        leida=bool(leida)
    )

    if alerta is None:
        return Response({'detail': 'Alerta no encontrada'}, status=status.HTTP_404_NOT_FOUND)

    serializer = AlertaDetailSerializer(alerta)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@extend_schema(
    methods=['GET'],
    responses=inline_serializer(
        name='AlertasRecientesResponse',
        fields={
            'count': rf_serializers.IntegerField(),
            'results': AlertaListSerializer(many=True),
        },
    ),
)
def alertas_recientes(request):
    """Obtiene alertas recientes para el usuario autenticado"""
    desde_raw = request.query_params.get('desde')
    desde = None
    if desde_raw:
        try:
            desde = timezone.datetime.fromisoformat(desde_raw)
            if timezone.is_naive(desde):
                desde = timezone.make_aware(desde)
        except ValueError:
            return Response({'detail': 'Formato de fecha inválido'}, status=status.HTTP_400_BAD_REQUEST)

    alertas = ServicioAlertas.obtener_alertas_recientes(
        request.user,
        desde=desde
    )

    serializer = AlertaListSerializer(alertas, many=True)
    return Response({'count': len(alertas), 'results': serializer.data})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@extend_schema(
    methods=['GET'],
    responses=inline_serializer(
        name='AlertasContadorResponse',
        fields={
            'alertas_nuevas': rf_serializers.IntegerField(),
            'alertas_criticas': rf_serializers.IntegerField(),
        },
    ),
)
def contador_alertas(request):
    """Obtener contador de alertas nuevas para el usuario"""
    user = request.user
    
    alertas_nuevas = Alerta.objects.filter(
        usuario_destinatario=user,
        estado='nueva'
    ).count()
    
    # Contadores por subtipo
    por_vencer = Alerta.objects.filter(
        usuario_destinatario=user,
        estado__in=['nueva', 'leida'],
        subtipo='por_vencer'
    ).count()
    vencidas = Alerta.objects.filter(
        usuario_destinatario=user,
        estado__in=['nueva', 'leida'],
        subtipo='vencida'
    ).count()
    
    return Response({
        'alertas_nuevas': alertas_nuevas,
        # Compatibilidad: mantenemos 'alertas_criticas' mapeada a 'vencidas'
        'alertas_criticas': vencidas,
        # Nuevas llaves específicas
        'alertas_por_vencer': por_vencer,
        'alertas_vencidas': vencidas,
    })


@api_view(['GET'])
@permission_classes([IsGerente])
@extend_schema(
    methods=['GET'],
    responses=EstadisticasAlertasSerializer,
)
def estadisticas_alertas(request):
    """Estadísticas generales de alertas - Solo gerentes"""
    
    # Estadísticas generales
    total_alertas = Alerta.objects.count()
    alertas_nuevas = Alerta.objects.filter(estado='nueva').count()
    alertas_criticas = Alerta.objects.filter(
        prioridad='critica',
        estado__in=['nueva', 'leida']
    ).count()
    
    # Alertas por tipo
    alertas_por_tipo = dict(
        Alerta.objects.values('tipo_alerta__tipo', 'tipo_alerta__nombre')
        .annotate(cantidad=Count('id'))
        .values_list('tipo_alerta__tipo', 'cantidad')
    )
    
    # Alertas por prioridad
    alertas_por_prioridad = dict(
        Alerta.objects.values_list('prioridad')
        .annotate(cantidad=Count('id'))
        .values_list('prioridad', 'cantidad')
    )
    
    # Alertas recientes (últimos 7 días)
    fecha_semana = timezone.now() - timezone.timedelta(days=7)
    alertas_recientes = Alerta.objects.filter(
        fecha_generacion__gte=fecha_semana
    ).count()

    alertas_por_dia = ServicioAlertas.estadisticas_por_dia(dias=7)
    tiempo_promedio = ServicioAlertas.tiempo_promedio_lectura()
    
    estadisticas = {
        'total_alertas': total_alertas,
        'alertas_nuevas': alertas_nuevas,
        'alertas_criticas': alertas_criticas,
        'alertas_recientes': alertas_recientes,
        'alertas_por_tipo': alertas_por_tipo,
        'alertas_por_prioridad': alertas_por_prioridad,
        'alertas_por_dia': alertas_por_dia,
        'tiempo_promedio_lectura': tiempo_promedio
    }
    
    serializer = EstadisticasAlertasSerializer(estadisticas)
    return Response(serializer.data)


 


# Gestión de tipos de alertas (solo gerentes)
class TipoAlertaListCreateView(generics.ListCreateAPIView):
    """Vista para listar y crear tipos de alertas - Solo gerentes"""
    queryset = TipoAlerta.objects.all()
    serializer_class = TipoAlertaSerializer
    permission_classes = [IsGerente]
    ordering = ['nombre']


class TipoAlertaDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Vista para gestionar tipos de alertas individuales - Solo gerentes"""
    queryset = TipoAlerta.objects.all()
    serializer_class = TipoAlertaSerializer
    permission_classes = [IsGerente]


# Configuración de alertas por usuario
class ConfiguracionAlertaListView(generics.ListCreateAPIView):
    """Vista para configuraciones de alertas del usuario"""
    serializer_class = ConfiguracionAlertaSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):  # type: ignore[override]
        return ConfiguracionAlerta.objects.filter(
            usuario=self.request.user
        ).select_related('tipo_alerta')
    
    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)


class ConfiguracionAlertaDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Vista para gestionar configuraciones individuales"""
    serializer_class = ConfiguracionAlertaSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):  # type: ignore[override]
        return ConfiguracionAlerta.objects.filter(usuario=self.request.user)
