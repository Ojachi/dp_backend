from django.db import models
from django.contrib.auth.models import AbstractUser

class CustomUser(AbstractUser):
    # Agrega aquí campos adicionales si lo requieres
    name = models.TextField(blank=True, null=True)
    email = models.EmailField(unique=True, blank=False, null=False)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return f"{self.name} {self.email}"
    
    def get_full_name(self):
        """Retorna el nombre completo del usuario"""
        return self.name or self.username or self.email.split('@')[0]
