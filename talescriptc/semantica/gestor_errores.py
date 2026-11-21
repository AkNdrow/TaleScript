"""
Gestor de Errores — Catálogo E01-E12, W01, L01-L02, S01
========================================================
Política anti-cascada: una vez que un símbolo se marca con tipo ERROR,
no se reportan errores adicionales que lo involucren.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class MensajeCompilador:
    """Un error, advertencia o log emitido durante la compilación."""
    codigo: str       # E01, W01, L01, S01, etc.
    nivel: str        # 'error' | 'warning' | 'log'
    linea: int
    mensaje: str


# ---------------------------------------------------------------------------
# Catálogo de mensajes
# ---------------------------------------------------------------------------
_CATALOGO = {
    # Errores semánticos
    'E01': ('error',   "Variable '{nombre}' no declarada."),
    'E02': ('error',   "Variable '{nombre}' ya declarada en este ámbito (primera declaración en línea {linea_previa})."),
    'E03': ('error',   "Tipo incompatible en asignación: se esperaba '{esperado}', se obtuvo '{obtenido}'."),
    'E04': ('error',   "Tipos incompatibles en operación '{op}': '{tipo_izq}' y '{tipo_der}'."),
    'E05': ('error',   "Nodo '{nombre}' referenciado pero nunca definido."),
    'E06': ('error',   "Nodo '{nombre}' ya definido (primera definición en línea {linea_previa})."),
    'E07': ('error',   "Nodo 'inicio' no definido. Todo programa TaleScript debe contener un nodo 'inicio'."),
    'E08': ('error',   "División por cero detectada en expresión constante."),
    'E09': ('error',   "La expresión en 'choice' debe ser de tipo 'string', se obtuvo '{tipo}'."),
    'E10': ('error',   "El destino '{nombre}' en 'choice' debe ser un nodo válido."),
    'E11': ('error',   "Nodo '{nombre}' no tiene sentencia de salida (goto, choice o exit)."),
    'E12': ('error',   "Nodo '{nombre}' es inalcanzable (ningún goto/choice lo referencia)."),
    # Advertencias
    'W01': ('warning', "Variable '{nombre}' declarada en línea {linea_decl} pero nunca usada."),
    # Logs informativos
    'L01': ('log',     "Plegado de constantes aplicado: {expr} → {valor}."),
    'L02': ('log',     "Propagación de copias aplicado: {variable} → {valor}."),
    # Error de sintaxis
    'S01': ('error',   "Error de sintaxis en línea {linea}: token inesperado '{token}'."),
}


class GestorErrores:
    """Recolecta y administra errores, advertencias y logs del compilador."""

    def __init__(self):
        self._mensajes: list[MensajeCompilador] = []
        self._errores_por_linea: set[int] = set()   # anti-cascada por línea
        self._conteo_errores: int = 0
        self._conteo_warnings: int = 0
        self._max_errores: int = 50  # límite razonable

    # ------------------------------------------------------------------
    # Emisión de mensajes
    # ------------------------------------------------------------------
    def error(self, codigo: str, linea: int, **kwargs) -> None:
        """Emite un error del catálogo. Respeta política anti-cascada."""
        if self._conteo_errores >= self._max_errores:
            return
        # Anti-cascada: si ya hay un error en esta línea, suprimir
        if linea in self._errores_por_linea and codigo not in ('E07',):
            return
        nivel, plantilla = _CATALOGO[codigo]
        mensaje = plantilla.format(linea=linea, **kwargs)
        self._mensajes.append(MensajeCompilador(codigo, nivel, linea, mensaje))
        if nivel == 'error':
            self._conteo_errores += 1
            self._errores_por_linea.add(linea)

    def warning(self, codigo: str, linea: int, **kwargs) -> None:
        """Emite una advertencia del catálogo."""
        nivel, plantilla = _CATALOGO[codigo]
        mensaje = plantilla.format(linea=linea, **kwargs)
        self._mensajes.append(MensajeCompilador(codigo, nivel, linea, mensaje))
        self._conteo_warnings += 1

    def log(self, codigo: str, linea: int, **kwargs) -> None:
        """Emite un mensaje informativo del catálogo."""
        nivel, plantilla = _CATALOGO[codigo]
        mensaje = plantilla.format(linea=linea, **kwargs)
        self._mensajes.append(MensajeCompilador(codigo, nivel, linea, mensaje))

    def error_tipo_propagado(self, *tipos: str) -> bool:
        """Retorna True si alguno de los tipos es ERROR (anti-cascada).
        Cuando un operando ya es ERROR, no se reportan errores adicionales."""
        return any(t == 'ERROR' for t in tipos)

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------
    def hay_errores(self) -> bool:
        return self._conteo_errores > 0

    @property
    def total_errores(self) -> int:
        return self._conteo_errores

    @property
    def total_warnings(self) -> int:
        return self._conteo_warnings

    def obtener_errores(self) -> list[MensajeCompilador]:
        return [m for m in self._mensajes if m.nivel == 'error']

    def obtener_advertencias(self) -> list[MensajeCompilador]:
        return [m for m in self._mensajes if m.nivel == 'warning']

    def obtener_todos(self) -> list[MensajeCompilador]:
        return list(self._mensajes)

    # ------------------------------------------------------------------
    # Volcado formateado
    # ------------------------------------------------------------------
    def dump(self) -> str:
        lines = []
        for m in self._mensajes:
            icono = {'error': '❌', 'warning': '⚠️', 'log': 'ℹ️'}.get(m.nivel, '?')
            lines.append(f'{icono} [{m.codigo}] Línea {m.linea}: {m.mensaje}')
        if not lines:
            lines.append('Sin errores ni advertencias.')
        resumen = f'\nTotal: {self._conteo_errores} error(es), {self._conteo_warnings} advertencia(s).'
        lines.append(resumen)
        return '\n'.join(lines)
