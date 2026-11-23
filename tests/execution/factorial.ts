// ====================================
// Factorial — Cálculo iterativo
// ====================================
// Calcula n! usando nodos y goto.

global int n = 5;
global int resultado = 1;
global int i = 1;

node inicio {
    say "Calculando {n}!";
    goto loop;
}

node loop {
    if (i <= n) {
        resultado = resultado * i;
        i = i + 1;
        goto loop;
    } else {
        goto fin;
    }
}

node fin {
    say "El factorial de {n} es {resultado}.";
    end;
}
