from django.db import models
from django.conf import settings

class Distribuidor(models.Model):
    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='perfil_distribuidor')
    codigo = models.CharField(max_length=50, unique=True)
    zona = models.CharField(max_length=100, blank=True, null=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.usuario.get_full_name()} ({self.codigo})"
