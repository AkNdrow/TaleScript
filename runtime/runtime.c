/*
 * TaleScript Runtime — Primitivas en C (Windows x64 ABI)
 * ======================================================
 * Compilar con: gcc -c runtime.c -o runtime.obj
 * Enlazar con:  gcc -o programa.exe programa.obj runtime.obj
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

#define TS_MAX_OPTS 32

static const char *_menu_opts[TS_MAX_OPTS];
static int         _menu_count = 0;

/* Imprime una cadena con salto de línea y vacía buffer inmediatamente */
void _ts_say(const char *text) {
    if (text) {
        printf("%s\n", text);
        fflush(stdout);
    }
}

/* Convierte un entero de 64 bits a cadena (para say int o cast) */
const char *_ts_int_to_str(int64_t i) {
    char *buf = (char *)malloc(32);
    if (!buf) {
        fprintf(stderr, "[runtime] Error: sin memoria en _ts_int_to_str\n");
        exit(1);
    }
    snprintf(buf, 32, "%lld", (long long)i);
    return buf;
}

/* Concatena string + string */
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
    memcpy(result + la, b, lb + 1);
    return result;
}

/* Concatena string + int */
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

/* Concatena int + string */
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

/* Compara dos cadenas por igualdad */
int64_t _ts_streq(const char *a, const char *b) {
    if (a == b) return 1;
    if (!a || !b) return 0;
    return (strcmp(a, b) == 0) ? 1 : 0;
}

/* Registra una opción del menú choice */
void _ts_add_opt(const char *text) {
    if (_menu_count < TS_MAX_OPTS) {
        _menu_opts[_menu_count++] = text ? text : "(opción vacía)";
    }
}

/* Muestra el menú y devuelve el índice elegido (0-based) */
int64_t _ts_exec_menu(void) {
    int choice = 0;
    int valid  = 0;

    if (_menu_count == 0) {
        return 0;
    }

    printf("\n");
    for (int i = 0; i < _menu_count; i++) {
        printf("  [%d] %s\n", i + 1, _menu_opts[i]);
    }

    while (!valid) {
        printf("\n> ");
        fflush(stdout);
        if (scanf("%d", &choice) != 1) {
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

    _menu_count = 0;
    return (int64_t)(choice - 1);
}

/* Error en tiempo de ejecución por división entre cero */
void _ts_div_zero(void) {
    fprintf(stderr, "\n[runtime] Error fatal: división o módulo entre cero.\n");
    fflush(stderr);
    exit(1);
}

/* Termina la ejecución de la historia */
void _ts_exit(void) {
    fflush(stdout);
    exit(0);
}