from __future__ import annotations

from typing import Dict, List

from django.core.exceptions import PermissionDenied
from django.db.models import QuerySet
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
    queryset = Pago.objects.select_related("factura", "factura__cliente", "usuario_registro", "cuenta")

    if _usuario_tiene_rol(user, "Gerente"):
        pass
    elif _usuario_tiene_rol(user, "Vendedor"):
        queryset = queryset.filter(factura__vendedor=user)
    elif _usuario_tiene_rol(user, "Distribuidor"):
        # Distribuidor solo ve pagos que él registró
        queryset = queryset.filter(usuario_registro=user)
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
    "comprobante_b64": validated_data.get("comprobante_b64"),
        "numero_comprobante": validated_data.get("numero_comprobante"),
        "referencia": validated_data.get("referencia"),
        "cuenta": validated_data.get("cuenta"),
        "notas": validated_data.get("notas"),
        # Campos de descuentos/retenciones/ICA/nota
        "descuento": validated_data.get("descuento", 0),
        "retencion": validated_data.get("retencion", 0),
        "ica": validated_data.get("ica", 0),
        "nota": validated_data.get("nota", 0),
    }

    return Pago.objects.create(**campos_creacion)


 
