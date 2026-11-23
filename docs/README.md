# TaleScript

TaleScript es un lenguaje para crear historias interactivas. Un programa se
divide en `node`; `goto` cambia de nodo, `call`/`return` permite ejecutar una
subrutina y `choice` presenta opciones con bloques de instrucciones.

## Requisitos en Windows

- Python 3.11 o posterior
- PLY (se instala desde `requirements.txt`)
- NASM 2.15 o posterior
- GCC de MinGW-w64

1. Instala Python desde [python.org](https://www.python.org/downloads/windows/)
   y habilita la opción para agregar Python al `PATH`.
2. Desde PowerShell, instala las dependencias del compilador:

```powershell
python -m pip install -r requirements.txt
```

3. Instala NASM desde [nasm.us](https://www.nasm.us/) y agrega su carpeta al
   `PATH`.
4. Instala [MSYS2](https://www.msys2.org/), abre su terminal **UCRT64** e
   instala MinGW-w64 GCC:

```bash
pacman -S mingw-w64-ucrt-x86_64-gcc
```

Agrega `C:\msys64\ucrt64\bin` al `PATH` de Windows. Abre una terminal nueva y
comprueba que `python`, `nasm` y `gcc` se puedan ejecutar.

## CLI

Ejecuta el compilador desde la raíz del repositorio:

```powershell
# Compilar un programa
python -m talescriptc.main tests/execution/historia.ts -o historia.exe

# Activar optimización O1
python -m talescriptc.main tests/execution/historia.ts -o historia.exe -O1

# Desactivar optimización (nivel predeterminado)
python -m talescriptc.main tests/execution/historia.ts -O0

# Mostrar tokens, tabla de símbolos, cuádruplas o tripletas
python -m talescriptc.main tests/execution/historia.ts --dump-tokens
python -m talescriptc.main tests/execution/historia.ts --dump-symtab
python -m talescriptc.main tests/execution/historia.ts --dump-tac
python -m talescriptc.main tests/execution/historia.ts --dump-triples

# Combinar opciones de inspección
python -m talescriptc.main tests/execution/historia.ts -O1 --dump-symtab --dump-tac --dump-triples
```

Las opciones disponibles son `-O0`, `-O1`, `--dump-tokens`,
`--dump-symtab`, `--dump-tac` y `--dump-triples`. La compilación nativa
requiere NASM y GCC disponibles en `PATH`.

## Sintaxis del lenguaje

Las palabras reservadas se escriben en minúsculas. Las declaraciones globales
van antes de los nodos; las variables locales se declaran dentro de un nodo.
Los bloques `if`, `while`, `do` y `choice` comparten el ámbito local del nodo.

```ts
global int karma = 0;
global const int LIMITE = 10;

node inicio {
    local int nivel = 1;
    say "Despiertas. Tu karma es {karma}.";
    if (karma < LIMITE) {
        goto pelea;
    } else {
        end;
    }
}

node pelea {
    local bool terminado = false;
    do {
        choice {
            "Continuar" {
                karma = karma + 1;
                terminado = true;
            }
            "Volver" {
                goto inicio;
            }
        }
    } while (not terminado);
    end;
}
```

### Declaraciones y control de flujo

- Global: `global int puntos = 0;` o `global const string titulo = "Inicio";`
- Local: `local bool terminado = false;` o `local int intentos;`
- Asignación: `puntos = puntos + 1;`
- Salida de texto: `say "Hola, {nombre}";`
- Saltos: `goto pelea;`, `call curar;`, `return;` y `end;`
- Menú: `choice { "Texto" { instrucciones; } }`

Los inicializadores globales y de constantes deben ser expresiones constantes.
Una local no puede sombrear una global y las constantes no se pueden reasignar.
El primer nodo declarado es el punto de entrada. `goto` puede referirse a un
nodo declarado más adelante; el compilador valida los destinos al terminar.

### Tipos y expresiones

Los tipos son `int`, `string` y `bool`. Los operadores aritméticos son `+`,
`-`, `*`, `/` y `%`; los relacionales, `<`, `<=`, `>`, `>=`, `==` y `!=`;
los lógicos, `not`, `and` y `or`. La precedencia se codifica en la gramática.
Las cadenas admiten escapes e interpolación de identificadores con `{nombre}`.

## Diagnósticos

| Código | Significado |
|---|---|
| E01 | Variable no declarada |
| E02 | Identificador duplicado en el mismo ámbito |
| E03 | Variable local con el mismo nombre que una global |
| E04 | Tipo incompatible en inicialización o asignación |
| E05 | Tipos inválidos para un operador |
| E06 | División o módulo entre cero constante |
| E07 | Condición de `if`, `while` o `do-while` no booleana |
| E08 | Nombre de nodo duplicado |
| E09 | Nodo de destino no declarado |
| E10 | Texto de opción duplicado en un `choice` |
| E11 | Reasignación de una constante |
| E12 | Inicializador que debe ser constante |
| W01 | Variable local declarada pero nunca leída |
| L01-L02 | Error léxico |
| S01 | Error sintáctico |

## Pruebas

Desde la raíz del repositorio:

```powershell
python -m unittest discover -s tests
```

Los programas de ejecución están en `tests/execution/`; los casos de
diagnóstico individual, en `tests/semantic/`; y el ejemplo para comparar TAC,
en `tests/intermediate/referencia_inicio_pelea.ts`.
