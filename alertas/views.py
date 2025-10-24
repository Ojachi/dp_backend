import csv
import io
from datetime import datetime

from rest_framework import generics, status, filters
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Q, QuerySet
from django.utils import timezone
from django.http import HttpResponse
from typing import Optional

from .models import Alerta, TipoAlerta, ConfiguracionAlerta
from .serializers import (
    AlertaListSerializer, AlertaDetailSerializer, AlertaUpdateSerializer,
    TipoAlertaSerializer, ConfiguracionAlertaSerializer,
    EstadisticasAlertasSerializer, GenerarAlertasSerializer
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


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def marcar_alertas_leidas(request):
    """Marcar alertas como leídas"""
    alertas_ids = request.data.get('alertas_ids', [])
    
    if alertas_ids:
        # Marcar alertas específicas
        alertas_actualizadas = ServicioAlertas.marcar_alertas_como_leidas(
            request.user, alertas_ids
        )
    else:
        # Marcar todas las alertas nuevas como leídas
        alertas_actualizadas = ServicioAlertas.marcar_alertas_como_leidas(
            request.user
        )
    
    return Response({
        'mensaje': f'{alertas_actualizadas} alertas marcadas como leídas',
        'alertas_actualizadas': alertas_actualizadas
    })


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
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


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def marcar_alertas_multiples(request):
    """Marcar un conjunto de alertas como leídas o no leídas"""
    ids = request.data.get('ids') or request.data.get('alertas_ids')
    if not ids:
        return Response({'detail': 'Debe incluir la lista de IDs'}, status=status.HTTP_400_BAD_REQUEST)

    leida = bool(request.data.get('leida', True))
    actualizadas = ServicioAlertas.cambiar_estado_multiple(
        request.user,
        alertas_ids=ids,
        leida=leida
    )

    return Response({
        'mensaje': 'Alertas actualizadas correctamente',
        'alertas_actualizadas': actualizadas,
        'leida': leida
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
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
def contador_alertas(request):
    """Obtener contador de alertas nuevas para el usuario"""
    user = request.user
    
    alertas_nuevas = Alerta.objects.filter(
        usuario_destinatario=user,
        estado='nueva'
    ).count()
    
    alertas_criticas = Alerta.objects.filter(
        usuario_destinatario=user,
        estado__in=['nueva', 'leida'],
        prioridad='critica'
    ).count()
    
    return Response({
        'alertas_nuevas': alertas_nuevas,
        'alertas_criticas': alertas_criticas
    })


@api_view(['GET'])
@permission_classes([IsGerente])
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
        'alertas_recientes': alertas_recientes,
        'alertas_por_tipo': alertas_por_tipo,
        'alertas_por_prioridad': alertas_por_prioridad,
        'alertas_por_dia': alertas_por_dia,
        'tiempo_promedio_lectura': tiempo_promedio
    }
    
    serializer = EstadisticasAlertasSerializer(estadisticas)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsGerente])
def generar_alertas_manual(request):
    """Generar alertas manualmente - Solo gerentes"""
    serializer = GenerarAlertasSerializer(data=request.data)
    
    if serializer.is_valid():
        tipos = serializer.validated_data.get('tipos', [])  # type: ignore[attr-defined]
        
        if 'todas' in tipos:
            resultados = ServicioAlertas.procesar_todas_las_alertas()
        else:
            resultados = {'detalle': {}, 'total_generadas': 0}
            total_generadas = 0

            if 'vencimiento' in tipos:
                cant = ServicioAlertas.generar_alertas_vencimiento()
                resultados['detalle']['vencimiento'] = cant
                total_generadas += cant

            resultados['total_generadas'] = total_generadas
        
        return Response({
            'mensaje': 'Alertas generadas exitosamente',
            'resultados': resultados
        })
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def exportar_alertas(request):
    """Exporta alertas del usuario autenticado según filtros"""
    queryset = ServicioAlertas.obtener_alertas_usuario(request.user)

    estado = request.query_params.get('estado')
    if estado:
        queryset = queryset.filter(estado=estado)

    prioridad = request.query_params.get('prioridad')
    if prioridad:
        queryset = queryset.filter(prioridad=prioridad)

    tipo = request.query_params.get('tipo')
    if tipo:
        queryset = queryset.filter(tipo_alerta__tipo=tipo)

    formato = request.query_params.get('formato', 'csv')

    if formato not in ['csv', 'xlsx']:
        return Response({'detail': 'Formato no soportado'}, status=status.HTTP_400_BAD_REQUEST)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        'ID', 'Título', 'Mensaje', 'Prioridad', 'Estado', 'Tipo',
        'Factura', 'Cliente', 'Fecha Generación', 'Fecha Leída'
    ])

    for alerta in queryset:
        alerta_id = getattr(alerta, 'pk', '')
        tipo_nombre = ''
        if alerta.tipo_alerta:
            tipo_nombre = getattr(alerta.tipo_alerta, 'get_tipo_display', lambda: '')()
        writer.writerow([
            alerta_id,
            alerta.titulo,
            alerta.mensaje,
            alerta.prioridad,
            alerta.estado,
            tipo_nombre,
            alerta.factura.numero_factura if alerta.factura else '',
            alerta.factura.cliente.nombre if alerta.factura and alerta.factura.cliente else '',
            alerta.fecha_generacion.isoformat() if alerta.fecha_generacion else '',
            alerta.fecha_leida.isoformat() if alerta.fecha_leida else ''
        ])

    response = HttpResponse(buffer.getvalue(), content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="alertas.csv"'
    return response


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
