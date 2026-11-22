"""
Generador de código de tres direcciones — Manual §3.3 (ListaCodigo) y §4
========================================================================
Una sola lista lineal de cuádruplas para todo el programa, dividida en
nodes por el marcador (node, -, -, id).  Por cada node:

  * nuevo_temporal() -> t1, t2...   y   nueva_etiqueta() -> L1, L2...
    (los contadores se reinician en reiniciar_node()).
  * insertar_en(pos, lista) inyecta opt/menu antes de los bloques del choice
    (Manual §4.6.1).  Las inserciones se hacen de adentro hacia afuera, así que
    nunca invalidan las posiciones guardadas en la pila de Choice.
  * Al cerrar el node las etiquetas se renumeran en orden de aparición, de modo
    que el listado coincide con la Tabla 13 aunque el parser pida Lfin del choice
    antes que las etiquetas de sus opciones.
"""
from __future__ import annotations

from typing import Optional, Union

from .cuadrupla import Cuadrupla, VACIO, es_etiqueta_local, es_temporal
from ..semantica.pila_semantica import texto_literal


class GeneradorTAC:
    def __init__(self):
        self._codigo: list[Cuadrupla] = []
        self._inicio_node = 0                      # índice donde empieza el node actual
        self._cont_temporal = 0
        self._cont_etiqueta = 0
        self.tipos_temporales: dict[str, Optional[str]] = {}
        self.temporales_por_node: dict[str, int] = {}
        self._node_actual: Optional[str] = None
        self._cadenas: dict[str, str] = {}         # valor -> etiqueta S_k (pool de textos)
        self._pila_choice: list[dict] = []
        self._pila_etiquetas: list[str] = []

    # ------------------------------------------------------------------
    # Emisión
    # ------------------------------------------------------------------
    def emitir(self, op: Union[str, Cuadrupla], arg1: str = VACIO, arg2: str = VACIO,
               res: str = VACIO, **extra) -> int:
        """emitir(Cuadrupla(...)) o emitir(op, a1, a2, r).  Devuelve la posición."""
        cuad = op if isinstance(op, Cuadrupla) else Cuadrupla(op, arg1, arg2, res, **extra)

        # El parser marca el inicio del node con (label, -, -, _node_x): se normaliza al
        # operador (node, -, -, x) de la Tabla 10.
        if cuad.op == 'label' and cuad.res.startswith('_node_'):
            cuad = Cuadrupla('node', VACIO, VACIO, cuad.res[len('_node_'):])
        if cuad.op == 'node':
            self._node_actual = cuad.res

        # (goto, -, -, L) seguido de (label, -, -, L): el goto no hace nada.  Ocurre en la
        # última opción de un choice; la Tabla 13 no lo incluye.
        if (cuad.es_etiqueta() and len(self._codigo) > self._inicio_node
                and self._codigo[-1].op == 'goto' and self._codigo[-1].res == cuad.res):
            self._codigo.pop()

        self._codigo.append(cuad)
        return len(self._codigo) - 1

    def posicion(self) -> int:
        return len(self._codigo)

    pos_actual = posicion
    posicion_actual = posicion

    def insertar_en(self, pos: int, lista: Union[Cuadrupla, list[Cuadrupla]]) -> None:
        """Inserta una o varias cuádruplas en `pos` (Manual: insertarEn)."""
        if isinstance(lista, Cuadrupla):
            lista = [lista]
        self._codigo[pos:pos] = list(lista)

    insertarEn = insertar_en

    # ------------------------------------------------------------------
    # Temporales y etiquetas (se reinician por node)
    # ------------------------------------------------------------------
    def nuevo_temporal(self, tipo: Optional[str] = None) -> str:
        self._cont_temporal += 1
        nombre = f't{self._cont_temporal}'
        self.tipos_temporales[nombre] = tipo
        return nombre

    def nueva_etiqueta(self) -> str:
        self._cont_etiqueta += 1
        return f'L{self._cont_etiqueta}'

    def reiniciar_node(self) -> None:
        """Se llama al entrar a cada node: cierra el anterior y reinicia contadores."""
        self._cerrar_node()
        self._inicio_node = len(self._codigo)
        self._cont_temporal = 0
        self._cont_etiqueta = 0
        self.tipos_temporales = {}

    def _cerrar_node(self) -> None:
        """Renumera etiquetas y temporales del node actual en orden de aparición."""
        segmento = self._codigo[self._inicio_node:]
        if not segmento:
            return
        etiquetas: dict[str, str] = {}
        temporales: dict[str, str] = {}
        for c in segmento:
            for campo in (c.arg1, c.arg2, c.res):
                if es_etiqueta_local(campo) and campo not in etiquetas:
                    etiquetas[campo] = f'L{len(etiquetas) + 1}'
                elif es_temporal(campo) and campo not in temporales:
                    temporales[campo] = f't{len(temporales) + 1}'
        nuevo = {**etiquetas, **temporales}
        for c in segmento:
            c.arg1 = nuevo.get(c.arg1, c.arg1)
            c.arg2 = nuevo.get(c.arg2, c.arg2)
            c.res = nuevo.get(c.res, c.res)
        self.tipos_temporales = {temporales.get(t, t): tp for t, tp in self.tipos_temporales.items()}
        if self._node_actual:
            self.temporales_por_node[self._node_actual] = len(temporales)

    # ------------------------------------------------------------------
    # Pila de Choice (Manual §4.6.1) — permite choice anidados
    # ------------------------------------------------------------------
    def abrir_choice(self) -> dict:
        """C1: guarda la posición donde irán opt/menu y la etiqueta de salida."""
        choice = {'pos': self.posicion(), 'Lfin': self.nueva_etiqueta(), 'opciones': []}
        self._pila_choice.append(choice)
        return choice

    def abrir_opcion(self, texto: str) -> tuple[str, bool]:
        """O1: nueva etiqueta para la opción.  Devuelve (Lk, repetida) para E10."""
        choice = self._pila_choice[-1]
        repetida = any(t == texto for t, _ in choice['opciones'])
        lk = self.nueva_etiqueta()
        choice['opciones'].append((texto, lk))
        self.emitir('label', VACIO, VACIO, lk)
        return lk, repetida

    def cerrar_opcion(self) -> None:
        """O2: salto al final del choice."""
        self.emitir('goto', VACIO, VACIO, self._pila_choice[-1]['Lfin'])

    def cerrar_choice(self) -> None:
        """C2: inserta los opt + menu en la posición guardada y emite Lfin."""
        choice = self._pila_choice.pop()
        cod = [Cuadrupla('opt', texto_literal(t), VACIO, lk) for t, lk in choice['opciones']]
        cod.append(Cuadrupla('menu'))
        self.insertar_en(choice['pos'], cod)
        self.emitir('label', VACIO, VACIO, choice['Lfin'])

    # ------------------------------------------------------------------
    # Pila de etiquetas genérica (if/while anidados)
    # ------------------------------------------------------------------
    def push_etiqueta(self, etiqueta: str) -> None:
        self._pila_etiquetas.append(etiqueta)

    def pop_etiqueta(self) -> str:
        return self._pila_etiquetas.pop()

    # ------------------------------------------------------------------
    # Pool de textos (.rodata S0, S1...)
    # ------------------------------------------------------------------
    def registrar_cadena(self, valor: str) -> str:
        if valor not in self._cadenas:
            self._cadenas[valor] = f'S{len(self._cadenas)}'
        return self._cadenas[valor]

    def obtener_cadenas(self) -> dict[str, str]:
        """{etiqueta: texto} en el orden en que aparecen en el código final
        (como en el Listing 11 del Manual); al final los que solo se registraron."""
        en_orden: list[str] = []
        for c in self.obtener_codigo():
            for campo in (c.arg1, c.arg2):
                if len(campo) >= 2 and campo[0] == '"' and campo[-1] == '"':
                    texto = _desescapar(campo[1:-1])
                    if texto not in en_orden:
                        en_orden.append(texto)
        for texto in self._cadenas:
            if texto not in en_orden:
                en_orden.append(texto)
        return {f'S{i}': t for i, t in enumerate(en_orden)}

    # ------------------------------------------------------------------
    # Acceso
    # ------------------------------------------------------------------
    def obtener_codigo(self) -> list[Cuadrupla]:
        self._cerrar_node()           # idempotente: renumerar dos veces no cambia nada
        return list(self._codigo)

    def __len__(self) -> int:
        return len(self._codigo)

    def reset(self) -> None:
        self.__init__()


def _desescapar(s: str) -> str:
    out, i = [], 0
    while i < len(s):
        if s[i] == '\\' and i + 1 < len(s):
            out.append({'n': '\n'}.get(s[i + 1], s[i + 1]))
            i += 2
        else:
            out.append(s[i])
            i += 1
    return ''.join(out)


# Nombre del Manual
ListaCodigo = GeneradorTAC
