// ============================================================================
// TaleScript — Combate Épico contra el Guardián de las Sombras
// ============================================================================
// Demostración completa de:
//  - Variables globales (karma, gloria, oro) y locales (vida, turnos, pociones)
//  - Estructuras cíclicas (while), bifurcaciones condicionales (if/else)
//  - Menú de decisiones por turnos (choice) con desenlaces múltiples:
//      * Atacar hasta la muerte (Final Conquistador)
//      * Perdonar y apelar a la empatía (Final Redención)
//      * Huir cobardemente (Final Supervivencia)
//      * Caer en combate (Final Muerte)
// ============================================================================

global int karma = 0;
global int gloria = 0;
global int oro = 50;

// ----------------------------------------------------------------------------
// Nodo 1: Inicio y Entrada a la Cripta
// ----------------------------------------------------------------------------
node inicio {
    say "Te adentras en la Cripta del Vacío Profundo.";
    say "Frente a ti se yergue Malakar, el Guardián de las Sombras.";
    say "Sus ojos carmesíes te observan fijamente blandiendo una espada de ébano.";
    goto preparacion;
}

// ----------------------------------------------------------------------------
// Nodo 2: Preparación del Enfrentamiento
// ----------------------------------------------------------------------------
node preparacion {
    local int bendicion = 0;
    say "Tienes unos segundos antes de que Malakar ataque.";
    choice {
        "Tomar postura defensiva" {
            say "Adoptas una guardia de hierro.";
            bendicion = 10;
            say "Tu concentración te otorga {bendicion} puntos de serenidad mental.";
            goto combate;
        }
        "Desenvainar sin vacilar y desafiarlo" {
            say "Gritas un juramento de batalla.";
            gloria = gloria + 5;
            goto combate;
        }
        "Intentar dialogar pacíficamente" {
            say "Bajas tu arma e intentas recordar quién fue antes de ser corrupto.";
            karma = karma + 10;
            goto combate;
        }
    }
}

// ----------------------------------------------------------------------------
// Nodo 3: El Combate por Turnos
// ----------------------------------------------------------------------------
node combate {
    local int vida_heroe = 100;
    local int vida_jefe = 80;
    local int pociones = 2;
    local int turno = 1;
    local bool combate_activo = true;

    say "¡Comienza el duelo a muerte contra Malakar!";

    while (combate_activo) {
        say "--- Turno {turno} ---";
        say "Tu Vida: {vida_heroe} | Vida de Malakar: {vida_jefe} | Pociones: {pociones}";

        choice {
            "Ataque con Espada de Luz" {
                say "Descargas un mandoble centellante sobre el Guardián.";
                vida_jefe = vida_jefe - 30;
                if (vida_jefe <= 0) {
                    combate_activo = false;
                    goto victoria_fuerza;
                } else {
                    say "Malakar ruge furioso y contraataca con un tajo sombrío.";
                    vida_heroe = vida_heroe - 20;
                }
            }
            "Beber Poción de Salud" {
                if (pociones > 0) {
                    say "Bebes un elixir revitalizante y recuperas fuerzas.";
                    vida_heroe = vida_heroe + 35;
                    pociones = pociones - 1;
                    say "Malakar aprovecha tu pausa y te asesta un golpe de refilón.";
                    vida_heroe = vida_heroe - 10;
                } else {
                    say "¡Tus frascos están vacíos! Pierdes el turno buscando una poción.";
                    vida_heroe = vida_heroe - 15;
                }
            }
            "Apelar a su alma y perdonar" {
                say "Miras fijamente a sus ojos y le recuerdas su juramento de honor.";
                karma = karma + 15;
                if (karma >= 30) {
                    combate_activo = false;
                    goto victoria_redencion;
                } else {
                    say "Malakar duda un instante... la oscuridad en su pecho flaquea, pero aún ataca débilmente.";
                    vida_heroe = vida_heroe - 5;
                }
            }
            "Huir hacia la salida de la cripta" {
                say "Das media vuelta y corres desesperadamente hacia la luz.";
                combate_activo = false;
                goto desenlace_huida;
            }
        }

        // Comprobación de estado tras el turno
        if (vida_heroe <= 0) {
            combate_activo = false;
            goto derrota;
        }

        turno = turno + 1;
    }
}

// ----------------------------------------------------------------------------
// Nodo 4A: Desenlace — Victoria por la Fuerza
// ----------------------------------------------------------------------------
node victoria_fuerza {
    say "Con un golpe definitivo, la armadura de Malakar se hace pedazos.";
    say "El Guardián cae de rodillas y se disuelve en cenizas negras.";
    gloria = gloria + 50;
    oro = oro + 100;
    say "Has triunfado por la fuerza de tu espada. Gloria acumulada: {gloria}. Oro: {oro}.";
    end;
}

// ----------------------------------------------------------------------------
// Nodo 4B: Desenlace — Victoria por Redención y Perdón
// ----------------------------------------------------------------------------
node victoria_redencion {
    say "La espada de Malakar cae estruendosamente al suelo de piedra.";
    say "La niebla oscura se disipa de sus ojos, revelando su rostro humano y cansado.";
    say "'Gracias por recordar quién era cuando todos me creyeron un monstruo...'";
    say "Malakar te entrega el Amuleto de los Ancestros como signo de gratitud eterna.";
    karma = karma + 50;
    gloria = gloria + 100;
    say "Final Noble: Has salvado un alma sin derramar sangre. Karma final: {karma}.";
    end;
}

// ----------------------------------------------------------------------------
// Nodo 4C: Desenlace — Huida y Escape
// ----------------------------------------------------------------------------
node desenlace_huida {
    say "Logras atravesar las puertas de la cripta mientras las piedras colapsan tras de ti.";
    say "Escapas con vida, pero el peso de la cobardía te acompañará por siempre.";
    oro = oro - 20;
    gloria = gloria - 10;
    say "Conservas tu aliento, pero perdiste parte de tus provisiones y honor.";
    end;
}

// ----------------------------------------------------------------------------
// Nodo 4D: Desenlace — Muerte y Derrota
// ----------------------------------------------------------------------------
node derrota {
    say "Tus fuerzas te abandonan... caes de rodillas sobre la piedra fría.";
    say "La hoja de Malakar reclama tu destino y la oscuridad lo envuelve todo.";
    say "=== GAME OVER ===";
    end;
}
