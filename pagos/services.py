from __future__ import annotations

from datetime import timedelta
from typing import Dict, Iterable, List

from django.core.exceptions import PermissionDenied
from django.db.models import Count, QuerySet, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from facturas.models import Factura

from .models import Pago

# Campos adicionales para cada método de pago. Se pueden extender según requisitos de negocio.
_METODOS_PAGO_METADATA: Dict[str, Dict[str, object]] = {
    "efectivo": {
        "requiere_referencia": False,
        "permite_comprobante": False,
        "descripcion": "Pago en efectivo sin comprobante obligatorio.",
    },
    "transferencia": {
        "requiere_referencia": True,
        "permite_comprobante": True,
        "descripcion": "Transferencia bancaria; requiere número de referencia.",
    },
    "cheque": {
        "requiere_referencia": True,
        "permite_comprobante": True,
        "descripcion": "Pago con cheque; registrar número de cheque.",
    },
    "tarjeta_credito": {
        "requiere_referencia": True,
        "permite_comprobante": True,
        "descripcion": "Pago con tarjeta de crédito procesado por pasarela.",
    },
    "tarjeta_debito": {
        "requiere_referencia": True,
        "permite_comprobante": True,
        "descripcion": "Pago con tarjeta de débito procesado por pasarela.",
    },
    "consignacion": {
        "requiere_referencia": True,
        "permite_comprobante": True,
        "descripcion": "Consignación bancaria; adjuntar soporte.",
    },
    "otro": {
        "requiere_referencia": False,
        "permite_comprobante": True,
        "descripcion": "Otro tipo de pago definido manualmente.",
    },
}


def _usuario_tiene_rol(user, nombre_rol: str) -> bool:
    return user.groups.filter(name=nombre_rol).exists()


def obtener_metodos_pago() -> List[Dict[str, object]]:
    """Retorna los métodos de pago disponibles con metadatos adicionales."""
    metodos: List[Dict[str, object]] = []
    for metodo_id, nombre in Pago.TIPOS_PAGO:
        metadata = _METODOS_PAGO_METADATA.get(metodo_id, {})
        metodos.append(
            {
                "id": metodo_id,
                "nombre": nombre,
                "requiere_referencia": metadata.get("requiere_referencia", False),
                "permite_comprobante": metadata.get("permite_comprobante", True),
                "descripcion": metadata.get("descripcion", ""),
            }
        )
    return metodos


def filtrar_pagos_por_usuario(user, params) -> QuerySet[Pago]:
    """Construye queryset de pagos según permisos y filtros enviados."""
    queryset = Pago.objects.select_related("factura", "factura__cliente", "usuario_registro")

    if _usuario_tiene_rol(user, "Gerente"):
        pass
    elif _usuario_tiene_rol(user, "Vendedor"):
        queryset = queryset.filter(factura__vendedor=user)
    elif _usuario_tiene_rol(user, "Distribuidor"):
        queryset = queryset.filter(factura__distribuidor=user)
    else:
        return queryset.none()

    factura_id = params.get("factura_id")
    if factura_id:
        queryset = queryset.filter(factura_id=factura_id)

    tipo_pago = params.get("tipo_pago")
    if tipo_pago:
        queryset = queryset.filter(tipo_pago=tipo_pago)

    fecha_desde = params.get("fecha_desde")
    if fecha_desde:
        queryset = queryset.filter(fecha_pago__date__gte=fecha_desde)

    fecha_hasta = params.get("fecha_hasta")
    if fecha_hasta:
        queryset = queryset.filter(fecha_pago__date__lte=fecha_hasta)

    return queryset


def validar_usuario_puede_registrar_pago(user, factura: Factura) -> None:
    """Verifica si el usuario autenticado puede registrar un pago para la factura."""
    if _usuario_tiene_rol(user, "Gerente"):
        return

    if _usuario_tiene_rol(user, "Vendedor") and factura.vendedor_id == user.id:  # type: ignore[attr-defined]
        return

    if _usuario_tiene_rol(user, "Distribuidor") and factura.distribuidor_id == user.id:  # type: ignore[attr-defined]
        return

    raise PermissionDenied("No tiene permisos para registrar pagos en esta factura")


