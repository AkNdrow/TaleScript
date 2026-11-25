// DEMO L01 (léxico): carácter que no pertenece al lenguaje.
// Error intencional en la línea 9: TaleScript usa la palabra 'and', no '&&'.
global int oro = 50;
global int vida = 100;

node inicio {
    say "Llegas a la puerta del castillo.";
    say "Tienes {oro} monedas de oro.";
    if (oro > 10 && vida > 0) {
        say "El guardia acepta tu soborno y te deja pasar.";
    }
    end;
}
