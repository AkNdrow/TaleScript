global int karma = 0;
global int asesinatos = 0;

node inicio {
    local int nivel = 1;
    say "Despiertas en un lugar oscuro.";
    goto pelea;
}

node pelea {
    local bool terminado = false;
    local int vida = 20;
    do {
        choice {
            "Pelear" { vida = vida - 5; asesinatos = asesinatos + 1; }
            "Perdonar" { karma = karma + 10; terminado = true; }
            "Huir" { terminado = true; }
        }
    } while (not terminado);
    if (karma < 0 or asesinatos >= 10) { say "Te teme."; }
    end;
}