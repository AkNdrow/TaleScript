// DEMO S01 (sintáctico): condición de 'if' sin paréntesis.
// Error intencional en la línea 7: debe escribirse 'if (oro > 10) { ... }'.
global int oro = 50;

node inicio {
    say "El puente tiene un peaje.";
    if oro > 10 {
        oro = oro - 10;
    }
    say "Cruzas el puente con {oro} monedas.";
    end;
}
