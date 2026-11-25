// DEMO E04 (semántico): tipo incompatible en una declaración.
// Error intencional en la línea 4: 'vida' es int pero se le asigna una cadena.
global int oro = 50;
global int vida = "cien";

node inicio {
    say "Tienes {oro} monedas.";
    end;
}
