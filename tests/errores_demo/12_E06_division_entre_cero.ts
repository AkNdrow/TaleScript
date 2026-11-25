// DEMO E06 (semántico): división entre la constante cero.
// Error intencional en la línea 7: el divisor es 0.
global int oro = 50;

node inicio {
    say "Repartes el tesoro entre tus compañeros.";
    oro = oro / 0;
    say "Te quedan {oro} monedas.";
    end;
}
