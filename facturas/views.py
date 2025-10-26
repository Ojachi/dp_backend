from typing import Type, cast

from django.db.models import QuerySet
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.serializers import Serializer

from .models import Factura
from .serializers import (
    FacturaCreateSerializer,
    FacturaDetailSerializer,
    FacturaListSerializer,
    FacturaUpdateSerializer,
)


class FacturaListCreateView(generics.ListCreateAPIView):
    """Vista para listar y crear facturas"""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    # Nota: removemos 'vendedor' y 'distribuidor' del filterset_fields porque
    # los parámetros del frontend traen el ID de las tablas Vendedor/Distribuidor,
    # no el ID del usuario. Los manejamos manualmente en get_queryset.
    filterset_fields = ['estado', 'cliente', 'tipo', 'valor_total']
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
        
        queryset = Factura.objects.select_related(
            'cliente',
            'vendedor',
            'distribuidor',
            'cliente_sucursal',
            'cliente_sucursal__poblacion',
        )
        
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
        
        # Filtro por vendedor: el frontend envía el ID del modelo Vendedor,
        # pero la FK en Factura apunta al usuario. Relación: vendedor (User)
        # -> perfil_vendedor (OneToOne) -> id del modelo Vendedor.
        vendedor_param = request.query_params.get('vendedor')
        if vendedor_param:
            queryset = queryset.filter(vendedor__perfil_vendedor__id=vendedor_param)
        
        # Filtro por distribuidor: análogo al caso vendedor.
        distrib_param = request.query_params.get('distribuidor')
        if distrib_param:
            queryset = queryset.filter(distribuidor__perfil_distribuidor__id=distrib_param)
            
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
        
        queryset = Factura.objects.select_related(
            'cliente',
            'vendedor',
            'distribuidor',
            'cliente_sucursal',
            'cliente_sucursal__poblacion',
        )
        
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
        # Permisos: gerente puede editar todo; distribuidor puede editar estado_entrega y observaciones; vendedor no edita
        user = self.request.user
        is_gerente = user.groups.filter(name='Gerente').exists()
        is_distrib = user.groups.filter(name='Distribuidor').exists()
        if not (is_gerente or is_distrib):
            raise PermissionDenied("No tienes permisos para editar esta factura")

        instance = self.get_object()
        data = serializer.validated_data
        # Si distribuidor intenta cambiar campos que no son de entrega, bloquear
        if is_distrib:
            campos_permitidos = {'estado_entrega', 'observaciones'}
            no_permitidos = set(data.keys()) - campos_permitidos
            if no_permitidos:
                raise PermissionDenied("El distribuidor solo puede cambiar estado de entrega u observaciones")

        obj = serializer.save()
        # Si cambió el estado de entrega, marcar auditoría
        if 'estado_entrega' in data:
            from django.utils import timezone
            obj.entrega_actualizado = timezone.now()
            obj.entrega_actualizado_por = user
            obj.save(update_fields=['entrega_actualizado', 'entrega_actualizado_por'])
    
    def perform_destroy(self, instance):
        # Solo los gerentes pueden eliminar facturas
        if not self.request.user.groups.filter(name='Gerente').exists():
            raise PermissionDenied("Solo los gerentes pueden eliminar facturas")
        
        # No permitir eliminar facturas que ya tienen pagos
        if instance.pagos.exists():
            raise ValidationError({
                'detail': "No se puede eliminar una factura que ya tiene pagos registrados"
            })
        
        instance.delete()
 
