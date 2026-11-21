"""
Tabla de Símbolos — Pila de ámbitos [Global, Local] + tabla de nodos
====================================================================
Soporta inserción, búsqueda por ámbito, resolución de referencias
adelantadas a nodos, y detección de variables no usadas (W01).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SimboloVariable:
    """Entrada de variable en la tabla de símbolos."""
    nombre: str
    tipo: str               # 'int' | 'string'
    linea_decl: int
    inicializada: bool = False
    usada: bool = False
    ambito: str = 'global'  # 'global' | 'local'


@dataclass
class SimboloNodo:
    """Entrada de nodo en la tabla de nodos."""
    nombre: str
    linea_decl: int
    definido: bool = True
    tiene_salida: bool = False          # True si contiene goto/choice/exit
    referenciado_por: list = field(default_factory=list)  # nodos que apuntan aquí


class TablaSimbolos:
    """Pila de diccionarios para ámbitos léxicos + tabla de nodos."""

    def __init__(self):
        # Pila de ámbitos: [global_scope, local_scope, ...]
        self._pila: list[dict[str, SimboloVariable]] = [{}]
        # Tabla de nodos (plano, no anidado)
        self._nodos: dict[str, SimboloNodo] = {}
        # Nodo actualmente en proceso de análisis
        self.nodo_actual: Optional[str] = None

    # ------------------------------------------------------------------
    # Ámbitos
    # ------------------------------------------------------------------
    def abrir_ambito(self):
        """Abre un nuevo ámbito local."""
        self._pila.append({})

    def cerrar_ambito(self) -> list[SimboloVariable]:
        """Cierra el ámbito actual y devuelve las variables no usadas."""
        ambito = self._pila.pop()
        no_usadas = [s for s in ambito.values() if not s.usada]
        return no_usadas

    @property
    def ambito_actual(self) -> dict[str, SimboloVariable]:
        return self._pila[-1]

    @property
    def ambito_global(self) -> dict[str, SimboloVariable]:
        return self._pila[0]

    # ------------------------------------------------------------------
    # Variables
    # ------------------------------------------------------------------
    def insertar(self, nombre: str, tipo: str, linea: int,
                 inicializada: bool = False) -> bool:
        """Inserta una variable en el ámbito actual.
        Retorna False si ya existe en el mismo ámbito (E02)."""
        if nombre in self.ambito_actual:
            return False
        nivel = 'global' if len(self._pila) == 1 else 'local'
        self.ambito_actual[nombre] = SimboloVariable(
            nombre=nombre, tipo=tipo, linea_decl=linea,
            inicializada=inicializada, ambito=nivel,
        )
        return True

    def buscar(self, nombre: str) -> Optional[SimboloVariable]:
        """Busca una variable desde el ámbito más interno al global."""
        for ambito in reversed(self._pila):
            if nombre in ambito:
                return ambito[nombre]
        return None

    def marcar_usada(self, nombre: str):
        """Marca la variable como usada (para W01)."""
        sym = self.buscar(nombre)
        if sym:
            sym.usada = True

    def marcar_inicializada(self, nombre: str):
        sym = self.buscar(nombre)
        if sym:
            sym.inicializada = True

    # ------------------------------------------------------------------
    # Nodos
    # ------------------------------------------------------------------
    def registrar_nodo(self, nombre: str, linea: int) -> bool:
        """Registra la definición de un nodo. Retorna False si ya existe (E06)."""
        if nombre in self._nodos and self._nodos[nombre].definido:
            return False
        if nombre in self._nodos:
            # Referencia adelantada previa → ahora se define
            self._nodos[nombre].definido = True
            self._nodos[nombre].linea_decl = linea
        else:
            self._nodos[nombre] = SimboloNodo(nombre=nombre, linea_decl=linea)
        return True

    def referenciar_nodo(self, nombre: str, desde: str):
        """Registra que `desde` referencia a `nombre` (goto/choice)."""
        if nombre not in self._nodos:
            # Referencia adelantada: crear entrada sin definir
            self._nodos[nombre] = SimboloNodo(
                nombre=nombre, linea_decl=0, definido=False
            )
        self._nodos[nombre].referenciado_por.append(desde)

    def marcar_nodo_con_salida(self, nombre: str):
        """Marca que el nodo tiene al menos una sentencia de salida."""
        if nombre in self._nodos:
            self._nodos[nombre].tiene_salida = True

    def obtener_nodo(self, nombre: str) -> Optional[SimboloNodo]:
        return self._nodos.get(nombre)

    @property
    def nodos(self) -> dict[str, SimboloNodo]:
        return self._nodos

    # ------------------------------------------------------------------
    # Verificaciones post-parse
    # ------------------------------------------------------------------
    def nodos_no_definidos(self) -> list[SimboloNodo]:
        """Nodos referenciados pero nunca definidos (E05)."""
        return [n for n in self._nodos.values() if not n.definido]

    def existe_nodo_inicio(self) -> bool:
        """Verifica que exista el nodo 'inicio' (E07)."""
        return 'inicio' in self._nodos and self._nodos['inicio'].definido

    def nodos_sin_salida(self) -> list[SimboloNodo]:
        """Nodos sin goto/choice/exit (E11)."""
        return [n for n in self._nodos.values()
                if n.definido and not n.tiene_salida]

    def nodos_inalcanzables(self) -> list[SimboloNodo]:
        """Nodos que nadie referencia y no son 'inicio' (E12)."""
        return [n for n in self._nodos.values()
                if n.definido and n.nombre != 'inicio'
                and len(n.referenciado_por) == 0]

    def variables_no_usadas(self) -> list[SimboloVariable]:
        """Variables declaradas pero nunca usadas en todos los ámbitos (W01)."""
        resultado = []
        for ambito in self._pila:
            for sym in ambito.values():
                if not sym.usada:
                    resultado.append(sym)
        return resultado

    # ------------------------------------------------------------------
    # Volcado (--dump-symtab)
    # ------------------------------------------------------------------
    def dump(self) -> str:
        """Representación legible de la tabla de símbolos."""
        lines = ['=== TABLA DE SÍMBOLOS ===']
        lines.append('\n--- Variables ---')
        lines.append(f'{"Nombre":<15} {"Tipo":<10} {"Ámbito":<10} {"Línea":<6} {"Init":<6} {"Usada":<6}')
        lines.append('-' * 60)
        for ambito in self._pila:
            for sym in ambito.values():
                lines.append(
                    f'{sym.nombre:<15} {sym.tipo:<10} {sym.ambito:<10} '
                    f'{sym.linea_decl:<6} {"Sí" if sym.inicializada else "No":<6} '
                    f'{"Sí" if sym.usada else "No":<6}'
                )
        lines.append('\n--- Nodos ---')
        lines.append(f'{"Nombre":<15} {"Línea":<6} {"Definido":<10} {"Salida":<8} {"Refs"}')
        lines.append('-' * 60)
        for nodo in self._nodos.values():
            refs = ', '.join(nodo.referenciado_por) if nodo.referenciado_por else '(ninguna)'
            lines.append(
                f'{nodo.nombre:<15} {nodo.linea_decl:<6} '
                f'{"Sí" if nodo.definido else "No":<10} '
                f'{"Sí" if nodo.tiene_salida else "No":<8} {refs}'
            )
        return '\n'.join(lines)
