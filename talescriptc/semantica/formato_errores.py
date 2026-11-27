"""
Formato Detallado de Diagnósticos
=================================
Convierte los registros de `GestorErrores` en un reporte legible que
muestra la línea de código afectada, un marcador `^` bajo la columna del
problema y una sugerencia para corregirlo:

    error[S01] (sintáctico): falta ';' al final de la sentencia.
      --> historia.ts:3:15
       |
     3 |     say "hola"
       |               ^ se esperaba ';' aquí
       = ayuda: toda sentencia termina en ';'.

El reporte se produce como una lista de segmentos `(texto, estilo)` para
que la consola (colores ANSI) y TaleScript Studio (tags de Tkinter) lo
pinten cada uno a su manera sin duplicar la lógica.
"""
from __future__ import annotations

import re
from typing import Iterable

from talescriptc.semantica.gestor_errores import ERROR, LEXICO, SINTACTICO, RegistroError

# Estilos que emite el formateador
TITULO_ERROR = 'titulo_error'
TITULO_AVISO = 'titulo_aviso'
UBICACION = 'ubicacion'
MARGEN = 'margen'
CODIGO = 'codigo'
MARCA_ERROR = 'marca_error'
MARCA_AVISO = 'marca_aviso'
AYUDA = 'ayuda'
NORMAL = 'normal'

_NOMBRE_FASE = {LEXICO: 'léxico', SINTACTICO: 'sintáctico'}

_ANSI = {
    TITULO_ERROR: '\033[1;31m',
    TITULO_AVISO: '\033[1;33m',
    UBICACION: '\033[36m',
    MARGEN: '\033[34m',
    CODIGO: '',
    MARCA_ERROR: '\033[1;31m',
    MARCA_AVISO: '\033[1;33m',
    AYUDA: '\033[32m',
    NORMAL: '',
}
_ANSI_RESET = '\033[0m'


def _columna_y_longitud(reg: RegistroError, texto_linea: str) -> tuple[int, int]:
    """Columna (1-based) y longitud del subrayado.

    Los errores semánticos solo traen la línea; en ese caso se busca el
    identificador involucrado (`contexto`) dentro de la línea y, si no
    aparece, se subraya la sentencia completa.
    """
    if reg.columna and reg.columna > 0:
        return reg.columna, max(1, reg.longitud)
    if reg.contexto:
        m = re.search(rf'\b{re.escape(reg.contexto)}\b', texto_linea)
        if m:
            return m.start() + 1, len(reg.contexto)
    contenido = texto_linea.rstrip()
    inicio = len(contenido) - len(contenido.lstrip())
    return inicio + 1, max(1, len(contenido) - inicio)


def segmentos_error(reg: RegistroError, fuente: str, archivo: str = '') -> list[tuple[str, str]]:
    """Segmentos (texto, estilo) de un diagnóstico, terminados en salto de línea."""
    es_error = reg.severidad == ERROR
    tipo = 'error' if es_error else 'aviso'
    fase = _NOMBRE_FASE.get(reg.fase, 'semántico')
    titulo = TITULO_ERROR if es_error else TITULO_AVISO
    marca = MARCA_ERROR if es_error else MARCA_AVISO

    seg: list[tuple[str, str]] = [
        (f'{tipo}[{reg.codigo}] ({fase}): ', titulo),
        (f'{reg.mensaje}\n', NORMAL),
    ]

    lineas = fuente.split('\n')
    if not (1 <= reg.linea <= len(lineas)):
        if reg.ayuda:
            seg.append((f'  = ayuda: {reg.ayuda}\n', AYUDA))
        return seg

    texto_linea = lineas[reg.linea - 1].rstrip('\r')
    col, largo = _columna_y_longitud(reg, texto_linea)
    ancho = len(str(reg.linea))
    vacio = ' ' * ancho
    nombre = archivo or '<editor>'

    seg.append((f'{vacio}--> ', MARGEN))
    seg.append((f'{nombre}:{reg.linea}:{col}\n', UBICACION))
    seg.append((f'{vacio} |\n', MARGEN))
    seg.append((f'{reg.linea} | ', MARGEN))
    seg.append((f'{texto_linea}\n', CODIGO))
    # Respetar tabuladores para que '^' quede alineado bajo el carácter
    prefijo = ''.join('\t' if c == '\t' else ' ' for c in texto_linea[:col - 1])
    if len(prefijo) < col - 1:
        prefijo += ' ' * (col - 1 - len(prefijo))
    seg.append((f'{vacio} | ', MARGEN))
    seg.append((prefijo + '^' * largo + '\n', marca))
    if reg.ayuda:
        seg.append((f'{vacio} = ayuda: {reg.ayuda}\n', AYUDA))
    return seg


def segmentos_reporte(registros: Iterable[RegistroError], fuente: str,
                      archivo: str = '') -> list[tuple[str, str]]:
    """Reporte completo: cada diagnóstico separado por una línea en blanco + resumen."""
    registros = list(registros)
    seg: list[tuple[str, str]] = []
    for reg in registros:
        seg.extend(segmentos_error(reg, fuente, archivo))
        seg.append(('\n', NORMAL))
    n_err = sum(1 for r in registros if r.severidad == ERROR)
    n_av = len(registros) - n_err
    estilo = TITULO_ERROR if n_err else (TITULO_AVISO if n_av else NORMAL)
    seg.append((f'{n_err} error(es), {n_av} aviso(s).\n', estilo))
    return seg


def reporte_detallado(registros: Iterable[RegistroError], fuente: str,
                      archivo: str = '', color: bool = False) -> str:
    """Reporte en texto plano (o con colores ANSI si `color=True`)."""
    partes = []
    for texto, estilo in segmentos_reporte(registros, fuente, archivo):
        codigo = _ANSI.get(estilo, '') if color else ''
        if codigo:
            # Cerrar el color antes del salto de línea
            cuerpo = texto.rstrip('\n')
            partes.append(f'{codigo}{cuerpo}{_ANSI_RESET}' + texto[len(cuerpo):])
        else:
            partes.append(texto)
    return ''.join(partes)
