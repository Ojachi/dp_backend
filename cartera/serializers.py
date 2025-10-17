from __future__ import annotations

from typing import Any, Dict, List

from rest_framework import serializers

from clientes.serializers import ClienteListSerializer
from facturas.serializers import FacturaListSerializer
from pagos.serializers import PagoListSerializer

from .models import EnvioEstadoCuenta, GestionCobranza, PerfilCreditoCliente


class PerfilCreditoSerializer(serializers.ModelSerializer):
    cliente = ClienteListSerializer(read_only=True)
    cliente_id = serializers.IntegerField(write_only=True, required=False)

    class Meta:
        model = PerfilCreditoCliente
        fields = [
            "cliente",
            "cliente_id",
            "limite_credito",
            "dias_promedio_cobranza",
            "porcentaje_mora",
            "notas",
        ]

    def create(self, validated_data: Dict[str, Any]) -> PerfilCreditoCliente:
        cliente_id = validated_data.pop("cliente_id")
        perfil, _ = PerfilCreditoCliente.objects.update_or_create(
            cliente_id=cliente_id,
            defaults=validated_data,
        )
        return perfil

    def update(self, instance: PerfilCreditoCliente, validated_data: Dict[str, Any]) -> PerfilCreditoCliente:
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class GestionCobranzaSerializer(serializers.ModelSerializer):
    cliente = ClienteListSerializer(read_only=True)
    cliente_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = GestionCobranza
        fields = [
            "id",
            "cliente",
            "cliente_id",
            "tipo",
            "resultado",
            "observaciones",
            "proximo_contacto",
            "creado",
        ]
        read_only_fields = ["id", "cliente", "creado"]

    def create(self, validated_data: Dict[str, Any]) -> GestionCobranza:
        usuario = self.context.get("request").user  # type: ignore[union-attr]
        validated_data["usuario"] = usuario if usuario.is_authenticated else None
        return super().create(validated_data)


class EnvioEstadoCuentaSerializer(serializers.ModelSerializer):
    cliente = ClienteListSerializer(read_only=True)
    cliente_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = EnvioEstadoCuenta
        fields = [
            "id",
            "cliente",
            "cliente_id",
            "medio",
            "estado",
            "detalle",
            "creado",
            "enviado_en",
        ]
        read_only_fields = ["id", "cliente", "estado", "detalle", "creado", "enviado_en"]

    def create(self, validated_data: Dict[str, Any]) -> EnvioEstadoCuenta:
        usuario = self.context.get("request").user  # type: ignore[union-attr]
        validated_data["usuario"] = usuario if usuario.is_authenticated else None
        envio = super().create(validated_data)
        return envio


class CarteraResumenSerializer(serializers.Serializer):
    total_cartera = serializers.DecimalField(max_digits=12, decimal_places=2)
    cuentas_por_cobrar = serializers.DecimalField(max_digits=12, decimal_places=2)
    facturas_pendientes = serializers.IntegerField()
    clientes_con_mora = serializers.IntegerField()
    dias_promedio_cobranza = serializers.IntegerField()
    porcentaje_mora = serializers.DecimalField(max_digits=5, decimal_places=2)


class CuentaPorCobrarSerializer(serializers.Serializer):
    cliente = ClienteListSerializer()
    total_pendiente = serializers.DecimalField(max_digits=12, decimal_places=2)
    facturas = FacturaListSerializer(many=True)


class DetalleCuentaSerializer(serializers.Serializer):
    cliente = ClienteListSerializer()
    facturas = FacturaListSerializer(many=True)
    pagos_recientes = PagoListSerializer(many=True)
    total_pendiente = serializers.DecimalField(max_digits=12, decimal_places=2)
    limite_credito = serializers.DecimalField(max_digits=12, decimal_places=2)


class EstadisticaMoraSerializer(serializers.Serializer):
    rango = serializers.CharField()
    total_facturas = serializers.IntegerField()
    monto_total = serializers.DecimalField(max_digits=12, decimal_places=2)


class ProyeccionCobranzaSerializer(serializers.Serializer):
    mes = serializers.CharField()
    monto_estimado = serializers.DecimalField(max_digits=12, decimal_places=2)
    facturas = serializers.IntegerField()
