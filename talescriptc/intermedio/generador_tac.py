"""
Generador de Código de Tres Direcciones (TAC)
=============================================
ListaCodigo con soporte de inserción posicional (insertarEn) para menús
choice, etiquetas Lk, temporales tk y tabla de cadenas literales.
"""
from __future__ import annotations
from typing import Optional
from .cuadrupla import Cuadrupla


class GeneradorTAC:
    """Emite y administra la lista lineal de cuádruplas (TAC)."""

    def __init__(self):
        self._codigo: list[Cuadrupla] = []
        self._cont_temporal: int = 0
        self._cont_etiqueta: int = 0
        self._cont_cadena: int = 0
        self._cadenas: dict[str, str] = {}       # label → valor string
        self._cadenas_inv: dict[str, str] = {}    # valor string → label (deduplicación)
        self._pila_etiquetas: list[str] = []      # para IF/ELSE y otros flujos

    # ------------------------------------------------------------------
    # Emisión de cuádruplas
    # ------------------------------------------------------------------
    def emitir(self, cuad: Cuadrupla) -> int:
        """Agrega una cuádrupla al final de la lista. Retorna su posición."""
        self._codigo.append(cuad)
        return len(self._codigo) - 1

    def insertarEn(self, pos: int, cuad: Cuadrupla) -> None:
        """Inserta una cuádrupla en la posición `pos` (desplaza las siguientes).
        Útil para insertar dispatch de choice después de conocer todas las opciones."""
        self._codigo.insert(pos, cuad)

    def posicion_actual(self) -> int:
        """Retorna la posición donde se insertará la próxima cuádrupla."""
        return len(self._codigo)

    # ------------------------------------------------------------------
    # Temporales: t0, t1, t2, ...
    # ------------------------------------------------------------------
    def nuevo_temporal(self) -> str:
        nombre = f't{self._cont_temporal}'
        self._cont_temporal += 1
        return nombre

    # ------------------------------------------------------------------
    # Etiquetas: L0, L1, L2, ...
    # ------------------------------------------------------------------
    def nueva_etiqueta(self) -> str:
        nombre = f'L{self._cont_etiqueta}'
        self._cont_etiqueta += 1
        return nombre

    # ------------------------------------------------------------------
    # Pila de etiquetas (para SDT de IF/ELSE)
    # ------------------------------------------------------------------
    def push_etiqueta(self, etiqueta: str):
        self._pila_etiquetas.append(etiqueta)

    def pop_etiqueta(self) -> str:
        return self._pila_etiquetas.pop()

    # ------------------------------------------------------------------
    # Cadenas literales: _str_0, _str_1, ...
    # ------------------------------------------------------------------
    def registrar_cadena(self, valor: str) -> str:
        """Registra un literal string y retorna su etiqueta.
        Deduplica cadenas idénticas."""
        if valor in self._cadenas_inv:
            return self._cadenas_inv[valor]
        label = f'_str_{self._cont_cadena}'
        self._cont_cadena += 1
        self._cadenas[label] = valor
        self._cadenas_inv[valor] = label
        return label

    def obtener_cadenas(self) -> dict[str, str]:
        """Retorna el diccionario label → valor de cadenas literales."""
        return dict(self._cadenas)

    # ------------------------------------------------------------------
    # Acceso a la lista de código
    # ------------------------------------------------------------------
    def obtener_codigo(self) -> list[Cuadrupla]:
        return list(self._codigo)

    def __len__(self) -> int:
        return len(self._codigo)

    # ------------------------------------------------------------------
    # Reset (para reusar en tests)
    # ------------------------------------------------------------------
    def reset(self):
        self._codigo.clear()
        self._cont_temporal = 0
        self._cont_etiqueta = 0
        self._cont_cadena = 0
        self._cadenas.clear()
        self._cadenas_inv.clear()
        self._pila_etiquetas.clear()
