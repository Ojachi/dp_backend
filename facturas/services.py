from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from io import BytesIO, StringIO
from typing import Any, Dict, Iterable, List, Tuple

import pandas as pd
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.utils import timezone

from .models import Factura, FacturaImportacion

_COLUMNAS_OBLIGATORIAS = [
    "numero_factura",
    "cliente_id",
    "fecha_emision",
    "fecha_vencimiento",
    "valor_total",
]
_COLUMNAS_OPCIONALES = [
    "vendedor_id",
    "distribuidor_id",
    "observaciones",
]


@dataclass
class ResultadoValidacion:
    total: int
    validos: int
    invalidos: int
    errores: List[Dict[str, Any]]


def _leer_dataframe_desde_archivo(archivo: UploadedFile) -> pd.DataFrame:
    nombre = archivo.name.lower()
    contenido = archivo.read()
    archivo.seek(0)

    if nombre.endswith((".xlsx", ".xls")):
        return pd.read_excel(BytesIO(contenido))
    if nombre.endswith(".csv"):
        return pd.read_csv(StringIO(contenido.decode("utf-8-sig")))
    raise ValueError("Formato de archivo no soportado. Use Excel o CSV.")


def validar_archivo_facturas(archivo: UploadedFile) -> ResultadoValidacion:
    df = _leer_dataframe_desde_archivo(archivo)
    columnas_faltantes = set(_COLUMNAS_OBLIGATORIAS) - set(df.columns)
    if columnas_faltantes:
        raise ValueError(f"Columnas faltantes: {', '.join(sorted(columnas_faltantes))}")

    errores: List[Dict[str, Any]] = []
    validos = 0

    for idx, fila in df.iterrows():
        fila_errores: List[str] = []

        for columna in _COLUMNAS_OBLIGATORIAS:
            if pd.isna(fila.get(columna)) or str(fila.get(columna)).strip() == "":
                fila_errores.append(f"El campo '{columna}' es obligatorio")

        try:
            valor_total = float(fila.get("valor_total", 0))
            if valor_total <= 0:
                fila_errores.append("El valor total debe ser mayor que cero")
        except (TypeError, ValueError):
            fila_errores.append("El valor total debe ser numérico")

        for campo_fecha in ("fecha_emision", "fecha_vencimiento"):
            try:
                pd.to_datetime(fila.get(campo_fecha))
            except (TypeError, ValueError):
                fila_errores.append(f"La columna {campo_fecha} no tiene un formato de fecha válido")

        if fila_errores:
            errores.append({"fila": int(idx) + 2, "errores": fila_errores})
        else:
            validos += 1

    return ResultadoValidacion(
        total=len(df.index),
        validos=validos,
        invalidos=len(errores),
        errores=errores,
    )


def generar_vista_previa(archivo: UploadedFile, limite: int = 10) -> List[Dict[str, Any]]:
    df = _leer_dataframe_desde_archivo(archivo)
    if not df.empty:
        return df.head(limite).fillna("").to_dict(orient="records")
    return []


def _preparar_datos_factura(fila: pd.Series) -> Dict[str, Any]:
    datos: Dict[str, Any] = {
        "numero_factura": str(fila["numero_factura"]).strip(),
        "cliente_id": int(fila["cliente_id"]),
        "fecha_emision": pd.to_datetime(fila["fecha_emision"]).date(),
        "fecha_vencimiento": pd.to_datetime(fila["fecha_vencimiento"]).date(),
        "valor_total": float(fila["valor_total"]),
    }

    if not pd.isna(fila.get("vendedor_id")):
        datos["vendedor_id"] = int(fila["vendedor_id"])
    if not pd.isna(fila.get("distribuidor_id")):
        datos["distribuidor_id"] = int(fila["distribuidor_id"])
    if not pd.isna(fila.get("observaciones")):
        datos["observaciones"] = str(fila["observaciones"])

    return datos


@transaction.atomic
def confirmar_importacion_facturas(
    archivo: UploadedFile,
    usuario,
) -> Tuple[FacturaImportacion, Dict[str, Any]]:
    registro = FacturaImportacion.objects.create(
        usuario=usuario if getattr(usuario, "is_authenticated", False) else None,
        archivo_nombre=archivo.name,
        estado="procesando",
    )

    df = _leer_dataframe_desde_archivo(archivo)
    columnas_faltantes = set(_COLUMNAS_OBLIGATORIAS) - set(df.columns)
    if columnas_faltantes:
        registro.registrar_detalle(
            total=0,
            validos=0,
            invalidos=0,
            errores=[{"errores": [f"Faltan columnas: {', '.join(sorted(columnas_faltantes))}"], "fila": 0}],
            estado="error",
            extra={},
        )
        raise ValueError(f"Columnas faltantes: {', '.join(sorted(columnas_faltantes))}")

    total = len(df.index)
    errores: List[Dict[str, Any]] = []
    creadas = 0
    actualizadas = 0

    for idx, fila in df.iterrows():
        numero_fila = int(idx) + 2
        try:
            datos = _preparar_datos_factura(fila)
        except Exception as exc:  # pragma: no cover - conversión defensiva
            errores.append({"fila": numero_fila, "errores": [str(exc)]})
            continue

        numero_factura = datos.pop("numero_factura")
        factura = Factura.objects.filter(numero_factura=numero_factura).first()

        try:
            if factura:
                if factura.pagos.exists():
                    raise ValueError("La factura ya tiene pagos registrados y no puede ser modificada")

                for campo, valor in datos.items():
                    setattr(factura, campo, valor)
                factura.save()
                actualizadas += 1
            else:
                Factura.objects.create(numero_factura=numero_factura, **datos)
                creadas += 1
        except Exception as exc:  # pragma: no cover - error al guardar factura
            errores.append({"fila": numero_fila, "errores": [str(exc)]})

    validos = total - len(errores)
    estado = "completado" if not errores else "error"

    detalle_extra = {
        "creadas": creadas,
        "actualizadas": actualizadas,
        "procesado_en": timezone.now().isoformat(),
    }

    registro.registrar_detalle(
        total=total,
        validos=validos,
        invalidos=len(errores),
        errores=errores,
        estado=estado,
        extra=detalle_extra,
    )

    return registro, {
        "importacion_id": registro.pk,
        "total_registros": total,
        "creadas": creadas,
        "actualizadas": actualizadas,
        "errores": errores,
        "estado": estado,
    }


def obtener_historial_importaciones(limit: int = 20) -> Iterable[FacturaImportacion]:
    return FacturaImportacion.objects.select_related("usuario").all()[:limit]