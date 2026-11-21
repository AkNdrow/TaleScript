/*
 * TaleScript Runtime — Primitivas en C
 * =====================================
 * Funciones invocadas desde el código ensamblador generado por talescriptc.
 * Compilar con: gcc -c runtime.c -o runtime.obj
 * Enlazar con:  gcc -o programa.exe programa.obj runtime.obj
 *
 * Convención: Microsoft x64 ABI (rcx, rdx, r8, r9 + shadow space)
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

/* -----------------------------------------------------------------------
 * Constantes
 * ----------------------------------------------------------------------- */
#define TS_MAX_OPTS 32
#define TS_STR_BUF  4096

/* -----------------------------------------------------------------------
 * Estado global del menú
 * ----------------------------------------------------------------------- */
static const char *_menu_opts[TS_MAX_OPTS];
static int         _menu_count = 0;

/* -----------------------------------------------------------------------
 * _ts_say — Imprime una cadena con salto de línea
 * Firma ASM: rcx = const char* texto
 * ----------------------------------------------------------------------- */
void _ts_say(const char *text) {
    if (text) {
        printf("%s\n", text);
    }
}

/* -----------------------------------------------------------------------
 * _ts_concat_ss — Concatena dos cadenas (string + string)
 * Firma ASM: rcx = const char* a,  rdx = const char* b
 * Retorna:   rax = const char* resultado (heap-allocated)
 * ----------------------------------------------------------------------- */
const char *_ts_concat_ss(const char *a, const char *b) {
    if (!a) a = "";
    if (!b) b = "";
    size_t la = strlen(a);
    size_t lb = strlen(b);
    char *result = (char *)malloc(la + lb + 1);
    if (!result) {
        fprintf(stderr, "[runtime] Error: sin memoria en _ts_concat_ss\n");
        exit(1);
    }
    memcpy(result, a, la);
    memcpy(result + la, b, lb + 1);  /* incluye '\0' */
    return result;
}

/* -----------------------------------------------------------------------
 * _ts_concat_si — Concatena cadena + entero (string + int)
 * Firma ASM: rcx = const char* s,  rdx = int64_t i
 * Retorna:   rax = const char* resultado
 * ----------------------------------------------------------------------- */
const char *_ts_concat_si(const char *s, int64_t i) {
    if (!s) s = "";
    char num_buf[32];
    snprintf(num_buf, sizeof(num_buf), "%lld", (long long)i);
    size_t ls = strlen(s);
    size_t ln = strlen(num_buf);
    char *result = (char *)malloc(ls + ln + 1);
    if (!result) {
        fprintf(stderr, "[runtime] Error: sin memoria en _ts_concat_si\n");
        exit(1);
    }
    memcpy(result, s, ls);
    memcpy(result + ls, num_buf, ln + 1);
    return result;
}

/* -----------------------------------------------------------------------
 * _ts_concat_is — Concatena entero + cadena (int + string)
 * Firma ASM: rcx = int64_t i,  rdx = const char* s
 * Retorna:   rax = const char* resultado
 * ----------------------------------------------------------------------- */
const char *_ts_concat_is(int64_t i, const char *s) {
    if (!s) s = "";
    char num_buf[32];
    snprintf(num_buf, sizeof(num_buf), "%lld", (long long)i);
    size_t ln = strlen(num_buf);
    size_t ls = strlen(s);
    char *result = (char *)malloc(ln + ls + 1);
    if (!result) {
        fprintf(stderr, "[runtime] Error: sin memoria en _ts_concat_is\n");
        exit(1);
    }
    memcpy(result, num_buf, ln);
    memcpy(result + ln, s, ls + 1);
    return result;
}

/* -----------------------------------------------------------------------
 * _ts_streq — Compara dos cadenas por igualdad
 * Firma ASM: rcx = const char* a,  rdx = const char* b
 * Retorna:   rax = 1 si iguales, 0 si no
 * ----------------------------------------------------------------------- */
int64_t _ts_streq(const char *a, const char *b) {
    if (a == b) return 1;
    if (!a || !b) return 0;
    return (strcmp(a, b) == 0) ? 1 : 0;
}

/* -----------------------------------------------------------------------
 * _ts_add_opt — Agrega una opción al menú interactivo
 * Firma ASM: rcx = const char* texto
 * ----------------------------------------------------------------------- */
void _ts_add_opt(const char *text) {
    if (_menu_count < TS_MAX_OPTS) {
        _menu_opts[_menu_count++] = text ? text : "(opción vacía)";
    }
}

/* -----------------------------------------------------------------------
 * _ts_exec_menu — Muestra el menú y retorna el índice seleccionado (0-based)
 * Firma ASM: (sin argumentos)
 * Retorna:   rax = índice seleccionado (0-based)
 * ----------------------------------------------------------------------- */
int64_t _ts_exec_menu(void) {
    int choice = 0;
    int valid  = 0;

    printf("\n");
    for (int i = 0; i < _menu_count; i++) {
        printf("  [%d] %s\n", i + 1, _menu_opts[i]);
    }

    while (!valid) {
        printf("\n> ");
        fflush(stdout);
        if (scanf("%d", &choice) != 1) {
            /* Limpiar entrada inválida */
            int c;
            while ((c = getchar()) != '\n' && c != EOF);
            printf("  Ingresa un número entre 1 y %d.\n", _menu_count);
            continue;
        }
        if (choice >= 1 && choice <= _menu_count) {
            valid = 1;
        } else {
            printf("  Opción inválida. Ingresa un número entre 1 y %d.\n", _menu_count);
        }
    }

    _menu_count = 0;  /* Reset para el próximo menú */
    return (int64_t)(choice - 1);
}

/* -----------------------------------------------------------------------
 * _ts_exit — Termina el programa con código 0
 * Firma ASM: (sin argumentos relevantes; rcx ignorado)
 * ----------------------------------------------------------------------- */
void _ts_exit(void) {
    exit(0);
}
