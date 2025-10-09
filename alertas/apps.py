from django.apps import AppConfig


class AlertasConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'alertas'
    
    def ready(self):
        """Registrar signals cuando la app esté lista"""
        import alertas.signals
