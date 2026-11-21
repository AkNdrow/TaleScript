# TaleScript (`talescriptc`) — Documentación Base del Proyecto (Fase 1)

Documento técnico de arquitectura, diseño e implementación de la estructura base del compilador **TaleScript** (`talescriptc`), diseñado para un lenguaje de historias interactivas basadas en máquinas de estado (`node` y menús `choice`), con backend generador de código objeto **x86-64 NASM** y runtime en **C** bajo **Windows (PowerShell)**.

---

## 1. Stack Tecnológico y Entorno de Ejecución

| Componente | Tecnología | Rol en el Proyecto |
|---|---|---|
| **Lenguaje del Compilador** | Python 3.11+ / 3.13 | Frontend, análisis semántico, TAC, optimizador y backend. |
| **Parser / Lexer** | `ply` (3.11+) (`ply.lex`, `ply.yacc`) | Analizador léxico y sintáctico ascendente LALR(1) con marcadores dirigidos por sintaxis (SDT). |
| **Generador de Ensamblador** | NASM (`nasm -f win64`) | Ensamblado de cuádruplas a código objeto nativo de 64 bits para Windows. |
| **Enlazador / Toolchain C** | GCC (MinGW-w64 / MSYS2) | Compilación de `runtime/runtime.c` y enlace con el objeto NASM para generar ejecutables `.exe`. |
| **Convención de Llamadas (ABI)** | Microsoft x64 ABI | Paso de argumentos en `rcx`, `rdx`, `r8`, `r9`, reserva de 32 bytes de *shadow space* y alineación de pila a múltiplos de 16 bytes. |

---

## 2. Estructura de Directorios Creada

La raíz del repositorio contiene la arquitectura modular completa:

```text
TaleScript/
├── talescriptc/
│   ├── __init__.py              # Definición del paquete talescriptc
│   ├── main.py                  # CLI con argparse: talescriptc archivo.ts -o archivo.exe [-O0|-O1] --dump-*
│   ├── lexer/
│   │   ├── __init__.py
│   │   └── lexer.py             # ply.lex: tokens, posiciones (línea/columna), comentarios // e interpolación {id}
│   ├── parser/
│   │   ├── __init__.py
│   │   └── parser.py            # ply.yacc: gramática GLC con marcadores ε para SDT
│   ├── semantica/
│   │   ├── __init__.py
│   │   ├── tabla_simbolos.py    # Ámbitos [Global, Local] + tabla_nodos (resolución de referencias adelantadas)
│   │   ├── pila_semantica.py    # Dataclass ElementoPilaSemantica (tipo, lugar, val, cte)
│   │   └── gestor_errores.py    # Catálogo E01-E12, W01, L01-L02, S01 con política anti-cascada (tipo ERROR)
│   ├── intermedio/
│   │   ├── __init__.py
│   │   ├── cuadrupla.py         # Dataclass Cuadrupla (op, arg1, arg2, res) y exportador a Tripletas indexadas (i)
│   │   └── generador_tac.py     # ListaCodigo con insertarEn(), etiquetas Lk, temporales tk y tabla de cadenas
│   ├── optimizador/
│   │   ├── __init__.py
│   │   └── optimizador.py       # Algoritmo de líderes (bloques básicos), folding, propagación, peephole y código muerto
│   └── backend/
│       ├── __init__.py
│       └── generador_x86_64.py  # Traductor TAC a NASM win64 y cálculo de marcos de pila (múltiplo de 16)
├── runtime/
│   └── runtime.c                # Primitivas C: _ts_say, _ts_concat_ss/si/is, _ts_streq, _ts_add_opt, _ts_exec_menu, _ts_exit
├── tests/
│   ├── semantic/                # Casos de prueba E01-E12 y W01
│   ├── intermediate/            # Caso de referencia (nodos inicio y pelea con choice)
│   └── execution/               # Ejemplos completos ejecutables: historia.ts, fibonacci.ts, factorial.ts
├── docs/
│   └── README.md                # Manual de usuario, especificación y comandos CLI en Windows
├── DOC_BASE_PRO.md              # Documento técnico consolidado de la fase inicial
├── requirements.txt             # ply>=3.11
└── .gitignore                   # Exclusión de __pycache__, *.obj, *.o, *.exe, *.asm, parser.out, etc.
```

---

## 3. Desglose Módulo por Módulo

