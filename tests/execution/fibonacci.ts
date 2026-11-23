global int n = 10;
global int a = 0;
global int b = 1;
global int temporal = 0;
global int i = 0;

node inicio {
    say "Calculando Fibonacci hasta n = " + n;
    while (i < n) {
        say "F({i}) = {a}";
        temporal = a + b;
        a = b;
        b = temporal;
        i = i + 1;
    }
    goto fin;
}

node fin {
    say "Secuencia completa.";
    end;
}
