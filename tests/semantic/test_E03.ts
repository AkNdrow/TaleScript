// E03: una variable local no puede sombrear una global
global int puntos = 0;

node inicio {
    local int puntos = 5;
    end;
}