def crear_pago_para_factura(user, factura: Factura, validated_data: Dict[str, object]) -> Pago:
    """Crea un pago asociado a una factura validando permisos y asignando usuario."""
    validar_usuario_puede_registrar_pago(user, factura)

    campos_creacion = {
        "factura": factura,
        "usuario_registro": user,
        "valor_pagado": validated_data.get("valor_pagado"),
        "tipo_pago": validated_data.get("tipo_pago"),
        "fecha_pago": validated_data.get("fecha_pago", timezone.now()),
        "comprobante": validated_data.get("comprobante"),
        "numero_comprobante": validated_data.get("numero_comprobante"),
        "notas": validated_data.get("notas"),
    }

    return Pago.objects.create(**campos_creacion)


def obtener_estadisticas_dashboard(queryset: QuerySet[Pago]) -> Dict[str, object]:
    """Construye la estructura del dashboard de pagos."""
    # Considerar solo pagos confirmados para métricas
    queryset = queryset.filter(estado='confirmado')
    hoy = timezone.now()
    inicio_mes = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    rango_semana = hoy - timedelta(days=6)

    total_pagos = queryset.count()
    monto_total = queryset.aggregate(total=Sum("valor_pagado"))[
        "total"
    ] or 0

    pagos_mes = queryset.filter(fecha_pago__gte=inicio_mes)
    pagos_mes_count = pagos_mes.count()
    pagos_mes_monto = pagos_mes.aggregate(total=Sum("valor_pagado"))["total"] or 0

    pagos_por_tipo: Dict[str, Dict[str, object]] = {}
    for tipo, nombre in Pago.TIPOS_PAGO:
        datos_tipo = queryset.filter(tipo_pago=tipo)
        pagos_por_tipo[tipo] = {
            "nombre": nombre,
            "cantidad": datos_tipo.count(),
            "monto": datos_tipo.aggregate(total=Sum("valor_pagado"))["total"] or 0,
        }

    tendencia = (
        queryset.filter(fecha_pago__date__gte=rango_semana.date())
        .annotate(fecha=TruncDate("fecha_pago"))
        .values("fecha")
        .annotate(pagos=Count("id"), monto=Sum("valor_pagado"))
        .order_by("fecha")
    )

    tendencia_list = [
        {
            "fecha": registro["fecha"].isoformat(),
            "pagos": registro["pagos"],
            "monto": registro["monto"] or 0,
        }
        for registro in tendencia
    ]

    return {
        "estadisticas_generales": {
            "total_pagos": total_pagos,
            "monto_total": monto_total,
        },
        "pagos_mes_actual": {
            "cantidad": pagos_mes_count,
            "monto": pagos_mes_monto,
        },
        "pagos_por_metodo": pagos_por_tipo,
        "tendencia_semanal": tendencia_list,
    }


def generar_filas_exportacion(queryset: QuerySet[Pago]) -> Iterable[List[object]]:
    """Genera filas para exportar pagos en formato tabular."""
    yield [
        "ID",
        "Fecha pago",
        "Factura",
        "Cliente",
        "Valor pagado",
        "Tipo pago",
        "Número comprobante",
        "Registrado por",
    ]

    for pago in queryset.iterator():
        yield [
            pago.id,  # type: ignore[attr-defined]
            pago.fecha_pago.isoformat(),
            pago.factura.numero_factura,
            pago.factura.cliente.nombre,
            float(pago.valor_pagado),
            pago.get_tipo_pago_display(),  # type: ignore[attr-defined]
            pago.numero_comprobante or "",
            pago.usuario_registro.get_full_name() if pago.usuario_registro else "",
        ]
