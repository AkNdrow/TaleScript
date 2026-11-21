"""
TaleScript Lexer — Analizador Léxico con ply.lex
=================================================
Tokens, posiciones (línea/columna), comentarios //, cadenas con escapes
e interpolación {id}.
"""
import ply.lex as lex

# ---------------------------------------------------------------------------
# Palabras reservadas
# ---------------------------------------------------------------------------
reserved = {
    'node':   'NODE',
    'choice': 'CHOICE',
    'say':    'SAY',
    'set':    'SET',
    'if':     'IF',
    'else':   'ELSE',
    'goto':   'GOTO',
    'exit':   'EXIT',
    'var':    'VAR',
    'int':    'INT_TYPE',
    'string': 'STRING_TYPE',
    'true':   'TRUE',
    'false':  'FALSE',
}

# ---------------------------------------------------------------------------
# Lista de tokens
# ---------------------------------------------------------------------------
tokens = [
    'ID', 'INTEGER', 'STRING',
    # Operadores aritméticos
    'PLUS', 'MINUS', 'TIMES', 'DIVIDE',
    # Operadores de comparación
    'EQ', 'NEQ', 'LT', 'GT', 'LEQ', 'GEQ',
    # Asignación
    'ASSIGN',
    # Delimitadores
    'LBRACE', 'RBRACE', 'LPAREN', 'RPAREN',
    'SEMICOLON', 'COLON',
] + list(reserved.values())

# ---------------------------------------------------------------------------
# Tokens simples (un carácter)
# ---------------------------------------------------------------------------
t_PLUS      = r'\+'
t_MINUS     = r'-'
t_TIMES     = r'\*'
t_DIVIDE    = r'/'
t_LBRACE    = r'\{'
t_RBRACE    = r'\}'
t_LPAREN    = r'\('
t_RPAREN    = r'\)'
t_SEMICOLON = r';'
t_COLON     = r':'

# ---------------------------------------------------------------------------
# Tokens de dos caracteres (antes que los de uno)
# ---------------------------------------------------------------------------
t_EQ  = r'=='
t_NEQ = r'!='
t_LEQ = r'<='
t_GEQ = r'>='
t_LT  = r'<'
t_GT  = r'>'
t_ASSIGN = r'='

# ---------------------------------------------------------------------------
# Ignorar espacios y tabulaciones (NO saltos de línea)
# ---------------------------------------------------------------------------
t_ignore = ' \t\r'

# ---------------------------------------------------------------------------
# Comentarios  // ... hasta fin de línea
# ---------------------------------------------------------------------------
def t_COMMENT(t):
    r'//[^\n]*'
    pass  # Se descarta

# ---------------------------------------------------------------------------
# Saltos de línea — actualiza el contador de líneas
# ---------------------------------------------------------------------------
def t_newline(t):
    r'\n+'
    t.lexer.lineno += len(t.value)

# ---------------------------------------------------------------------------
# Literales enteros
# ---------------------------------------------------------------------------
def t_INTEGER(t):
    r'\d+'
    t.value = int(t.value)
    return t

# ---------------------------------------------------------------------------
# Cadenas con escapes y marcado de interpolación
# Valor del token: lista de tuplas  [('str', texto), ('id', nombre), ...]
# ---------------------------------------------------------------------------
def t_STRING(t):
    r'"([^"\\]|\\.)*"'
    raw = t.value[1:-1]  # quitar comillas externas
    parts = []
    current = ''
    i = 0
    escape_map = {'n': '\n', 't': '\t', '\\': '\\', '"': '"', '{': '{', '}': '}'}
    while i < len(raw):
        ch = raw[i]
        if ch == '\\' and i + 1 < len(raw):
            current += escape_map.get(raw[i + 1], '\\' + raw[i + 1])
            i += 2
        elif ch == '{':
            # Inicio de interpolación
            if current:
                parts.append(('str', current))
                current = ''
            j = raw.find('}', i + 1)
            if j == -1:
                # Llave sin cerrar — incluir literal
                current += '{'
                i += 1
            else:
                var_name = raw[i + 1:j].strip()
                if var_name:
                    parts.append(('id', var_name))
                i = j + 1
        else:
            current += ch
            i += 1
    if current:
        parts.append(('str', current))
    if not parts:
        parts = [('str', '')]
    t.value = parts
    return t

# ---------------------------------------------------------------------------
# Identificadores y palabras reservadas
# ---------------------------------------------------------------------------
def t_ID(t):
    r'[a-zA-Z_][a-zA-Z_0-9]*'
    t.type = reserved.get(t.value, 'ID')
    return t

# ---------------------------------------------------------------------------
# Errores léxicos
# ---------------------------------------------------------------------------
def t_error(t):
    col = _find_column(t.lexer.lexdata, t)
    print(f"[LEX] Carácter ilegal '{t.value[0]}' en línea {t.lineno}, columna {col}")
    t.lexer.skip(1)

# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def _find_column(input_text, token):
    """Calcula la columna (1-based) de un token."""
    line_start = input_text.rfind('\n', 0, token.lexpos) + 1
    return (token.lexpos - line_start) + 1


def find_column(input_text, token):
    """Interfaz pública para cálculo de columna."""
    return _find_column(input_text, token)


def crear_lexer():
    """Construye y devuelve una instancia del lexer PLY."""
    return lex.lex()