### 3.1. Analizador Léxico (`talescriptc/lexer/lexer.py`)
- **Implementación:** Basada en `ply.lex`.
- **Palabras Reservadas:** `node`, `choice`, `say`, `set`, `if`, `else`, `goto`, `exit`, `var`, `int`, `string`, `true`, `false`.
- **Operadores y Delimitadores:** Aritméticos (`+`, `-`, `*`, `/`), relacionales (`==`, `!=`, `<`, `>`, `<=`, `>=`), asignación (`=`), delimitadores (`{`, `}`, `(`, `)`, `;`, `:`).
- **Comentarios:** Soporte de comentarios de línea estilo C++ (`// ...`) descartados automáticamente.
- **Rastreo de Posición:** Conteo de líneas con saltos `\n` y cálculo exacto de columna con la función `find_column`.
- **Cadenas con Interpolación `{id}`:** La regla `t_STRING` detecta secuencias de escape (`\n`, `\t`, `\"`, `\\`) y tokeniza el cuerpo de la cadena como una lista de tuplas estructuradas `[('str', texto), ('id', variable)]`, permitiendo al analizador sintáctico y al SDT desglosar interpolaciones en concatenaciones dinámicas.

---

### 3.2. Analizador Sintáctico y SDT (`talescriptc/parser/parser.py`)
- **Algoritmo:** Analizador ascendente **LALR(1)** mediante `ply.yacc`.
- **Manejo de Ambigüedades:** Precedencia explícita para operadores aritméticos y relacionales; resolución del conflicto *dangling-else* mediante la pseudotoken `IF_PREC` y regla `ELSE`.
- **Traducción Dirigida por la Sintaxis (SDT) con Marcadores $\epsilon$:**
  - `marker_pre_nodo`: Registra el nodo en la tabla de símbolos antes de procesar su cuerpo y emite la etiqueta `LABEL _node_<id>`.
  - `marker_cond`: Evalúa la condición en la pila semántica y emite un salto condicional `IF_FALSE` hacia una etiqueta que aún no ha terminado de parsearse.
  - `marker_else`: Emite el `GOTO` de salto al final de la estructura `if-else` y fija la etiqueta para la rama falsa.
- **Menús `choice`:** Recolecta las opciones `(texto, destino)` y emite las cuádruplas `ADD_OPT`, `EXEC_MENU` e instrucciones de salto condicional `IF_EQ` hacia las etiquetas destino.

---

### 3.3. Semántica y Gestión de Ámbitos

#### Tabla de Símbolos (`talescriptc/semantica/tabla_simbolos.py`)
- **Pila de Ámbitos:** Lista de diccionarios `[ambito_global, ambito_local]`.
- **Registro de Variables:** Inspecciona redeclaraciones (`E02`), variables no declaradas (`E01`) y rastrea el uso de cada identificador para emitir advertencias de variables no usadas (`W01`).
- **Tabla de Nodos (Referencias Adelantadas):** Almacena las definiciones y referencias a nodos (`goto` o `choice`). Permite referenciar un nodo antes de que su definición haya sido leída en el archivo fuente, resolviendo la validez en una pasada de verificación post-parse.
- **Validaciones Globales Post-Parse:**
  - Existencia del nodo principal `inicio` (`E07`).
  - Nodos referenciados pero nunca definidos (`E05`).
  - Nodos huérfanos sin sentencias de salida (`goto`, `choice`, `exit`) (`E11`).
  - Nodos inalcanzables que no son referenciados por nadie (`E12`).

#### Pila Semántica (`talescriptc/semantica/pila_semantica.py`)
- `ElementoPilaSemantica`: Transporta `(tipo, lugar, val, cte)` durante las reducciones sintácticas.
- Permite sintetizar tipos en expresiones compuestas y propagar valores constantes para el plegado de constantes.

#### Gestor de Errores y Política Anti-Cascada (`talescriptc/semantica/gestor_errores.py`)
- **Catálogo Implementado:**
  - `E01`: Variable no declarada.
  - `E02`: Variable ya declarada en el mismo ámbito.
  - `E03`: Incompatibilidad de tipos en asignación o inicialización.
  - `E04`: Incompatibilidad de tipos en operaciones aritméticas o relacionales.
  - `E05`: Nodo referenciado pero nunca definido.
  - `E06`: Nodo duplicado.
  - `E07`: Falta nodo `inicio`.
  - `E08`: División por cero detectada en tiempo de compilación.
  - `E09`: Expresión en `choice` debe ser de tipo `string`.
  - `E10`: Destino en `choice` debe ser un nodo válido.
  - `E11`: Nodo sin sentencia de salida (`goto`/`choice`/`exit`).
  - `E12`: Nodo inalcanzable.
  - `W01`: Variable declarada pero nunca usada.
  - `L01`: Log de plegado de constantes.
  - `L02`: Log de propagación de copias.
  - `S01`: Error de sintaxis.
- **Política Anti-Cascada:** Cuando un identificador genera un error de tipo o declaración, se le asigna el tipo sintético `ERROR`. Las operaciones subsecuentes que involucran un operando con tipo `ERROR` se omiten silenciosamente sin generar falsos positivos.

