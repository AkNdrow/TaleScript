"""
TaleScript Parser — Analizador Sintáctico LALR(1) con ply.yacc
===============================================================
Gramática GLC completa (Listado 2 del Manual) sin declaraciones de
precedencia artificiales y con marcadores vacíos (ε) para traducción
dirigida por la sintaxis (SDT) en una sola pasada.
"""
from __future__ import annotations
import ply.yacc as yacc
import inspect
from dataclasses import dataclass, field
from typing import Optional

from talescriptc.lexer.lexer import tokens, crear_lexer, find_column

# Importaciones de Ficha 2 (con respaldo para pruebas aisladas del Front-End)
try:
    from talescriptc.semantica.tabla_simbolos import TablaSimbolos
    from talescriptc.semantica.pila_semantica import PilaSemantica, ElementoPilaSemantica
    from talescriptc.semantica.gestor_errores import GestorErrores
    from talescriptc.intermedio.cuadrupla import Cuadrupla
    from talescriptc.intermedio.generador_tac import GeneradorTAC
except ImportError:
    @dataclass
    class ElementoPilaSemantica:  # type: ignore
        tipo: str = 'ERROR'
        lugar: str = '_err'
        val: object = None
        cte: bool = False

    class PilaSemantica:  # type: ignore
        def __init__(self): self._pila = []
        def push(self, x): self._pila.append(x)
        def pop(self): return self._pila.pop() if self._pila else ElementoPilaSemantica()

    class GestorErrores:  # type: ignore
        def __init__(self):
            self.errores = []
            self.advertencias = []
        def error(self, codigo, linea, **kwargs):
            self.errores.append((codigo, linea, kwargs))
        def warning(self, codigo, linea, **kwargs):
            self.advertencias.append((codigo, linea, kwargs))
        def error_tipo_propagado(self, *tipos): return 'ERROR' in tipos
        def hay_errores(self): return len(self.errores) > 0
        def obtener_errores(self): return self.errores
        def obtener_advertencias(self): return self.advertencias
        def dump(self):
            return '\n'.join(f"[{c}] Línea {l}: {kw}" for c, l, kw in self.errores)

    class TablaSimbolos:  # type: ignore
        def __init__(self): self._global = {}; self._local = None; self._nodes = {}
        def insertar(self, *a, **kw): return True
        def buscar(self, nombre): return None
        def entrar_node(self, nombre, linea=0): self._local = {}
        def salir_node(self): self._local = None
        def registrar_nodo(self, nombre, linea=0): return True
        def referenciar_nodo(self, destino, origen=''): pass
        def marcar_usada(self, nombre): pass
        def dump(self): return '<TablaSimbolos stub>'

    @dataclass
    class Cuadrupla:  # type: ignore
        op: str
        arg1: object
        arg2: object
        res: object

    class GeneradorTAC:  # type: ignore
        def __init__(self):
            self._codigo = []
            self._cadenas = {}
            self._t = 0
            self._l = 0
        def reiniciar_node(self): self._t = 0; self._l = 0
        def nuevo_temporal(self): self._t += 1; return f't{self._t}'
        def nueva_etiqueta(self): self._l += 1; return f'L{self._l}'
        def emitir(self, c): self._codigo.append(c)
        def pos_actual(self): return len(self._codigo)
        def insertar_en(self, pos, lista): self._codigo[pos:pos] = lista
        def registrar_cadena(self, s):
            lbl = f'_str_{len(self._cadenas)}'
            self._cadenas[lbl] = s
            return lbl
        def obtener_codigo(self): return self._codigo
        def obtener_cadenas(self): return self._cadenas


# ---------------------------------------------------------------------------
# Estado global del compilador (se reinicia en cada llamada a parsear())
# ---------------------------------------------------------------------------
_ts: TablaSimbolos = None   # type: ignore
_ps: PilaSemantica = None   # type: ignore
_ge: GestorErrores = None   # type: ignore
_gt: GeneradorTAC  = None   # type: ignore
_parser_inst       = None
_fuente: str       = ''
_nodo_actual: Optional[str] = None
_pila_choice: list = []


@dataclass
class ResultadoCompilacion:
    """Resultado devuelto por parsear()."""
    exito: bool
    codigo_tac: list
    tabla_simbolos: TablaSimbolos
    tabla_cadenas: dict
    gestor_errores: GestorErrores
    errores: list = field(default_factory=list)
    advertencias: list = field(default_factory=list)


