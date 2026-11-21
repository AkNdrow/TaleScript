// ====================================
// Historia Interactiva — Ejemplo base
// ====================================
// Programa TaleScript con nodos, choices, variables e interpolación.

var string nombre = "Héroe";
var int vida = 100;

node inicio {
    say("Bienvenido, {nombre}. Tu aventura comienza aquí.");
    say("Tienes {vida} puntos de vida.");
    choice {
        "Explorar el bosque": bosque;
        "Ir a la taberna": taberna;
    }
}

node bosque {
    say("Te adentras en un bosque oscuro...");
    say("¡Un dragón aparece!");
    set vida = vida - 30;
    say("El dragón te ataca. Vida restante: {vida}");
    choice {
        "Luchar contra el dragón": pelea;
        "Huir a la taberna": taberna;
    }
}

node taberna {
    say("Entras a una taberna cálida.");
    say("Un anciano te ofrece una poción.");
    set vida = vida + 20;
    say("Vida recuperada. Vida actual: {vida}");
    goto inicio;
}

node pelea {
    say("¡Luchas valientemente contra el dragón!");
    if (vida > 50) {
        say("¡Has derrotado al dragón! ¡Victoria!");
    } else {
        say("El dragón es demasiado fuerte...");
        say("Has caído en batalla.");
    }
    exit;
}
