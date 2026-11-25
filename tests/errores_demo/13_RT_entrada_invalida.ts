// DEMO de errores en TIEMPO DE EJECUCIÓN (este programa compila sin errores).
// Al jugar el .exe, prueba escribir: "abc", "7", "" (vacío) y luego "1".
// El runtime rechaza cada entrada inválida con un mensaje detallado.
global int oro = 50;

node inicio {
    say "Un guardia te cierra el paso.";
    choice {
        "Pagarle 10 monedas" {
            oro = oro - 10;
            say "Te deja pasar. Te quedan {oro} monedas.";
            end;
        }
        "Huir" {
            say "Escapas por el bosque.";
            end;
        }
    }
}
