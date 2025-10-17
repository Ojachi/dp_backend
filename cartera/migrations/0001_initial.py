# Generated manually for initial Cartera models
from __future__ import annotations

import decimal

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("clientes", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PerfilCreditoCliente",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "limite_credito",
                    models.DecimalField(decimal_places=2, default=decimal.Decimal("0.00"), max_digits=12),
                ),
                ("dias_promedio_cobranza", models.PositiveIntegerField(default=0)),
                (
                    "porcentaje_mora",
                    models.DecimalField(decimal_places=2, default=decimal.Decimal("0.00"), max_digits=5),
                ),
                ("notas", models.TextField(blank=True)),
                ("creado", models.DateTimeField(auto_now_add=True)),
                ("actualizado", models.DateTimeField(auto_now=True)),
                (
                    "cliente",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="perfil_credito",
                        to="clientes.cliente",
                    ),
                ),
            ],
            options={
                "verbose_name": "Perfil de crédito",
                "verbose_name_plural": "Perfiles de crédito",
            },
        ),
        migrations.CreateModel(
            name="GestionCobranza",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "tipo",
                    models.CharField(
                        choices=[
                            ("llamada", "Llamada"),
                            ("correo", "Correo"),
                            ("visita", "Visita"),
                            ("mensaje", "Mensaje"),
                            ("otro", "Otro"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "resultado",
                    models.CharField(
                        choices=[
                            ("promesa_pago", "Promesa de pago"),
                            ("no_contactado", "No contactado"),
                            ("recordatorio", "Recordatorio"),
                            ("negociacion", "En negociación"),
                            ("otro", "Otro"),
                        ],
                        max_length=20,
                    ),
                ),
                ("observaciones", models.TextField(blank=True)),
                ("proximo_contacto", models.DateField(blank=True, null=True)),
                ("creado", models.DateTimeField(auto_now_add=True)),
                (
                    "cliente",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="gestiones_cobranza",
                        to="clientes.cliente",
                    ),
                ),
                (
                    "usuario",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="gestiones_registradas",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-creado"]},
        ),
        migrations.CreateModel(
            name="EnvioEstadoCuenta",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("medio", models.CharField(default="email", max_length=30)),
                (
                    "estado",
                    models.CharField(
                        choices=[
                            ("pendiente", "Pendiente"),
                            ("enviado", "Enviado"),
                            ("error", "Error"),
                        ],
                        default="pendiente",
                        max_length=20,
                    ),
                ),
                ("detalle", models.JSONField(blank=True, default=dict)),
                ("enviado_en", models.DateTimeField(blank=True, null=True)),
                ("creado", models.DateTimeField(auto_now_add=True)),
                (
                    "cliente",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="envios_estado_cuenta",
                        to="clientes.cliente",
                    ),
                ),
                (
                    "usuario",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="envios_estado_cuenta",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-creado"]},
        ),
    ]
