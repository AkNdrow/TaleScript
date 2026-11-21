// ====================================
// Factorial — Cálculo iterativo
// ====================================
// Calcula n! usando nodos y goto.

var int n = 5;
var int resultado = 1;
var int i = 1;

node inicio {
    say("Calculando {n}!");
    goto loop;
}

node loop {
    if (i <= n) {
        set resultado = resultado * i;
        set i = i + 1;
        goto loop;
    } else {
        goto fin;
    }
}

node fin {
    say("El factorial de {n} es {resultado}");
    exit;
}
