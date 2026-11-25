"""
Gestor de Errores — Catálogo del Apéndice A del Manual
=======================================================
Centraliza los diagnósticos léxicos (L01-L02), sintácticos (S01),
semánticos (E01-E12) y avisos (W01) para producir un reporte único
ordenado por línea (Manual §3.4).

Política anti-cascada (Manual §3.4): si un operando ya tiene tipo ERROR,
la reducción propaga ERROR, NO reporta un segundo error y NO emite
cuádruplas. Esa decisión la toma la acción semántica consultando
`error_tipo_propagado(...)`; el gestor además descarta duplicados exactos.
"""
from __future__ import annotations

from dataclasses import dataclass

# Tipo especial que marca un subárbol con error (Manual §3.2)
TIPO_ERROR = 'ERROR'

# Fases y severidades (Manual, Listing 8)
LEXICO = 'LEXICO'
SINTACTICO = 'SINTACTICO'
SEMANTICO = 'SEMANTICO'
ERROR = 'ERROR'
WARNING = 'WARNING'


@dataclass
class RegistroError:
    """Un diagnóstico del compilador (Manual, Listing 8)."""
    codigo: str          # "E01".."E12", "W01", "L01", "L02", "S01"
    fase: str            # LEXICO | SINTACTICO | SEMANTICO
    severidad: str       # ERROR | WARNING
    linea: int
    columna: int
    mensaje: str
    contexto: str = ''   # lexema o expresión involucrada
    ayuda: str = ''      # sugerencia para corregir el error (reporte detallado)
    longitud: int = 1    # cuántas columnas subrayar con ^ en el reporte detallado

    # Compatibilidad con código que esperaba MensajeCompilador.nivel
    @property
    def nivel(self) -> str:
        return 'error' if self.severidad == ERROR else 'warning'

    def formato(self, archivo: str = '') -> str:
        """archivo:linea:col: CODIGO: mensaje"""
        prefijo = f'{archivo}:' if archivo else ''
        return f'{prefijo}{self.linea}:{self.columna}: {self.codigo}: {self.mensaje}'


# Alias para no romper importaciones antiguas
MensajeCompilador = RegistroError


class _Faltantes(dict):
    """Permite formatear plantillas aunque falte algún argumento."""
    def __missing__(self, clave):
        return '?'


# ---------------------------------------------------------------------------
# Catálogo (Manual, Tabla 17).  codigo -> (fase, severidad, plantilla)
# Las plantillas usan los argumentos con nombre que envían parser y lexer.
# ---------------------------------------------------------------------------
CATALOGO: dict[str, tuple[str, str, str]] = {
    'E01': (SEMANTICO, ERROR, "Variable '{nombre}' no declarada."),
    'E02': (SEMANTICO, ERROR, "Identificador '{nombre}' ya declarado en el mismo ámbito."),
    'E03': (SEMANTICO, ERROR, "La local '{nombre}' tiene el mismo nombre que una global "
                              "(sombreado no permitido)."),
    'E04': (SEMANTICO, ERROR, "Tipo incompatible: se esperaba '{esperado}' y se obtuvo '{obtenido}'."),
    'E05': (SEMANTICO, ERROR, "Operandos de tipo inválido para '{op}': '{tipo_izq}' y '{tipo_der}'."),
    'E06': (SEMANTICO, ERROR, "División o módulo entre cero constante."),
    'E07': (SEMANTICO, ERROR, "La condición de if/while/do-while debe ser bool; se obtuvo '{obtenido}'."),
    'E08': (SEMANTICO, ERROR, "Ya existe otro node llamado '{nombre}'."),
    'E09': (SEMANTICO, ERROR, "{instruccion} {nombre}: no existe ningún node '{nombre}'."),
    'E10': (SEMANTICO, ERROR, "La opción \"{opcion}\" aparece dos veces en el mismo choice."),
    'E11': (SEMANTICO, ERROR, "'{nombre}' es constante y no se puede reasignar."),
    'E12': (SEMANTICO, ERROR, "El valor de '{nombre}' debe ser una expresión constante."),
    'W01': (SEMANTICO, WARNING, "La variable local '{nombre}' se declara pero nunca se lee."),
    'L01': (LEXICO, ERROR, "{detalle}"),
    'L02': (LEXICO, ERROR, "{detalle}"),
    'S01': (SINTACTICO, ERROR, "Error de sintaxis: se encontró {encontrado}; se esperaba {esperado}."),
}

