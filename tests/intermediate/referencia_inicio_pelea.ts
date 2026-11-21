// Caso de referencia para verificación de TAC
// Dos nodos: inicio y pelea, con variables y choice

var string heroe = "Arturo";
var int fuerza = 80;

node inicio {
    say("El valiente {heroe} se prepara para la batalla.");
    say("Fuerza: {fuerza}");
    choice {
        "Atacar": pelea;
        "Prepararse": inicio;
    }
}

node pelea {
    say("¡{heroe} ataca con fuerza {fuerza}!");
    set fuerza = fuerza - 10;
    if (fuerza > 0) {
        say("¡Victoria!");
    } else {
        say("Derrota...");
    }
    exit;
}
