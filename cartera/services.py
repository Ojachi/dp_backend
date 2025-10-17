from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Dict, Iterable, List, TypedDict, cast

from django.db.models import Count, QuerySet, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from clientes.models import Cliente
from facturas.models import Factura
from pagos.models import Pago

from .models import GestionCobranza, PerfilCreditoCliente


RANGOS_MORA = [
    (0, 30, "0-30"),
    (31, 60, "31-60"),
    (61, 90, "61-90"),
    (91, 9999, "90+"),
]


class DatosCuentaAgrupada(TypedDict):
    cliente: Cliente
    total_pendiente: Decimal
    facturas: List[Factura]


def obtener_resumen_cartera() -> Dict[str, Decimal | int]:
    hoy = timezone.now().date()
    facturas = Factura.objects.all()
    pendientes = facturas.filter(estado__in=["pendiente", "parcial", "vencida"])

    total_cartera = pendientes.aggregate(total=Sum("valor_total"))["total"] or Decimal("0.00")
    total_pagado = pendientes.aggregate(total=Sum("pagos__valor_pagado"))["total"] or Decimal("0.00")
    cuentas_por_cobrar = total_cartera - total_pagado

    facturas_pendientes = pendientes.count()
    clientes_con_mora = (
        Factura.objects.filter(estado__in=["vencida"], fecha_vencimiento__lt=hoy)
        .values("cliente_id")
        .distinct()
        .count()
    )

    # Calcular días promedio de cobranza usando diferencia entre fecha pago más reciente y emisión
    pagos = (
        Pago.objects.filter(factura__in=pendientes)
        .select_related("factura")
        .values("factura_id", "fecha_pago", "factura__fecha_emision")
    )
    dias_totales = 0
    pagos_contados = 0
    for pago in pagos:
        fecha_pago = pago["fecha_pago"].date()
        fecha_emision = pago["factura__fecha_emision"]
        dias_totales += (fecha_pago - fecha_emision).days
        pagos_contados += 1
    dias_promedio = int(dias_totales / pagos_contados) if pagos_contados else 0

    total_facturas = facturas.count() or 1
    facturas_mora = pendientes.filter(fecha_vencimiento__lt=hoy).count()
    porcentaje_mora = (Decimal(facturas_mora) / Decimal(total_facturas)) * Decimal("100")

    return {
        "total_cartera": total_cartera,
        "cuentas_por_cobrar": cuentas_por_cobrar,
        "facturas_pendientes": facturas_pendientes,
        "clientes_con_mora": clientes_con_mora,
        "dias_promedio_cobranza": dias_promedio,
        "porcentaje_mora": porcentaje_mora.quantize(Decimal("0.01")),
    }


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
    queryset = cuentas_por_cobrar_queryset(filtros)
    agrupado: Dict[int, DatosCuentaAgrupada] = {}

    for factura in queryset:
        cliente_id = cast(int, getattr(factura, "cliente_id"))
        if cliente_id not in agrupado:
            agrupado[cliente_id] = {
                "cliente": factura.cliente,
                "total_pendiente": Decimal("0.00"),
                "facturas": [],
            }
        agrupado[cliente_id]["total_pendiente"] += factura.saldo_pendiente
        agrupado[cliente_id]["facturas"].append(factura)

    return list(agrupado.values())


def obtener_detalle_cuenta(cliente_id: int) -> Dict[str, object]:
    facturas = Factura.objects.filter(cliente_id=cliente_id).select_related("cliente")
    if not facturas.exists():
        from django.core.exceptions import ObjectDoesNotExist

        raise ObjectDoesNotExist("Cliente sin facturas registradas")

    primer_registro = facturas.first()
    if primer_registro is None:
        from django.core.exceptions import ObjectDoesNotExist

        raise ObjectDoesNotExist("Cliente sin facturas registradas")

    cliente = primer_registro.cliente
    pagos_recientes = (
        Pago.objects.filter(factura__cliente_id=cliente_id)
        .select_related("factura")
        .order_by("-fecha_pago")[:10]
    )

    total_pendiente = sum((factura.saldo_pendiente for factura in facturas), Decimal("0.00"))

    perfil = PerfilCreditoCliente.objects.filter(cliente_id=cliente_id).first()
    limite_credito = perfil.limite_credito if perfil else Decimal("0.00")

    return {
        "cliente": cliente,
        "facturas": list(facturas),
        "pagos_recientes": list(pagos_recientes),
        "total_pendiente": total_pendiente,
        "limite_credito": limite_credito,
    }


def actualizar_limite_credito(cliente_id: int, limite: Decimal, notas: str | None = None) -> PerfilCreditoCliente:
    perfil, _ = PerfilCreditoCliente.objects.get_or_create(cliente_id=cliente_id)
    perfil.limite_credito = limite
    if notas is not None:
        perfil.notas = notas
    perfil.save(update_fields=["limite_credito", "notas", "actualizado"])
    return perfil


def obtener_estadisticas_mora() -> List[Dict[str, object]]:
    hoy = timezone.now().date()
    facturas = Factura.objects.filter(estado__in=["pendiente", "parcial", "vencida"])
    resultado: List[Dict[str, object]] = []

    for minimo, maximo, etiqueta in RANGOS_MORA:
        limite_inferior = hoy - timedelta(days=maximo)
        limite_superior = hoy - timedelta(days=minimo)
        qs = facturas.filter(
            fecha_vencimiento__lte=limite_superior,
            fecha_vencimiento__gt=limite_inferior,
        )
        resultado.append(
            {
                "rango": etiqueta,
                "total_facturas": qs.count(),
                "monto_total": qs.aggregate(total=Sum("valor_total"))["total"] or Decimal("0.00"),
            }
        )

    return resultado


def proyeccion_cobranza(meses: int = 6) -> List[Dict[str, object]]:
    hoy = timezone.now().date()
    inicio = hoy.replace(day=1)
    fin = inicio + timedelta(days=meses * 31)

    facturas = (
        Factura.objects.filter(fecha_vencimiento__gte=inicio, fecha_vencimiento__lte=fin)
        .annotate(mes=TruncMonth("fecha_vencimiento"))
        .values("mes")
        .annotate(monto_estimado=Sum("valor_total"), facturas=Count("id"))
        .order_by("mes")
    )

    proyeccion: List[Dict[str, object]] = []
    for item in facturas:
        mes = item["mes"].strftime("%Y-%m") if item["mes"] else ""
        proyeccion.append(
            {
                "mes": mes,
                "monto_estimado": item["monto_estimado"] or Decimal("0.00"),
                "facturas": item["facturas"],
            }
        )

    return proyeccion


def historial_gestiones(cliente_id: int, limite: int = 20) -> Iterable[GestionCobranza]:
    return GestionCobranza.objects.filter(cliente_id=cliente_id).select_related("cliente", "usuario")[:limite]