# Sugerencias por defecto para el reporte detallado (se usan cuando quien
# reporta el error no envía una ayuda más específica).
AYUDAS: dict[str, str] = {
    'E01': "Declárala antes de usarla, p. ej. 'global int {nombre} = 0;' o 'local int {nombre} = 0;'.",
    'E02': "Cambia el nombre de una de las dos declaraciones o elimina la repetida.",
    'E03': "Usa un nombre distinto para la variable local.",
    'E04': "El valor asignado debe ser de tipo '{esperado}'. Usa una conversión explícita, "
           "p. ej. {esperado}(expr), o cambia el tipo de la variable.",
    'E05': "Ambos operandos deben ser del tipo que admite '{op}' (int para aritmética, bool para and/or).",
    'E06': "El divisor es la constante 0: revisa la expresión.",
    'E07': "Usa una comparación, p. ej. 'if (x > 0)' en lugar de 'if (x)'.",
    'E08': "Cada node necesita un nombre único; renombra uno de ellos.",
    'E09': "Declara 'node {nombre} {{ ... }}' o corrige el nombre del destino.",
    'E10': "Cada opción de un choice debe tener un texto distinto.",
    'E11': "Quita 'const' de la declaración si necesitas modificarla.",
    'E12': "Inicializa la constante con literales u otras constantes.",
    'W01': "Usa la variable o elimina su declaración.",
}


class GestorErrores:
    """Recolecta los diagnósticos y genera el reporte ordenado por línea."""

    def __init__(self, archivo: str = ''):
        self.archivo = archivo
        self.lista_errores: list[RegistroError] = []
        self._vistos: set[tuple] = set()

    # ------------------------------------------------------------------
    # Registro (Manual: reportar(codigo, fase, severidad, linea, col, mensaje))
    # ------------------------------------------------------------------
    def reportar(self, codigo: str, fase: str, severidad: str, linea: int,
                 columna: int, mensaje: str, contexto: str = '') -> None:
        clave = (codigo, linea, columna, mensaje)
        if clave in self._vistos:          # mismo problema reportado dos veces
            return
        self._vistos.add(clave)
        self.lista_errores.append(
            RegistroError(codigo, fase, severidad, linea or 0, columna or 0, mensaje, contexto))

    def error(self, codigo: str, linea: int, columna: int = 0, mensaje: str | None = None,
              contexto: str = '', **datos) -> None:
        """Reporta un diagnóstico del catálogo con sus datos (nombre=, op=, ...)."""
        fase, severidad, plantilla = CATALOGO.get(codigo, (SEMANTICO, ERROR, '{detalle}'))
        ayuda = datos.pop('ayuda', None)
        longitud = datos.pop('longitud', 1)
        datos.setdefault('detalle', mensaje or '')
        if codigo in ('L01', 'L02', 'S01') and mensaje:
            texto = mensaje
        else:
            texto = plantilla.format_map(_Faltantes(datos))
        if ayuda is None:
            ayuda = AYUDAS.get(codigo, '').format_map(_Faltantes(datos))
        if not contexto and isinstance(datos.get('nombre'), str):
            contexto = datos['nombre']
        self.reportar(codigo, fase, severidad, linea, columna, texto, contexto)
        registro = self.lista_errores[-1] if self.lista_errores else None
        if registro is not None and registro.codigo == codigo and registro.mensaje == texto:
            registro.ayuda = ayuda or ''
            registro.longitud = max(1, int(longitud or 1))

    def warning(self, codigo: str, linea: int, columna: int = 0, **datos) -> None:
        self.error(codigo, linea, columna, **datos)

    @staticmethod
    def error_tipo_propagado(*tipos: str) -> bool:
        """True si algún operando ya es ERROR: no se reporta de nuevo ni se emite código."""
        return any(t == TIPO_ERROR for t in tipos)

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------
    @property
    def hay_errores_fatales(self) -> bool:
        return any(r.severidad == ERROR for r in self.lista_errores)

    def hay_errores(self) -> bool:
        """Solo cuentan los errores; los avisos no detienen la compilación."""
        return self.hay_errores_fatales

    def obtener_errores(self) -> list[RegistroError]:
        return [r for r in self.ordenados() if r.severidad == ERROR]

    def obtener_advertencias(self) -> list[RegistroError]:
        return [r for r in self.ordenados() if r.severidad == WARNING]

    def obtener_todos(self) -> list[RegistroError]:
        return self.ordenados()

    def codigos(self) -> list[str]:
        """Códigos en orden de línea (útil para las pruebas)."""
        return [r.codigo for r in self.ordenados()]

    @property
    def total_errores(self) -> int:
        return len(self.obtener_errores())

    @property
    def total_warnings(self) -> int:
        return len(self.obtener_advertencias())

    def ordenados(self) -> list[RegistroError]:
        return sorted(self.lista_errores, key=lambda r: (r.linea, r.columna))

    # ------------------------------------------------------------------
    # Reporte
    # ------------------------------------------------------------------
    def imprimir_reporte(self) -> str:
        """Formato del Manual: archivo:linea:col: E04: mensaje"""
        lineas = [r.formato(self.archivo) for r in self.ordenados()]
        lineas.append(f'{self.total_errores} error(es), {self.total_warnings} aviso(s).')
        return '\n'.join(lineas)

    imprimirReporte = imprimir_reporte

    def dump(self) -> str:
        return self.imprimir_reporte()
