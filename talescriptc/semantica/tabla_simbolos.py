"""
Tabla de Símbolos — Manual §3.1
================================
Tres estructuras coordinadas:
  * pila de ámbitos  [global, local del node actual]
  * tabla de nodes   (permite saltos hacia adelante: goto pelea; antes de node pelea)
  * contadores de direcciones G0, G1... (globales) y L0, L1... (locales, por node)

Diagnósticos que produce (Manual, Tabla 5):
  E02 duplicado en el mismo ámbito   -> insertar() devuelve False (el parser lo reporta)
  E03 local con nombre de global     -> se reporta en validar_final()
  E08 node duplicado                 -> entrar_node() devuelve False (el parser lo reporta)
  E09 goto/call a node inexistente   -> validar_final()
  W01 local declarada y nunca leída  -> validar_final()
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

VARIABLE = 'VARIABLE'
CONSTANTE = 'CONSTANTE'
GLOBAL = 'global'
LOCAL = 'local'


@dataclass
class EntradaSimbolo:
    """Manual, Listing 4."""
    nombre: str
    tipo: str                         # 'int' | 'string' | 'bool'
    ambito: str                       # 'global' | 'local'
    linea: int
    categoria: str = VARIABLE         # VARIABLE | CONSTANTE
    direccion: str = '-'              # G0.. | L0.. | '-' si es constante
    valor_inicial: Any = None         # valor constante conocido (None si no hay)
    es_const: bool = False
    se_lee: bool = False
    columna: int = 0
    node: Optional[str] = None        # node dueño (solo locales)

    # Alias en camelCase / nombres usados por otros módulos
    @property
    def esConstante(self) -> bool:
        return self.es_const

    @property
    def seLee(self) -> bool:
        return self.se_lee

    @property
    def usada(self) -> bool:
        return self.se_lee

    @property
    def linea_decl(self) -> int:
        return self.linea


@dataclass
class EntradaNode:
    """Manual, Listing 4."""
    nombre: str
    linea_declaracion: int = -1       # -1 mientras no se haya declarado
    declarado: bool = False
    etiqueta_inicio: str = ''         # "_node_pelea"
    tamano_marco: int = 0             # lo fija el back-end
    orden: int = -1                   # posición de declaración (0 = punto de entrada)
    # (linea, instruccion, node_origen) de cada goto/call hecho ANTES de declararlo
    referencias_pendientes: list = field(default_factory=list)
    # todas las referencias (para el reporte)
    referencias: list = field(default_factory=list)
    tabla_local: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.etiqueta_inicio:
            self.etiqueta_inicio = f'_node_{self.nombre}'


class TablaSimbolos:
    """Pila de tablas [global, local] + tabla de nodes (Manual, Listing 4 y 5)."""

    def __init__(self):
        self.tabla_global: dict[str, EntradaSimbolo] = {}
        self.pila_ambitos: list[dict[str, EntradaSimbolo]] = [self.tabla_global]
        self.tabla_nodes: dict[str, EntradaNode] = {}
        self.contador_global = 0
        self.contador_local = 0
        self.node_actual: Optional[str] = None
        self._sombreados: list[EntradaSimbolo] = []      # E03 pendientes de reportar
        self._tablas_duplicadas: list[dict] = []         # locales de nodes con E08
        self.historial: list[tuple[int, str, str]] = []  # (linea, pila, accion) — Manual §3.1.3

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------
    @property
    def ambito_actual(self) -> str:
        return LOCAL if len(self.pila_ambitos) > 1 else GLOBAL

    @property
    def tabla_local(self) -> Optional[dict[str, EntradaSimbolo]]:
        return self.pila_ambitos[-1] if len(self.pila_ambitos) > 1 else None

    @property
    def ambito_global(self) -> dict[str, EntradaSimbolo]:
        """Alias de la API anterior (lo usa el back-end actual)."""
        return self.tabla_global

    def _pila_texto(self) -> str:
        return f'[G, L({self.node_actual})]' if self.tabla_local is not None else '[G]'

    def _registrar(self, linea: int, accion: str) -> None:
        self.historial.append((linea, self._pila_texto(), accion))

    # ------------------------------------------------------------------
    # insertar / buscar / existe  (Manual, Listing 5)
    # ------------------------------------------------------------------
    def insertar(self, nombre: str, tipo: str, linea: int, ambito: Optional[str] = None,
                 valor_inicial: Any = None, es_const: bool = False, columna: int = 0,
                 **_ignorados) -> bool:
        """Inserta en la tabla actual. Devuelve False solo en caso de duplicado (E02).

        El sombreado de una global (E03) no devuelve False para que el parser no lo
        confunda con E02: queda registrado y validar_final() lo reporta como E03.
        """
        entrada = EntradaSimbolo(
            nombre=nombre, tipo=tipo, ambito=self.ambito_actual, linea=linea,
            categoria=CONSTANTE if es_const else VARIABLE, valor_inicial=valor_inicial,
            es_const=es_const, columna=columna,
        )
        local = self.tabla_local
        if local is not None:
            if nombre in local:
                return False                                       # E02
            if nombre in self.tabla_global:
                self._sombreados.append(entrada)                   # E03
                self._registrar(linea, f'insertar({nombre}): choca con una global (E03)')
                return True
            entrada.node = self.node_actual
            if not es_const:
                entrada.direccion = f'L{self.contador_local}'
                self.contador_local += 1
            local[nombre] = entrada
            self._registrar(linea, f'insertar({nombre}) en la local')
        else:
            if nombre in self.tabla_global:
                return False                                       # E02
            if not es_const:
                entrada.direccion = f'G{self.contador_global}'
                self.contador_global += 1
            self.tabla_global[nombre] = entrada
            self._registrar(linea, f'insertar({nombre}) en la global')
        return True

    def buscar(self, nombre: str) -> Optional[EntradaSimbolo]:
        """Local del node actual y luego global. None => el llamador reporta E01."""
        local = self.tabla_local
        if local is not None and nombre in local:
            return local[nombre]
        return self.tabla_global.get(nombre)

    def existe(self, nombre: str) -> bool:
        return self.buscar(nombre) is not None

    def marcar_usada(self, nombre: str) -> None:
        """seLee = True cuando la variable aparece en una expresión o interpolación."""
        entrada = self.buscar(nombre)
        if entrada is not None:
            entrada.se_lee = True

    marcar_leida = marcar_usada

    # ------------------------------------------------------------------
    # Nodes
    # ------------------------------------------------------------------
    def entrar_node(self, nombre: str, linea: int = 0) -> bool:
        """Registra el node y abre su tabla local. False si ya existía (E08)."""
        duplicado = False
        entrada = self.tabla_nodes.get(nombre)
        if entrada is not None and entrada.declarado:
            duplicado = True
            tabla = {}
            self._tablas_duplicadas.append(tabla)
        else:
            if entrada is None:
                entrada = EntradaNode(nombre)
                self.tabla_nodes[nombre] = entrada
            entrada.declarado = True
            entrada.linea_declaracion = linea
            entrada.orden = sum(1 for n in self.tabla_nodes.values() if n.declarado) - 1
            tabla = entrada.tabla_local
        self.node_actual = nombre
        self.contador_local = 0
        self.pila_ambitos.append(tabla)
        self._registrar(linea, f'entrarNode({nombre}): tabla local vacía'
                        + (' (duplicado, E08)' if duplicado else ''))
        return not duplicado

    def salir_node(self, linea: int = 0) -> None:
        """Saca la tabla local de la pila; queda guardada en EntradaNode.tabla_local."""
        if self.tabla_local is None:
            return
        nombre = self.node_actual
        self.pila_ambitos.pop()
        self.node_actual = None
        self._registrar(linea, f'salirNode(): sale {nombre}')

    def referenciar_nodo(self, nombre: str, origen: str = '', linea: int = 0,
                         instruccion: str = 'goto') -> None:
        """Registra un goto/call. Si el node aún no existe queda pendiente."""
        entrada = self.tabla_nodes.get(nombre)
        if entrada is None:
            entrada = EntradaNode(nombre)
            self.tabla_nodes[nombre] = entrada
        if not linea and origen in self.tabla_nodes:
            linea = self.tabla_nodes[origen].linea_declaracion   # mejor que 0
        ref = (linea, instruccion, origen)
        entrada.referencias.append(ref)
        if not entrada.declarado:
            entrada.referencias_pendientes.append(ref)
            self._registrar(linea, f'{instruccion} {nombre}: aún no existe, queda pendiente')

    referenciar_node = referenciar_nodo

    # Compatibilidad con la API anterior del parser
    def registrar_nodo(self, nombre: str, linea: int = 0) -> bool:
        return self.entrar_node(nombre, linea)

    # ------------------------------------------------------------------
    # Validación al final del archivo
    # ------------------------------------------------------------------
    def resolver_pendientes(self, gestor) -> None:
        """E09 por cada referencia a un node que nunca se declaró."""
        for entrada in self.tabla_nodes.values():
            if entrada.declarado:
                continue
            for linea, instruccion, _origen in entrada.referencias_pendientes:
                gestor.error('E09', linea, nombre=entrada.nombre, instruccion=instruccion)

    def validar_final(self, gestor) -> None:
        """Lo llama el parser al terminar: E03, W01 y E09."""
        for e in self._sombreados:
            gestor.error('E03', e.linea, e.columna, nombre=e.nombre)
        for entrada in self.nodes_en_orden():
            for var in entrada.tabla_local.values():
                if not var.se_lee and not var.es_const:
                    gestor.warning('W01', var.linea, var.columna, nombre=var.nombre)
        self.resolver_pendientes(gestor)
        self._registrar(0, 'fin: resolverPendientes()')

    # ------------------------------------------------------------------
    # Consultas para el optimizador y el back-end
    # ------------------------------------------------------------------
    def nodes_en_orden(self) -> list[EntradaNode]:
        return sorted((n for n in self.tabla_nodes.values() if n.declarado), key=lambda n: n.orden)

    @property
    def nodos(self) -> dict[str, EntradaNode]:
        return self.tabla_nodes

    def obtener_nodo(self, nombre: str) -> Optional[EntradaNode]:
        return self.tabla_nodes.get(nombre)

    def punto_entrada(self) -> Optional[str]:
        orden = self.nodes_en_orden()
        return orden[0].nombre if orden else None

    def locales_de(self, nombre_node: str) -> dict[str, EntradaSimbolo]:
        entrada = self.tabla_nodes.get(nombre_node)
        return entrada.tabla_local if entrada else {}

    # ------------------------------------------------------------------
    # Volcado (--dump-symtab), mismo formato que las Tablas 6 y 7 del Manual
    # ------------------------------------------------------------------
    @staticmethod
    def _valor(v: Any) -> str:
        if v is None:
            return '-'
        if isinstance(v, bool):
            return 'true' if v else 'false'
        if isinstance(v, str):
            return f'"{v}"'
        return str(v)

    def _filas(self, tabla: dict[str, EntradaSimbolo]) -> list[str]:
        filas = []
        for e in tabla.values():
            nombre = e.nombre + (' (const)' if e.es_const else '')
            filas.append(f'{nombre:<16} {e.tipo:<7} {e.ambito:<7} {e.direccion:<5} '
                         f'{e.linea:<6} {self._valor(e.valor_inicial):<14} {"sí" if e.se_lee else "no"}')
        return filas or ['(vacía)']

    def dump(self) -> str:
        enc = f'{"Nombre":<16} {"Tipo":<7} {"Ámbito":<7} {"Dir.":<5} {"Línea":<6} {"Valor inic.":<14} ¿Se lee?'
        sep = '-' * len(enc)
        out = ['=== TABLA DE SÍMBOLOS ===', '', 'Tabla global', enc, sep]
        out += self._filas(self.tabla_global)
        for n in self.nodes_en_orden():
            out += ['', f'Tabla local del node {n.nombre}', enc, sep]
            out += self._filas(n.tabla_local)

        out += ['', 'Tabla de nodes', f'{"Node":<16} {"Línea":<6} Observación', '-' * 70]
        entrada = self.punto_entrada()
        for n in self.nodes_en_orden():
            obs = []
            if n.nombre == entrada:
                obs.append('Punto de entrada: es el primer node del archivo.')
            for linea, instr, origen in n.referencias_pendientes:
                obs.append(f'Referenciado por {instr} {n.nombre} (línea {linea}, node {origen}) '
                           f'antes de ser declarado.')
            out.append(f'{n.nombre:<16} {n.linea_declaracion:<6} {" ".join(obs) or "-"}')
        for n in self.tabla_nodes.values():
            if not n.declarado:
                out.append(f'{n.nombre:<16} {"-":<6} No declarado (E09).')
        return '\n'.join(out)

    def dump_historial(self) -> str:
        """Evolución de la pila de tablas (Manual §3.1.3)."""
        out = [f'{"Línea":<6} {"Pila":<22} Acción', '-' * 70]
        out += [f'{l or "fin":<6} {p:<22} {a}' for l, p, a in self.historial]
        return '\n'.join(out)