---

### 3.4. Código Intermedio (`talescriptc/intermedio/`)

#### Cuádruplas y Tripletas (`cuadrupla.py`)
- **Cuádrupla:** Estructura `(op, arg1, arg2, res)`.
- **Tripletas:** Conversor `cuadruplas_a_tripletas()`. Adapta la representación de tres direcciones al formato indexado `(i) (op, arg1, arg2)`:
  - Las asignaciones a variables conservan el destino: `(i) (ASSIGN, var, (j))`.
  - Los saltos condicionales e incondicionales integran sus etiquetas de destino en los argumentos correspondientes.
  - Los resultados de operaciones temporales previas se referencian mediante el índice de instrucción `(i)`.

#### Generador TAC (`generador_tac.py`)
- Estructura `GeneradorTAC`:
  - Temporales: Generador secuencial `t0, t1, t2, ...`.
  - Etiquetas: Generador secuencial `L0, L1, L2, ...`.
  - Soporte de inserción posicional `insertarEn(pos, cuad)` para acomodar saltos y despachos de menús dinámicos.
  - Tabla de cadenas literales deduplicadas (`_str_0`, `_str_1`, ...).

---

### 3.5. Optimizador de Código Intermedio (`talescriptc/optimizador/optimizador.py`)
Se estructura en pasadas sobre el flujo de control:
1. **Algoritmo de Líderes:**
   - La primera instrucción es líder.
   - Todo destino de salto incondicional o condicional es líder.
   - Toda instrucción que sigue inmediatamente a un salto es líder.
   - Construcción de `BloqueBasico` con cálculo de aristas de predecesores y sucesores.
2. **Plegado de Constantes (*Constant Folding*):** Simplificación en tiempo de compilación de operaciones con literales enteros (`ADD`, `SUB`, `MUL`, `DIV`, `NEG`) y operadores relacionales (`EQ`, `NEQ`, `LT`, etc.).
3. **Propagación de Copias Local (*Copy Propagation*):** Propagación de asignaciones simples (`ASSIGN x _ y`) dentro de cada bloque básico, con invalidación inmediata al redefinirse la variable destino o fuente.
4. **Eliminación de Código Muerto (*Dead Code Elimination*):** Supresión de cálculos y asignaciones sobre temporales `tk` cuyo valor nunca es leído.
5. **Peephole:**
   - Supresión de auto-asignaciones (`ASSIGN x _ x`).
   - Identidades algebraicas: $x + 0 \to x$, $x \times 1 \to x$, $x \times 0 \to 0$, $x - 0 \to x$.
   - Eliminación de saltos redundantes a la etiqueta inmediatamente adyacente (`GOTO L` seguido de `LABEL L`).

---

### 3.6. Backend NASM x86-64 y Microsoft x64 ABI (`talescriptc/backend/generador_x86_64.py`)
- **Directiva:** `default rel` (direccionamiento relativo por defecto para código de posición independiente).
- **Sección `.data`:** Emisión de literales string en formato NASM `db`, codificando secuencias imprimibles y valores ASCII especiales.
- **Sección `.text`:**
  - Exportación global del punto de entrada `main`.
  - Declaración de funciones externas del runtime: `_ts_say`, `_ts_concat_ss`, `_ts_concat_si`, `_ts_concat_is`, `_ts_streq`, `_ts_add_opt`, `_ts_exec_menu`, `_ts_exit`.
- **Cumplimiento estricto de la Microsoft x64 ABI:**
  - **Paso de Argumentos:**
    - 1er argumento: `rcx`
    - 2do argumento: `rdx`
    - 3er argumento: `r8`
    - 4to argumento: `r9`
  - **Shadow Space:** Reserva obligatoria de 32 bytes (4 quadwords) en la base de la pila del llamador antes de cada instrucción `call`.
  - **Alineación de Pila:** Cálculo dinámico del marco de pila:
    $$\text{frame\_size} = (\text{offset\_variables} + 32 + 15) \ \& \ \sim 15$$
    Garantiza que `rsp` esté siempre alineado a 16 bytes al ejecutar cualquier instrucción `call`.
- **Inicialización Global:** Las variables globales se evalúan e inicializan secuencialmente en el prólogo antes de transferir el control al nodo de inicio `_node_inicio`.

---

