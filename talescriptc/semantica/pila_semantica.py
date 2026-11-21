"""
Pila Semántica — Atributos sintetizados para SDT
=================================================
Cada elemento transporta (tipo, lugar, val, cte) por la pila durante
las reducciones del parser LALR(1).
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class ElementoPilaSemantica:
    """Atributos sintetizados de un símbolo gramatical."""
    tipo:  str                    # 'int' | 'string' | 'bool' | 'ERROR'
    lugar: str                    # nombre de variable, temporal (tk) o etiqueta de cadena (_str_k)
    val:   Optional[Any] = None   # valor conocido en tiempo de compilación (para plegado)
    cte:   bool = False           # True si el valor es constante


class PilaSemantica:
    """Pila LIFO de ElementoPilaSemantica para acciones semánticas dirigidas
    por la sintaxis (SDT)."""

    def __init__(self):
        self._pila: list[ElementoPilaSemantica] = []
        self._etiquetas: list[str] = []  # pila auxiliar de etiquetas para control de flujo

    # ------------------------------------------------------------------
    # Operaciones sobre la pila de atributos
    # ------------------------------------------------------------------
    def push(self, elem: ElementoPilaSemantica):
        self._pila.append(elem)

    def pop(self) -> ElementoPilaSemantica:
        if not self._pila:
            raise RuntimeError('Pila semántica vacía al intentar pop()')
        return self._pila.pop()

    def top(self) -> ElementoPilaSemantica:
        if not self._pila:
            raise RuntimeError('Pila semántica vacía al intentar top()')
        return self._pila[-1]

    @property
    def vacia(self) -> bool:
        return len(self._pila) == 0

    @property
    def tamanio(self) -> int:
        return len(self._pila)

    # ------------------------------------------------------------------
    # Pila auxiliar de etiquetas (para IF/ELSE, WHILE, etc.)
    # ------------------------------------------------------------------
    def push_etiqueta(self, etiqueta: str):
        self._etiquetas.append(etiqueta)

    def pop_etiqueta(self) -> str:
        if not self._etiquetas:
            raise RuntimeError('Pila de etiquetas vacía al intentar pop_etiqueta()')
        return self._etiquetas.pop()

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------
    def reset(self):
        self._pila.clear()
        self._etiquetas.clear()

    def __repr__(self):
        return f'PilaSemantica(tam={len(self._pila)}, etiquetas={len(self._etiquetas)})'
