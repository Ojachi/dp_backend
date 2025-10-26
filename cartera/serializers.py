from __future__ import annotations

from rest_framework import serializers

from clientes.serializers import ClienteListSerializer
from facturas.serializers import FacturaListSerializer


class CuentaPorCobrarSerializer(serializers.Serializer):
    cliente = ClienteListSerializer()
    total_pendiente = serializers.DecimalField(max_digits=12, decimal_places=2)
    facturas = FacturaListSerializer(many=True)
    total_facturas = serializers.IntegerField()
    facturas_activas = serializers.IntegerField()
    activas_pendientes = serializers.IntegerField()
    activas_parciales = serializers.IntegerField()
    activas_vencidas = serializers.IntegerField()

 

 




 







