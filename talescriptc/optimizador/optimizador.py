"""
Optimizador de Código Intermedio
================================
Pasadas sobre cuádruplas:
  1. Identificación de bloques básicos (algoritmo de líderes)
  2. Plegado de constantes
  3. Propagación de copias
  4. Eliminación de código muerto
  5. Peephole (optimizaciones locales)
"""
from __future__ import annotations
from copy import deepcopy
from talescriptc.intermedio.cuadrupla import Cuadrupla


class BloqueBasico:
    """Un bloque básico: secuencia maximal de instrucciones sin saltos internos."""

    def __init__(self, id: int):
        self.id = id
        self.instrucciones: list[Cuadrupla] = []
        self.sucesores: list[int] = []
        self.predecesores: list[int] = []

    def __repr__(self):
        return f'BB{self.id}[{len(self.instrucciones)} instr]'


class Optimizador:
    """Aplica pasadas de optimización sobre la lista de cuádruplas."""

    def __init__(self):
        self._bloques: list[BloqueBasico] = []

    def optimizar(self, codigo: list[Cuadrupla]) -> list[Cuadrupla]:
        """Ejecuta todas las pasadas de optimización y retorna el código optimizado."""
        codigo = deepcopy(codigo)
        # Pasada 1: Plegado de constantes
        codigo = self._plegado_constantes(codigo)
        # Pasada 2: Propagación de copias
        codigo = self._propagacion_copias(codigo)
        # Pasada 3: Eliminar código muerto
        codigo = self._eliminar_codigo_muerto(codigo)
        # Pasada 4: Peephole
        codigo = self._peephole(codigo)
        return codigo

    # ------------------------------------------------------------------
    # Bloques básicos (algoritmo de líderes)
    # ------------------------------------------------------------------
    def construir_bloques(self, codigo: list[Cuadrupla]) -> list[BloqueBasico]:
        """Construye bloques básicos usando el algoritmo de líderes."""
        if not codigo:
            return []

        # Paso 1: Identificar líderes
        lideres = {0}  # Primera instrucción siempre es líder
        etiquetas_pos: dict[str, int] = {}

        for i, cuad in enumerate(codigo):
            if cuad.es_etiqueta():
                lideres.add(i)
                etiquetas_pos[cuad.res] = i
            if cuad.es_salto():
                # La instrucción destino es líder
                if cuad.res in etiquetas_pos:
                    lideres.add(etiquetas_pos[cuad.res])
                # La instrucción siguiente al salto es líder
                if i + 1 < len(codigo):
                    lideres.add(i + 1)

        # Segunda pasada para resolver etiquetas forward
        for i, cuad in enumerate(codigo):
            if cuad.es_salto() and cuad.res:
                for j, c2 in enumerate(codigo):
                    if c2.es_etiqueta() and c2.res == cuad.res:
                        lideres.add(j)
                        break

        # Paso 2: Crear bloques
        lideres_ord = sorted(lideres)
        bloques = []

        for idx, inicio in enumerate(lideres_ord):
            bb = BloqueBasico(id=idx)
            fin = lideres_ord[idx + 1] if idx + 1 < len(lideres_ord) else len(codigo)
            bb.instrucciones = codigo[inicio:fin]
            bloques.append(bb)

        # Paso 3: Conectar sucesores/predecesores
        for idx, bb in enumerate(bloques):
            if not bb.instrucciones:
                continue
            ultima = bb.instrucciones[-1]
            if ultima.op in ('GOTO', 'goto'):
                # Solo salta al destino
                dest_bb = self._encontrar_bloque(bloques, ultima.res, codigo, lideres_ord)
                if dest_bb is not None:
                    bb.sucesores.append(dest_bb)
            elif ultima.es_salto():
                # Salto condicional: puede ir al destino o caer al siguiente
                dest_bb = self._encontrar_bloque(bloques, ultima.res, codigo, lideres_ord)
                if dest_bb is not None:
                    bb.sucesores.append(dest_bb)
                if idx + 1 < len(bloques):
                    bb.sucesores.append(idx + 1)
            elif ultima.op not in ('EXIT', 'end'):
                # Cae al siguiente bloque
                if idx + 1 < len(bloques):
                    bb.sucesores.append(idx + 1)

        self._bloques = bloques
        return bloques

    def _encontrar_bloque(self, bloques, label, codigo, lideres_ord):
        """Encuentra el índice del bloque que comienza con la etiqueta dada."""
        for i, cuad in enumerate(codigo):
            if cuad.es_etiqueta() and cuad.res == label:
                if i in lideres_ord:
                    return lideres_ord.index(i)
        return None

    # ------------------------------------------------------------------
    # Plegado de constantes
    # ------------------------------------------------------------------
    def _plegado_constantes(self, codigo: list[Cuadrupla]) -> list[Cuadrupla]:
        """Evalúa operaciones sobre constantes conocidas en tiempo de compilación."""
        resultado = []
        for cuad in codigo:
            if cuad.op in ('ADD', 'SUB', 'MUL', 'DIV', '+', '-', '*', '/'):
                a1 = _try_int(cuad.arg1)
                a2 = _try_int(cuad.arg2)
                if a1 is not None and a2 is not None:
                    try:
                        if cuad.op in ('ADD', '+'): val = a1 + a2
                        elif cuad.op in ('SUB', '-'): val = a1 - a2
                        elif cuad.op in ('MUL', '*'): val = a1 * a2
                        elif cuad.op in ('DIV', '/'):
                            if a2 == 0:
                                resultado.append(cuad)
                                continue
                            val = int(a1 / a2)
                        resultado.append(Cuadrupla('=', str(val), '-', cuad.res, tipo1='int', linea=cuad.linea, comentario=cuad.comentario))
                        continue
                    except Exception:
                        pass
            elif cuad.op in ('NEG', 'neg'):
                a1 = _try_int(cuad.arg1)
                if a1 is not None:
                    resultado.append(Cuadrupla('=', str(-a1), '-', cuad.res, tipo1='int', linea=cuad.linea, comentario=cuad.comentario))
                    continue
            resultado.append(cuad)
        return resultado

    # ------------------------------------------------------------------
    # Propagación de copias (por bloque básico)
    # ------------------------------------------------------------------
    def _propagacion_copias(self, codigo: list[Cuadrupla]) -> list[Cuadrupla]:
        """Reemplaza usos de variables copiadas por su origen dentro de cada bloque básico."""
        bloques = self.construir_bloques(codigo)
        codigo_optimizado: list[Cuadrupla] = []

        for bb in bloques:
            copias: dict[str, str] = {}  # destino → origen activo
            for cuad in bb.instrucciones:
                # 1. Aplicar sustitución de copias activas
                nuevo_arg1 = _resolver_cadena_copias(cuad.arg1, copias) if cuad.arg1 else cuad.arg1
                nuevo_arg2 = _resolver_cadena_copias(cuad.arg2, copias) if cuad.arg2 else cuad.arg2
                nueva_cuad = Cuadrupla(op=cuad.op, arg1=nuevo_arg1, arg2=nuevo_arg2, res=cuad.res,
                                       tipo1=cuad.tipo1, tipo2=cuad.tipo2,
                                       linea=cuad.linea, comentario=cuad.comentario)
                codigo_optimizado.append(nueva_cuad)

                # 2. Invalidar copias donde se redefina la variable
                if cuad.res:
                    # Invalidar si cuad.res era destino o fuente de alguna copia
                    copias.pop(cuad.res, None)
                    claves_a_borrar = [k for k, v in copias.items() if v == cuad.res]
                    for k in claves_a_borrar:
                        copias.pop(k, None)

                # 3. Registrar nueva copia simple (= x - y o ASSIGN x _ y)
                if cuad.op in ('ASSIGN', '=') and (cuad.arg2 is None or cuad.arg2 == '-') and cuad.res and nuevo_arg1:
                    if cuad.res != nuevo_arg1:
                        copias[cuad.res] = nuevo_arg1

        return codigo_optimizado

    # ------------------------------------------------------------------
    # Eliminación de código muerto
    # ------------------------------------------------------------------
    def _eliminar_codigo_muerto(self, codigo: list[Cuadrupla]) -> list[Cuadrupla]:
        """Elimina asignaciones a temporales que nunca se usan."""
        # Recolectar todos los usos
        usados: set[str] = set()
        for cuad in codigo:
            if cuad.arg1 and not _es_constante(cuad.arg1):
                usados.add(cuad.arg1)
            if cuad.arg2 and not _es_constante(cuad.arg2):
                usados.add(cuad.arg2)

        # Eliminar asignaciones a temporales no usados
        resultado = []
        for cuad in codigo:
            if (cuad.op in ('ASSIGN', '=', 'ADD', 'SUB', 'MUL', 'DIV', 'NEG',
                            '+', '-', '*', '/', '%', 'neg',
                            'EQ', 'NEQ', 'LT', 'GT', 'LEQ', 'GEQ', 'STREQ',
                            '==', '!=', '<', '<=', '>', '>=',
                            'CONCAT_SS', 'CONCAT_SI', 'CONCAT_IS', 'concat')
                    and cuad.res
                    and cuad.res.startswith('t')
                    and cuad.res not in usados):
                continue  # Muerto
            resultado.append(cuad)
        return resultado

    # ------------------------------------------------------------------
    # Peephole
    # ------------------------------------------------------------------
    def _peephole(self, codigo: list[Cuadrupla]) -> list[Cuadrupla]:
        """Optimizaciones locales (ventana pequeña)."""
        resultado = []
        i = 0
        while i < len(codigo):
            cuad = codigo[i]

            # Patrón: = x - x  → eliminar (auto-asignación)
            if (cuad.op in ('ASSIGN', '=') and (cuad.arg2 is None or cuad.arg2 == '-')
                    and cuad.arg1 == cuad.res):
                i += 1
                continue

            # Patrón: + x 0 res  o  + 0 x res → = x - res
            if cuad.op in ('ADD', '+'):
                if cuad.arg2 == '0':
                    resultado.append(Cuadrupla('=', cuad.arg1, '-', cuad.res, tipo1=cuad.tipo1, linea=cuad.linea))
                    i += 1
                    continue
                if cuad.arg1 == '0':
                    resultado.append(Cuadrupla('=', cuad.arg2, '-', cuad.res, tipo1=cuad.tipo2, linea=cuad.linea))
                    i += 1
                    continue

            # Patrón: * x 1 res → = x - res
            if cuad.op in ('MUL', '*'):
                if cuad.arg2 == '1':
                    resultado.append(Cuadrupla('=', cuad.arg1, '-', cuad.res, tipo1=cuad.tipo1, linea=cuad.linea))
                    i += 1
                    continue
                if cuad.arg1 == '1':
                    resultado.append(Cuadrupla('=', cuad.arg2, '-', cuad.res, tipo1=cuad.tipo2, linea=cuad.linea))
                    i += 1
                    continue
                # * x 0 → = 0 - res
                if cuad.arg2 == '0' or cuad.arg1 == '0':
                    resultado.append(Cuadrupla('=', '0', '-', cuad.res, tipo1='int', linea=cuad.linea))
                    i += 1
                    continue

            # Patrón: - x 0 res → = x - res
            if cuad.op in ('SUB', '-') and cuad.arg2 == '0':
                resultado.append(Cuadrupla('=', cuad.arg1, '-', cuad.res, tipo1=cuad.tipo1, linea=cuad.linea))
                i += 1
                continue

            # Patrón: goto L seguido de label L → solo label L
            if (cuad.op in ('GOTO', 'goto') and i + 1 < len(codigo)
                    and codigo[i + 1].op in ('LABEL', 'label')
                    and codigo[i + 1].res == cuad.res):
                i += 1  # Saltar el GOTO redundante
                continue

            resultado.append(cuad)
            i += 1

        return resultado


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def _try_int(s: str | None) -> int | None:
    if s is None:
        return None
    try:
        return int(s)
    except (ValueError, TypeError):
        return None


def _es_constante(s: str) -> bool:
    if not s:
        return False
    try:
        int(s)
        return True
    except ValueError:
        return s.startswith('_str_')


def _resolver_cadena_copias(nombre: str, copias: dict[str, str]) -> str:
    visitados = set()
    while nombre in copias and nombre not in visitados:
        visitados.add(nombre)
        nombre = copias[nombre]
    return nombre
