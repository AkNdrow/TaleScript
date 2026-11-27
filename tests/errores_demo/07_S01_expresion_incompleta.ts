// DEMO S01 (sintáctico): expresión incompleta.
// Error intencional en la línea 7: falta el valor después de '+'.
global int oro = 50;

node inicio {
    say "Un mercader te ofrece un trato.";
    oro = oro + ;
    say "Ahora tienes {oro} monedas.";
    end;
}
