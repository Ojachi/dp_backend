from rest_framework import serializers

from .models import Factura, FacturaImportacion
from vendedores.models import Vendedor
from distribuidores.models import Distribuidor
from clientes.serializers import ClienteListSerializer
from users.serializers import UserBasicSerializer

class FacturaListSerializer(serializers.ModelSerializer):
    """Serializer para listar facturas con información básica"""
    cliente_nombre = serializers.CharField(source='cliente.nombre', read_only=True)
    vendedor_nombre = serializers.SerializerMethodField()
    distribuidor_nombre = serializers.SerializerMethodField()
    total_pagado = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    saldo_pendiente = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    esta_vencida = serializers.BooleanField(read_only=True)
    dias_vencimiento = serializers.IntegerField(read_only=True)

    class Meta:
        model = Factura
        fields = [
            'id', 'numero_factura', 'cliente', 'cliente_nombre',
            'vendedor', 'vendedor_nombre', 'distribuidor', 'distribuidor_nombre',
            'tipo',
            'fecha_emision', 'fecha_vencimiento', 'valor_total', 'estado',
            'total_pagado', 'saldo_pendiente', 'esta_vencida', 'dias_vencimiento',
            'creado', 'actualizado'
        ]
        read_only_fields = ['creado', 'actualizado']

    def get_vendedor_nombre(self, obj):
        """Obtener nombre del vendedor manejando casos null"""
        return obj.vendedor.get_full_name() if obj.vendedor else None

    def get_distribuidor_nombre(self, obj):
        """Obtener nombre del distribuidor manejando casos null"""
        return obj.distribuidor.get_full_name() if obj.distribuidor else None

class FacturaDetailSerializer(serializers.ModelSerializer):
    """Serializer detallado para facturas con información completa"""
    cliente = ClienteListSerializer(read_only=True)
    vendedor = UserBasicSerializer(read_only=True)
    distribuidor = UserBasicSerializer(read_only=True)
    total_pagado = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    saldo_pendiente = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    esta_vencida = serializers.BooleanField(read_only=True)
    dias_vencimiento = serializers.IntegerField(read_only=True)
    
    # IDs para asignación
    cliente_id = serializers.IntegerField(write_only=True)
    vendedor_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    distribuidor_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = Factura
        fields = [
            'id', 'numero_factura', 'cliente', 'cliente_id',
            'vendedor', 'vendedor_id', 'distribuidor', 'distribuidor_id',
            'tipo',
            'fecha_emision', 'fecha_vencimiento', 'valor_total', 'estado',
            'observaciones', 'total_pagado', 'saldo_pendiente', 
            'esta_vencida', 'dias_vencimiento', 'creado', 'actualizado'
        ]
        read_only_fields = ['creado', 'actualizado']

    def validate_numero_factura(self, value):
        """Validar que el número de factura sea único"""
        if self.instance and self.instance.numero_factura == value:
            return value
        if Factura.objects.filter(numero_factura=value).exists():
            raise serializers.ValidationError("Ya existe una factura con este número")
        return value

    def validate(self, attrs):
        """Validaciones generales"""
        if attrs.get('fecha_vencimiento') and attrs.get('fecha_emision'):
            if attrs['fecha_vencimiento'] < attrs['fecha_emision']:
                raise serializers.ValidationError(
                    "La fecha de vencimiento no puede ser anterior a la fecha de emisión"
                )
        
        if attrs.get('valor_total') and attrs['valor_total'] <= 0:
            raise serializers.ValidationError(
                "El valor total debe ser mayor a cero"
            )
        
        return attrs