def _emitir_error(codigo: str, linea: int, **kwargs) -> None:
    """Emite errores en GestorErrores tolerando diferencias de plantilla entre versiones."""
    global _ge
    if _ge is None:
        return
    try:
        _ge.error(codigo, linea, **kwargs)
    except KeyError:
        defaults = {
            'nombre': '?',
            'linea_previa': '?',
            'esperado': '?',
            'obtenido': '?',
            'op': '?',
            'tipo_izq': '?',
            'tipo_der': '?',
            'tipo': '?',
            'token': kwargs.get('encontrado', '?'),
        }
        defaults.update(kwargs)
        try:
            _ge.error(codigo, linea, **defaults)
        except Exception:
            print(f"[{codigo}] Línea {linea}: {kwargs}")


def _ts_insertar(nombre: str, tipo: str, linea: int, **kwargs) -> bool:
    """Llama a _ts.insertar pasando solo los argumentos soportados por la versión actual."""
    global _ts
    sig = inspect.signature(_ts.insertar)
    params = sig.parameters
    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()):
        return _ts.insertar(nombre, tipo, linea, **kwargs)
    filtrados = {k: v for k, v in kwargs.items() if k in params}
    return _ts.insertar(nombre, tipo, linea, **filtrados)


# ===================================================================
# 1. ESTRUCTURA DEL PROGRAMA (Listado 2 del Manual)
# ===================================================================

def p_programa(p):
    '''programa : lista_decl_globales lista_nodos'''
    pass


def p_lista_decl_globales_multi(p):
    '''lista_decl_globales : lista_decl_globales decl_global'''
    pass


def p_lista_decl_globales_vacia(p):
    '''lista_decl_globales : empty'''
    pass


def p_decl_global_var(p):
    '''decl_global : GLOBAL tipo ID ASSIGN expr SEMI'''
    global _ts, _ps, _ge, _gt
    tipo_var = p[2]
    nombre = p[3]
    linea = p.lineno(3)
    expr_attr = _ps.pop()

    if _ge.error_tipo_propagado(expr_attr.tipo):
        return
    if not expr_attr.cte:
        _ge.error('E12', linea, nombre=nombre)
        return
    if tipo_var != expr_attr.tipo:
        _ge.error('E04', linea, esperado=tipo_var, obtenido=expr_attr.tipo)
        return
    if not _ts_insertar(nombre, tipo_var, linea, ambito='global',
                        valor_inicial=expr_attr.val, es_const=False, inicializada=True):
        _ge.error('E02', linea, nombre=nombre)


def p_decl_global_const(p):
    '''decl_global : GLOBAL CONST tipo ID ASSIGN expr SEMI'''
    global _ts, _ps, _ge
    tipo_var = p[3]
    nombre = p[4]
    linea = p.lineno(4)
    expr_attr = _ps.pop()

    if _ge.error_tipo_propagado(expr_attr.tipo):
        return
    if not expr_attr.cte:
        _ge.error('E12', linea, nombre=nombre)
        return
    if tipo_var != expr_attr.tipo:
        _ge.error('E04', linea, esperado=tipo_var, obtenido=expr_attr.tipo)
        return
    if not _ts_insertar(nombre, tipo_var, linea, ambito='global',
                        valor_inicial=expr_attr.val, es_const=True, inicializada=True):
        _ge.error('E02', linea, nombre=nombre)


def p_lista_nodos_multi(p):
    '''lista_nodos : lista_nodos nodo'''
    pass


def p_lista_nodos_single(p):
    '''lista_nodos : nodo'''
    pass


def p_nodo(p):
    '''nodo : NODE ID marker_inicio_nodo LBRACE lista_sentencias RBRACE'''
    global _ts, _gt, _nodo_actual
    # Return implícito al cierre de cada node (Ficha 2)
    _gt.emitir(Cuadrupla('return', '-', '-', '-'))
    if hasattr(_ts, 'salir_node'):
        _ts.salir_node()
    _nodo_actual = None


def p_marker_inicio_nodo(p):
    '''marker_inicio_nodo : '''
    global _ts, _ge, _gt, _nodo_actual
    nombre = p[-1]
    linea = getattr(p.stack[-1], 'lineno', p.lexer.lineno)
    _nodo_actual = nombre

    if hasattr(_gt, 'reiniciar_node'):
        _gt.reiniciar_node()

    if hasattr(_ts, 'entrar_node'):
        if not _ts.entrar_node(nombre, linea):
            _ge.error('E08', linea, nombre=nombre)
    elif not _ts.registrar_nodo(nombre, linea):
        _ge.error('E08', linea, nombre=nombre)

    _gt.emitir(Cuadrupla('label', '-', '-', f'_node_{nombre}'))


def p_lista_sentencias_multi(p):
    '''lista_sentencias : lista_sentencias sentencia'''
    pass


def p_lista_sentencias_vacia(p):
    '''lista_sentencias : empty'''
    pass


def p_empty(p):
    '''empty : '''
    pass


# ===================================================================
# 2. SENTENCIAS
# ===================================================================

