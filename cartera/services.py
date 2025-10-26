from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Dict, List, TypedDict, cast

from django.db.models import Count, QuerySet, Q

from clientes.models import Cliente
from facturas.models import Factura


class DatosCuentaAgrupada(TypedDict):
    cliente: Cliente
    total_pendiente: Decimal
    facturas: List[Factura]
    total_facturas: int
    facturas_activas: int
    activas_pendientes: int
    activas_parciales: int
    activas_vencidas: int


 


def cuentas_por_cobrar_queryset(filtros: Dict[str, str]) -> QuerySet[Factura]:
    queryset = Factura.objects.select_related("cliente", "vendedor", "distribuidor").filter(
        estado__in=["pendiente", "parcial", "vencida"]
    )

    if cliente_id := filtros.get("cliente"):
        queryset = queryset.filter(cliente_id=cliente_id)

    if monto_min := filtros.get("monto_min"):
        queryset = queryset.filter(valor_total__gte=monto_min)

    if monto_max := filtros.get("monto_max"):
        queryset = queryset.filter(valor_total__lte=monto_max)

    if estado := filtros.get("estado"):
        queryset = queryset.filter(estado=estado)

    return queryset


def obtener_cuentas_por_cobrar(filtros: Dict[str, str]) -> List[DatosCuentaAgrupada]:
    """
    Devuelve una lista por cliente con su total pendiente y facturas pendientes.
    Incluye también clientes "al día" (sin facturas pendientes) con total 0 y facturas vacías.

    Filtros admitidos:
    - cliente: ID del cliente
    - estado: 'vencida' (solo facturas vencidas) o 'aldia' (solo clientes sin deuda)
    - monto_min / monto_max: se aplican sobre el total_pendiente agregado por cliente
    """

    # 1) Construir agrupado para clientes con facturas pendientes
    queryset = cuentas_por_cobrar_queryset(filtros)
    agrupado: Dict[int, DatosCuentaAgrupada] = {}

    for factura in queryset:
        cliente_id = cast(int, getattr(factura, "cliente_id"))
        if cliente_id not in agrupado:
            agrupado[cliente_id] = {
                "cliente": factura.cliente,
                "total_pendiente": Decimal("0.00"),
                "facturas": [],
                "total_facturas": 0,
                "facturas_activas": 0,
                "activas_pendientes": 0,
                "activas_vencidas": 0,
                "activas_parciales": 0,
            }
        agrupado[cliente_id]["total_pendiente"] += factura.saldo_pendiente
        agrupado[cliente_id]["facturas"].append(factura)

    # 2) Incluir todos los clientes (al día) que no aparecieron en el agrupado
    clientes_qs = Cliente.objects.all()
    if cliente_id := filtros.get("cliente"):
        try:
            clientes_qs = clientes_qs.filter(id=int(cliente_id))
        except (TypeError, ValueError):
            pass

    # Si se pide solo vencidas, ya lo manejamos en el queryset de facturas. Si se pide 'aldia',
    # más abajo filtramos por total_pendiente == 0
    for cliente in clientes_qs:
        cid = cast(int, getattr(cliente, "id"))
        if cid not in agrupado:
            agrupado[cid] = {
                "cliente": cliente,
                "total_pendiente": Decimal("0.00"),
                "facturas": [],
                "total_facturas": 0,
                "facturas_activas": 0,
                "activas_pendientes": 0,
                "activas_vencidas": 0,
                "activas_parciales": 0,
            }

    # 2.5) Calcular métricas por cliente (totales y activas/breakdown) en bloque
    cliente_ids = list(agrupado.keys())
    if cliente_ids:
        stats = (
            Factura.objects.filter(cliente_id__in=cliente_ids)
            .values("cliente_id")
            .annotate(
                total=Count("id"),
                activas=Count("id", filter=Q(estado__in=["pendiente", "parcial", "vencida"])),
                pend=Count("id", filter=Q(estado="pendiente")),
                parc=Count("id", filter=Q(estado="parcial")),
                venc=Count("id", filter=Q(estado="vencida")),
            )
        )
        for row in stats:
            cid = cast(int, row["cliente_id"])  # type: ignore[index]
            if cid in agrupado:
                agrupado[cid]["total_facturas"] = int(row.get("total", 0))
                agrupado[cid]["facturas_activas"] = int(row.get("activas", 0))
                agrupado[cid]["activas_pendientes"] = int(row.get("pend", 0))
                agrupado[cid]["activas_parciales"] = int(row.get("parc", 0))
                agrupado[cid]["activas_vencidas"] = int(row.get("venc", 0))

    resultados = list(agrupado.values())

    # 3) Aplicar filtros por monto total agregado
    try:
        monto_min_str = filtros.get("monto_min")
        if monto_min_str not in (None, ""):
            monto_min = Decimal(str(monto_min_str))
            resultados = [r for r in resultados if r["total_pendiente"] >= monto_min]
    except (InvalidOperation, ValueError, TypeError):
        pass

    try:
        monto_max_str = filtros.get("monto_max")
        if monto_max_str not in (None, ""):
            monto_max = Decimal(str(monto_max_str))
            resultados = [r for r in resultados if r["total_pendiente"] <= monto_max]
    except (InvalidOperation, ValueError, TypeError):
        pass

    # 4) Filtro por estado agregado (al día)
    estado = filtros.get("estado")
    if estado == "aldia":
        resultados = [r for r in resultados if r["total_pendiente"] <= Decimal("0.00")]

    return resultados


 


 


 


 


 