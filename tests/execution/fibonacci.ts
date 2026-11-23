// ====================================
// Fibonacci — Secuencia iterativa
// ====================================
// Calcula los primeros 10 números de Fibonacci usando nodos y goto.

global int n = 10;
global int a = 0;
global int b = 1;
global int temp = 0;
global int i = 0;

node inicio {
    say "Calculando Fibonacci hasta n = {n}";
    goto loop;
}

node loop {
    if (i < n) {
        say "F({i}) = {a}";
        temp = a + b;
        a = b;
        b = temp;
        i = i + 1;
        goto loop;
    } else {
        goto fin;
    }
}

node fin {
    say "Secuencia completa.";
    end;
}