def p_sentencia(p):
    '''sentencia : decl_local
                 | asignacion
                 | sent_say
                 | sent_goto
                 | sent_call
                 | sent_return
                 | condicional
                 | sent_while
                 | sent_dowhile
                 | sent_choice
                 | sent_end'''
    pass


# --- Declaración local ---
def p_decl_local_init(p):
    '''decl_local : LOCAL tipo ID ASSIGN expr SEMI'''
    global _ts, _ps, _ge, _gt
    tipo_var = p[2]
    nombre = p[3]
    linea = p.lineno(3)
    expr_attr = _ps.pop()

    if _ge.error_tipo_propagado(expr_attr.tipo):
        return
    if tipo_var != expr_attr.tipo:
        _ge.error('E04', linea, esperado=tipo_var, obtenido=expr_attr.tipo)
        return
    if not _ts_insertar(nombre, tipo_var, linea, ambito='local',
                        valor_inicial=expr_attr.val if expr_attr.cte else None, inicializada=True):
        _ge.error('E02', linea, nombre=nombre)
        return
    _gt.emitir(Cuadrupla('=', expr_attr.lugar, '-', nombre))


def p_decl_local_sin_init(p):
    '''decl_local : LOCAL tipo ID SEMI'''
    global _ts, _ge, _gt
    tipo_var = p[2]
    nombre = p[3]
    linea = p.lineno(3)
    defaults = {'int': '0', 'bool': 'false', 'string': '""'}

    if not _ts_insertar(nombre, tipo_var, linea, ambito='local', inicializada=False):
        _ge.error('E02', linea, nombre=nombre)
        return
    _gt.emitir(Cuadrupla('=', defaults.get(tipo_var, '0'), '-', nombre))


def p_decl_local_const(p):
    '''decl_local : LOCAL CONST tipo ID ASSIGN expr SEMI'''
    global _ts, _ps, _ge, _gt
    tipo_var = p[3]
    nombre = p[4]
    linea = p.lineno(4)
    expr_attr = _ps.pop()

    if _ge.error_tipo_propagado(expr_attr.tipo):
        return
    if not expr_attr.cte:
        _ge.error('E12', linea, nombre=nombre)
        return
    if tipo_var != expr_attr.tipo:
        _ge.error('E04', linea, esperado=tipo_var, obtenido=expr_attr.tipo)
        return
    if not _ts_insertar(nombre, tipo_var, linea, ambito='local',
                        valor_inicial=expr_attr.val, es_const=True, inicializada=True):
        _ge.error('E02', linea, nombre=nombre)
        return
    _gt.emitir(Cuadrupla('=', expr_attr.lugar, '-', nombre))


# --- Asignación ---
def p_asignacion(p):
    '''asignacion : ID ASSIGN expr SEMI'''
    global _ts, _ps, _ge, _gt
    nombre = p[1]
    linea = p.lineno(1)
    expr_attr = _ps.pop()

    sym = _ts.buscar(nombre)
    if sym is None:
        _ge.error('E01', linea, nombre=nombre)
        return
    if getattr(sym, 'es_const', False):
        _ge.error('E11', linea, nombre=nombre)
        return
    if _ge.error_tipo_propagado(expr_attr.tipo):
        return
    if sym.tipo != expr_attr.tipo:
        _ge.error('E04', linea, esperado=sym.tipo, obtenido=expr_attr.tipo)
        return
    _gt.emitir(Cuadrupla('=', expr_attr.lugar, '-', nombre))


# --- Say ---
def p_sent_say(p):
    '''sent_say : SAY expr SEMI'''
    global _ps, _ge, _gt
    attr = _ps.pop()
    linea = p.lineno(1)

    if _ge.error_tipo_propagado(attr.tipo):
        return
    if attr.tipo not in ('string', 'int'):
        _ge.error('E04', linea, esperado='string o int', obtenido=attr.tipo)
        return
    _gt.emitir(Cuadrupla('say', attr.lugar, '-', '-'))


# --- Goto, Call, Return, End ---
def p_sent_goto(p):
    '''sent_goto : GOTO ID SEMI'''
    global _ts, _gt, _nodo_actual
    destino = p[2]
    _ts.referenciar_nodo(destino, _nodo_actual or '__global__')
    _gt.emitir(Cuadrupla('goto', '-', '-', destino))


def p_sent_call(p):
    '''sent_call : CALL ID SEMI'''
    global _ts, _gt, _nodo_actual
    destino = p[2]
    _ts.referenciar_nodo(destino, _nodo_actual or '__global__')
    _gt.emitir(Cuadrupla('call', '-', '-', destino))


def p_sent_return(p):
    '''sent_return : RETURN SEMI'''
    global _gt
    _gt.emitir(Cuadrupla('return', '-', '-', '-'))


