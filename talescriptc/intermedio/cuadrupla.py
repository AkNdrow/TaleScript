"""
Cuádrupla y Tripleta — Manual §3.3, §4.1 y Tabla 4
===================================================
Cuádrupla: (op, arg1, arg2, res)     representación interna principal
Tripleta:  (op, arg1, arg2)          solo para el reporte --dump-triples

Operadores (Manual, Tabla 10):
  + - * / %  neg  < <= > >= == !=  and or not  concat  =  cast
  label goto ifTrue ifFalse  say opt menu end  call return node
Un campo sin uso se escribe "-".  (node, -, -, id) marca el inicio del código
de un node; temporales, etiquetas y números de tripleta se reinician en cada node.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

VACIO = '-'
SALTOS = ('goto', 'ifTrue', 'ifFalse')
# Tras estas instrucciones empieza un bloque básico nuevo (Manual §5.1)
FIN_DE_BLOQUE = ('goto', 'ifTrue', 'ifFalse', 'menu', 'end', 'return', 'call')
# No producen valor en `res`
SIN_RESULTADO = ('label', 'goto', 'ifTrue', 'ifFalse', 'say', 'opt', 'menu',
                 'end', 'call', 'return', 'node')


def _campo(x) -> str:
    return VACIO if x is None or x == '' else str(x)


@dataclass
class Cuadrupla:
    """Manual, Listing 7."""
    op: str
    arg1: Optional[str] = VACIO
    arg2: Optional[str] = VACIO
    res: Optional[str] = VACIO
    tipo1: Optional[str] = None      # tipos de los operandos (los usa el back-end)
    tipo2: Optional[str] = None
    linea: int = 0
    comentario: str = ''

    def __post_init__(self):
        self.arg1, self.arg2, self.res = _campo(self.arg1), _campo(self.arg2), _campo(self.res)

    def __str__(self) -> str:
        return f'({self.op}, {self.arg1}, {self.arg2}, {self.res})'

    __repr__ = __str__

    # ---- Clasificación ----
    def es_salto(self) -> bool:
        return self.op in SALTOS

    def es_salto_a_etiqueta(self) -> bool:
        """goto a otro node no cuenta: su destino no es una etiqueta local."""
        return self.op in SALTOS and es_etiqueta_local(self.res)

    def es_etiqueta(self) -> bool:
        return self.op == 'label'

    def es_node(self) -> bool:
        return self.op == 'node'

    def termina_bloque(self) -> bool:
        return self.op in FIN_DE_BLOQUE

    def produce_valor(self) -> bool:
        return self.op not in SIN_RESULTADO


@dataclass
class Tripleta:
    """(n) (op, arg1, arg2).  indice = -1 se usa para el encabezado de un node."""
    indice: int
    op: str
    arg1: Optional[str] = VACIO
    arg2: Optional[str] = VACIO
    comentario: str = ''

    def __post_init__(self):
        self.arg1, self.arg2 = _campo(self.arg1), _campo(self.arg2)

    def __str__(self) -> str:
        return f'({self.indice}) ({self.op}, {self.arg1}, {self.arg2})'

    __repr__ = __str__


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def es_temporal(x: Optional[str]) -> bool:
    return bool(x) and x[0] == 't' and x[1:].isdigit()


def es_etiqueta_local(x: Optional[str]) -> bool:
    return bool(x) and x[0] == 'L' and x[1:].isdigit()


def dividir_por_node(cuadruplas: list[Cuadrupla]) -> list[tuple[str, list[Cuadrupla]]]:
    """[(nombre_node, [cuádruplas sin el marcador node])...] en orden de declaración."""
    nodes: list[tuple[str, list[Cuadrupla]]] = []
    for c in cuadruplas:
        if c.es_node():
            nodes.append((c.res, []))
        elif nodes:
            nodes[-1][1].append(c)
        else:
            nodes.append(('?', [c]))
    return nodes


# ---------------------------------------------------------------------------
# Conversión a tripletas (Manual §2.4: derivadas de las cuádruplas)
# ---------------------------------------------------------------------------
def _tripletas_de_node(cuads: list[Cuadrupla]) -> list[Tripleta]:
    # 1) número de cada instrucción (las label no ocupan número)
    numero_temp: dict[str, int] = {}
    destino_etq: dict[str, int] = {}
    pendientes: list[str] = []
    n = 0
    for c in cuads:
        if c.es_etiqueta():
            pendientes.append(c.res)
            continue
        for etq in pendientes:
            destino_etq[etq] = n
        pendientes.clear()
        if es_temporal(c.res) and c.produce_valor():
            numero_temp[c.res] = n
        n += 1
    for etq in pendientes:                # etiqueta al final del node
        destino_etq[etq] = n

    def ref(x: str) -> str:
        if es_temporal(x) and x in numero_temp:
            return f'({numero_temp[x]})'
        if es_etiqueta_local(x) and x in destino_etq:
            return f'({destino_etq[x]})'
        return x

    # 2) traducción
    trip: list[Tripleta] = []
    coment: list[str] = []
    for c in cuads:
        if c.es_etiqueta():
            if c.comentario:
                coment.append(c.comentario)
            continue
        op = c.op
        if op == '=':
            a1, a2 = c.res, ref(c.arg1)                  # (=, x, a)
        elif op in ('goto', 'call'):
            a1, a2 = ref(c.res), VACIO                   # (goto, (16), -) | (goto, pelea, -)
        elif op in ('ifTrue', 'ifFalse', 'opt'):
            a1, a2 = ref(c.arg1), ref(c.res)             # (ifTrue, (16), (2))
        else:
            a1, a2 = ref(c.arg1), ref(c.arg2)
        texto = '; '.join(coment + ([c.comentario] if c.comentario else []))
        coment = []
        trip.append(Tripleta(len(trip), op, a1, a2, texto))
    return trip


def cuadruplas_a_tripletas(cuadruplas: list[Cuadrupla]) -> list[Tripleta]:
    """Convierte todo el programa.  Cada node empieza con una Tripleta(-1, 'node', nombre)
    como encabezado y su numeración arranca en (0)."""
    resultado: list[Tripleta] = []
    for nombre, cuads in dividir_por_node(cuadruplas):
        resultado.append(Tripleta(-1, 'node', nombre))
        resultado.extend(_tripletas_de_node(cuads))
    return resultado


# ---------------------------------------------------------------------------
# Reportes --dump-tac y --dump-triples
# ---------------------------------------------------------------------------
def dump_cuadruplas(cuadruplas: list[Cuadrupla]) -> str:
    out = ['=== CÓDIGO INTERMEDIO (cuádruplas) ===']
    for nombre, cuads in dividir_por_node(cuadruplas):
        out.append('')
        out.append(f'node {nombre}  ({len(cuads)} cuádruplas)')
        out.append(f'{"#":>4}  {"Cuádrupla":<44} Comentario')
        out.append('-' * 70)
        for i, c in enumerate(cuads, 1):
            out.append(f'{i:>4}  {str(c):<44} {c.comentario}'.rstrip())
    return '\n'.join(out)


def dump_tripletas(tripletas: list[Tripleta]) -> str:
    out = ['=== CÓDIGO INTERMEDIO (tripletas) ===']
    for t in tripletas:
        if t.indice < 0:
            out += ['', f'node {t.arg1}', f'{"#":>5}  {"Tripleta":<40} Comentario', '-' * 70]
            continue
        out.append(f'{"(" + str(t.indice) + ")":>5}  {f"({t.op}, {t.arg1}, {t.arg2})":<40} '
                   f'{t.comentario}'.rstrip())
    return '\n'.join(out)
