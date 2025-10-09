from django.core.management.base import BaseCommand
from django.utils import timezone
from alertas.services import ServicioAlertas
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Procesa automáticamente todas las alertas del sistema'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--tipos',
            nargs='+',
            default=['todas'],
            choices=['vencimiento', 'monto_alto', 'sin_pagos', 'todas'],
            help='Tipos de alertas a procesar (por defecto: todas)'
        )
        
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Mostrar información detallada'
        )
    
    def handle(self, *args, **options):
        inicio = timezone.now()
        tipos = options['tipos']
        verbose = options['verbose']
        
        self.stdout.write(
            self.style.SUCCESS(f"Iniciando procesamiento de alertas: {inicio}")
        )
        
        try:
            if 'todas' in tipos:
                resultados = ServicioAlertas.procesar_todas_las_alertas()
            else:
                resultados = {'detalle': {}}
                total_generadas = 0
                
                if 'vencimiento' in tipos:
                    if verbose:
                        self.stdout.write("Procesando alertas de vencimiento...")
                    cant = ServicioAlertas.generar_alertas_vencimiento()
                    resultados['detalle']['vencimiento'] = cant
                    total_generadas += cant
                    
                if 'monto_alto' in tipos:
                    if verbose:
                        self.stdout.write("Procesando alertas de montos altos...")
                    cant = ServicioAlertas.generar_alertas_montos_altos()
                    resultados['detalle']['montos_altos'] = cant
                    total_generadas += cant
                    
                if 'sin_pagos' in tipos:
                    if verbose:
                        self.stdout.write("Procesando alertas de sin pagos...")
                    cant = ServicioAlertas.generar_alertas_sin_pagos()
                    resultados['detalle']['sin_pagos'] = cant
                    total_generadas += cant
                
                resultados['total_generadas'] = total_generadas
            
            # Mostrar resultados
            total = resultados['total_generadas']
            
            if verbose:
                self.stdout.write(f"\nResultados detallados:")
                for tipo, cantidad in resultados['detalle'].items():
                    self.stdout.write(f"  - {tipo}: {cantidad} alertas")
            
            fin = timezone.now()
            duracion = (fin - inicio).total_seconds()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nProcesamiento completado: {total} alertas generadas en {duracion:.2f} segundos"
                )
            )
            
            # Log para auditoría
            logger.info(
                f"Alertas procesadas automáticamente: {total} generadas. "
                f"Tipos: {tipos}. Duración: {duracion:.2f}s"
            )
            
        except Exception as e:
            error_msg = f"Error procesando alertas: {str(e)}"
            self.stdout.write(self.style.ERROR(error_msg))
            logger.error(error_msg, exc_info=True)
            raise