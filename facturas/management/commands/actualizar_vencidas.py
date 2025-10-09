"""
Comando para actualizar automáticamente los estados de facturas vencidas
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from facturas.models import Factura


class Command(BaseCommand):
    help = 'Actualiza automáticamente el estado de facturas vencidas'

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Mostrar información detallada del proceso',
        )

    def handle(self, *args, **options):
        verbose = options['verbose']
        
        if verbose:
            self.stdout.write('🔄 Iniciando actualización de estados de facturas vencidas...')
        
        # Actualizar facturas vencidas
        count = Factura.actualizar_estados_vencidas()
        
        if verbose:
            self.stdout.write(f'📋 Se encontraron {count} facturas para actualizar a estado "vencida"')
            
            # Mostrar estadísticas actuales
            from django.db.models import Count
            stats = Factura.objects.values('estado').annotate(count=Count('id'))
            
            self.stdout.write('\n📊 Estadísticas actuales de facturas:')
            for stat in stats:
                estado_display = dict(Factura.ESTADOS).get(stat['estado'], stat['estado'])
                self.stdout.write(f"   {estado_display}: {stat['count']} facturas")
        
        if count > 0:
            self.stdout.write(
                self.style.SUCCESS(f'✅ Se actualizaron {count} facturas a estado "vencida"')
            )
        else:
            self.stdout.write(
                self.style.WARNING('ℹ️  No se encontraron facturas para actualizar')
            )