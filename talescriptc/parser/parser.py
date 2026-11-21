"""
TaleScript Parser — Analizador Sintáctico LALR(1) con ply.yacc
===============================================================
Gramática GLC con marcadores vacíos (ε) para traducción dirigida
por la sintaxis (SDT).  Las acciones semánticas invocan directamente
la tabla de símbolos, la pila semántica, el gestor de errores y el
generador de TAC.
"""
from __future__ import annotations
import ply.yacc as yacc
from dataclasses import dataclass, field
from typing import Optional

from talescriptc.lexer.lexer import tokens, crear_lexer, find_column
from talescriptc.semantica.tabla_simbolos import TablaSimbolos
from talescriptc.semantica.pila_semantica import PilaSemantica, ElementoPilaSemantica
from talescriptc.semantica.gestor_errores import GestorErrores
from talescriptc.intermedio.cuadrupla import Cuadrupla
from talescriptc.intermedio.generador_tac import GeneradorTAC

# ---------------------------------------------------------------------------
# Estado global del compilador (se reinicia con cada llamada a parsear())
# ---------------------------------------------------------------------------
_ts: TablaSimbolos    = None   # type: ignore
_ps: PilaSemantica    = None   # type: ignore
_ge: GestorErrores    = None   # type: ignore
_gt: GeneradorTAC     = None   # type: ignore
_fuente: str          = ''
_nodo_actual: Optional[str] = None


@dataclass
class ResultadoCompilacion:
    """Resultado devuelto por parsear()."""
    exito: bool
    codigo_tac: list
    tabla_simbolos: TablaSimbolos
    tabla_cadenas: dict
    gestor_errores: GestorErrores
    errores: list   = field(default_factory=list)
    advertencias: list = field(default_factory=list)


# ===================================================================
# PRECEDENCIA (de menor a mayor)
# ===================================================================
precedence = (
    ('nonassoc', 'IF_PREC'),       # para resolver dangling else
    ('nonassoc', 'ELSE'),
    ('left', 'EQ', 'NEQ'),
    ('left', 'LT', 'GT', 'LEQ', 'GEQ'),
    ('left', 'PLUS', 'MINUS'),
    ('left', 'TIMES', 'DIVIDE'),
    ('right', 'UMINUS'),
)


# ===================================================================
# GRAMÁTICA
# ===================================================================

# --- Programa ---
def p_programa(p):
    '''programa : lista_declaraciones'''
    pass

def p_lista_declaraciones_multi(p):
    '''lista_declaraciones : lista_declaraciones declaracion'''
    pass

def p_lista_declaraciones_single(p):
    '''lista_declaraciones : declaracion'''
    pass

def p_declaracion(p):
    '''declaracion : decl_variable
                   | decl_nodo'''
    pass

# --- Declaración de variables ---
def p_decl_variable_init(p):
    '''decl_variable : VAR tipo ID ASSIGN expr SEMICOLON'''
    global _ts, _ps, _ge, _gt
    tipo_var = p[2]
    nombre = p[3]
    linea = p.lineno(3)
    expr_attr = _ps.pop()

    # Anti-cascada
    if _ge.error_tipo_propagado(expr_attr.tipo):
        _ts.insertar(nombre, tipo_var, linea, inicializada=True)
        return

    # Verificar tipos
    if tipo_var != expr_attr.tipo and expr_attr.tipo != 'ERROR':
        _ge.error('E03', linea, esperado=tipo_var, obtenido=expr_attr.tipo)
    # Registrar
    if not _ts.insertar(nombre, tipo_var, linea, inicializada=True):
        prev = _ts.buscar(nombre)
        _ge.error('E02', linea, nombre=nombre,
                  linea_previa=prev.linea_decl if prev else '?')
        return
    _ts.marcar_inicializada(nombre)
    # Emitir TAC
    _gt.emitir(Cuadrupla('ASSIGN', expr_attr.lugar, None, nombre))


def p_decl_variable_sin_init(p):
    '''decl_variable : VAR tipo ID SEMICOLON'''
    global _ts, _ge
    tipo_var = p[2]
    nombre = p[3]
    linea = p.lineno(3)
    if not _ts.insertar(nombre, tipo_var, linea, inicializada=False):
        prev = _ts.buscar(nombre)
        _ge.error('E02', linea, nombre=nombre,
                  linea_previa=prev.linea_decl if prev else '?')


def p_tipo_int(p):
    '''tipo : INT_TYPE'''
    p[0] = 'int'

def p_tipo_string(p):
    '''tipo : STRING_TYPE'''
    p[0] = 'string'


