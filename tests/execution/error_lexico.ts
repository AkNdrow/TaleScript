// ============================================================================
// Ejemplo 1: Error Léxico (Fase de Análisis Léxico)
// ============================================================================
// Descripción:
// Un error léxico se produce cuando el código fuente contiene caracteres o
// secuencias que no pertenecen al alfabeto formal de TaleScript o que no pueden
// ser agrupados en ningún token válido (palabra reservada, identificador,
// número, operador o delimitador).
//
// En este archivo:
// Se utiliza el símbolo '@' (arroba). Dado que '@' no es un operador ni un
// símbolo permitido en TaleScript, el analizador léxico (PLY lex) lo rechaza
// inmediatamente y el Gestor de Errores emite el diagnóstico L01.
//
// Diagnóstico emitido por el Gestor de Errores:
// [L01] Línea 24:5: Carácter no reconocido '@'.
// ============================================================================

global int oro = 150;

node inicio {
    say "Bienvenido a la tienda arcana del reino.";
    say "Tu bolsa contiene {oro} monedas de oro.";
    
    // ERROR LÉXICO (L01): Carácter '@' no admitido en el vocabulario de TaleScript
    @
    
    say "Adquiriendo poción de maná...";
    end;
}
