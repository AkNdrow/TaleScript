// DEMO S01 (sintáctico): bloque sin su llave de cierre '}'.
// Error intencional: al node 'pasillo' (línea 10) le falta su '}' final.
global int oro = 50;

node inicio {
    say "Entras a la cripta.";
    goto pasillo;
}

node pasillo {
    say "Ves dos caminos.";
    choice {
        "Ir a la izquierda" {
            oro = oro + 20;
            say "Encuentras un cofre: ahora tienes {oro} monedas.";
            end;
        }
        "Ir a la derecha" {
            say "Caes en una trampa.";
            end;
        }
    }
