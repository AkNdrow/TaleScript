// DEMO E01 (semántico): variable usada sin declararla.
// Error intencional en la línea 7: 'monedas' nunca fue declarada (la variable se llama 'oro').
global int oro = 50;

node inicio {
    say "Encuentras una bolsa en el suelo.";
    monedas = monedas + 5;
    say "Tienes {oro} monedas.";
    end;
}
