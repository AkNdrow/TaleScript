// ============================================================================
// Ejemplo 2: Error Sintáctico (Fase de Análisis Sintáctico / Parser)
// ============================================================================
// Descripción:
// Un error sintáctico ocurre cuando los tokens reconocidos son válidos por sí
// mismos, pero su orden o combinación infringe las reglas de la Gramática Libre
// de Contexto (GLC) implementada en el parser LALR(1) (PLY yacc).
//
// En este archivo:
// La sentencia condicional 'if' omite los paréntesis obligatorios '(' y ')'
// en la expresión lógica:
//     Regla sintáctica formal: 'if' '(' expr ')' '{' sentencias '}'
// Al encontrar el identificador 'vida_guerrero' sin el paréntesis de apertura '(',
// el parser detecta la violación gramatical y el Gestor de Errores emite S01.
//
// Diagnóstico emitido por el Gestor de Errores:
// [S01] Línea 26:8: Error de sintaxis: se encontró ID ('vida_guerrero'); se esperaba LPAREN.
// ============================================================================

global int vida_guerrero = 80;

node inicio {
    say "El guerrero desenvaina su espada frente a la mazmorra...";
    
    // ERROR SINTÁCTICO (S01):
    // Falta '(' antes de la condición.
    // En TaleScript la sintaxis estricta es: if (vida_guerrero > 0)
    if vida_guerrero > 0 {
        say "El guerrero está listo para la batalla.";
    }
    
    end;
}
