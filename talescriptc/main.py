"""
TaleScript Compiler — CLI Principal
====================================
Uso:
    python -m talescriptc historia.ts -o historia.exe [-O0|-O1]
           [--dump-tokens] [--dump-symtab] [--dump-tac] [--dump-triples]
"""
from __future__ import annotations
import argparse
import os
import subprocess
import sys

from talescriptc.lexer.lexer import crear_lexer
from talescriptc.parser.parser import parsear
from talescriptc.intermedio.cuadrupla import (
    dump_cuadruplas, dump_tripletas, cuadruplas_a_tripletas,
)
from talescriptc.optimizador.optimizador import Optimizador
from talescriptc.backend.generador_x86_64 import GeneradorX86_64
from talescriptc.semantica.formato_errores import reporte_detallado


def main():
    # Si se pasa --gui o no se proporcionan argumentos, lanzar TaleScript Studio
    if '--gui' in sys.argv or len(sys.argv) == 1:
        from talescriptc.gui.studio import main as gui_main
        gui_main()
        return

    args = _parse_args()
    if args.gui or not args.source:
        from talescriptc.gui.studio import main as gui_main
        gui_main()
        return

    source_path = args.source
    output_path = args.output

    # 1. Leer archivo fuente
    try:
        with open(source_path, 'r', encoding='utf-8') as f:
            source_code = f.read()
    except FileNotFoundError:
        print(f'Error: archivo no encontrado: {source_path}', file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f'Error leyendo {source_path}: {e}', file=sys.stderr)
        sys.exit(1)

    # 2. Dump de tokens (opcional)
    if args.dump_tokens:
        _dump_tokens(source_code)

    # 3. Parsing + Análisis Semántico + Generación de TAC
    print(f'[talescriptc] Compilando {source_path}...')
    resultado = parsear(source_code)

    # 4. Dump de tabla de símbolos (opcional)
    if args.dump_symtab:
        print(resultado.tabla_simbolos.dump())

    # 5. Mostrar errores y advertencias
    if resultado.errores or resultado.advertencias:
        if args.formato_corto:
            print(resultado.gestor_errores.dump())
        else:
            print(reporte_detallado(resultado.gestor_errores.obtener_todos(), source_code,
                                    source_path, color=_usar_color()))

    if not resultado.exito:
        print(f'\n[talescriptc] Compilación fallida con {len(resultado.errores)} error(es).')
        sys.exit(1)

    codigo_tac = resultado.codigo_tac

    # 6. Dump de TAC antes de optimizar (opcional)
    if args.dump_tac:
        print(dump_cuadruplas(codigo_tac))

    # 7. Dump de tripletas (opcional)
    if args.dump_triples:
        tripletas = cuadruplas_a_tripletas(codigo_tac)
        print(dump_tripletas(tripletas))

    # 8. Optimización
    if args.opt_level >= 1:
        print('[talescriptc] Optimizando (nivel O1)...')
        opt = Optimizador()
        codigo_tac = opt.optimizar(codigo_tac)
        if args.dump_tac:
            print('\n--- TAC Optimizado ---')
            print(dump_cuadruplas(codigo_tac))

    # 9. Generación de código x86-64
    print('[talescriptc] Generando ensamblador NASM x86-64...')
    gen = GeneradorX86_64()
    asm_code = gen.generar(codigo_tac, resultado.tabla_cadenas, resultado.tabla_simbolos)

    base_name = os.path.splitext(output_path)[0]
    asm_path = base_name + '.asm'
    obj_path = base_name + '.obj'

    with open(asm_path, 'w', encoding='utf-8') as f:
        f.write(asm_code)
    print(f'[talescriptc] Ensamblador escrito en {asm_path}')

    # 10. Ensamblar con NASM
    runtime_c = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             'runtime', 'runtime.c')
    print('[talescriptc] Ensamblando con NASM...')
    nasm_cmd = ['nasm', '-f', 'win64', asm_path, '-o', obj_path]
    try:
        subprocess.run(nasm_cmd, check=True, capture_output=True, text=True)
    except FileNotFoundError:
        print('Error: NASM no encontrado. Instala NASM y agrégalo al PATH.', file=sys.stderr)
        print(f'  El archivo .asm se generó en: {asm_path}', file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f'Error de NASM:\n{e.stderr}', file=sys.stderr)
        sys.exit(1)

    # 11. Enlazar con GCC (MinGW-w64)
    print('[talescriptc] Enlazando con GCC...')
    gcc_cmd = ['gcc', '-o', output_path, obj_path, runtime_c, '-lmsvcrt']
    try:
        subprocess.run(gcc_cmd, check=True, capture_output=True, text=True)
    except FileNotFoundError:
        print('Error: GCC no encontrado. Instala MinGW-w64 y agrégalo al PATH.',
              file=sys.stderr)
        print(f'  El archivo .obj se generó en: {obj_path}', file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f'Error de GCC:\n{e.stderr}', file=sys.stderr)
        sys.exit(1)

    # 12. Limpiar archivos intermedios
    _cleanup(asm_path, obj_path, keep_asm=args.dump_tac)

    print(f'[talescriptc] ✅ Ejecutable generado: {output_path}')


