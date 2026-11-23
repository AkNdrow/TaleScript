"""
Generador de Código x86-64 — NASM win64 (Microsoft x64 ABI)
===========================================================
Traduce cuádruplas (optimizadas o sin optimizar) a ensamblador NASM
para Windows x64, enlazable con runtime/runtime.c.
"""
from __future__ import annotations

from typing import Optional
from talescriptc.intermedio.cuadrupla import Cuadrupla
from talescriptc.semantica.tabla_simbolos import TablaSimbolos


class GeneradorX86_64:
    """Genera código NASM x86-64 para Windows a partir de cuádruplas."""

    def __init__(self):
        self._lines: list[str] = []
        self._cadenas: dict[str, str] = {}        # etiqueta -> texto literal
        self._texto_a_label: dict[str, str] = {}   # texto literal -> etiqueta
        self._str_counter: int = 0

        self._globales: dict[str, str] = {}        # nombre -> tipo ('int'|'string'|'bool')
        self._nodos_conocidos: set[str] = set()
        self._nodo_inicio: str = 'inicio'

        # Estado del marco de pila del nodo actual
        self._nodo_actual: Optional[str] = None
        self._offsets: dict[str, int] = {}
        self._tipos_locales: dict[str, str] = {}
        self._frame_size: int = 32
        self._offset_actual: int = 0

        # Cola temporal de opciones parachoice -> menu
        self._opciones_menu: list[str] = []

    def generar(self, codigo: list[Cuadrupla], tabla_cadenas: dict[str, str],
                tabla_simbolos: TablaSimbolos) -> str:
        """Genera el código ensamblador NASM completo."""
        self._lines = []
        self._cadenas = dict(tabla_cadenas) if tabla_cadenas else {}
        self._texto_a_label = {v: k for k, v in self._cadenas.items()}
        self._str_counter = len(self._cadenas)

        self._globales = {}
        self._nodos_conocidos = set()
        self._opciones_menu = []

        # 1. Registrar variables globales y nodos desde TablaSimbolos
        for nombre, entrada in tabla_simbolos.ambito_global.items():
            self._globales[nombre] = entrada.tipo

        if hasattr(tabla_simbolos, 'tabla_nodes'):
            for nombre, nodo_info in tabla_simbolos.tabla_nodes.items():
                self._nodos_conocidos.add(nombre)
                if getattr(nodo_info, 'orden', -1) == 0:
                    self._nodo_inicio = nombre

        # También detectar nodos directamente de las cuádruplas (node, -, -, id)
        primer_nodo = None
        for cuad in codigo:
            if cuad.op == 'node':
                self._nodos_conocidos.add(cuad.res)
                if primer_nodo is None:
                    primer_nodo = cuad.res
        if primer_nodo and self._nodo_inicio not in self._nodos_conocidos:
            self._nodo_inicio = primer_nodo

        # 2. Pre-recolectar todos los literales de cadena usados en las cuádruplas
        self._recolectar_cadenas(codigo)

        # 3. Separar instrucciones globales (antes del primer node) de las de cada node
        inst_globales: list[Cuadrupla] = []
        bloques_nodos: list[tuple[str, list[Cuadrupla]]] = []
        nodo_corriente: Optional[str] = None
        inst_corriente: list[Cuadrupla] = []

        for cuad in codigo:
            if cuad.op == 'node':
                if nodo_corriente is not None:
                    bloques_nodos.append((nodo_corriente, inst_corriente))
                nodo_corriente = cuad.res
                inst_corriente = []
            else:
                if nodo_corriente is None:
                    inst_globales.append(cuad)
                else:
                    inst_corriente.append(cuad)

        if nodo_corriente is not None:
            bloques_nodos.append((nodo_corriente, inst_corriente))

        # 4. Emitir secciones NASM
        self._generar_cabecera()
        self._generar_data()
        self._generar_bss()
        self._generar_text(inst_globales, bloques_nodos, tabla_simbolos)

        return '\n'.join(self._lines)

    # ------------------------------------------------------------------
    # Recolección de cadenas literales
    # ------------------------------------------------------------------
    def _registrar_cadena(self, texto: str) -> str:
        """Devuelve la etiqueta .data de una cadena literal, creándola si no existe."""
        if texto in self._texto_a_label:
            return self._texto_a_label[texto]
        label = f'_str_{self._str_counter}'
        self._str_counter += 1
        self._cadenas[label] = texto
        self._texto_a_label[texto] = label
        return label

    @staticmethod
    def _es_literal_cadena(op: Optional[str]) -> bool:
        return bool(op and len(op) >= 2 and op.startswith('"') and op.endswith('"'))

    @staticmethod
    def _extraer_cadena(op: str) -> str:
        raw = op[1:-1]
        return (raw.replace('\\n', '\n')
                   .replace('\\t', '\t')
                   .replace('\\"', '"')
                   .replace('\\\\', '\\'))

    def _recolectar_cadenas(self, codigo: list[Cuadrupla]):
        for cuad in codigo:
            for campo in (cuad.arg1, cuad.arg2):
                if self._es_literal_cadena(campo):
                    self._registrar_cadena(self._extraer_cadena(campo))

    # ------------------------------------------------------------------
    # Secciones NASM (.data, .bss, .text)
    # ------------------------------------------------------------------
    def _generar_cabecera(self):
        self._emit('; =====================================================================')
        self._emit('; TaleScript — Código ensamblador generado por talescriptc')
        self._emit('; Objetivo: NASM x86-64 Windows (Microsoft x64 ABI)')
        self._emit('; =====================================================================')
        self._emit('default rel')
        self._emit('')

    def _generar_data(self):
        self._emit('section .data')
        self._emit('    _str_vacio db 0')
        for label, valor in self._cadenas.items():
            encoded = self._nasm_string(valor)
            self._emit(f'    {label} db {encoded}, 0')
        self._emit('')

    def _generar_bss(self):
        self._emit('section .bss')
        for nombre in self._globales:
            self._emit(f'    _glob_{nombre} resq 1')
        self._emit('')

    def _generar_text(self, inst_globales: list[Cuadrupla],
                      bloques_nodos: list[tuple[str, list[Cuadrupla]]],
                      tabla_simbolos: TablaSimbolos):
        self._emit('section .text')
        for func in ('_ts_say', '_ts_int_to_str', '_ts_concat_ss', '_ts_concat_si',
                     '_ts_concat_is', '_ts_streq', '_ts_add_opt', '_ts_exec_menu',
                     '_ts_div_zero', '_ts_exit'):
            self._emit(f'    extern {func}')
        self._emit('    global main')
        self._emit('')

        # ---- Punto de entrada main ----
        self._emit('main:')
        self._emit('    push rbp')
        self._emit('    mov rbp, rsp')
        self._emit('    sub rsp, 32')  # Shadow space para MS x64 ABI

        # Inicializar variables globales con valor_inicial de TablaSimbolos
        for nombre, entrada in tabla_simbolos.ambito_global.items():
            val = getattr(entrada, 'valor_inicial', None)
            if val is not None:
                if isinstance(val, bool):
                    self._emit(f'    mov qword [rel _glob_{nombre}], {1 if val else 0}')
                elif isinstance(val, int):
                    self._emit(f'    mov qword [rel _glob_{nombre}], {val}')
                elif isinstance(val, str):
                    lbl = self._registrar_cadena(val)
                    self._emit(f'    lea rax, [rel {lbl}]')
                    self._emit(f'    mov [rel _glob_{nombre}], rax')
            elif entrada.tipo == 'string':
                self._emit('    lea rax, [rel _str_vacio]')
                self._emit(f'    mov [rel _glob_{nombre}], rax')

        # Ejecutar cualquier cuádrupla global previa al primer node
        for cuad in inst_globales:
            self._traducir(cuad)

        # Invocar al nodo inicial
        self._emit(f'    call _node_{self._nodo_inicio}')
        self._emit('    add rsp, 32')
        self._emit('    pop rbp')
        self._emit('    xor eax, eax')
        self._emit('    ret')
        self._emit('')

        # ---- Subrutinas de cada node ----
        for nombre_nodo, instrucciones in bloques_nodos:
            self._generar_nodo(nombre_nodo, instrucciones, tabla_simbolos)

    # ------------------------------------------------------------------
    # Generación por cada node (marco de pila independiente)
    # ------------------------------------------------------------------
    def _generar_nodo(self, nombre_nodo: str, instrucciones: list[Cuadrupla],
                      tabla_simbolos: TablaSimbolos):
        self._nodo_actual = nombre_nodo
        self._offsets = {}
        self._tipos_locales = {}
        self._offset_actual = 0
        self._opciones_menu = []

        # Obtener variables locales del nodo desde tabla_nodes
        nodo_info = None
        if hasattr(tabla_simbolos, 'tabla_nodes'):
            nodo_info = tabla_simbolos.tabla_nodes.get(nombre_nodo)

        if nodo_info and hasattr(nodo_info, 'tabla_local'):
            for var_name, entrada in nodo_info.tabla_local.items():
                self._offset_actual += 8
                self._offsets[var_name] = self._offset_actual
                self._tipos_locales[var_name] = entrada.tipo

        # Pre-inferencia de tipos para temporales del nodo
        self._tipos_temporales = {}
        for cuad in instrucciones:
            if cuad.op == 'concat':
                if cuad.res and cuad.res != '-':
                    self._tipos_temporales[cuad.res] = 'string'
            elif cuad.op in ('+', '-', '*', '/', '%', 'neg'):
                if cuad.res and cuad.res != '-':
                    self._tipos_temporales[cuad.res] = 'int'
            elif cuad.op in ('<', '<=', '>', '>=', '==', '!=', 'and', 'or', 'not'):
                if cuad.res and cuad.res != '-':
                    self._tipos_temporales[cuad.res] = 'bool'
            elif cuad.op == '=':
                if cuad.res and cuad.res != '-':
                    t_src = self._inferir_tipo(cuad.arg1)
                    self._tipos_temporales[cuad.res] = t_src
            elif cuad.op.startswith('cast_'):
                if cuad.res and cuad.res != '-':
                    self._tipos_temporales[cuad.res] = cuad.op[5:]

        # Asignar slots en pila para temporales tk y cualquier local detectada en TAC
        for cuad in instrucciones:
            for campo in (cuad.arg1, cuad.arg2, cuad.res):
                if not campo or campo == '-':
                    continue
                if self._es_temporal(campo) or (
                    campo.isidentifier()
                    and campo not in self._globales
                    and campo not in self._nodos_conocidos
                    and campo not in ('true', 'false')
                    and not self._es_etiqueta(campo)
                ):
                    if campo not in self._offsets:
                        self._offset_actual += 8
                        self._offsets[campo] = self._offset_actual

        # Calcular tamaño de marco múltiplo de 16 + 32 bytes de shadow space
        total = self._offset_actual + 32
        self._frame_size = (total + 15) & ~15

        if nodo_info is not None:
            nodo_info.tamano_marco = self._frame_size

        # Prólogo del nodo
        self._emit(f'_node_{nombre_nodo}:')
        self._emit('    push rbp')
        self._emit('    mov rbp, rsp')
        self._emit(f'    sub rsp, {self._frame_size}')

        # Valores por defecto para variables locales (0, false, o "")
        for var_name, off in self._offsets.items():
            if not self._es_temporal(var_name):
                if self._tipos_locales.get(var_name) == 'string':
                    self._emit('    lea rax, [rel _str_vacio]')
                    self._emit(f'    mov [rbp - {off}], rax')
                else:
                    self._emit(f'    mov qword [rbp - {off}], 0')

        # Traducir cuerpo del nodo
        for cuad in instrucciones:
            self._traducir(cuad)

        # Epílogo del nodo
        self._emit(f'.epilogo_{nombre_nodo}:')
        self._emit('    mov rsp, rbp')
        self._emit('    pop rbp')
        self._emit('    ret')
        self._emit('')

    # ------------------------------------------------------------------
    # Traducción de cada cuádrupla a NASM x86-64
    # ------------------------------------------------------------------
    def _traducir(self, cuad: Cuadrupla):
        op = cuad.op

        if op == 'label':
            self._emit(f'.{cuad.res}:')

        elif op == '=':
            self._cargar('rax', cuad.arg1)
            self._guardar('rax', cuad.res)

        elif op in ('+', '-', '*'):
            self._cargar('rax', cuad.arg1)
            self._cargar('rcx', cuad.arg2)
            mnem = {'+': 'add', '-': 'sub', '*': 'imul'}[op]
            self._emit(f'    {mnem} rax, rcx')
            self._guardar('rax', cuad.res)

        elif op in ('/', '%'):
            self._cargar('rax', cuad.arg1)
            self._cargar('rcx', cuad.arg2)
            self._emit('    test rcx, rcx')
            self._emit('    jz _ts_div_zero')
            self._emit('    cqo')
            self._emit('    idiv rcx')
            reg_res = 'rax' if op == '/' else 'rdx'
            self._guardar(reg_res, cuad.res)

        elif op == 'neg':
            self._cargar('rax', cuad.arg1)
            self._emit('    neg rax')
            self._guardar('rax', cuad.res)

        elif op in ('<', '<=', '>', '>=', '==', '!='):
            t1 = cuad.tipo1 or self._inferir_tipo(cuad.arg1)
            t2 = cuad.tipo2 or self._inferir_tipo(cuad.arg2)
            if op in ('==', '!=') and (t1 == 'string' or t2 == 'string'):
                self._cargar('rcx', cuad.arg1)
                self._cargar('rdx', cuad.arg2)
                self._emit('    call _ts_streq')
                if op == '!=':
                    self._emit('    xor rax, 1')
                self._guardar('rax', cuad.res)
            else:
                self._cargar('rax', cuad.arg1)
                self._cargar('rcx', cuad.arg2)
                self._emit('    cmp rax, rcx')
                setcc = {
                    '==': 'sete', '!=': 'setne',
                    '<': 'setl', '<=': 'setle',
                    '>': 'setg', '>=': 'setge',
                }[op]
                self._emit(f'    {setcc} al')
                self._emit('    movzx rax, al')
                self._guardar('rax', cuad.res)

        elif op == 'and':
            self._cargar('rax', cuad.arg1)
            self._cargar('rcx', cuad.arg2)
            self._emit('    and rax, rcx')
            self._guardar('rax', cuad.res)

        elif op == 'or':
            self._cargar('rax', cuad.arg1)
            self._cargar('rcx', cuad.arg2)
            self._emit('    or rax, rcx')
            self._guardar('rax', cuad.res)

        elif op == 'not':
            self._cargar('rax', cuad.arg1)
            self._emit('    xor rax, 1')
            self._guardar('rax', cuad.res)

        elif op == 'concat':
            t1 = cuad.tipo1 or self._inferir_tipo(cuad.arg1)
            t2 = cuad.tipo2 or self._inferir_tipo(cuad.arg2)
            self._cargar('rcx', cuad.arg1)
            self._cargar('rdx', cuad.arg2)
            if t1 == 'int' and t2 == 'string':
                self._emit('    call _ts_concat_is')
            elif t1 == 'string' and t2 == 'int':
                self._emit('    call _ts_concat_si')
            else:
                self._emit('    call _ts_concat_ss')
            self._guardar('rax', cuad.res)

        elif op == 'cast':
            # Conversión explícita (si se usa en extensiones)
            t_dest = cuad.arg2
            t_orig = cuad.tipo1 or self._inferir_tipo(cuad.arg1)
            self._cargar('rcx', cuad.arg1)
            if t_dest == 'string' and t_orig == 'int':
                self._emit('    call _ts_int_to_str')
                self._guardar('rax', cuad.res)
            else:
                self._guardar('rcx', cuad.res)

        elif op == 'say':
            t1 = cuad.tipo1 or self._inferir_tipo(cuad.arg1)
            self._cargar('rcx', cuad.arg1)
            if t1 == 'int':
                self._emit('    call _ts_int_to_str')
                self._emit('    mov rcx, rax')
            elif t1 == 'bool':
                lbl_f = f'_str_f_{self._str_counter}'
                lbl_e = f'_str_e_{self._str_counter}'
                self._str_counter += 1
                self._emit('    test rcx, rcx')
                self._emit(f'    jz .{lbl_f}')
                lbl_true = self._registrar_cadena('true')
                self._emit(f'    lea rcx, [rel {lbl_true}]')
                self._emit(f'    jmp .{lbl_e}')
                self._emit(f'.{lbl_f}:')
                lbl_false = self._registrar_cadena('false')
                self._emit(f'    lea rcx, [rel {lbl_false}]')
                self._emit(f'.{lbl_e}:')
            self._emit('    call _ts_say')

        elif op == 'opt':
            # (opt, "Texto", -, Lk)
            self._cargar('rcx', cuad.arg1)
            self._emit('    call _ts_add_opt')
            self._opciones_menu.append(cuad.res)

        elif op == 'menu':
            # Muestra menú y salta según índice retornado en rax (0..N-1)
            self._emit('    call _ts_exec_menu')
            for idx, label_dest in enumerate(self._opciones_menu):
                self._emit(f'    cmp rax, {idx}')
                self._emit(f'    je .{label_dest}')
            self._opciones_menu = []

        elif op == 'goto':
            destino = cuad.res
            if destino in self._nodos_conocidos:
                # Salto entre nodos: destruye marco actual y conserva dirección de retorno
                self._emit('    mov rsp, rbp')
                self._emit('    pop rbp')
                self._emit(f'    jmp _node_{destino}')
            else:
                # Salto local dentro del mismo nodo
                self._emit(f'    jmp .{destino}')

        elif op == 'ifTrue':
            self._cargar('rax', cuad.arg1)
            self._emit('    test rax, rax')
            self._emit(f'    jnz .{cuad.res}')

        elif op == 'ifFalse':
            self._cargar('rax', cuad.arg1)
            self._emit('    test rax, rax')
            self._emit(f'    jz .{cuad.res}')

        elif op == 'call':
            self._emit(f'    call _node_{cuad.res}')

        elif op == 'return':
            if self._nodo_actual:
                self._emit(f'    jmp .epilogo_{self._nodo_actual}')
            else:
                self._emit('    ret')

        elif op == 'end':
            self._emit('    xor ecx, ecx')
            self._emit('    call _ts_exit')

        else:
            self._emit(f'    ; [WARN] Operador no reconocido: {cuad}')

    # ------------------------------------------------------------------
    # Helpers de acceso a memoria y operandos
    # ------------------------------------------------------------------
    def _cargar(self, reg: str, operando: Optional[str]):
        if operando is None or operando == '-':
            return
        if operando == 'true':
            self._emit(f'    mov {reg}, 1')
        elif operando == 'false':
            self._emit(f'    mov {reg}, 0')
        elif self._es_entero(operando):
            self._emit(f'    mov {reg}, {int(operando)}')
        elif self._es_literal_cadena(operando):
            lbl = self._registrar_cadena(self._extraer_cadena(operando))
            self._emit(f'    lea {reg}, [rel {lbl}]')
        elif operando.startswith('_str_') or operando in self._cadenas or (operando.startswith('S') and operando[1:].isdigit()):
            self._emit(f'    lea {reg}, [rel {operando}]')
        elif operando in self._offsets:
            off = self._offsets[operando]
            self._emit(f'    mov {reg}, [rbp - {off}]')
        elif operando in self._globales:
            self._emit(f'    mov {reg}, [rel _glob_{operando}]')
        else:
            self._emit(f'    mov {reg}, {operando}')

    def _guardar(self, reg: str, destino: Optional[str]):
        if destino is None or destino == '-':
            return
        if destino in self._offsets:
            off = self._offsets[destino]
            self._emit(f'    mov [rbp - {off}], {reg}')
        elif destino in self._globales:
            self._emit(f'    mov [rel _glob_{destino}], {reg}')
        else:
            self._offset_actual += 8
            self._offsets[destino] = self._offset_actual
            self._emit(f'    mov [rbp - {self._offset_actual}], {reg}')

    def _inferir_tipo(self, operando: Optional[str]) -> str:
        if not operando or operando == '-':
            return 'int'
        if self._es_literal_cadena(operando) or operando.startswith('_str_'):
            return 'string'
        if operando in self._cadenas or (operando.startswith('S') and operando[1:].isdigit()):
            return 'string'
        if operando in ('true', 'false'):
            return 'bool'
        if self._es_entero(operando):
            return 'int'
        if operando in self._tipos_temporales:
            return self._tipos_temporales[operando]
        if operando in self._tipos_locales:
            return self._tipos_locales[operando]
        if operando in self._globales:
            return self._globales[operando]
        return 'int'

    def _emit(self, line: str):
        self._lines.append(line)

    @staticmethod
    def _es_entero(s: str) -> bool:
        try:
            int(s)
            return True
        except (ValueError, TypeError):
            return False

    @staticmethod
    def _es_temporal(s: str) -> bool:
        return len(s) >= 2 and s[0] == 't' and s[1:].isdigit()

    @staticmethod
    def _es_etiqueta(s: str) -> bool:
        return len(s) >= 2 and s[0] == 'L' and s[1:].isdigit()

    @staticmethod
    def _nasm_string(s: str) -> str:
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