def p_sent_end(p):
    '''sent_end : END SEMI'''
    global _gt
    _gt.emitir(Cuadrupla('end', '-', '-', '-'))


# --- Condicional if / if-else ---
def p_condicional_if(p):
    '''condicional : IF LPAREN expr RPAREN marker_if LBRACE lista_sentencias RBRACE'''
    global _gt
    lbl_fin = p[5]
    _gt.emitir(Cuadrupla('label', '-', '-', lbl_fin))


def p_condicional_if_else(p):
    '''condicional : IF LPAREN expr RPAREN marker_if LBRACE lista_sentencias RBRACE ELSE marker_else LBRACE lista_sentencias RBRACE'''
    global _gt
    lbl_fin = p[10]
    _gt.emitir(Cuadrupla('label', '-', '-', lbl_fin))


def p_marker_if(p):
    '''marker_if : '''
    global _ps, _ge, _gt
    attr = _ps.pop()
    # p.stack[-4] corresponde al token IF en: IF LPAREN expr RPAREN
    linea = getattr(p.stack[-4], 'lineno', p.lexer.lineno)
    lbl_falso = _gt.nueva_etiqueta()

    if not _ge.error_tipo_propagado(attr.tipo):
        if attr.tipo != 'bool':
            _ge.error('E07', linea, obtenido=attr.tipo)
        else:
            _gt.emitir(Cuadrupla('ifFalse', attr.lugar, '-', lbl_falso))
    p[0] = lbl_falso


def p_marker_else(p):
    '''marker_else : '''
    global _gt
    lbl_else = p[-5]
    lbl_fin = _gt.nueva_etiqueta()
    _gt.emitir(Cuadrupla('goto', '-', '-', lbl_fin))
    _gt.emitir(Cuadrupla('label', '-', '-', lbl_else))
    p[0] = lbl_fin


# --- Ciclo while ---
def p_sent_while(p):
    '''sent_while : WHILE LPAREN marker_while_ini expr RPAREN marker_while_cond LBRACE lista_sentencias RBRACE'''
    global _gt
    lbl_ini = p[3]
    lbl_fin = p[6]
    _gt.emitir(Cuadrupla('goto', '-', '-', lbl_ini))
    _gt.emitir(Cuadrupla('label', '-', '-', lbl_fin))


def p_marker_while_ini(p):
    '''marker_while_ini : '''
    global _gt
    lbl_ini = _gt.nueva_etiqueta()
    _gt.emitir(Cuadrupla('label', '-', '-', lbl_ini))
    p[0] = lbl_ini


def p_marker_while_cond(p):
    '''marker_while_cond : '''
    global _ps, _ge, _gt
    attr = _ps.pop()
    # p.stack[-5] corresponde al token WHILE en: WHILE LPAREN marker_while_ini expr RPAREN
    linea = getattr(p.stack[-5], 'lineno', p.lexer.lineno)
    lbl_fin = _gt.nueva_etiqueta()

    if not _ge.error_tipo_propagado(attr.tipo):
        if attr.tipo != 'bool':
            _ge.error('E07', linea, obtenido=attr.tipo)
        else:
            _gt.emitir(Cuadrupla('ifFalse', attr.lugar, '-', lbl_fin))
    p[0] = lbl_fin


# --- Ciclo do-while ---
def p_sent_dowhile(p):
    '''sent_dowhile : DO marker_dowhile_ini LBRACE lista_sentencias RBRACE WHILE LPAREN expr RPAREN SEMI'''
    global _ps, _ge, _gt
    lbl_ini = p[2]
    attr = _ps.pop()
    linea = p.lineno(6)

    if not _ge.error_tipo_propagado(attr.tipo):
        if attr.tipo != 'bool':
            _ge.error('E07', linea, obtenido=attr.tipo)
        else:
            _gt.emitir(Cuadrupla('ifTrue', attr.lugar, '-', lbl_ini))


def p_marker_dowhile_ini(p):
    '''marker_dowhile_ini : '''
    global _gt
    lbl_ini = _gt.nueva_etiqueta()
    _gt.emitir(Cuadrupla('label', '-', '-', lbl_ini))
    p[0] = lbl_ini


# ===================================================================
# 3. MENÚ DE DECISIÓN (CHOICE)
# ===================================================================

