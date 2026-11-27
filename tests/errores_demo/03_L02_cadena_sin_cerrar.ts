// DEMO L02 (léxico): cadena de texto sin comilla de cierre.
// Error intencional en la línea 6: falta la comilla doble (") al final del texto.
global int oro = 50;

node inicio {
    say "Bienvenido al calabozo, aventurero.;
    goto salida;
}

node salida {
    say "Encuentras la salida con {oro} monedas.";
    end;
}
