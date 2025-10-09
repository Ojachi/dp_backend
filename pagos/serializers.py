from rest_framework import serializers
from .models import Pago
from facturas.serializers import FacturaListSerializer

class PagoListSerializer(serializers.ModelSerializer):
    """Serializer para listar pagos"""
    factura_numero = serializers.CharField(source='factura.numero_factura', read_only=True)
    cliente_nombre = serializers.CharField(source='factura.cliente.nombre', read_only=True)
    usuario_nombre = serializers.CharField(source='usuario_registro.get_full_name', read_only=True)

    class Meta:
        model = Pago
        fields = [
            'id', 'factura', 'factura_numero', 'cliente_nombre',
            'fecha_pago', 'valor_pagado', 'tipo_pago', 
            'numero_comprobante', 'usuario_registro', 'usuario_nombre',
            'creado'
        ]

class PagoDetailSerializer(serializers.ModelSerializer):
    """Serializer detallado para pagos"""
    factura = FacturaListSerializer(read_only=True)
    usuario_registro_nombre = serializers.CharField(source='usuario_registro.get_full_name', read_only=True)
    
    class Meta:
        model = Pago
        fields = [
            'id', 'factura', 'fecha_pago', 'valor_pagado', 'tipo_pago',
            'comprobante', 'numero_comprobante', 'notas', 
            'usuario_registro', 'usuario_registro_nombre',
            'creado', 'actualizado'
        ]
        read_only_fields = ['creado', 'actualizado', 'usuario_registro']

class PagoCreateSerializer(serializers.ModelSerializer):
    """Serializer para crear pagos"""
    factura_id = serializers.IntegerField()

    class Meta:
        model = Pago
        fields = [
            'factura_id', 'fecha_pago', 'valor_pagado', 'tipo_pago',
            'comprobante', 'numero_comprobante', 'notas'
        ]

    def validate(self, attrs):
        """Validaciones del pago"""
        factura_id = attrs.get('factura_id')
        valor_pagado = attrs.get('valor_pagado')

        if valor_pagado <= 0:
            raise serializers.ValidationError(
                "El valor del pago debe ser mayor a cero"
            )

        # Validar que la factura existe y puede recibir pagos
        try:
            from facturas.models import Factura
            factura = Factura.objects.get(id=factura_id)
            puede_pagar, mensaje = factura.puede_recibir_pago(valor_pagado)
            if not puede_pagar:
                raise serializers.ValidationError(mensaje)
        except Factura.DoesNotExist:
            raise serializers.ValidationError("La factura especificada no existe")

        return attrs

    def create(self, validated_data):
        """Crear pago y asignar usuario que lo registra"""
        # El usuario se asigna en la vista
        return super().create(validated_data)

class PagoUpdateSerializer(serializers.ModelSerializer):
    """Serializer para actualizar pagos (limitado)"""
    
    class Meta:
        model = Pago
        fields = [
            'fecha_pago', 'tipo_pago', 'comprobante', 
            'numero_comprobante', 'notas'
        ]
        
    def validate(self, attrs):
        """Validar que no se cambie el valor del pago una vez creado"""
        if 'valor_pagado' in attrs:
            raise serializers.ValidationError(
                "No se puede modificar el valor de un pago ya registrado"
            )
        return attrs