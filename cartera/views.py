from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, cast

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from .models import EnvioEstadoCuenta
from .serializers import (
    CarteraResumenSerializer,
    CuentaPorCobrarSerializer,
    DetalleCuentaSerializer,
    EnvioEstadoCuentaSerializer,
    GestionCobranzaSerializer,
    PerfilCreditoSerializer,
    EstadisticaMoraSerializer,
    ProyeccionCobranzaSerializer,
)
from .services import (
    actualizar_limite_credito,
    historial_gestiones,
    obtener_cuentas_por_cobrar,
    obtener_detalle_cuenta,
    obtener_estadisticas_mora,
    obtener_resumen_cartera,
    proyeccion_cobranza,
)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def resumen_cartera(request: Request) -> Response:
    data = obtener_resumen_cartera()
    serializer = CarteraResumenSerializer(data)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def cuentas_por_cobrar(request: Request) -> Response:
    params = cast(Mapping[str, Any], request.query_params)
    filtros = {key: str(params.get(key, "")) for key in params}
    datos = obtener_cuentas_por_cobrar(filtros)
    serializer = CuentaPorCobrarSerializer(datos, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def detalle_cuenta(request: Request, cliente_id: int) -> Response:
    try:
        detalle = obtener_detalle_cuenta(cliente_id)
    except ObjectDoesNotExist:
        return Response({"error": "Cliente no encontrado"}, status=status.HTTP_404_NOT_FOUND)

    serializer = DetalleCuentaSerializer(detalle)
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def registrar_gestion_cobranza(request: Request, cliente_id: int) -> Response:
    data = cast(Mapping[str, Any], request.data)
    payload = {key: data.get(key) for key in data}
    payload["cliente_id"] = cliente_id
    serializer = GestionCobranzaSerializer(data=payload, context={"request": request})
    serializer.is_valid(raise_exception=True)
    gestion = serializer.save()
    return Response(GestionCobranzaSerializer(gestion).data, status=status.HTTP_201_CREATED)


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def actualizar_limite(request: Request, cliente_id: int) -> Response:
    data = cast(Mapping[str, Any], request.data)
    limite = data.get("limite_credito")
    notas = data.get("notas")

    if limite is None:
        return Response({"error": "Debe proporcionar un límite de crédito"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        limite_decimal = Decimal(str(limite))
    except (InvalidOperation, ValueError, TypeError):
        return Response({"error": "El límite debe ser un número válido"}, status=status.HTTP_400_BAD_REQUEST)

    perfil = actualizar_limite_credito(cliente_id, limite_decimal, notas)
    serializer = PerfilCreditoSerializer(perfil)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def estadisticas_mora(request: Request) -> Response:
    datos = obtener_estadisticas_mora()
    serializer = EstadisticaMoraSerializer(datos, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def proyeccion_cobranza_view(request: Request) -> Response:
    meses = request.query_params.get("meses")
    try:
        cantidad_meses = int(meses) if meses else 6
    except ValueError:
        cantidad_meses = 6

    datos = proyeccion_cobranza(cantidad_meses)
    serializer = ProyeccionCobranzaSerializer(datos, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def historial_gestiones_view(request: Request, cliente_id: int) -> Response:
    limite = request.query_params.get("limit")
    try:
        limite_int = int(limite) if limite else 20
    except ValueError:
        limite_int = 20

    gestiones = historial_gestiones(cliente_id, limite_int)
    serializer = GestionCobranzaSerializer(gestiones, many=True)
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def enviar_estado_cuenta(request: Request, cliente_id: int) -> Response:
    data = cast(Mapping[str, Any], request.data)
    payload = {key: data.get(key) for key in data}
    payload["cliente_id"] = cliente_id
    serializer = EnvioEstadoCuentaSerializer(data=payload, context={"request": request})
    serializer.is_valid(raise_exception=True)
    envio = cast(EnvioEstadoCuenta, serializer.save())
    # Simulación de envío
    envio.marcar_enviado({"mensaje": "Estado de cuenta enviado"})
    return Response(EnvioEstadoCuentaSerializer(envio).data, status=status.HTTP_201_CREATED)