# --- Declaración de nodo ---
def p_decl_nodo(p):
    '''decl_nodo : NODE ID marker_pre_nodo LBRACE lista_sentencias RBRACE'''
    global _ts, _ge, _gt, _nodo_actual
    nombre = p[2]
    # Verificar que el nodo tenga salida (E11 se chequea en post-parse)
    _nodo_actual = None


def p_marker_pre_nodo(p):
    '''marker_pre_nodo : '''
    global _ts, _ge, _gt, _nodo_actual
    nombre = p[-1]  # El ID que precede al marker
    linea = p.lineno(-1)
    _nodo_actual = nombre
    if not _ts.registrar_nodo(nombre, linea):
        prev = _ts.obtener_nodo(nombre)
        _ge.error('E06', linea, nombre=nombre,
                  linea_previa=prev.linea_decl if prev else '?')
    # Emitir etiqueta de nodo
    _gt.emitir(Cuadrupla('LABEL', None, None, f'_node_{nombre}'))


# --- Lista de sentencias ---
def p_lista_sentencias_multi(p):
    '''lista_sentencias : lista_sentencias sentencia'''
    pass

def p_lista_sentencias_vacia(p):
    '''lista_sentencias : vacio'''
    pass

def p_vacio(p):
    '''vacio : '''
    pass


# --- Sentencias ---
def p_sentencia(p):
    '''sentencia : sent_say
                 | sent_set
                 | sent_if
                 | sent_goto
                 | sent_exit
                 | sent_choice'''
    pass


# --- SAY ---
def p_sent_say(p):
    '''sent_say : SAY LPAREN expr RPAREN SEMICOLON'''
    global _ps, _gt
    attr = _ps.pop()
    if attr.tipo != 'ERROR':
        _gt.emitir(Cuadrupla('SAY', attr.lugar, None, None))


# --- SET ---
def p_sent_set(p):
    '''sent_set : SET ID ASSIGN expr SEMICOLON'''
    global _ts, _ps, _ge, _gt
    nombre = p[2]
    linea = p.lineno(2)
    expr_attr = _ps.pop()

    sym = _ts.buscar(nombre)
    if sym is None:
        _ge.error('E01', linea, nombre=nombre)
        return

    _ts.marcar_usada(nombre)
    if _ge.error_tipo_propagado(expr_attr.tipo):
        return
    if sym.tipo != expr_attr.tipo and expr_attr.tipo != 'ERROR':
        _ge.error('E03', linea, esperado=sym.tipo, obtenido=expr_attr.tipo)
        return
    _ts.marcar_inicializada(nombre)
    _gt.emitir(Cuadrupla('ASSIGN', expr_attr.lugar, None, nombre))


# --- IF / IF-ELSE ---
def p_sent_if(p):
    '''sent_if : IF LPAREN expr RPAREN marker_cond LBRACE lista_sentencias RBRACE %prec IF_PREC'''
    global _gt
    label_false = p[5]
    _gt.emitir(Cuadrupla('LABEL', None, None, label_false))


def p_sent_if_else(p):
    '''sent_if : IF LPAREN expr RPAREN marker_cond LBRACE lista_sentencias RBRACE ELSE marker_else LBRACE lista_sentencias RBRACE'''
    global _gt
    label_end = p[10]
    _gt.emitir(Cuadrupla('LABEL', None, None, label_end))


def p_marker_cond(p):
    '''marker_cond : '''
    global _ps, _gt
    attr = _ps.pop()
    label_false = _gt.nueva_etiqueta()
    if attr.tipo != 'ERROR':
        _gt.emitir(Cuadrupla('IF_FALSE', attr.lugar, None, label_false))
    p[0] = label_false


def p_marker_else(p):
    '''marker_else : '''
    global _gt
    label_false = p[-5]  # marker_cond value from same production
    label_end = _gt.nueva_etiqueta()
    _gt.emitir(Cuadrupla('GOTO', None, None, label_end))
    _gt.emitir(Cuadrupla('LABEL', None, None, label_false))
    p[0] = label_end


# --- GOTO ---
def p_sent_goto(p):
    '''sent_goto : GOTO ID SEMICOLON'''
    global _ts, _gt, _nodo_actual
    destino = p[2]
    _ts.referenciar_nodo(destino, _nodo_actual or '__global__')
    if _nodo_actual:
        _ts.marcar_nodo_con_salida(_nodo_actual)
    _gt.emitir(Cuadrupla('GOTO', None, None, f'_node_{destino}'))


