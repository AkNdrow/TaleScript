// DEMO S01 (sintáctico): falta ';' al final de una sentencia.
// Error intencional en la línea 7: la sentencia 'say' no termina en ';'.
global int oro = 50;

node inicio {
    say "Despiertas en una celda oscura.";
    say "Escuchas pasos acercándose"
    goto pasillo;
}

node pasillo {
    say "Corres por el pasillo con {oro} monedas.";
    end;
}
