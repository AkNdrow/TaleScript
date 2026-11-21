"""
Cuádrupla y Tripleta — Representación de código intermedio
==========================================================
Cuádrupla: (op, arg1, arg2, res)
Tripleta:  (índice) (op, arg1, arg2)   donde argN puede ser (ref_triple_i)
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Any


@dataclass
class Cuadrupla:
    """Representación de una instrucción de tres direcciones como cuádrupla."""
    op:   str                       # Operación: ADD, SUB, ASSIGN, GOTO, LABEL, SAY, etc.
    arg1: Optional[str] = None      # Primer operando
    arg2: Optional[str] = None      # Segundo operando
    res:  Optional[str] = None      # Resultado / destino

    def __str__(self) -> str:
        a1 = self.arg1 if self.arg1 is not None else '_'
        a2 = self.arg2 if self.arg2 is not None else '_'
        r  = self.res  if self.res  is not None else '_'
        return f'({self.op}, {a1}, {a2}, {r})'

    def __repr__(self) -> str:
        return self.__str__()

    def es_salto(self) -> bool:
        return self.op in ('GOTO', 'IF_FALSE', 'IF_TRUE', 'IF_EQ', 'IF_NE',
                           'IF_LT', 'IF_GT', 'IF_LE', 'IF_GE')

    def es_etiqueta(self) -> bool:
        return self.op == 'LABEL'


@dataclass
class Tripleta:
    """Representación como tripleta indexada (sin campo res explícito)."""
    indice: int
    op:   str
    arg1: Optional[str] = None
    arg2: Optional[str] = None

    def __str__(self) -> str:
        a1 = self.arg1 if self.arg1 is not None else '_'
        a2 = self.arg2 if self.arg2 is not None else '_'
        return f'({self.indice}) ({self.op}, {a1}, {a2})'


def cuadruplas_a_tripletas(cuadruplas: list[Cuadrupla]) -> list[Tripleta]:
    """Convierte una lista de cuádruplas a tripletas.

    En la representación por tripletas, el resultado de cada instrucción se
    referencia por su índice (i).  Las asignaciones a variables conservan el
    nombre de la variable destino en arg1 o arg2.
    """
    tripletas: list[Tripleta] = []
    # Mapeo: nombre de temporal → índice de tripleta que lo definió
    mapa_def: dict[str, str] = {}

    for i, cuad in enumerate(cuadruplas):
        op = cuad.op
        a1 = _resolver_ref(cuad.arg1, mapa_def)
        a2 = _resolver_ref(cuad.arg2, mapa_def)

        if op == 'ASSIGN':
            # Asignación a variable: (ASSIGN, destino, valor)
            trip = Tripleta(indice=i, op=op, arg1=cuad.res, arg2=a1)
        elif op == 'GOTO':
            trip = Tripleta(indice=i, op=op, arg1=cuad.res, arg2=None)
        elif op in ('IF_FALSE', 'IF_TRUE'):
            trip = Tripleta(indice=i, op=op, arg1=a1, arg2=cuad.res)
        elif op in ('IF_EQ', 'IF_NE', 'IF_LT', 'IF_GT', 'IF_LE', 'IF_GE'):
            trip = Tripleta(indice=i, op=f'{op}[{cuad.res}]', arg1=a1, arg2=a2)
        elif op == 'LABEL':
            trip = Tripleta(indice=i, op=op, arg1=cuad.res, arg2=None)
        else:
            trip = Tripleta(indice=i, op=op, arg1=a1, arg2=a2)

        tripletas.append(trip)

        # Si la cuádrupla define un temporal, registrar la referencia (i)
        if cuad.res and cuad.res.startswith('t') and cuad.res[1:].isdigit():
            mapa_def[cuad.res] = f'({i})'

    return tripletas


def _resolver_ref(arg: Optional[str], mapa_def: dict[str, str]) -> Optional[str]:
    """Si el argumento es un temporal con definición conocida, usa la referencia (i)."""
    if arg is None:
        return None
    if arg in mapa_def:
        return mapa_def[arg]
    return arg


def dump_cuadruplas(cuadruplas: list[Cuadrupla]) -> str:
    """Formato legible para --dump-tac."""
    lines = ['=== CÓDIGO INTERMEDIO (Cuádruplas) ===']
    lines.append(f'{"#":<5} {"Op":<14} {"Arg1":<18} {"Arg2":<18} {"Res":<18}')
    lines.append('-' * 75)
    for i, c in enumerate(cuadruplas):
        a1 = c.arg1 if c.arg1 is not None else '_'
        a2 = c.arg2 if c.arg2 is not None else '_'
        r  = c.res  if c.res  is not None else '_'
        lines.append(f'{i:<5} {c.op:<14} {a1:<18} {a2:<18} {r:<18}')
    return '\n'.join(lines)


def dump_tripletas(tripletas: list[Tripleta]) -> str:
    """Formato legible para --dump-triples."""
    lines = ['=== CÓDIGO INTERMEDIO (Tripletas) ===']
    lines.append(f'{"#":<5} {"Op":<14} {"Arg1":<18} {"Arg2":<18}')
    lines.append('-' * 60)
    for t in tripletas:
        a1 = t.arg1 if t.arg1 is not None else '_'
        a2 = t.arg2 if t.arg2 is not None else '_'
        lines.append(f'{t.indice:<5} {t.op:<14} {a1:<18} {a2:<18}')
    return '\n'.join(lines)
