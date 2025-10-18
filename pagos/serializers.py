from django.core.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework import serializers
from decimal import Decimal

from facturas.models import Factura
from facturas.serializers import FacturaListSerializer

from .models import Pago
from .services import crear_pago_para_factura

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
            'estado', 'descuento', 'retencion', 'ica', 'nota',
            'creado'
        ]

class PagoDetailSerializer(serializers.ModelSerializer):
    """Serializer detallado para pagos"""
    factura = FacturaListSerializer(read_only=True)
    usuario_registro_nombre = serializers.CharField(source='usuario_registro.get_full_name', read_only=True)
    usuario_confirmacion_nombre = serializers.CharField(source='usuario_confirmacion.get_full_name', read_only=True)
    
    class Meta:
        model = Pago
        fields = [
            'id', 'factura', 'fecha_pago', 'valor_pagado', 'tipo_pago',
            'comprobante', 'numero_comprobante', 'notas', 
            'usuario_registro', 'usuario_registro_nombre',
            'estado', 'usuario_confirmacion_nombre', 'fecha_confirmacion',
            'descuento', 'retencion', 'ica', 'nota',
            'creado', 'actualizado'
        ]
        read_only_fields = ['creado', 'actualizado', 'usuario_registro', 'estado', 'fecha_confirmacion']

class PagoCreateSerializer(serializers.ModelSerializer):
    """Serializer para crear pagos"""
    factura_id = serializers.IntegerField()

    class Meta:
        model = Pago
        fields = [
            'factura_id', 'fecha_pago', 'valor_pagado', 'tipo_pago',
            'comprobante', 'numero_comprobante', 'notas',
            'descuento', 'retencion', 'ica', 'nota'
        ]

    def validate(self, attrs):
        """Validaciones del pago"""
        factura_id = attrs.get('factura_id')
        # normalizar cantidades
        valor_pagado = Decimal(attrs.get('valor_pagado') or 0)
        descuento = Decimal(attrs.get('descuento') or 0)
        retencion = Decimal(attrs.get('retencion') or 0)
        ica = Decimal(attrs.get('ica') or 0)
        nota = Decimal(attrs.get('nota') or 0)

        for nombre, valor in (
            ("valor_pagado", valor_pagado),
            ("descuento", descuento),
            ("retencion", retencion),
            ("ica", ica),
            ("nota", nota),
        ):
            if valor < 0:
                raise serializers.ValidationError({nombre: "No puede ser negativo"})

        total_aplicar = valor_pagado + descuento + retencion + ica + nota
        if total_aplicar <= 0:
            raise serializers.ValidationError(
                "Debe indicar al menos un valor a aplicar (pago, descuento, retención, ICA o nota)"
            )

        # Validar que la factura existe; permitir registro sin validar saldo
        try:
            factura = Factura.objects.get(id=factura_id)
        except Factura.DoesNotExist:
            raise serializers.ValidationError("La factura especificada no existe")

        # No permitir registrar pagos en facturas canceladas o ya pagadas
        if factura.estado == 'cancelada':
            raise DRFValidationError("No se pueden registrar pagos en facturas canceladas")
        if factura.estado == 'pagada':
            raise DRFValidationError("La factura ya está completamente pagada")

        return attrs

    def create(self, validated_data):
        """Crear pago y asignar usuario que lo registra"""
        request = self.context.get('request')
        if request is None or not request.user.is_authenticated:
            raise PermissionDenied("Autenticación requerida para registrar pagos")

        factura_id = validated_data.pop('factura_id')

        try:
            factura = Factura.objects.select_related('cliente', 'vendedor', 'distribuidor').get(id=factura_id)
        except Factura.DoesNotExist as exc:  # pragma: no cover - validación previa debería atraparlo
            raise serializers.ValidationError("La factura especificada no existe") from exc

        return crear_pago_para_factura(request.user, factura, validated_data)

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


class PagoConfirmSerializer(serializers.Serializer):
    """Serializer para confirmar pagos"""
    confirmar = serializers.BooleanField(default=True)