def p_sent_choice(p):
    '''sent_choice : CHOICE marker_choice_ini LBRACE lista_opciones RBRACE'''
    global _ge, _gt, _pila_choice
    pos_insercion, lbl_fin = _pila_choice.pop()
    opciones = p[4]  # [(texto, lbl_opt, linea), ...]

    vistos = set()
    cuadruplas_menu = []
    for texto, lbl_opt, linea in opciones:
        if texto in vistos:
            _ge.error('E10', linea, opcion=texto)
        vistos.add(texto)
        cuadruplas_menu.append(Cuadrupla('opt', f'"{texto}"', '-', lbl_opt))
    cuadruplas_menu.append(Cuadrupla('menu', '-', '-', '-'))

    if hasattr(_gt, 'insertar_en'):
        _gt.insertar_en(pos_insercion, cuadruplas_menu)
    elif hasattr(_gt, 'insertarEn'):
        _gt.insertarEn(pos_insercion, cuadruplas_menu)

    _gt.emitir(Cuadrupla('label', '-', '-', lbl_fin))


def p_marker_choice_ini(p):
    '''marker_choice_ini : '''
    global _gt, _pila_choice
    pos = _gt.pos_actual() if hasattr(_gt, 'pos_actual') else len(_gt.obtener_codigo())
    lbl_fin = _gt.nueva_etiqueta()
    _pila_choice.append((pos, lbl_fin))
    p[0] = (pos, lbl_fin)


def p_lista_opciones_multi(p):
    '''lista_opciones : lista_opciones opcion'''
    p[0] = p[1] + [p[2]]


def p_lista_opciones_single(p):
    '''lista_opciones : opcion'''
    p[0] = [p[1]]


def p_opcion(p):
    '''opcion : STR marker_opcion LBRACE lista_sentencias RBRACE'''
    global _gt
    texto, lbl_opt, lbl_fin, linea = p[2]
    _gt.emitir(Cuadrupla('goto', '-', '-', lbl_fin))
    p[0] = (texto, lbl_opt, linea)


def p_marker_opcion(p):
    '''marker_opcion : '''
    global _gt, _pila_choice
    parts = p[-1]
    linea = getattr(p.stack[-1], 'lineno', p.lexer.lineno)
    lbl_fin = _pila_choice[-1][1] if _pila_choice else _gt.nueva_etiqueta()

    texto = ''.join(item[1] if isinstance(item, tuple) else item for item in parts)
    lbl_opt = _gt.nueva_etiqueta()
    _gt.emitir(Cuadrupla('label', '-', '-', lbl_opt))
    p[0] = (texto, lbl_opt, lbl_fin, linea)


# ===================================================================
# 4. TIPOS
# ===================================================================

def p_tipo_int(p):
    '''tipo : INT'''
    p[0] = 'int'


def p_tipo_string(p):
    '''tipo : STRING'''
    p[0] = 'string'


def p_tipo_bool(p):
    '''tipo : BOOL'''
    p[0] = 'bool'


# ===================================================================
# 5. EXPRESIONES (Jerarquía estricta sin tuple precedence)
#    or < and < not < relacionales < + - < * / % < - unario < F
# ===================================================================

# --- Nivel E: OR lógico ---
def p_expr_or(p):
    '''expr : expr OR conj'''
    global _ps, _ge, _gt
    der = _ps.pop()
    izq = _ps.pop()
    linea = p.lineno(2)

    if _ge.error_tipo_propagado(izq.tipo, der.tipo):
        _ps.push(ElementoPilaSemantica(tipo='ERROR', lugar='_err'))
        return
    if izq.tipo != 'bool' or der.tipo != 'bool':
        _ge.error('E05', linea, op='or', tipo_izq=izq.tipo, tipo_der=der.tipo)
        _ps.push(ElementoPilaSemantica(tipo='ERROR', lugar='_err'))
        return
    if izq.cte and der.cte:
        val = bool(izq.val or der.val)
        _ps.push(ElementoPilaSemantica(tipo='bool', lugar='true' if val else 'false', val=val, cte=True))
        return
    t = _gt.nuevo_temporal()
    _gt.emitir(Cuadrupla('or', izq.lugar, der.lugar, t))
    _ps.push(ElementoPilaSemantica(tipo='bool', lugar=t))


def p_expr_to_conj(p):
    '''expr : conj'''
    pass


# --- Nivel C: AND lógico ---
def p_conj_and(p):
    '''conj : conj AND neg'''
    global _ps, _ge, _gt
    der = _ps.pop()
    izq = _ps.pop()
    linea = p.lineno(2)

    if _ge.error_tipo_propagado(izq.tipo, der.tipo):
        _ps.push(ElementoPilaSemantica(tipo='ERROR', lugar='_err'))
        return
    if izq.tipo != 'bool' or der.tipo != 'bool':
        _ge.error('E05', linea, op='and', tipo_izq=izq.tipo, tipo_der=der.tipo)
        _ps.push(ElementoPilaSemantica(tipo='ERROR', lugar='_err'))
        return
    if izq.cte and der.cte:
        val = bool(izq.val and der.val)
        _ps.push(ElementoPilaSemantica(tipo='bool', lugar='true' if val else 'false', val=val, cte=True))
        return
    t = _gt.nuevo_temporal()
    _gt.emitir(Cuadrupla('and', izq.lugar, der.lugar, t))
    _ps.push(ElementoPilaSemantica(tipo='bool', lugar=t))