# --- EXIT ---
def p_sent_exit(p):
    '''sent_exit : EXIT SEMICOLON'''
    global _ts, _gt, _nodo_actual
    if _nodo_actual:
        _ts.marcar_nodo_con_salida(_nodo_actual)
    _gt.emitir(Cuadrupla('EXIT', None, None, None))


# --- CHOICE ---
def p_sent_choice(p):
    '''sent_choice : CHOICE LBRACE lista_opciones RBRACE'''
    global _ts, _ge, _gt, _nodo_actual
    opciones = p[3]  # list of (texto_label, nodo_destino)
    if _nodo_actual:
        _ts.marcar_nodo_con_salida(_nodo_actual)

    for texto_label, destino in opciones:
        _gt.emitir(Cuadrupla('ADD_OPT', texto_label, None, None))
        _ts.referenciar_nodo(destino, _nodo_actual or '__global__')

    temp = _gt.nuevo_temporal()
    _gt.emitir(Cuadrupla('EXEC_MENU', None, None, temp))

    for i, (texto_label, destino) in enumerate(opciones):
        _gt.emitir(Cuadrupla('IF_EQ', temp, str(i), f'_node_{destino}'))


def p_lista_opciones_multi(p):
    '''lista_opciones : lista_opciones opcion'''
    p[0] = p[1] + [p[2]]

def p_lista_opciones_single(p):
    '''lista_opciones : opcion'''
    p[0] = [p[1]]


def p_opcion(p):
    '''opcion : STRING COLON ID SEMICOLON'''
    parts = p[1]  # list of ('str', text) / ('id', var) from lexer
    # En opciones de choice solo se aceptan strings simples (sin interpolación)
    if len(parts) == 1 and parts[0][0] == 'str':
        texto = parts[0][1]
    else:
        texto = ''.join(part[1] for part in parts)
    label = _gt.registrar_cadena(texto)
    destino = p[3]
    p[0] = (label, destino)


# ===================================================================
# EXPRESIONES
# ===================================================================

# --- Operaciones aritméticas ---
def p_expr_binop_arit(p):
    '''expr : expr PLUS expr
            | expr MINUS expr
            | expr TIMES expr
            | expr DIVIDE expr'''
    global _ps, _ge, _gt
    right = _ps.pop()
    left  = _ps.pop()
    op_map = {'+': 'ADD', '-': 'SUB', '*': 'MUL', '/': 'DIV'}
    op_tac = op_map[p[2]]
    op_sym = p[2]
    linea = p.lineno(2)

    if _ge.error_tipo_propagado(left.tipo, right.tipo):
        _ps.push(ElementoPilaSemantica(tipo='ERROR', lugar='_err'))
        return

    # String + (cualquier cosa) → concatenación
    if op_sym == '+' and (left.tipo == 'string' or right.tipo == 'string'):
        temp = _gt.nuevo_temporal()
        if left.tipo == 'string' and right.tipo == 'string':
            _gt.emitir(Cuadrupla('CONCAT_SS', left.lugar, right.lugar, temp))
        elif left.tipo == 'string' and right.tipo == 'int':
            _gt.emitir(Cuadrupla('CONCAT_SI', left.lugar, right.lugar, temp))
        else:
            _gt.emitir(Cuadrupla('CONCAT_IS', left.lugar, right.lugar, temp))
        _ps.push(ElementoPilaSemantica(tipo='string', lugar=temp))
        return

    # Aritmética entera
    if left.tipo != 'int' or right.tipo != 'int':
        _ge.error('E04', linea, op=op_sym, tipo_izq=left.tipo, tipo_der=right.tipo)
        _ps.push(ElementoPilaSemantica(tipo='ERROR', lugar='_err'))
        return

    # Plegado de constantes
    if left.cte and right.cte:
        try:
            if op_sym == '+': val = left.val + right.val
            elif op_sym == '-': val = left.val - right.val
            elif op_sym == '*': val = left.val * right.val
            elif op_sym == '/':
                if right.val == 0:
                    _ge.error('E08', linea)
                    _ps.push(ElementoPilaSemantica(tipo='ERROR', lugar='_err'))
                    return
                val = int(left.val / right.val)
            _ge.log('L01', linea, expr=f'{left.val} {op_sym} {right.val}', valor=val)
            _ps.push(ElementoPilaSemantica(tipo='int', lugar=str(val), val=val, cte=True))
        except Exception:
            _ps.push(ElementoPilaSemantica(tipo='ERROR', lugar='_err'))
        return

    temp = _gt.nuevo_temporal()
    _gt.emitir(Cuadrupla(op_tac, left.lugar, right.lugar, temp))
    _ps.push(ElementoPilaSemantica(tipo='int', lugar=temp))


