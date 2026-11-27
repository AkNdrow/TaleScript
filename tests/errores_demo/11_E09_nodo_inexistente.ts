// DEMO E09 (semántico): salto a un node que no existe.
// Error intencional en la línea 7: no hay ningún 'node castillo'.
global int oro = 50;

node inicio {
    say "Ves un castillo a lo lejos.";
    goto castillo;
}

node bosque {
    say "Te pierdes en el bosque con {oro} monedas.";
    end;
}
