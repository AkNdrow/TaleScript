# TaleScript — Manual de Usuario

## ¿Qué es TaleScript?

**TaleScript** es un lenguaje de programación diseñado para crear **historias interactivas** basadas en **máquinas de estado**. Cada historia se compone de **nodos** (`node`) que representan escenas, y **menús** (`choice`) que permiten al lector tomar decisiones que modifican el flujo narrativo.

El compilador `talescriptc` traduce programas `.ts` a **ejecutables nativos x86-64** para Windows.

---

## Requisitos en Windows

| Herramienta        | Versión mínima | Propósito                        |
|--------------------|----------------|----------------------------------|
| **Python**         | 3.11+          | Ejecutar el compilador           |
| **PLY**            | 3.11+          | Parser LALR(1) y lexer           |
| **NASM**           | 2.15+          | Ensamblador x86-64               |
| **GCC (MinGW-w64)**| 12+            | Enlazador y compilador de C      |

### Instalación

```powershell
# Instalar PLY
pip install ply

# Instalar NASM (descargar de https://www.nasm.us/)
# Agregar al PATH: C:\nasm

# Instalar MinGW-w64 (descargar de https://www.mingw-w64.org/)
# Agregar al PATH: C:\mingw64\bin
```

---

## Uso de la CLI

```powershell
# Compilación básica
python -m talescriptc historia.ts -o historia.exe

# Con optimización nivel 1
python -m talescriptc historia.ts -o historia.exe -O1

# Dump de tokens (análisis léxico)
python -m talescriptc historia.ts --dump-tokens

# Dump de tabla de símbolos
python -m talescriptc historia.ts --dump-symtab

# Dump de código intermedio (cuádruplas)
python -m talescriptc historia.ts --dump-tac

# Dump de código intermedio (tripletas)
python -m talescriptc historia.ts --dump-triples

# Combinación completa
python -m talescriptc historia.ts -o historia.exe -O1 --dump-tokens --dump-symtab --dump-tac --dump-triples
```

---

## El Lenguaje TaleScript

### Tipos de datos

| Tipo     | Descripción                    | Ejemplo          |
|----------|--------------------------------|------------------|
| `int`    | Entero de 64 bits con signo    | `42`, `-7`, `0`  |
| `string` | Cadena de texto UTF-8          | `"Hola, mundo"`  |

### Variables

```ts
var int vida = 100;
var string nombre = "Héroe";
var int contador;              // Sin inicializar
```

### Nodos (escenas)

```ts
node inicio {
    say("Bienvenido a la aventura.");
    goto siguiente;
}
```

Todo programa **debe** tener un nodo llamado `inicio`.

### Sentencias

| Sentencia             | Descripción                                      |
|-----------------------|--------------------------------------------------|
| `say(expr);`          | Imprime una expresión (string o int)             |
| `set var = expr;`     | Asigna un valor a una variable existente          |
| `goto nodo;`          | Salta a otro nodo                                 |
| `exit;`               | Termina el programa                               |
| `if (cond) { ... }`  | Ejecución condicional                             |
| `if (...) { } else { }` | Condicional con rama alternativa               |
| `choice { ... }`     | Menú interactivo                                  |

### Menú Choice

```ts
choice {
    "Explorar el bosque": bosque;
    "Ir a la taberna": taberna;
    "Descansar": descanso;
}
```

Cada opción tiene un **texto** (string) y un **destino** (nombre de nodo).

### Interpolación de cadenas

Usa `{variable}` dentro de strings para insertar el valor de una variable:

```ts
var string nombre = "Arturo";
var int nivel = 5;
say("Jugador: {nombre}, Nivel: {nivel}");
// Imprime: Jugador: Arturo, Nivel: 5
```

### Operadores

| Operador | Descripción         | Tipos soportados         |
|----------|---------------------|--------------------------|
| `+`      | Suma / Concatenar   | `int+int`, `string+any`  |
| `-`      | Resta               | `int`                    |
| `*`      | Multiplicación      | `int`                    |
| `/`      | División entera     | `int`                    |
| `==`     | Igualdad            | `int`, `string`          |
| `!=`     | Desigualdad         | `int`, `string`          |
| `<` `>`  | Comparación         | `int`                    |
| `<=` `>=`| Comparación         | `int`                    |

### Comentarios

```ts
// Esto es un comentario de línea
say("Hola");  // Comentario al final
```

---

## Códigos de Error

| Código | Tipo  | Descripción                                               |
|--------|-------|-----------------------------------------------------------|
| E01    | Error | Variable no declarada                                     |
| E02    | Error | Variable ya declarada en el mismo ámbito                  |
| E03    | Error | Tipo incompatible en asignación                           |
| E04    | Error | Tipos incompatibles en operación binaria                  |
| E05    | Error | Nodo referenciado pero nunca definido                     |
| E06    | Error | Nodo duplicado                                            |
| E07    | Error | Nodo `inicio` no definido                                 |
| E08    | Error | División por cero en expresión constante                  |
| E09    | Error | Expresión en `choice` debe ser tipo `string`              |
| E10    | Error | Destino en `choice` debe ser un nodo válido               |
| E11    | Error | Nodo sin sentencia de salida (`goto`/`choice`/`exit`)     |
| E12    | Error | Nodo inalcanzable                                         |
| W01    | Warn  | Variable declarada pero nunca usada                       |
| L01    | Log   | Plegado de constantes aplicado                            |
| L02    | Log   | Propagación de copias aplicada                            |
| S01    | Error | Error de sintaxis                                         |

---

## Arquitectura del Compilador

```text
  .ts ──▶ [Lexer] ──▶ [Parser LALR(1) + SDT] ──▶ [TAC (cuádruplas)]
                               │                         │
                        tabla_simbolos              ┌─────▼──────┐
                        pila_semántica              │ Optimizador │
                        gestor_errores              └─────┬──────┘
                                                          │
                                                   ┌──────▼───────┐
                                                   │ Backend x86  │
                                                   │ (NASM win64) │
                                                   └──────┬───────┘
                                                          │
                                                   ┌──────▼───────┐
                                                   │  NASM + GCC  │
                                                   │  → .exe      │
                                                   └──────────────┘
```

---

## Ejemplo Completo

```ts
// aventura.ts — Una mini-aventura
var string nombre = "Héroe";
var int vida = 100;

node inicio {
    say("¡Bienvenido, {nombre}!");
    say("Tienes {vida} puntos de vida.");
    choice {
        "Explorar": bosque;
        "Descansar": descanso;
    }
}

node bosque {
    say("Un lobo aparece...");
    set vida = vida - 25;
    say("Vida: {vida}");
    if (vida > 0) {
        goto inicio;
    } else {
        say("Has caído...");
        exit;
    }
}

node descanso {
    say("Descansas junto a la fogata.");
    set vida = vida + 10;
    say("Vida: {vida}");
    goto inicio;
}
```

Compilar y ejecutar:

```powershell
python -m talescriptc aventura.ts -o aventura.exe -O1
.\aventura.exe
```
