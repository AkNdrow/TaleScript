"""
TaleScript Lexer — Analizador Léxico con ply.lex
=================================================
Tokens, posiciones (línea/columna), comentarios //, cadenas con escapes
e interpolación {id}, y reporte de errores léxicos L01 y L02.
"""
from __future__ import annotations
import re
import ply.lex as lex

# ---------------------------------------------------------------------------
# Palabras reservadas (22 palabras en minúscula — Sección 7.1 del Manual)
# ---------------------------------------------------------------------------
reserved = {
    'node':   'NODE',
    'global': 'GLOBAL',
    'local':  'LOCAL',
    'const':  'CONST',
    'int':    'INT',
    'string': 'STRING',
    'bool':   'BOOL',
    'say':    'SAY',
    'goto':   'GOTO',
    'call':   'CALL',
    'return': 'RETURN',
    'if':     'IF',
    'else':   'ELSE',
    'while':  'WHILE',
    'do':     'DO',
    'choice': 'CHOICE',
    'end':    'END',
    'and':    'AND',
    'or':     'OR',
    'not':    'NOT',
    'true':   'TRUE',
    'false':  'FALSE',
}

# ---------------------------------------------------------------------------
# Lista de tokens
# ---------------------------------------------------------------------------
tokens = [
    'ID', 'NUM', 'STR',
    # Operadores aritméticos
    'PLUS', 'MINUS', 'STAR', 'SLASH', 'PERCENT',
    # Operadores relacionales
    'LT', 'LE', 'GT', 'GE', 'EQ', 'NE',
    # Asignación
    'ASSIGN',
    # Delimitadores
    'LPAREN', 'RPAREN', 'LBRACE', 'RBRACE', 'SEMI',
] + list(reserved.values())

# ---------------------------------------------------------------------------
# Tokens de dos caracteres (se evalúan antes que los de un carácter)
# ---------------------------------------------------------------------------
t_LE = r'<='
t_GE = r'>='
t_EQ = r'=='
t_NE = r'!='

# ---------------------------------------------------------------------------
# Tokens simples (un carácter)
# ---------------------------------------------------------------------------
t_PLUS    = r'\+'
t_MINUS   = r'-'
t_STAR    = r'\*'
t_SLASH   = r'/'
t_PERCENT = r'%'
t_LT      = r'<'
t_GT      = r'>'
t_ASSIGN  = r'='
t_LPAREN  = r'\('
t_RPAREN  = r'\)'
t_LBRACE  = r'\{'
t_RBRACE  = r'\}'
t_SEMI    = r';'

# ---------------------------------------------------------------------------
# Ignorar espacios y tabulaciones (NO saltos de línea)
# ---------------------------------------------------------------------------
t_ignore = ' \t\r'

_ID_RE = re.compile(r'^[a-zA-Z_][a-zA-Z_0-9]*$')


def _reportar_error_lexico(lexer, codigo: str, linea: int, columna: int, detalle: str):
    """Envía el error léxico a GestorErrores si está adjunto al lexer."""
    ge = getattr(lexer, 'gestor_errores', None)
    if ge is not None and hasattr(ge, 'error'):
        try:
            ge.error(codigo, linea, columna=columna, mensaje=detalle, token=detalle, detalle=detalle)
            return
        except (TypeError, KeyError):
            pass
    print(f"[LEX {codigo}] Línea {linea}, columna {columna}: {detalle}")


# ---------------------------------------------------------------------------
# Comentarios // ... hasta fin de línea
# ---------------------------------------------------------------------------
def t_COMMENT(t):
    r'//[^\n]*'
    pass


# ---------------------------------------------------------------------------
# Saltos de línea — actualiza el contador de líneas
# ---------------------------------------------------------------------------
def t_newline(t):
    r'\n+'
    t.lexer.lineno += len(t.value)


# ---------------------------------------------------------------------------
# Literales enteros sin signo (NUM)
# ---------------------------------------------------------------------------
def t_NUM(t):
    r'\d+'
    t.value = int(t.value)
    return t


# ---------------------------------------------------------------------------
# Cadenas con escapes (\", \\, \n, \{) e interpolación {id}
# Valor del token: lista de partes, ej. ["Tu karma es ", ("VAR", "karma")]
# ---------------------------------------------------------------------------
def t_STR(t):
    r'"([^"\\\n]|\\.)*"'
    col_inicio = _find_column(t.lexer.lexdata, t)
    raw = t.value[1:-1]
    parts = []
    current = ''
    i = 0
    escape_map = {'n': '\n', '\\': '\\', '"': '"', '{': '{', '}': '}', 't': '\t'}

    while i < len(raw):
        ch = raw[i]
        if ch == '\\':
            if i + 1 < len(raw):
                esc = raw[i + 1]
                current += escape_map.get(esc, '\\' + esc)
                i += 2
            else:
                _reportar_error_lexico(
                    t.lexer, 'L02', t.lineno, col_inicio + i + 1,
                    'Secuencia de escape incompleta al final de la cadena.'
                )
                i += 1
        elif ch == '{':
            if current:
                parts.append(current)
                current = ''
            j = raw.find('}', i + 1)
            if j == -1:
                _reportar_error_lexico(
                    t.lexer, 'L02', t.lineno, col_inicio + i + 1,
                    "Interpolación '{' sin llave de cierre '}' en la cadena."
                )
                current += raw[i:]
                break
            var_name = raw[i + 1:j].strip()
            if not var_name or not _ID_RE.match(var_name):
                _reportar_error_lexico(
                    t.lexer, 'L02', t.lineno, col_inicio + i + 1,
                    f"Identificador inválido en interpolación: '{{{raw[i + 1:j]}}}'."
                )
            else:
                parts.append(('VAR', var_name))
            i = j + 1
        else:
            current += ch
            i += 1

    if current or not parts:
        parts.append(current)

    t.value = parts
    return t


# ---------------------------------------------------------------------------
# Cadena sin cerrar antes de salto de línea o EOF (Error L02)
# ---------------------------------------------------------------------------
def t_STR_UNCLOSED(t):
    r'"([^"\\\n]|\\.)*'
    col = _find_column(t.lexer.lexdata, t)
    _reportar_error_lexico(
        t.lexer, 'L02', t.lineno, col,
        'Cadena de texto sin cerrar antes del fin de línea o archivo.'
    )


# ---------------------------------------------------------------------------
# Identificadores y palabras reservadas
# ---------------------------------------------------------------------------
def t_ID(t):
    r'[a-zA-Z_][a-zA-Z_0-9]*'
    t.type = reserved.get(t.value, 'ID')
    return t


# ---------------------------------------------------------------------------
# Carácter no reconocido (Error L01)
# ---------------------------------------------------------------------------
def t_error(t):
    col = _find_column(t.lexer.lexdata, t)
    _reportar_error_lexico(
        t.lexer, 'L01', t.lineno, col,
        f"Carácter no reconocido '{t.value[0]}'."
    )
    t.lexer.skip(1)


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def _find_column(input_text: str, token) -> int:
    """Calcula la columna (1-based) donde empieza un token."""
    line_start = input_text.rfind('\n', 0, token.lexpos) + 1
    return (token.lexpos - line_start) + 1


def find_column(input_text: str, token) -> int:
    """Interfaz pública para el cálculo de columna."""
    return _find_column(input_text, token)


def crear_lexer(gestor_errores=None):
    """Construye y devuelve una instancia del lexer PLY."""
    lexer = lex.lex()
    lexer.gestor_errores = gestor_errores
    return lexer