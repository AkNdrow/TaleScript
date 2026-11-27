// ============================================================================
// Ejemplo 3: Error Semántico (Fase de Análisis Semántico / Tipos)
// ============================================================================
// Descripción:
// Un error semántico surge cuando el programa es léxica y sintácticamente
// correcto (los tokens y la estructura gramatical son válidos), pero se violan
// las reglas de consistencia lógica, ámbitos o sistema de tipos del compilador.
//
// En este archivo:
// Se produce una incompatibilidad de tipos (E04). Se intenta asignar el valor
// de una variable de tipo 'string' ("Fuego Sagrado") a una variable de tipo
// 'int' (nivel_magia). La pila semántica y la tabla de tipos detectan el conflicto.
//
// Diagnóstico emitido por el Gestor de Errores:
// [E04] Línea 24:0: Tipo incompatible: se esperaba 'int' y se obtuvo 'string'.
// ============================================================================

global int nivel_magia = 5;
global string pergamino = "Fuego Sagrado";

node inicio {
    say "Has entrado a la Gran Biblioteca Arcana.";
    say "Nivel de magia actual: {nivel_magia}";
    
    // ERROR SEMÁNTICO (E04):
    // La variable 'nivel_magia' fue declarada como 'int',
    // pero se le intenta asignar 'pergamino' cuyo tipo es 'string'.
    nivel_magia = pergamino;
    
    end;
}
