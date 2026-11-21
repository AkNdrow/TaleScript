// ====================================
// Fibonacci — Secuencia iterativa
// ====================================
// Calcula los primeros 10 números de Fibonacci usando nodos y goto.

var int n = 10;
var int a = 0;
var int b = 1;
var int temp = 0;
var int i = 0;

node inicio {
    say("Calculando Fibonacci hasta n = {n}");
    goto loop;
}

node loop {
    if (i < n) {
        say("F({i}) = {a}");
        set temp = a + b;
        set a = b;
        set b = temp;
        set i = i + 1;
        goto loop;
    } else {
        goto fin;
    }
}

node fin {
    say("Secuencia completa.");
    exit;
}
