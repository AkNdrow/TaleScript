"""
Generador de Código x86-64 — NASM win64
========================================
Traduce cuádruplas optimizadas a ensamblador NASM para Windows x64.
Respeta Microsoft x64 ABI:
  - Argumentos en rcx, rdx, r8, r9
  - 32 bytes de shadow space antes de cada CALL
  - Pila alineada a 16 bytes
"""
from __future__ import annotations
from talescriptc.intermedio.cuadrupla import Cuadrupla
from talescriptc.semantica.tabla_simbolos import TablaSimbolos


class GeneradorX86_64:
    """Genera código NASM x86-64 para Windows a partir de cuádruplas."""

    def __init__(self):
        self._lines: list[str] = []
        self._data: list[str] = []
        self._cadenas: dict[str, str] = {}
        self._offsets: dict[str, int] = {}   # nombre → offset desde rbp
        self._frame_size: int = 0
        self._offset_actual: int = 0

    def generar(self, codigo: list[Cuadrupla], tabla_cadenas: dict[str, str],
                tabla_simbolos: TablaSimbolos) -> str:
        """Genera el código NASM completo."""
        self._cadenas = tabla_cadenas
        self._lines = []
        self._data = []
        self._offsets = {}
        self._offset_actual = 0

        # Asignar slots de pila para variables y temporales
        self._asignar_variables(tabla_simbolos)
        self._asignar_temporales(codigo)
        self._calcular_frame()

        # Generar secciones
        self._generar_cabecera()
        self._generar_data()
        self._generar_text(codigo)

        return '\n'.join(self._lines)

    # ------------------------------------------------------------------
    # Asignación de espacio en pila
    # ------------------------------------------------------------------
    def _asignar_variables(self, ts: TablaSimbolos):
        """Asigna un slot de pila a cada variable."""
        for ambito in [ts.ambito_global]:
            for nombre in ambito:
                self._offset_actual += 8
                self._offsets[nombre] = self._offset_actual

    def _asignar_temporales(self, codigo: list[Cuadrupla]):
        """Asigna slots a temporales (tk) encontrados en el código."""
        for cuad in codigo:
            for campo in (cuad.arg1, cuad.arg2, cuad.res):
                if campo and campo.startswith('t') and campo[1:].isdigit():
                    if campo not in self._offsets:
                        self._offset_actual += 8
                        self._offsets[campo] = self._offset_actual

    def _calcular_frame(self):
        """Calcula el tamaño del marco de pila (múltiplo de 16).
        Incluye 32 bytes de shadow space para las llamadas."""
        total = self._offset_actual + 32  # vars + temps + shadow space
        # Alinear a múltiplo de 16
        self._frame_size = (total + 15) & ~15

    # ------------------------------------------------------------------
    # Generación de secciones
    # ------------------------------------------------------------------
    def _generar_cabecera(self):
        self._emit('; ═══════════════════════════════════════════════════')
        self._emit('; TaleScript — Código generado por talescriptc')
        self._emit('; Formato: NASM win64 (Microsoft x64 ABI)')
        self._emit('; ═══════════════════════════════════════════════════')
        self._emit('default rel')
        self._emit('')

    def _generar_data(self):
        """Genera la sección .data con cadenas literales."""
        self._emit('section .data')
        for label, valor in self._cadenas.items():
            # Escapar caracteres especiales para NASM
            encoded = self._nasm_string(valor)
            self._emit(f'    {label} db {encoded}, 0')
        self._emit('')

    def _generar_text(self, codigo: list[Cuadrupla]):
        """Genera la sección .text con el código ejecutable."""
        self._emit('section .text')
        # Declarar funciones externas del runtime
        for func in ('_ts_say', '_ts_concat_ss', '_ts_concat_si', '_ts_concat_is',
                      '_ts_streq', '_ts_add_opt', '_ts_exec_menu', '_ts_exit'):
            self._emit(f'    extern {func}')
        self._emit('    global main')
        self._emit('')

        # Prólogo de main
        self._emit('main:')
        self._emit('    push rbp')
        self._emit('    mov rbp, rsp')
        self._emit(f'    sub rsp, {self._frame_size}')
        self._emit('')

        # Traducir cada cuádrupla garantizando que las inicializaciones globales
        # se ejecuten antes de saltar a _node_inicio
        salto_inicio_emitido = False
        primer_nodo_es_inicio = False

        for cuad in codigo:
            if cuad.es_etiqueta() and cuad.res and cuad.res.startswith('_node_'):
                if not salto_inicio_emitido:
                    salto_inicio_emitido = True
                    if cuad.res != '_node_inicio':
                        self._emit('    ; Saltar al nodo de inicio')
                        self._emit('    jmp _node_inicio')
                        self._emit('')
            self._traducir(cuad)

        # Epílogo (en caso de que se llegue aquí sin EXIT)
        self._emit('')
        self._emit('._epilogo:')
        self._emit(f'    add rsp, {self._frame_size}')
        self._emit('    pop rbp')
        self._emit('    xor eax, eax')
        self._emit('    ret')

    # ------------------------------------------------------------------
    # Traducción de cuádruplas individuales
    # ------------------------------------------------------------------
    def _traducir(self, cuad: Cuadrupla):
        op = cuad.op
        if op == 'LABEL':
            self._emit(f'{cuad.res}:')
        elif op == 'ASSIGN':
            self._cargar('rax', cuad.arg1)
            self._guardar('rax', cuad.res)
        elif op in ('ADD', 'SUB'):
            self._cargar('rax', cuad.arg1)
            self._cargar('rbx', cuad.arg2)
            inst = 'add' if op == 'ADD' else 'sub'
            self._emit(f'    {inst} rax, rbx')
            self._guardar('rax', cuad.res)
        elif op == 'MUL':
            self._cargar('rax', cuad.arg1)
            self._cargar('rbx', cuad.arg2)
            self._emit('    imul rax, rbx')
            self._guardar('rax', cuad.res)
        elif op == 'DIV':
            self._cargar('rax', cuad.arg1)
            self._emit('    cqo')
            self._cargar('rbx', cuad.arg2)
            self._emit('    idiv rbx')
            self._guardar('rax', cuad.res)
        elif op == 'NEG':
            self._cargar('rax', cuad.arg1)
            self._emit('    neg rax')
            self._guardar('rax', cuad.res)
        elif op in ('EQ', 'NEQ', 'LT', 'GT', 'LEQ', 'GEQ'):
            self._cargar('rax', cuad.arg1)
            self._cargar('rbx', cuad.arg2)
            self._emit('    cmp rax, rbx')
            setcc = {'EQ': 'sete', 'NEQ': 'setne', 'LT': 'setl',
                     'GT': 'setg', 'LEQ': 'setle', 'GEQ': 'setge'}[op]
            self._emit(f'    {setcc} al')
            self._emit('    movzx rax, al')
            self._guardar('rax', cuad.res)
        elif op == 'STREQ':
            self._cargar('rcx', cuad.arg1)
            self._cargar('rdx', cuad.arg2)
            self._emit_call('_ts_streq')
            self._guardar('rax', cuad.res)
        elif op == 'CONCAT_SS':
            self._cargar('rcx', cuad.arg1)
            self._cargar('rdx', cuad.arg2)
            self._emit_call('_ts_concat_ss')
            self._guardar('rax', cuad.res)
        elif op == 'CONCAT_SI':
            self._cargar('rcx', cuad.arg1)
            self._cargar('rdx', cuad.arg2)
            self._emit_call('_ts_concat_si')
            self._guardar('rax', cuad.res)
        elif op == 'CONCAT_IS':
            self._cargar('rcx', cuad.arg1)
            self._cargar('rdx', cuad.arg2)
            self._emit_call('_ts_concat_is')
            self._guardar('rax', cuad.res)
        elif op == 'SAY':
            self._cargar('rcx', cuad.arg1)
            self._emit_call('_ts_say')
        elif op == 'ADD_OPT':
            self._cargar('rcx', cuad.arg1)
            self._emit_call('_ts_add_opt')
        elif op == 'EXEC_MENU':
            self._emit_call('_ts_exec_menu')
            self._guardar('rax', cuad.res)
        elif op == 'GOTO':
            self._emit(f'    jmp {cuad.res}')
        elif op == 'IF_FALSE':
            self._cargar('rax', cuad.arg1)
            self._emit('    test rax, rax')
            self._emit(f'    jz {cuad.res}')
        elif op == 'IF_EQ':
            self._cargar('rax', cuad.arg1)
            self._cargar('rbx', cuad.arg2)
            self._emit('    cmp rax, rbx')
            self._emit(f'    je {cuad.res}')
        elif op == 'EXIT':
            self._emit('    xor ecx, ecx')
            self._emit_call('_ts_exit')
        else:
            self._emit(f'    ; *** OP NO IMPLEMENTADA: {cuad} ***')

    # ------------------------------------------------------------------
    # Helpers de bajo nivel
    # ------------------------------------------------------------------
    def _cargar(self, reg: str, operando: str):
        """Genera instrucción para cargar un operando en un registro."""
        if operando is None:
            return
        if self._es_entero(operando):
            self._emit(f'    mov {reg}, {operando}')
        elif operando.startswith('_str_'):
            self._emit(f'    lea {reg}, [{operando}]')
        elif operando.startswith('_node_'):
            self._emit(f'    lea {reg}, [{operando}]')
        elif operando in self._offsets:
            off = self._offsets[operando]
            self._emit(f'    mov {reg}, [rbp - {off}]')
        else:
            # Puede ser una constante o referencia desconocida
            self._emit(f'    mov {reg}, {operando}')

    def _guardar(self, reg: str, destino: str):
        """Genera instrucción para guardar un registro en un destino."""
        if destino is None:
            return
        if destino in self._offsets:
            off = self._offsets[destino]
            self._emit(f'    mov [rbp - {off}], {reg}')
        else:
            # Variable no encontrada — crear slot dinámicamente
            self._offset_actual += 8
            self._offsets[destino] = self._offset_actual
            off = self._offsets[destino]
            self._emit(f'    mov [rbp - {off}], {reg}')

    def _emit_call(self, func: str):
        """Emite una llamada a función respetando MS x64 ABI.
        Los argumentos ya deben estar en rcx, rdx, r8, r9.
        El shadow space de 32 bytes ya está reservado en el frame."""
        self._emit(f'    call {func}')

    def _emit(self, line: str):
        self._lines.append(line)

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------
    @staticmethod
    def _es_entero(s: str) -> bool:
        try:
            int(s)
            return True
        except (ValueError, TypeError):
            return False

    @staticmethod
    def _nasm_string(s: str) -> str:
        """Convierte un string Python a formato NASM db.
        Maneja caracteres especiales con secuencias de bytes."""
        if not s:
            return '""'
        parts = []
        current = ''
        for ch in s:
            code = ord(ch)
            if 32 <= code < 127 and ch not in ('"', '\\'):
                current += ch
            else:
                if current:
                    parts.append(f'"{current}"')
                    current = ''
                parts.append(str(code))
        if current:
            parts.append(f'"{current}"')
        return ', '.join(parts) if parts else '""'