# --- Operaciones de comparación ---
def p_expr_binop_comp(p):
    '''expr : expr EQ expr
            | expr NEQ expr
            | expr LT expr
            | expr GT expr
            | expr LEQ expr
            | expr GEQ expr'''
    global _ps, _ge, _gt
    right = _ps.pop()
    left  = _ps.pop()
    op_sym = p[2]
    linea = p.lineno(2)

    if _ge.error_tipo_propagado(left.tipo, right.tipo):
        _ps.push(ElementoPilaSemantica(tipo='ERROR', lugar='_err'))
        return

    temp = _gt.nuevo_temporal()

    if left.tipo == 'string' and right.tipo == 'string':
        if op_sym in ('==', '!='):
            _gt.emitir(Cuadrupla('STREQ', left.lugar, right.lugar, temp))
            if op_sym == '!=':
                # Negar el resultado de STREQ
                temp2 = _gt.nuevo_temporal()
                _gt.emitir(Cuadrupla('EQ', temp, '0', temp2))
                temp = temp2
        else:
            _ge.error('E04', linea, op=op_sym, tipo_izq='string', tipo_der='string')
            _ps.push(ElementoPilaSemantica(tipo='ERROR', lugar='_err'))
            return
    elif left.tipo == 'int' and right.tipo == 'int':
        op_map = {'==': 'EQ', '!=': 'NEQ', '<': 'LT', '>': 'GT', '<=': 'LEQ', '>=': 'GEQ'}
        # Plegado de constantes para comparaciones
        if left.cte and right.cte:
            comp_ops = {
                '==': lambda a, b: a == b, '!=': lambda a, b: a != b,
                '<': lambda a, b: a < b,  '>': lambda a, b: a > b,
                '<=': lambda a, b: a <= b, '>=': lambda a, b: a >= b,
            }
            val = 1 if comp_ops[op_sym](left.val, right.val) else 0
            _ge.log('L01', linea, expr=f'{left.val} {op_sym} {right.val}', valor=val)
            _ps.push(ElementoPilaSemantica(tipo='int', lugar=str(val), val=val, cte=True))
            return
        _gt.emitir(Cuadrupla(op_map[op_sym], left.lugar, right.lugar, temp))
    else:
        _ge.error('E04', linea, op=op_sym, tipo_izq=left.tipo, tipo_der=right.tipo)
        _ps.push(ElementoPilaSemantica(tipo='ERROR', lugar='_err'))
        return

    _ps.push(ElementoPilaSemantica(tipo='int', lugar=temp))


# --- Negación unaria ---
def p_expr_uminus(p):
    '''expr : MINUS expr %prec UMINUS'''
    global _ps, _ge, _gt
    attr = _ps.pop()
    if _ge.error_tipo_propagado(attr.tipo):
        _ps.push(ElementoPilaSemantica(tipo='ERROR', lugar='_err'))
        return
    if attr.tipo != 'int':
        _ge.error('E04', p.lineno(1), op='-unario', tipo_izq=attr.tipo, tipo_der='_')
        _ps.push(ElementoPilaSemantica(tipo='ERROR', lugar='_err'))
        return
    if attr.cte:
        val = -attr.val
        _ps.push(ElementoPilaSemantica(tipo='int', lugar=str(val), val=val, cte=True))
        return
    temp = _gt.nuevo_temporal()
    _gt.emitir(Cuadrupla('NEG', attr.lugar, None, temp))
    _ps.push(ElementoPilaSemantica(tipo='int', lugar=temp))


# --- Agrupación ---
def p_expr_paren(p):
    '''expr : LPAREN expr RPAREN'''
    pass  # El valor ya está en la pila semántica


# --- Literales ---
def p_expr_integer(p):
    '''expr : INTEGER'''
    global _ps
    val = p[1]
    _ps.push(ElementoPilaSemantica(tipo='int', lugar=str(val), val=val, cte=True))


def p_expr_string(p):
    '''expr : STRING'''
    global _ps, _gt, _ts, _ge
    parts = p[1]  # list of ('str', text) / ('id', varname)
    linea = p.lineno(1)
    if len(parts) == 1 and parts[0][0] == 'str':
        label = _gt.registrar_cadena(parts[0][1])
        _ps.push(ElementoPilaSemantica(tipo='string', lugar=label, val=parts[0][1], cte=True))
    else:
        # Interpolación: construir cadena concatenada
        resultado = _procesar_interpolacion(parts, linea)
        _ps.push(resultado)