def p_conj_to_neg(p):
    '''conj : neg'''
    pass


# --- Nivel N: NOT lógico ---
def p_neg_not(p):
    '''neg : NOT neg'''
    global _ps, _ge, _gt
    attr = _ps.pop()
    linea = p.lineno(1)

    if _ge.error_tipo_propagado(attr.tipo):
        _ps.push(ElementoPilaSemantica(tipo='ERROR', lugar='_err'))
        return
    if attr.tipo != 'bool':
        _ge.error('E05', linea, op='not', tipo_izq=attr.tipo, tipo_der='-')
        _ps.push(ElementoPilaSemantica(tipo='ERROR', lugar='_err'))
        return
    if attr.cte:
        val = not bool(attr.val)
        _ps.push(ElementoPilaSemantica(tipo='bool', lugar='true' if val else 'false', val=val, cte=True))
        return
    t = _gt.nuevo_temporal()
    _gt.emitir(Cuadrupla('not', attr.lugar, '-', t))
    _ps.push(ElementoPilaSemantica(tipo='bool', lugar=t))


def p_neg_to_rel(p):
    '''neg : rel'''
    pass


# --- Nivel R: Relacionales (< <= > >= == !=) ---
def p_rel_op(p):
    '''rel : arit relop arit'''
    global _ps, _ge, _gt
    der = _ps.pop()
    izq = _ps.pop()
    op = p[2]
    linea = p.lineno(2)

    if _ge.error_tipo_propagado(izq.tipo, der.tipo):
        _ps.push(ElementoPilaSemantica(tipo='ERROR', lugar='_err'))
        return

    if op in ('<', '<=', '>', '>='):
        if izq.tipo != 'int' or der.tipo != 'int':
            _ge.error('E05', linea, op=op, tipo_izq=izq.tipo, tipo_der=der.tipo)
            _ps.push(ElementoPilaSemantica(tipo='ERROR', lugar='_err'))
            return
    else:  # ==, !=
        if izq.tipo != der.tipo:
            _ge.error('E05', linea, op=op, tipo_izq=izq.tipo, tipo_der=der.tipo)
            _ps.push(ElementoPilaSemantica(tipo='ERROR', lugar='_err'))
            return

    if izq.cte and der.cte:
        ops = {
            '<': lambda a, b: a < b, '<=': lambda a, b: a <= b,
            '>': lambda a, b: a > b, '>=': lambda a, b: a >= b,
            '==': lambda a, b: a == b, '!=': lambda a, b: a != b,
        }
        val = bool(ops[op](izq.val, der.val))
        _ps.push(ElementoPilaSemantica(tipo='bool', lugar='true' if val else 'false', val=val, cte=True))
        return

    t = _gt.nuevo_temporal()
    _gt.emitir(Cuadrupla(op, izq.lugar, der.lugar, t))
    _ps.push(ElementoPilaSemantica(tipo='bool', lugar=t))


def p_relop(p):
    '''relop : LT
             | LE
             | GT
             | GE
             | EQ
             | NE'''
    p[0] = p[1]


def p_rel_to_arit(p):
    '''rel : arit'''
    pass


# --- Nivel A: Suma y resta (+ -) ---
def p_arit_binop(p):
    '''arit : arit PLUS term
            | arit MINUS term'''
    global _ps, _ge, _gt
    der = _ps.pop()
    izq = _ps.pop()
    op = p[2]
    linea = p.lineno(2)

    if _ge.error_tipo_propagado(izq.tipo, der.tipo):
        _ps.push(ElementoPilaSemantica(tipo='ERROR', lugar='_err'))
        return

    # Concatenación con + si al menos un operando es string
    if op == '+' and ('string' in (izq.tipo, der.tipo)):
        if izq.tipo not in ('string', 'int') or der.tipo not in ('string', 'int'):
            _ge.error('E05', linea, op='+', tipo_izq=izq.tipo, tipo_der=der.tipo)
            _ps.push(ElementoPilaSemantica(tipo='ERROR', lugar='_err'))
            return
        t = _gt.nuevo_temporal()
        _gt.emitir(Cuadrupla('concat', izq.lugar, der.lugar, t))
        _ps.push(ElementoPilaSemantica(tipo='string', lugar=t))
        return

    if izq.tipo != 'int' or der.tipo != 'int':
        _ge.error('E05', linea, op=op, tipo_izq=izq.tipo, tipo_der=der.tipo)
        _ps.push(ElementoPilaSemantica(tipo='ERROR', lugar='_err'))
        return

    if izq.cte and der.cte:
        val = (izq.val + der.val) if op == '+' else (izq.val - der.val)
        _ps.push(ElementoPilaSemantica(tipo='int', lugar=str(val), val=val, cte=True))
        return

    t = _gt.nuevo_temporal()
    _gt.emitir(Cuadrupla(op, izq.lugar, der.lugar, t))
    _ps.push(ElementoPilaSemantica(tipo='int', lugar=t))


