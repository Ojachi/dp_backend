# Generated manually to add FacturaImportacion tracking model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("facturas", "0002_alter_factura_options_alter_factura_estado_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="FacturaImportacion",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("archivo_nombre", models.CharField(max_length=255)),
                (
                    "estado",
                    models.CharField(
                        choices=[
                            ("pendiente", "Pendiente"),
                            ("validado", "Validado"),
                            ("procesando", "Procesando"),
                            ("completado", "Completado"),
                            ("error", "Error"),
                        ],
                        default="pendiente",
                        max_length=20,
                    ),
                ),
                ("total_registros", models.PositiveIntegerField(default=0)),
                ("registros_validos", models.PositiveIntegerField(default=0)),
                ("registros_invalidos", models.PositiveIntegerField(default=0)),
                ("detalle", models.JSONField(blank=True, default=dict)),
                ("errores", models.JSONField(blank=True, default=list)),
                ("creado", models.DateTimeField(auto_now_add=True)),
                ("actualizado", models.DateTimeField(auto_now=True)),
                (
                    "usuario",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="importaciones_facturas",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-creado"]},
        ),
    ]
