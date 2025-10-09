from rest_framework import generics, status, filters
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from django.utils import timezone
import pandas as pd
import io

from .models import Factura
from .serializers import (
    FacturaListSerializer, FacturaDetailSerializer, 
    FacturaCreateSerializer, FacturaUpdateSerializer
)
from users.permissions import IsGerente, IsVendedor, IsRepartidor


class FacturaListCreateView(generics.ListCreateAPIView):
    """Vista para listar y crear facturas"""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['estado', 'cliente', 'vendedor', 'distribuidor']
    search_fields = ['numero_factura', 'cliente__nombre', 'observaciones']
    ordering_fields = ['fecha_emision', 'fecha_vencimiento', 'valor_total', 'estado']
    ordering = ['-fecha_emision']

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return FacturaCreateSerializer
        return FacturaListSerializer

    def get_queryset(self):
        user = self.request.user
        
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
        elif user.groups.filter(name='Repartidor').exists():
            # Los repartidores solo ven sus facturas asignadas
            queryset = queryset.filter(distribuidor=user)
        else:
            # Sin rol específico, no ve nada
            queryset = queryset.none()
        
        # Filtros adicionales por parámetros de query
        estado = self.request.query_params.get('estado')
        if estado:
            queryset = queryset.filter(estado=estado)
            
        fecha_desde = self.request.query_params.get('fecha_desde')
        if fecha_desde:
            queryset = queryset.filter(fecha_emision__gte=fecha_desde)
            
        fecha_hasta = self.request.query_params.get('fecha_hasta')
        if fecha_hasta:
            queryset = queryset.filter(fecha_emision__lte=fecha_hasta)
        
        vencidas = self.request.query_params.get('vencidas')
        if vencidas and vencidas.lower() == 'true':
            queryset = queryset.filter(
                fecha_vencimiento__lt=timezone.now().date(),
                estado__in=['pendiente', 'parcial']
            )
        
        return queryset

    def perform_create(self, serializer):
        # Solo los gerentes pueden crear facturas
        if not self.request.user.groups.filter(name='Gerente').exists():
            raise PermissionError("Solo los gerentes pueden crear facturas")
        serializer.save()


class FacturaDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Vista para ver, actualizar y eliminar facturas individuales"""
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return FacturaUpdateSerializer
        return FacturaDetailSerializer

    def get_queryset(self):
        user = self.request.user
        
        # Actualizar automáticamente facturas vencidas antes de consultar
        Factura.actualizar_estados_vencidas()
        
        queryset = Factura.objects.select_related('cliente', 'vendedor', 'distribuidor')
        
        # Filtrar según el rol del usuario
        if user.groups.filter(name='Gerente').exists():
            return queryset
        elif user.groups.filter(name='Vendedor').exists():
            return queryset.filter(vendedor=user)
        elif user.groups.filter(name='Repartidor').exists():
            return queryset.filter(distribuidor=user)
        else:
            return queryset.none()
    
    def perform_update(self, serializer):
        # Solo los gerentes pueden editar facturas
        if not self.request.user.groups.filter(name='Gerente').exists():
            raise PermissionError("Solo los gerentes pueden editar facturas")
        serializer.save()
    
    def perform_destroy(self, instance):
        # Solo los gerentes pueden eliminar facturas
        if not self.request.user.groups.filter(name='Gerente').exists():
            raise PermissionError("Solo los gerentes pueden eliminar facturas")
        
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
    elif user.groups.filter(name='Repartidor').exists():
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


@api_view(['POST'])
@permission_classes([IsGerente])  # Solo gerentes pueden importar
def importar_facturas_excel(request):
    """Endpoint para importar facturas desde archivo Excel"""
    if 'archivo' not in request.FILES:
        return Response(
            {'error': 'Debe proporcionar un archivo Excel'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    archivo = request.FILES['archivo']
    
    try:
        # Leer archivo Excel
        df = pd.read_excel(io.BytesIO(archivo.read()))
        
        # Validar columnas esperadas (ajustar según tu formato)
        columnas_esperadas = [
            'numero_factura', 'cliente_id', 'fecha_emision', 
            'fecha_vencimiento', 'valor_total'
        ]
        
        columnas_faltantes = set(columnas_esperadas) - set(df.columns)
        if columnas_faltantes:
            return Response(
                {'error': f'Columnas faltantes: {list(columnas_faltantes)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        facturas_creadas = 0
        facturas_actualizadas = 0
        errores = []
        
        for index, row in df.iterrows():
            try:
                # Buscar si la factura ya existe
                factura_existente = Factura.objects.filter(
                    numero_factura=row['numero_factura']
                ).first()
                
                datos_factura = {
                    'numero_factura': row['numero_factura'],
                    'cliente_id': row['cliente_id'],
                    'fecha_emision': pd.to_datetime(row['fecha_emision']).date(),
                    'fecha_vencimiento': pd.to_datetime(row['fecha_vencimiento']).date(),
                    'valor_total': float(row['valor_total']),
                }
                
                # Campos opcionales
                if 'vendedor_id' in row and pd.notna(row['vendedor_id']):
                    datos_factura['vendedor_id'] = int(row['vendedor_id'])
                if 'distribuidor_id' in row and pd.notna(row['distribuidor_id']):
                    datos_factura['distribuidor_id'] = int(row['distribuidor_id'])
                if 'observaciones' in row and pd.notna(row['observaciones']):
                    datos_factura['observaciones'] = row['observaciones']
                
                if factura_existente:
                    # Actualizar factura existente (solo si no tiene pagos)
                    if not factura_existente.pagos.exists():
                        for campo, valor in datos_factura.items():
                            if campo != 'numero_factura':  # No cambiar número
                                setattr(factura_existente, campo, valor)
                        factura_existente.save()
                        facturas_actualizadas += 1
                else:
                    # Crear nueva factura
                    Factura.objects.create(**datos_factura)
                    facturas_creadas += 1
                    
            except Exception as e:
                errores.append(f"Fila {index + 2}: {str(e)}")
        
        return Response({
            'mensaje': 'Importación completada',
            'facturas_creadas': facturas_creadas,
            'facturas_actualizadas': facturas_actualizadas,
            'errores': errores
        })
        
    except Exception as e:
        return Response(
            {'error': f'Error procesando archivo: {str(e)}'},
            status=status.HTTP_400_BAD_REQUEST
        )
