from __future__ import annotations

from typing import Any, Mapping, cast

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from .serializers import CuentaPorCobrarSerializer
from .services import obtener_cuentas_por_cobrar


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def cuentas_por_cobrar(request: Request) -> Response:
    params = cast(Mapping[str, Any], request.query_params)
    filtros = {key: str(params.get(key, "")) for key in params}
    datos = obtener_cuentas_por_cobrar(filtros)
    serializer = CuentaPorCobrarSerializer(datos, many=True)
    return Response(serializer.data)

