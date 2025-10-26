from rest_framework import serializers
from django.db import models
from .models import Cliente, Poblacion, ClienteSucursal

class ClienteListSerializer(serializers.ModelSerializer):
    """Serializer para listar clientes"""
    facturas_count = serializers.SerializerMethodField()
    saldo_pendiente = serializers.SerializerMethodField()
    creador_nombre = serializers.CharField(source='creador.get_full_name', read_only=True)
    
    class Meta:
        model = Cliente
        fields = [
            'id', 'nombre', 'direccion', 'telefono', 'email',
            'facturas_count', 'saldo_pendiente', 'creador_nombre', 'creado'
        ]
    
    def get_facturas_count(self, obj):
        return obj.facturas.count()
    
    def get_saldo_pendiente(self, obj):
        facturas = obj.facturas.filter(
            estado__in=['pendiente', 'parcial']
        ).prefetch_related('pagos')
        
        # Calcular saldo pendiente manualmente
        saldo_total = 0
        for factura in facturas:
            saldo_total += factura.saldo_pendiente
        return saldo_total

class ClienteDetailSerializer(serializers.ModelSerializer):
    """Serializer detallado para clientes"""
    estadisticas_facturas = serializers.SerializerMethodField()
    facturas_recientes = serializers.SerializerMethodField()
    creador_info = serializers.SerializerMethodField()
    
    class Meta:
        model = Cliente
        fields = [
            'id', 'nombre', 'direccion', 'telefono', 'email',
            'estadisticas_facturas', 'facturas_recientes', 'creador_info',
            'creado', 'actualizado'
        ]
    
    def get_estadisticas_facturas(self, obj):
        facturas = obj.facturas.all()
        from django.db.models import Sum, Count
        
        stats = facturas.aggregate(
            total_facturas=Count('id'),
            valor_total=Sum('valor_total'),
            facturas_pendientes=Count('id', 
                                    filter=models.Q(estado__in=['pendiente', 'parcial'])),
            facturas_vencidas=Count('id', 
                                  filter=models.Q(estado='vencida'))
        )
        
        # Calcular saldo pendiente manualmente para facturas pendientes/parciales
        facturas_pendientes = facturas.filter(
            estado__in=['pendiente', 'parcial']
        ).prefetch_related('pagos')
        
        saldo_pendiente = sum(factura.saldo_pendiente for factura in facturas_pendientes)
        
        return {
            'total_facturas': stats['total_facturas'] or 0,
            'valor_total_facturado': stats['valor_total'] or 0,
            'saldo_pendiente': saldo_pendiente,
            'facturas_pendientes': stats['facturas_pendientes'] or 0,
            'facturas_vencidas': stats['facturas_vencidas'] or 0
        }
    
    def get_facturas_recientes(self, obj):
        facturas_recientes = obj.facturas.order_by('-fecha_emision')[:5]
        return [{
            'id': f.pk,
            'numero_factura': f.numero_factura,
            'fecha_emision': f.fecha_emision,
            'fecha_vencimiento': f.fecha_vencimiento,
            'valor_total': f.valor_total,
            'saldo_pendiente': f.saldo_pendiente,
            'estado': f.estado
        } for f in facturas_recientes]
    
    def get_creador_info(self, obj):
        if obj.creador:
            return {
                'id': obj.creador.pk,
                'nombre': obj.creador.get_full_name(),
                'email': obj.creador.email
            }
        return None

class ClienteCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer para crear/actualizar clientes"""
    id = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Cliente
        fields = ['id', 'nombre', 'direccion', 'telefono', 'email']
    
    def validate_nombre(self, value):
        """Validar nombre único"""
        if self.instance and self.instance.nombre == value:
            return value
        if Cliente.objects.filter(nombre=value).exists():
            raise serializers.ValidationError("Ya existe un cliente con este nombre")
        return value


class PoblacionSerializer(serializers.ModelSerializer):
    vendedor_nombre = serializers.CharField(source='vendedor.get_full_name', read_only=True)
    distribuidor_nombre = serializers.CharField(source='distribuidor.get_full_name', read_only=True)

    class Meta:
        model = Poblacion
        fields = [
            'id', 'nombre', 'descripcion', 'vendedor', 'vendedor_nombre',
            'distribuidor', 'distribuidor_nombre', 'creado', 'actualizado'
        ]
        read_only_fields = ['creado', 'actualizado']


class ClienteSucursalSerializer(serializers.ModelSerializer):
    cliente_nombre = serializers.CharField(source='cliente.nombre', read_only=True)
    poblacion_nombre = serializers.CharField(source='poblacion.nombre', read_only=True)

    class Meta:
        model = ClienteSucursal
        fields = [
            'id', 'cliente', 'cliente_nombre', 'poblacion', 'poblacion_nombre',
            'codigo', 'condicion_pago', 'direccion', 'activo', 'creado', 'actualizado'
        ]
        read_only_fields = ['creado', 'actualizado']
    
    def validate_codigo(self, value):
        """Enforce código de sucursal único a nivel global."""
        qs = ClienteSucursal.objects.filter(codigo=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('Este código ya está en uso por otra sucursal')
        return value