def p_expr_id(p):
    '''expr : ID'''
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


def p_expr_true(p):
    '''expr : TRUE'''
    global _ps
    _ps.push(ElementoPilaSemantica(tipo='int', lugar='1', val=1, cte=True))


def p_expr_false(p):
    '''expr : FALSE'''
    global _ps
    _ps.push(ElementoPilaSemantica(tipo='int', lugar='0', val=0, cte=True))


# ===================================================================
# ERROR DE SINTAXIS
# ===================================================================
def p_error(p):
    global _ge
    if p:
        _ge.error('S01', p.lineno, token=p.value)
    else:
        _ge.error('S01', 0, token='EOF')


# ===================================================================
# FUNCIONES AUXILIARES
# ===================================================================

def _procesar_interpolacion(parts: list, linea: int) -> ElementoPilaSemantica:
    """Procesa una cadena con interpolación {id} y emite TAC de concatenación."""
    global _ts, _ge, _gt

    resultado = None
    for kind, value in parts:
        if kind == 'str':
            label = _gt.registrar_cadena(value)
            parte = ElementoPilaSemantica(tipo='string', lugar=label, cte=True)
        else:  # 'id'
            sym = _ts.buscar(value)
            if sym is None:
                _ge.error('E01', linea, nombre=value)
                return ElementoPilaSemantica(tipo='ERROR', lugar='_err')
            _ts.marcar_usada(value)
            parte = ElementoPilaSemantica(tipo=sym.tipo, lugar=value)

        if resultado is None:
            resultado = parte
        else:
            temp = _gt.nuevo_temporal()
            if resultado.tipo == 'string' and parte.tipo == 'string':
                _gt.emitir(Cuadrupla('CONCAT_SS', resultado.lugar, parte.lugar, temp))
            elif resultado.tipo == 'string' and parte.tipo == 'int':
                _gt.emitir(Cuadrupla('CONCAT_SI', resultado.lugar, parte.lugar, temp))
            elif resultado.tipo == 'int' and parte.tipo == 'string':
                _gt.emitir(Cuadrupla('CONCAT_IS', resultado.lugar, parte.lugar, temp))
            else:
                _gt.emitir(Cuadrupla('CONCAT_SI', '_str_empty', resultado.lugar, temp))
            resultado = ElementoPilaSemantica(tipo='string', lugar=temp)

    return resultado or ElementoPilaSemantica(tipo='string', lugar=_gt.registrar_cadena(''), cte=True)


def _verificaciones_post_parse():
    """Chequeos semánticos que requieren visión global del programa."""
    global _ts, _ge

    # E07: falta nodo inicio
    if not _ts.existe_nodo_inicio():
        _ge.error('E07', 0)

    # E05: nodos referenciados pero no definidos
    for nodo in _ts.nodos_no_definidos():
        _ge.error('E05', 0, nombre=nodo.nombre)

    # E11: nodos sin salida
    for nodo in _ts.nodos_sin_salida():
        _ge.error('E11', nodo.linea_decl, nombre=nodo.nombre)

    # E12: nodos inalcanzables
    for nodo in _ts.nodos_inalcanzables():
        _ge.error('E12', nodo.linea_decl, nombre=nodo.nombre)

    # W01: variables no usadas
    for sym in _ts.variables_no_usadas():
        _ge.warning('W01', sym.linea_decl, nombre=sym.nombre, linea_decl=sym.linea_decl)


# ===================================================================
# INTERFAZ PÚBLICA
# ===================================================================

def parsear(source_code: str) -> ResultadoCompilacion:
    """Punto de entrada del frontend: lexing + parsing + semántica + TAC."""
    global _ts, _ps, _ge, _gt, _fuente, _nodo_actual

    _ts = TablaSimbolos()
    _ps = PilaSemantica()
    _ge = GestorErrores()
    _gt = GeneradorTAC()
    _fuente = source_code
    _nodo_actual = None

    # Registrar cadena vacía
    _gt.registrar_cadena('')

    lexer_inst = crear_lexer()
    parser_inst = yacc.yacc(debug=False, write_tables=False)
    parser_inst.parse(source_code, lexer=lexer_inst)

    # Verificaciones post-parse
    _verificaciones_post_parse()

    return ResultadoCompilacion(
        exito=not _ge.hay_errores(),
        codigo_tac=_gt.obtener_codigo(),
        tabla_simbolos=_ts,
        tabla_cadenas=_gt.obtener_cadenas(),
        gestor_errores=_ge,
        errores=_ge.obtener_errores(),
        advertencias=_ge.obtener_advertencias(),
    )