def _parse_args():
    p = argparse.ArgumentParser(
        prog='talescriptc',
        description='Compilador TaleScript — historias interactivas compiladas a x86-64',
    )
    p.add_argument('source', nargs='?', default=None, help='Archivo fuente .ts (opcional si se usa --gui)')
    p.add_argument('--gui', action='store_true',
                   help='Iniciar el entorno gráfico TaleScript Studio (IDE)')
    p.add_argument('-o', '--output', default='a.exe',
                   help='Archivo ejecutable de salida (por defecto: a.exe)')
    p.add_argument('-O0', dest='opt_level', action='store_const', const=0, default=0,
                   help='Sin optimización (por defecto)')
    p.add_argument('-O1', dest='opt_level', action='store_const', const=1,
                   help='Optimización nivel 1')
    p.add_argument('--dump-tokens', action='store_true',
                   help='Mostrar tokens del análisis léxico')
    p.add_argument('--dump-symtab', action='store_true',
                   help='Mostrar tabla de símbolos')
    p.add_argument('--dump-tac', action='store_true',
                   help='Mostrar código intermedio (cuádruplas)')
    p.add_argument('--dump-triples', action='store_true',
                   help='Mostrar código intermedio (tripletas)')
    p.add_argument('--formato-corto', action='store_true',
                   help='Errores en una sola línea (archivo:linea:col: CODIGO: mensaje)')
    return p.parse_args()


def _usar_color() -> bool:
    """Colores ANSI solo en una terminal interactiva y si NO_COLOR no está definido."""
    if os.environ.get('NO_COLOR') or not sys.stdout.isatty():
        return False
    if os.name == 'nt':
        os.system('')  # activa las secuencias ANSI (VT) en la consola de Windows
    return True


def _dump_tokens(source: str):
    """Muestra todos los tokens del archivo fuente."""
    lex = crear_lexer()
    lex.input(source)
    print('=== TOKENS ===')
    print(f'{"Tipo":<15} {"Valor":<30} {"Línea":<6} {"Pos":<6}')
    print('-' * 60)
    while True:
        tok = lex.token()
        if not tok:
            break
        print(f'{tok.type:<15} {str(tok.value):<30} {tok.lineno:<6} {tok.lexpos:<6}')
    print()


def _cleanup(asm_path: str, obj_path: str, keep_asm: bool = False):
    """Elimina archivos intermedios."""
    try:
        if not keep_asm and os.path.exists(asm_path):
            os.remove(asm_path)
        if os.path.exists(obj_path):
            os.remove(obj_path)
    except OSError:
        pass


if __name__ == '__main__':
    main()