### 3.7. Runtime en C (`runtime/runtime.c`)
Primitivas compiladas y enlazadas con GCC/MinGW-w64:
- `void _ts_say(const char *text)`: Salida estándar con salto de línea.
- `const char *_ts_concat_ss(const char *a, const char *b)`: Asignación dinámica en heap y concatenación de dos cadenas.
- `const char *_ts_concat_si(const char *s, int64_t i)`: Concatenación de cadena y entero de 64 bits.
- `const char *_ts_concat_is(int64_t i, const char *s)`: Concatenación de entero de 64 bits y cadena.
- `int64_t _ts_streq(const char *a, const char *b)`: Comparación lexicográfica con `strcmp`.
- `void _ts_add_opt(const char *text)`: Registro de una opción en el buffer de menú global.
- `int64_t _ts_exec_menu(void)`: Despliegue interactivo con validación de entrada estándar (`scanf`) y retorno del índice seleccionado (0-based).
- `void _ts_exit(void)`: Salida del proceso con código de retorno 0.

---

### 3.8. Interfaz de Línea de Comandos (`talescriptc/main.py`)
Manejo completo mediante `argparse`:
- `talescriptc archivo.ts -o archivo.exe`: Compilación completa a binario nativo.
- `-O0` / `-O1`: Selección de nivel de optimización (sin optimizar o con pasadas completas de líderes, plegado, propagación y peephole).
- `--dump-tokens`: Volcado del flujo léxico con tipos, lexemas, líneas y posiciones.
- `--dump-symtab`: Volcado tabular de variables, tipos, ámbitos, estados de uso y tabla de nodos.
- `--dump-tac`: Volcado de la lista de cuádruplas `(op, arg1, arg2, res)`.
- `--dump-triples`: Volcado de la lista de tripletas indexadas `(i) (op, arg1, arg2)`.

---

## 4. Resultados de Verificación y Pruebas

Se validaron todos los casos de prueba provistos en la suite:

### Casos Semánticos (`tests/semantic/`)
| Archivo de Prueba | Código Esperado | Resultado | Estado |
|---|---|---|---|
| `test_E01_var_no_declarada.ts` | E01 | `['E01']` | ✅ PASÓ |
| `test_E02_var_duplicada.ts` | E02 | `['E02', 'W01']` | ✅ PASÓ |
| `test_E03_tipo_incompatible.ts` | E03 | `['E03', 'W01']` | ✅ PASÓ |
| `test_E04_tipos_operacion.ts` | E04 | `['E04', 'W01']` | ✅ PASÓ |
| `test_E05_nodo_no_definido.ts` | E05 | `['E05']` | ✅ PASÓ |
| `test_E06_nodo_duplicado.ts` | E06 | `['E06']` | ✅ PASÓ |
| `test_E07_sin_inicio.ts` | E07 | `['E07']` | ✅ PASÓ |
| `test_E08_div_cero.ts` | E08 | `['E08', 'W01']` | ✅ PASÓ |
| `test_E10_choice_nodo_invalido.ts` | E05 | `['E05']` | ✅ PASÓ |
| `test_E11_sin_salida.ts` | E11 | `['E11']` | ✅ PASÓ |
| `test_E12_inalcanzable.ts` | E12 | `['E12']` | ✅ PASÓ |
| `test_W01_var_no_usada.ts` | W01 | `['W01', 'W01']` | ✅ PASÓ |

### Programas de Ejecución e Intermedio (`tests/execution/`, `tests/intermediate/`)
| Programa | Descripción | TAC Original | TAC Optimizado (-O1) | Ensamblador NASM Generado | Estado |
|---|---|---|---|---|---|
| `factorial.ts` | Cálculo de factorial iterativo con nodos y condicionales | 26 cuádruplas | 25 cuádruplas | 96 líneas ASM | ✅ Correcto |
| `fibonacci.ts` | Generación de la serie de Fibonacci mediante bucle de nodos | 30 cuádruplas | 27 cuádruplas | 98 líneas ASM | ✅ Correcto |
| `historia.ts` | Aventura interactiva completa con nodos, variables y menús `choice` | 45 cuádruplas | 45 cuádruplas | 161 líneas ASM | ✅ Correcto |
| `referencia_inicio_pelea.ts`| Caso de referencia con interpolación de variables y branching | 29 cuádruplas | 29 cuádruplas | 120 líneas ASM | ✅ Correcto |

---

## 5. Instrucciones de Uso en Windows (PowerShell)

### Instalación de dependencias:
```powershell
pip install -r requirements.txt
```

### Ejemplos de invocación del compilador:
```powershell
# 1. Inspeccionar tokens
python -m talescriptc tests/execution/historia.ts --dump-tokens

# 2. Inspeccionar tabla de símbolos
python -m talescriptc tests/execution/historia.ts --dump-symtab

# 3. Inspeccionar TAC y Tripletas
python -m talescriptc tests/execution/historia.ts --dump-tac --dump-triples

# 4. Compilación con optimización a ejecutable Windows .exe
python -m talescriptc tests/execution/historia.ts -o historia.exe -O1

# 5. Ejecutar la historia compilada
.\historia.exe
```
