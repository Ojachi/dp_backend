from rest_framework import generics, status, filters
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Q
from django.utils import timezone

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
    
    def get_queryset(self):
        user = self.request.user
        queryset = ServicioAlertas.obtener_alertas_usuario(user)
        
        # Filtros adicionales por parámetros de query
        estado = self.request.query_params.get('estado')
        if estado:
            queryset = queryset.filter(estado=estado)
            
        prioridad = self.request.query_params.get('prioridad')
        if prioridad:
            queryset = queryset.filter(prioridad=prioridad)
            
        solo_nuevas = self.request.query_params.get('solo_nuevas')
        if solo_nuevas and solo_nuevas.lower() == 'true':
            queryset = queryset.filter(estado='nueva')
        
        # Filtro por tipo de alerta
        tipo = self.request.query_params.get('tipo')
        if tipo:
            queryset = queryset.filter(tipo_alerta__tipo=tipo)
        
        return queryset


class AlertaDetailView(generics.RetrieveUpdateAPIView):
    """Vista para ver y actualizar alertas individuales"""
    serializer_class = AlertaDetailSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        return Alerta.objects.filter(usuario_destinatario=user)
    
    def get_serializer_class(self):
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
    
    estadisticas = {
        'total_alertas': total_alertas,
        'alertas_nuevas': alertas_nuevas,
        'alertas_criticas': alertas_criticas,
        'alertas_recientes': alertas_recientes,
        'alertas_por_tipo': alertas_por_tipo,
        'alertas_por_prioridad': alertas_por_prioridad
    }
    
    serializer = EstadisticasAlertasSerializer(estadisticas)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsGerente])
def generar_alertas_manual(request):
    """Generar alertas manualmente - Solo gerentes"""
    serializer = GenerarAlertasSerializer(data=request.data)
    
    if serializer.is_valid():
        tipos = serializer.validated_data['tipos']
        
        if 'todas' in tipos:
            resultados = ServicioAlertas.procesar_todas_las_alertas()
        else:
            resultados = {'detalle': {}}
            total_generadas = 0
            
            if 'vencimiento' in tipos:
                cant = ServicioAlertas.generar_alertas_vencimiento()
                resultados['detalle']['vencimiento'] = cant
                total_generadas += cant
            
            if 'monto_alto' in tipos:
                cant = ServicioAlertas.generar_alertas_montos_altos()
                resultados['detalle']['montos_altos'] = cant
                total_generadas += cant
            
            if 'sin_pagos' in tipos:
                cant = ServicioAlertas.generar_alertas_sin_pagos()
                resultados['detalle']['sin_pagos'] = cant
                total_generadas += cant
            
            resultados['total_generadas'] = total_generadas
        
        return Response({
            'mensaje': 'Alertas generadas exitosamente',
            'resultados': resultados
        })
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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
    
    def get_queryset(self):
        return ConfiguracionAlerta.objects.filter(
            usuario=self.request.user
        ).select_related('tipo_alerta')
    
    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)


class ConfiguracionAlertaDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Vista para gestionar configuraciones individuales"""
    serializer_class = ConfiguracionAlertaSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return ConfiguracionAlerta.objects.filter(usuario=self.request.user)
