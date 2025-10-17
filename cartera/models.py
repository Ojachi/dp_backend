from __future__ import annotations

from decimal import Decimal
from typing import Optional

from django.conf import settings
from django.db import models
from django.utils import timezone

from clientes.models import Cliente


class PerfilCreditoCliente(models.Model):
    cliente = models.OneToOneField(
        Cliente,
        on_delete=models.CASCADE,
        related_name="perfil_credito",
    )
    limite_credito = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    dias_promedio_cobranza = models.PositiveIntegerField(default=0)
    porcentaje_mora = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    notas = models.TextField(blank=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Perfil de crédito"
        verbose_name_plural = "Perfiles de crédito"

    def __str__(self) -> str:
        return f"Perfil crédito {self.cliente.nombre}"

    def actualizar_metricas(
        self,
        *,
        dias_promedio: Optional[int] = None,
        porcentaje_mora: Optional[Decimal] = None,
    ) -> None:
        cambios = {}
        if dias_promedio is not None:
            self.dias_promedio_cobranza = dias_promedio
            cambios["dias_promedio_cobranza"] = dias_promedio
        if porcentaje_mora is not None:
            self.porcentaje_mora = porcentaje_mora
            cambios["porcentaje_mora"] = porcentaje_mora
        if cambios:
            self.save(update_fields=[*cambios.keys(), "actualizado"])


class GestionCobranza(models.Model):
    TIPOS_GESTION = [
        ("llamada", "Llamada"),
        ("correo", "Correo"),
        ("visita", "Visita"),
        ("mensaje", "Mensaje"),
        ("otro", "Otro"),
    ]

    RESULTADOS = [
        ("promesa_pago", "Promesa de pago"),
        ("no_contactado", "No contactado"),
        ("recordatorio", "Recordatorio"),
        ("negociacion", "En negociación"),
        ("otro", "Otro"),
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="gestiones_cobranza")
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gestiones_registradas",
    )
    tipo = models.CharField(max_length=20, choices=TIPOS_GESTION)
    resultado = models.CharField(max_length=20, choices=RESULTADOS)
    observaciones = models.TextField(blank=True)
    proximo_contacto = models.DateField(null=True, blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado"]

    def tipo_display(self) -> str:
        return dict(self.TIPOS_GESTION).get(self.tipo, self.tipo)

    def __str__(self) -> str:
        return f"Gestión {self.tipo_display()} - {self.cliente.nombre}"


class EnvioEstadoCuenta(models.Model):
    ESTADOS = [
        ("pendiente", "Pendiente"),
        ("enviado", "Enviado"),
        ("error", "Error"),
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="envios_estado_cuenta")
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="envios_estado_cuenta",
    )
    medio = models.CharField(max_length=30, default="email")
    estado = models.CharField(max_length=20, choices=ESTADOS, default="pendiente")
    detalle = models.JSONField(default=dict, blank=True)
    enviado_en = models.DateTimeField(null=True, blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado"]

    def marcar_enviado(self, detalle: Optional[dict] = None) -> None:
        self.estado = "enviado"
        self.enviado_en = timezone.now()
        if detalle is not None:
            self.detalle = detalle
        self.save(update_fields=["estado", "enviado_en", "detalle"])

    def marcar_error(self, mensaje: str) -> None:
        self.estado = "error"
        self.detalle = {"error": mensaje}
        self.enviado_en = timezone.now()
        self.save(update_fields=["estado", "detalle", "enviado_en"])
