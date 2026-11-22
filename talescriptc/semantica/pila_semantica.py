"""
Pila Semántica — Manual §3.2 y Tabla 11
========================================
Guarda los atributos sintetizados durante el análisis ascendente.  Cada
reducción saca los atributos de sus operandos, valida tipos, calcula `val`
si es constante y deja en `lugar` dónde queda el resultado (variable,
temporal tN o literal).

Además de la pila, este módulo concentra las REGLAS DE TIPOS (Tabla 11) y la
ARITMÉTICA DEL DESTINO (§5.2: enteros de 64 bits con signo, división truncada
hacia cero, módulo con el signo del dividendo) para que parser y optimizador
usen exactamente las mismas reglas.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .gestor_errores import TIPO_ERROR

INT, STRING, BOOL = 'int', 'string', 'bool'
RELACIONALES = ('<', '<=', '>', '>=')
IGUALDAD = ('==', '!=')
ARITMETICOS = ('+', '-', '*', '/', '%')
LOGICOS = ('and', 'or')


@dataclass
class ElementoPilaSemantica:
    """Manual, Listing 6.  Orden de campos compatible con el parser:
    ElementoPilaSemantica(tipo='int', lugar='t1', val=None, cte=False)."""
    tipo: str = TIPO_ERROR          # int | string | bool | ERROR
    lugar: str = '_err'             # variable ("karma"), temporal ("t1") o literal ("10", "\"txt\"")
    val: Optional[Any] = None       # valor si es constante en compilación
    cte: bool = False               # el subárbol es una expresión constante válida
    simbolo: str = ''               # "A", "M", "id", "+", "relop"...
    lexema: str = ''
    etiqueta_verdadero: str = ''    # reservados (cortocircuito futuro)
    etiqueta_falso: str = ''

    @property
    def es_error(self) -> bool:
        return self.tipo == TIPO_ERROR

    # ---- Constructores de las hojas (Tabla 11) ----
    @classmethod
    def error(cls) -> 'ElementoPilaSemantica':
        return cls(TIPO_ERROR, '_err')

    @classmethod
    def literal(cls, valor: Any) -> 'ElementoPilaSemantica':
        """F → num | true | false | str (sin interpolación)."""
        if isinstance(valor, bool):
            return cls(BOOL, 'true' if valor else 'false', valor, True, 'F', str(valor).lower())
        if isinstance(valor, int):
            return cls(INT, str(valor), valor, True, 'F', str(valor))
        return cls(STRING, texto_literal(valor), valor, True, 'F', valor)

    @classmethod
    def desde_simbolo(cls, entrada) -> 'ElementoPilaSemantica':
        """F → id.  Una const se sustituye por su valor (Manual §2.4: constantes sin
        almacenamiento); una variable deja su nombre en `lugar`."""
        if getattr(entrada, 'es_const', False) and entrada.valor_inicial is not None:
            elem = cls.literal(entrada.valor_inicial)
            elem.lexema = entrada.nombre
            return elem
        return cls(entrada.tipo, entrada.nombre, None, False, 'F', entrada.nombre)


def texto_literal(valor: str) -> str:
    """Representación de un literal de texto en una cuádrupla: "texto"."""
    return '"' + valor.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n') + '"'


class PilaSemantica:
    """Pila LIFO paralela a la pila de análisis."""

    def __init__(self):
        self._pila: list[ElementoPilaSemantica] = []
        self._etiquetas: list[str] = []

    def push(self, elem: ElementoPilaSemantica) -> None:
        self._pila.append(elem)

    apilar = push

    def pop(self) -> ElementoPilaSemantica:
        """Si la pila está vacía (p. ej. tras recuperar un error sintáctico)
        devuelve un elemento ERROR en lugar de abortar: así actúa la anti-cascada."""
        return self._pila.pop() if self._pila else ElementoPilaSemantica.error()

    desapilar = pop

    def top(self) -> ElementoPilaSemantica:
        return self._pila[-1] if self._pila else ElementoPilaSemantica.error()

    @property
    def vacia(self) -> bool:
        return not self._pila

    @property
    def tamanio(self) -> int:
        return len(self._pila)

    # Pila auxiliar de etiquetas (if/while anidados)
    def push_etiqueta(self, etiqueta: str) -> None:
        self._etiquetas.append(etiqueta)

    def pop_etiqueta(self) -> str:
        return self._etiquetas.pop()

    def reset(self) -> None:
        self._pila.clear()
        self._etiquetas.clear()

    def __repr__(self) -> str:
        return '[' + ', '.join(f'{e.lugar}:{e.tipo}' for e in self._pila) + ']'


# ---------------------------------------------------------------------------
# Reglas de tipos (Manual, Tabla 11).  Devuelven el tipo del resultado o
# None si los operandos son inválidos (=> E05).
# ---------------------------------------------------------------------------
def tipo_binario(op: str, t1: str, t2: str) -> Optional[str]:
    if op == '+':
        if t1 == INT and t2 == INT:
            return INT
        if STRING in (t1, t2) and t1 in (INT, STRING) and t2 in (INT, STRING):
            return STRING                       # concatenación
        return None
    if op in ('-', '*', '/', '%'):
        return INT if t1 == INT and t2 == INT else None
    if op in RELACIONALES:
        return BOOL if t1 == INT and t2 == INT else None
    if op in IGUALDAD:
        return BOOL if t1 == t2 else None
    if op in LOGICOS:
        return BOOL if t1 == BOOL and t2 == BOOL else None
    return None


def tipo_unario(op: str, t: str) -> Optional[str]:
    if op in ('neg', '-'):
        return INT if t == INT else None
    if op == 'not':
        return BOOL if t == BOOL else None
    return None


def op_intermedio(op: str, t1: str, t2: str) -> str:
    """'+' entre textos se emite como concat (Tabla 11)."""
    return 'concat' if op == '+' and STRING in (t1, t2) else op


# ---------------------------------------------------------------------------
# Aritmética del destino (Manual §5.2)
# ---------------------------------------------------------------------------
_MASK = (1 << 64) - 1


def a_int64(x: int) -> int:
    """Desbordamiento circular a 64 bits con signo."""
    x &= _MASK
    return x - (1 << 64) if x >> 63 else x


def evaluar_binario(op: str, a: Any, b: Any) -> Any:
    """Evalúa una operación con operandos constantes.  No llamar con divisor 0 (E06)."""
    if op in ('+', 'concat') and (isinstance(a, str) or isinstance(b, str)):
        return _texto(a) + _texto(b)
    if op == '+':
        return a_int64(a + b)
    if op == '-':
        return a_int64(a - b)
    if op == '*':
        return a_int64(a * b)
    if op == '/':
        q = abs(a) // abs(b)
        return a_int64(q if (a < 0) == (b < 0) else -q)      # trunca hacia cero (idiv)
    if op == '%':
        return a - b * evaluar_binario('/', a, b)              # signo del dividendo
    if op == '<':
        return a < b
    if op == '<=':
        return a <= b
    if op == '>':
        return a > b
    if op == '>=':
        return a >= b
    if op == '==':
        return a == b
    if op == '!=':
        return a != b
    if op == 'and':
        return bool(a and b)
    if op == 'or':
        return bool(a or b)
    raise ValueError(f'operador desconocido {op}')


def evaluar_unario(op: str, a: Any) -> Any:
    if op in ('neg', '-'):
        return a_int64(-a)
    if op == 'not':
        return not a
    raise ValueError(f'operador desconocido {op}')


def _texto(v: Any) -> str:
    if isinstance(v, bool):
        return 'true' if v else 'false'
    return str(v)


# ---------------------------------------------------------------------------
# Acciones completas de reducción (validar + val/cte + emitir), listas para
# usarse desde las producciones de expresiones del parser.
# ---------------------------------------------------------------------------
def reducir_binario(op: str, izq: ElementoPilaSemantica, der: ElementoPilaSemantica,
                    linea: int, gestor, generador, emitir: bool = True) -> ElementoPilaSemantica:
    """A → A op M, R → A relop A, C → C and N, E → E or C ...

    emitir=False suprime las cuádruplas (contexto de global/const: solo importa val).
    """
    if gestor.error_tipo_propagado(izq.tipo, der.tipo):
        return ElementoPilaSemantica.error()                      # anti-cascada
    tipo = tipo_binario(op, izq.tipo, der.tipo)
    if tipo is None:
        gestor.error('E05', linea, op=op, tipo_izq=izq.tipo, tipo_der=der.tipo)
        return ElementoPilaSemantica.error()
    if op in ('/', '%') and der.cte and der.val == 0:
        gestor.error('E06', linea)
        return ElementoPilaSemantica.error()

    cte = izq.cte and der.cte
    val = evaluar_binario(op, izq.val, der.val) if cte else None
    if not emitir:
        if cte:
            return ElementoPilaSemantica.literal(val)
        return ElementoPilaSemantica(tipo, '_sin_lugar', None, False)
    t = generador.nuevo_temporal(tipo)
    generador.emitir(op_intermedio(op, izq.tipo, der.tipo), izq.lugar, der.lugar, t)
    return ElementoPilaSemantica(tipo, t, val, cte)


def reducir_unario(op: str, elem: ElementoPilaSemantica, linea: int, gestor, generador,
                   emitir: bool = True) -> ElementoPilaSemantica:
    """U → - U   y   N → not N."""
    if gestor.error_tipo_propagado(elem.tipo):
        return ElementoPilaSemantica.error()
    tipo = tipo_unario(op, elem.tipo)
    if tipo is None:
        gestor.error('E05', linea, op='-' if op == 'neg' else op, tipo_izq=elem.tipo, tipo_der='-')
        return ElementoPilaSemantica.error()
    val = evaluar_unario(op, elem.val) if elem.cte else None
    if not emitir:
        return ElementoPilaSemantica.literal(val) if elem.cte else ElementoPilaSemantica(tipo, '_sin_lugar')
    t = generador.nuevo_temporal(tipo)
    generador.emitir('neg' if op == '-' else op, elem.lugar, '-', t)
    return ElementoPilaSemantica(tipo, t, val, elem.cte)