def p_arit_to_term(p):
    '''arit : term'''
    pass


# --- Nivel M: Multiplicación, división y módulo (* / %) ---
def p_term_binop(p):
    '''term : term STAR unario
            | term SLASH unario
            | term PERCENT unario'''
    global _ps, _ge, _gt
    der = _ps.pop()
    izq = _ps.pop()
    op = p[2]
    linea = p.lineno(2)

    if _ge.error_tipo_propagado(izq.tipo, der.tipo):
        _ps.push(ElementoPilaSemantica(tipo='ERROR', lugar='_err'))
        return
    if izq.tipo != 'int' or der.tipo != 'int':
        _ge.error('E05', linea, op=op, tipo_izq=izq.tipo, tipo_der=der.tipo)
        _ps.push(ElementoPilaSemantica(tipo='ERROR', lugar='_err'))
        return
    if op in ('/', '%') and der.cte and der.val == 0:
        _ge.error('E06', linea)
        _ps.push(ElementoPilaSemantica(tipo='ERROR', lugar='_err'))
        return

    if izq.cte and der.cte:
        if op == '*':
            val = izq.val * der.val
        elif op == '/':
            val = int(izq.val / der.val)
        else:
            val = izq.val % der.val
        _ps.push(ElementoPilaSemantica(tipo='int', lugar=str(val), val=val, cte=True))
        return

    t = _gt.nuevo_temporal()
    _gt.emitir(Cuadrupla(op, izq.lugar, der.lugar, t))
    _ps.push(ElementoPilaSemantica(tipo='int', lugar=t))


def p_term_to_unario(p):
    '''term : unario'''
    pass


# --- Nivel U: Menos unario (- U) ---
def p_unario_neg(p):
    '''unario : MINUS unario'''
    global _ps, _ge, _gt
    attr = _ps.pop()
    linea = p.lineno(1)

    if _ge.error_tipo_propagado(attr.tipo):
        _ps.push(ElementoPilaSemantica(tipo='ERROR', lugar='_err'))
        return
    if attr.tipo != 'int':
        _ge.error('E05', linea, op='-unario', tipo_izq=attr.tipo, tipo_der='-')
        _ps.push(ElementoPilaSemantica(tipo='ERROR', lugar='_err'))
        return
    if attr.cte:
        val = -attr.val
        _ps.push(ElementoPilaSemantica(tipo='int', lugar=str(val), val=val, cte=True))
        return
    t = _gt.nuevo_temporal()
    _gt.emitir(Cuadrupla('neg', attr.lugar, '-', t))
    _ps.push(ElementoPilaSemantica(tipo='int', lugar=t))


def p_unario_to_factor(p):
    '''unario : factor'''
    pass


# --- Nivel F: Paréntesis, literales, identificadores y casting ---
def p_factor_paren(p):
    '''factor : LPAREN expr RPAREN'''
    pass


def p_factor_cast(p):
    '''factor : tipo LPAREN expr RPAREN'''
    global _ps, _ge, _gt
    destino = p[1]
    linea = p.lineno(2)
    attr = _ps.pop()

    if _ge.error_tipo_propagado(attr.tipo):
        _ps.push(ElementoPilaSemantica(tipo='ERROR', lugar='_err'))
        return
    if attr.tipo == destino:
        _ps.push(attr)
        return
    t = _gt.nuevo_temporal()
    _gt.emitir(Cuadrupla(f'cast_{destino}', attr.lugar, '-', t))
    _ps.push(ElementoPilaSemantica(tipo=destino, lugar=t))


def p_factor_num(p):
    '''factor : NUM'''
    global _ps
    val = p[1]
    _ps.push(ElementoPilaSemantica(tipo='int', lugar=str(val), val=val, cte=True))