class FacturaCreateSerializer(serializers.ModelSerializer):
    """Serializer para crear facturas"""
    cliente_id = serializers.IntegerField()
    vendedor_id = serializers.IntegerField(required=False, allow_null=True)
    distribuidor_id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = Factura
        fields = [
            'numero_factura', 'cliente_id', 'vendedor_id', 'distribuidor_id',
            'tipo',
            'fecha_emision', 'fecha_vencimiento', 'valor_total', 'observaciones'
        ]

    def validate_numero_factura(self, value):
        """Validar que el número de factura sea único"""
        if Factura.objects.filter(numero_factura=value).exists():
            raise serializers.ValidationError("Ya existe una factura con este número")
        return value

    def validate(self, attrs):
        """Validaciones generales"""
        # Mapear IDs de Vendedor/Distribuidor (modelos) a IDs de usuario para el modelo Factura.
        # También aceptar compatibilidad si se envía directamente el ID del usuario.
        vend_id = attrs.get('vendedor_id', None)
        if vend_id is not None:
            if Vendedor.objects.filter(pk=vend_id).exists():
                vendedor = Vendedor.objects.get(pk=vend_id)
                attrs['vendedor_id'] = vendedor.usuario.id
            elif Vendedor.objects.filter(usuario_id=vend_id).exists():
                # Ya es ID de usuario
                attrs['vendedor_id'] = vend_id
            else:
                raise serializers.ValidationError("El vendedor especificado no existe")

        dist_id = attrs.get('distribuidor_id', None)
        if dist_id is not None:
            if Distribuidor.objects.filter(pk=dist_id).exists():
                distrib = Distribuidor.objects.get(pk=dist_id)
                attrs['distribuidor_id'] = distrib.usuario.id
            elif Distribuidor.objects.filter(usuario_id=dist_id).exists():
                # Ya es ID de usuario
                attrs['distribuidor_id'] = dist_id
            else:
                raise serializers.ValidationError("El distribuidor especificado no existe")

        if attrs.get('fecha_vencimiento') and attrs.get('fecha_emision'):
            if attrs['fecha_vencimiento'] < attrs['fecha_emision']:
                raise serializers.ValidationError(
                    "La fecha de vencimiento no puede ser anterior a la fecha de emisión"
                )
        
        if attrs.get('valor_total') and attrs['valor_total'] <= 0:
            raise serializers.ValidationError(
                "El valor total debe ser mayor a cero"
            )
        
        return attrs

class FacturaUpdateSerializer(serializers.ModelSerializer):
    """Serializer para actualizar facturas (solo ciertos campos)"""
    vendedor_id = serializers.IntegerField(required=False, allow_null=True)
    distribuidor_id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = Factura
        fields = [
            'vendedor_id', 'distribuidor_id', 'fecha_vencimiento', 
            'tipo',
            'observaciones', 'estado'
        ]

    def validate_estado(self, value):
        """Validar cambios de estado"""
        if self.instance and value == 'pagada':
            if self.instance.saldo_pendiente > 0:
                raise serializers.ValidationError(
                    "No se puede marcar como pagada una factura con saldo pendiente"
                )
        return value

    def validate(self, attrs):
        # Mapear IDs de Vendedor/Distribuidor (modelos) a IDs de usuario para el modelo Factura
        if 'vendedor_id' in attrs and attrs['vendedor_id'] is not None:
            vend_id = attrs['vendedor_id']
            if Vendedor.objects.filter(pk=vend_id).exists():
                vendedor = Vendedor.objects.get(pk=vend_id)
                attrs['vendedor_id'] = vendedor.usuario.id
            elif Vendedor.objects.filter(usuario_id=vend_id).exists():
                attrs['vendedor_id'] = vend_id
            else:
                raise serializers.ValidationError("El vendedor especificado no existe")

        if 'distribuidor_id' in attrs and attrs['distribuidor_id'] is not None:
            dist_id = attrs['distribuidor_id']
            if Distribuidor.objects.filter(pk=dist_id).exists():
                distrib = Distribuidor.objects.get(pk=dist_id)
                attrs['distribuidor_id'] = distrib.usuario.id
            elif Distribuidor.objects.filter(usuario_id=dist_id).exists():
                attrs['distribuidor_id'] = dist_id
            else:
                raise serializers.ValidationError("El distribuidor especificado no existe")

        return attrs


class FacturaImportacionSerializer(serializers.ModelSerializer):
    usuario = UserBasicSerializer(read_only=True)

    class Meta:
        model = FacturaImportacion
        fields = [
            'id',
            'archivo_nombre',
            'estado',
            'total_registros',
            'registros_validos',
            'registros_invalidos',
            'detalle',
            'errores',
            'usuario',
            'creado',
            'actualizado',
        ]
        read_only_fields = fields