def p_factor_str(p):
    '''factor : STR'''
    global _ps, _gt, _ts, _ge
    parts = p[1]  # ["texto", ("VAR", "karma"), ...]
    linea = p.lineno(1)

    if len(parts) == 1 and isinstance(parts[0], str):
        texto = parts[0]
        _gt.registrar_cadena(texto)
        _ps.push(ElementoPilaSemantica(tipo='string', lugar=f'"{texto}"', val=texto, cte=True))
        return

    resultado = None
    for parte in parts:
        if isinstance(parte, str):
            _gt.registrar_cadena(parte)
            elem = ElementoPilaSemantica(tipo='string', lugar=f'"{parte}"', cte=True)
        else:
            _, var_name = parte
            sym = _ts.buscar(var_name)
            if sym is None:
                _ge.error('E01', linea, nombre=var_name)
                _ps.push(ElementoPilaSemantica(tipo='ERROR', lugar='_err'))
                return
            if sym.tipo != 'int':
                _ge.error('E05', linea, op='interpolación', tipo_izq=sym.tipo, tipo_der='int')
                _ps.push(ElementoPilaSemantica(tipo='ERROR', lugar='_err'))
                return
            _ts.marcar_usada(var_name)
            elem = ElementoPilaSemantica(tipo='int', lugar=var_name)

        if resultado is None:
            resultado = elem
        else:
            t = _gt.nuevo_temporal()
            _gt.emitir(Cuadrupla('concat', resultado.lugar, elem.lugar, t))
            resultado = ElementoPilaSemantica(tipo='string', lugar=t)

    _ps.push(resultado or ElementoPilaSemantica(tipo='string', lugar='""', cte=True))


def p_factor_true(p):
    '''factor : TRUE'''
    global _ps
    _ps.push(ElementoPilaSemantica(tipo='bool', lugar='true', val=True, cte=True))


def p_factor_false(p):
    '''factor : FALSE'''
    global _ps
    _ps.push(ElementoPilaSemantica(tipo='bool', lugar='false', val=False, cte=True))


def p_factor_id(p):
    '''factor : ID'''
    global _ts, _ps, _ge
    nombre = p[1]
    linea = p.lineno(1)
    sym = _ts.buscar(nombre)
    if sym is None:
        _ge.error('E01', linea, nombre=nombre)
        _ps.push(ElementoPilaSemantica(tipo='ERROR', lugar='_err'))
        return
    _ts.marcar_usada(nombre)
    _ps.push(ElementoPilaSemantica(tipo=sym.tipo, lugar=nombre))


# ===================================================================
# RECUPERACIÓN DE ERRORES EN MODO PÁNICO (S01)
# ===================================================================

def p_error(p):
    global _parser_inst, _fuente
    if p is None:
        _emitir_error('S01', 0, token='EOF', esperado='fin de sentencia o bloque', encontrado='EOF')
        return

    col = find_column(_fuente, p) if _fuente else 0
    esperados = []
    if _parser_inst is not None and hasattr(_parser_inst, 'state'):
        acciones = _parser_inst.action.get(_parser_inst.state, {})
        esperados = sorted(tok for tok in acciones.keys() if tok != '$end')

    encontrado_str = f"{p.type} ('{p.value}')"
    _emitir_error(
        'S01', p.lineno,
        token=encontrado_str,
        columna=col,
        esperado=', '.join(esperados[:6]) if esperados else 'token válido',
        encontrado=encontrado_str,
    )

    # Modo pánico: descartar tokens hasta ';' (SEMI) o '}' (RBRACE)
    if _parser_inst is not None:
        while True:
            tok = _parser_inst.token()
            if not tok or tok.type in ('SEMI', 'RBRACE'):
                break
        _parser_inst.errok()


# ===================================================================
# INTERFAZ PÚBLICA
# ===================================================================

def construir_parser(debug: bool = True, write_tables: bool = True):
    """Construye el analizador sintáctico LALR(1) y genera parser.out."""
    return yacc.yacc(debug=debug, write_tables=write_tables)


def parsear(source_code: str) -> ResultadoCompilacion:
    """Punto de entrada del Front-End: lexing + parsing + SDT."""
    global _ts, _ps, _ge, _gt, _parser_inst, _fuente, _nodo_actual, _pila_choice

    _ts = TablaSimbolos()
    _ps = PilaSemantica()
    _ge = GestorErrores()
    _gt = GeneradorTAC()
    _fuente = source_code
    _nodo_actual = None
    _pila_choice = []

    lexer_inst = crear_lexer(gestor_errores=_ge)
    _parser_inst = construir_parser(debug=True, write_tables=True)
    _parser_inst.parse(source_code, lexer=lexer_inst)

    if hasattr(_ts, 'validar_final'):
        _ts.validar_final(_ge)

    return ResultadoCompilacion(
        exito=not _ge.hay_errores(),
        codigo_tac=_gt.obtener_codigo(),
        tabla_simbolos=_ts,
        tabla_cadenas=_gt.obtener_cadenas(),
        gestor_errores=_ge,
        errores=_ge.obtener_errores(),
        advertencias=_ge.obtener_advertencias(),
    )