"""Optimizaciones de TAC por node y por bloques básicos."""
from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass, field, replace

from talescriptc.intermedio.cuadrupla import Cuadrupla, es_etiqueta_local, es_temporal
from talescriptc.semantica.pila_semantica import a_int64, texto_literal


_TERMINADORES = {'goto', 'ifTrue', 'ifFalse', 'menu', 'end', 'return', 'call'}
_SALTOS_CONDICIONALES = {'ifTrue', 'ifFalse'}
_OPERACIONES_PURO = {
    '+', '-', '*', '/', '%', 'neg', '<', '<=', '>', '>=', '==', '!=',
    'and', 'or', 'not', 'concat', '=',
}
_OPERACIONES_FUSIONABLES = _OPERACIONES_PURO - {'='}
_ENTERO = re.compile(r'-?\d+\Z')


@dataclass
class BloqueBasico:
    """Bloque maximal sin instrucciones de transferencia de control internas."""

    id: int
    instrucciones: list[Cuadrupla] = field(default_factory=list)
    sucesores: list[int] = field(default_factory=list)
    predecesores: list[int] = field(default_factory=list)

    def __repr__(self) -> str:
        return f'BB{self.id}[{len(self.instrucciones)} instr]'


class Optimizador:
    """Optimiza cuádruplas TaleScript, cuyos operadores se escriben en minúsculas."""

    def __init__(self):
        self._bloques: list[BloqueBasico] = []

    def optimizar(self, codigo: list[Cuadrupla], tabla_simbolos=None) -> list[Cuadrupla]:
        """Optimiza cada node independientemente y no modifica la lista recibida."""
        resultado: list[Cuadrupla] = []
        segmento: list[Cuadrupla] = []
        nombre_node: str | None = None

        for cuad in deepcopy(codigo):
            if cuad.es_node():
                if segmento:
                    resultado.extend(self._optimizar_segmento(segmento, nombre_node, tabla_simbolos))
                segmento = [cuad]
                nombre_node = cuad.res
            else:
                segmento.append(cuad)
        if segmento:
            resultado.extend(self._optimizar_segmento(segmento, nombre_node, tabla_simbolos))
        return resultado

    def _optimizar_segmento(self, segmento, nombre_node, tabla_simbolos):
        encabezado = segmento[:1] if segmento and segmento[0].es_node() else []
        codigo = segmento[len(encabezado):]
        locales_no_leidos = self._locales_no_leidos(nombre_node, tabla_simbolos)
        tipos = self._tipos_node(nombre_node, tabla_simbolos)
        inicializaciones_default = self._inicializaciones_default(nombre_node, tabla_simbolos)

        for _ in range(8):
            anterior = tuple(map(str, codigo))
            codigo = self._eliminar_inalcanzable(codigo)
            codigo = self._propagar_y_plegar(codigo)
            codigo = self._peephole(codigo, tipos)
            codigo = self._eliminar_inicializaciones_redundantes(codigo, inicializaciones_default)
            codigo = self._eliminar_codigo_muerto(codigo, locales_no_leidos)
            codigo = self._eliminar_inalcanzable(codigo)
            if tuple(map(str, codigo)) == anterior:
                break

        if nombre_node and tabla_simbolos is not None and locales_no_leidos:
            nodo = tabla_simbolos.obtener_nodo(nombre_node)
            for nombre in locales_no_leidos:
                nodo.tabla_local.pop(nombre, None)
        return encabezado + self._compactar_nombres(codigo)

    @staticmethod
    def _locales_no_leidos(nombre_node, tabla_simbolos) -> set[str]:
        if not nombre_node or tabla_simbolos is None:
            return set()
        nodo = tabla_simbolos.obtener_nodo(nombre_node)
        if nodo is None:
            return set()
        return {
            nombre for nombre, simbolo in nodo.tabla_local.items()
            if not getattr(simbolo, 'es_const', False)
            and not getattr(simbolo, 'seLee', getattr(simbolo, 'se_lee', True))
        }

    @staticmethod
    def _tipos_node(nombre_node, tabla_simbolos) -> dict[str, str]:
        if tabla_simbolos is None:
            return {}
        tipos = {nombre: simbolo.tipo for nombre, simbolo in tabla_simbolos.tabla_global.items()}
        nodo = tabla_simbolos.obtener_nodo(nombre_node) if nombre_node else None
        if nodo is not None:
            tipos.update({nombre: simbolo.tipo for nombre, simbolo in nodo.tabla_local.items()})
        return tipos

    @staticmethod
    def _inicializaciones_default(nombre_node, tabla_simbolos) -> dict[str, str]:
        if not nombre_node or tabla_simbolos is None:
            return {}
        nodo = tabla_simbolos.obtener_nodo(nombre_node)
        if nodo is None:
            return {}
        por_tipo = {'int': ('0', 0), 'bool': ('false', False), 'string': ('""', '')}
        resultado = {}
        for nombre, simbolo in nodo.tabla_local.items():
            literal, valor = por_tipo.get(simbolo.tipo, (None, None))
            if simbolo.es_const or literal is None:
                continue
            inicial = simbolo.valor_inicial
            if inicial is None or (type(inicial) is type(valor) and inicial == valor):
                resultado[nombre] = literal
        return resultado

    def construir_bloques(self, codigo: list[Cuadrupla]) -> list[BloqueBasico]:
        """Aplica el algoritmo de líderes; también resuelve destinos hacia adelante."""
        if not codigo:
            self._bloques = []
            return []

        etiquetas = {cuad.res: i for i, cuad in enumerate(codigo) if cuad.es_etiqueta()}
        lideres = {0}
        for i, cuad in enumerate(codigo):
            if cuad.es_node() or cuad.es_etiqueta():
                lideres.add(i)
            if cuad.op in _TERMINADORES:
                if i + 1 < len(codigo):
                    lideres.add(i + 1)
                if cuad.op in {'goto', *_SALTOS_CONDICIONALES} and es_etiqueta_local(cuad.res):
                    destino = etiquetas.get(cuad.res)
                    if destino is not None:
                        lideres.add(destino)

        inicios = sorted(lideres)
        bloques = [
            BloqueBasico(
                i,
                codigo[inicio:inicios[i + 1] if i + 1 < len(inicios) else len(codigo)],
                [],
                [],
            )
            for i, inicio in enumerate(inicios)
        ]
        bloque_por_etiqueta = {
            cuad.res: numero
            for numero, bloque in enumerate(bloques)
            for cuad in bloque.instrucciones[:1]
            if cuad.es_etiqueta()
        }
        for i, bloque in enumerate(bloques):
            if not bloque.instrucciones:
                continue
            ultima = bloque.instrucciones[-1]
            if ultima.op == 'goto':
                destino = bloque_por_etiqueta.get(ultima.res)
                if destino is not None:
                    bloque.sucesores.append(destino)
            elif ultima.op in _SALTOS_CONDICIONALES:
                destino = bloque_por_etiqueta.get(ultima.res)
                if destino is not None:
                    bloque.sucesores.append(destino)
                if i + 1 < len(bloques):
                    bloque.sucesores.append(i + 1)
            elif ultima.op == 'menu':
                inicio = inicios[i]
                cursor = inicio + len(bloque.instrucciones) - 2
                while cursor >= 0 and codigo[cursor].op == 'opt':
                    destino = bloque_por_etiqueta.get(codigo[cursor].res)
                    if destino is not None:
                        bloque.sucesores.append(destino)
                    cursor -= 1
            elif ultima.op not in {'end', 'return'} and i + 1 < len(bloques):
                bloque.sucesores.append(i + 1)

        for bloque in bloques:
            for sucesor in bloque.sucesores:
                if bloque.id not in bloques[sucesor].predecesores:
                    bloques[sucesor].predecesores.append(bloque.id)
        self._bloques = bloques
        return bloques

    def _propagar_y_plegar(self, codigo: list[Cuadrupla]) -> list[Cuadrupla]:
        resultado: list[Cuadrupla] = []
        for bloque in self.construir_bloques(codigo):
            conocidos: dict[str, str] = {}
            for original in bloque.instrucciones:
                actual = replace(
                    original,
                    arg1=_resolver(original.arg1, conocidos),
                    arg2=_resolver(original.arg2, conocidos),
                )
                actual = _plegar(actual)
                resultado.append(actual)

                if actual.op == 'call':
                    conocidos.clear()
                    continue
                if actual.res != '-':
                    conocidos.pop(actual.res, None)
                    for destino, origen in list(conocidos.items()):
                        if _resolver(origen, conocidos) == actual.res:
                            conocidos.pop(destino, None)
                if actual.op == '=' and actual.res != '-' and actual.arg1 != actual.res:
                    conocidos[actual.res] = actual.arg1
        return resultado

    def _plegado_constantes(self, codigo: list[Cuadrupla]) -> list[Cuadrupla]:
        return [_plegar(cuad) for cuad in codigo]

    def _propagacion_copias(self, codigo: list[Cuadrupla]) -> list[Cuadrupla]:
        return self._propagar_y_plegar(codigo)

    def _peephole(self, codigo: list[Cuadrupla], tipos: dict[str, str] | None = None) -> list[Cuadrupla]:
        tipos = tipos or {}
        usos = _contar_usos(codigo)
        tipos_temporales: dict[str, str] = {}
        resultado: list[Cuadrupla] = []
        i = 0
        while i < len(codigo):
            actual = codigo[i]
            tipo_a = _tipo_operando(actual.arg1, tipos, tipos_temporales)
            tipo_b = _tipo_operando(actual.arg2, tipos, tipos_temporales)

            if (actual.op == 'not' and es_temporal(actual.res) and usos.get(actual.res, 0) == 1
                    and i + 1 < len(codigo)
                    and codigo[i + 1].op in _SALTOS_CONDICIONALES
                    and codigo[i + 1].arg1 == actual.res):
                salto = codigo[i + 1]
                op = 'ifFalse' if salto.op == 'ifTrue' else 'ifTrue'
                resultado.append(replace(salto, op=op, arg1=actual.arg1))
                i += 2
                continue

            if (actual.op in _OPERACIONES_FUSIONABLES and es_temporal(actual.res)
                    and usos.get(actual.res, 0) == 1 and i + 1 < len(codigo)
                    and codigo[i + 1].op == '=' and codigo[i + 1].arg1 == actual.res):
                copia = codigo[i + 1]
                resultado.append(replace(actual, res=copia.res))
                i += 2
                continue

            simplificado = _simplificar_identidad(actual, tipo_a, tipo_b)
            if simplificado is None:
                i += 1
                continue
            if simplificado.op == 'goto' and i + 1 < len(codigo):
                siguiente = codigo[i + 1]
                if siguiente.es_etiqueta() and siguiente.res == simplificado.res:
                    i += 1
                    continue
            resultado.append(simplificado)
            if es_temporal(simplificado.res):
                tipo_resultado = _tipo_resultado(actual, tipo_a, tipo_b)
                if tipo_resultado:
                    tipos_temporales[simplificado.res] = tipo_resultado
            i += 1
        return resultado

    def _eliminar_codigo_muerto(self, codigo, locales_no_leidos=frozenset()):
        resultado = list(codigo)
        while True:
            usados = _contar_usos(resultado)
            nuevo = []
            for cuad in resultado:
                destino_local_muerto = cuad.op == '=' and cuad.res in locales_no_leidos
                resultado_temporal_muerto = (
                    cuad.op in _OPERACIONES_PURO
                    and es_temporal(cuad.res)
                    and usados.get(cuad.res, 0) == 0
                )
                if destino_local_muerto or resultado_temporal_muerto:
                    continue
                nuevo.append(cuad)
            if len(nuevo) == len(resultado):
                return nuevo
            resultado = nuevo

    @staticmethod
    def _eliminar_inalcanzable(codigo: list[Cuadrupla]) -> list[Cuadrupla]:
        if not codigo:
            return []
        optimizador = Optimizador()
        bloques = optimizador.construir_bloques(codigo)
        alcanzables = {0}
        pendientes = [0]
        while pendientes:
            actual = pendientes.pop()
            for sucesor in bloques[actual].sucesores:
                if sucesor not in alcanzables:
                    alcanzables.add(sucesor)
                    pendientes.append(sucesor)
        return [
            instruccion
            for bloque in bloques if bloque.id in alcanzables
            for instruccion in bloque.instrucciones
        ]

    @staticmethod
    def _eliminar_inicializaciones_redundantes(codigo, inicializaciones_default):
        escritas: set[str] = set()
        resultado = []
        for cuad in codigo:
            if cuad.op == '=' and cuad.res in inicializaciones_default:
                literal = inicializaciones_default[cuad.res]
                if cuad.res not in escritas and cuad.arg1 == literal:
                    escritas.add(cuad.res)
                    continue
                escritas.add(cuad.res)
            resultado.append(cuad)
        return resultado

    @staticmethod
    def _compactar_nombres(codigo: list[Cuadrupla]) -> list[Cuadrupla]:
        etiquetas: dict[str, str] = {}
        temporales: dict[str, str] = {}
        for cuad in codigo:
            if cuad.es_etiqueta() and cuad.res not in etiquetas:
                etiquetas[cuad.res] = f'L{len(etiquetas) + 1}'
            for campo in (cuad.arg1, cuad.arg2, cuad.res):
                if es_temporal(campo) and campo not in temporales:
                    temporales[campo] = f't{len(temporales) + 1}'

        mapeo = {**etiquetas, **temporales}
        return [
            replace(cuad,
                    arg1=mapeo.get(cuad.arg1, cuad.arg1),
                    arg2=mapeo.get(cuad.arg2, cuad.arg2),
                    res=mapeo.get(cuad.res, cuad.res))
            for cuad in codigo
        ]


def _resolver(operando: str, conocidos: dict[str, str]) -> str:
    vistos = set()
    while operando in conocidos and operando not in vistos:
        vistos.add(operando)
        operando = conocidos[operando]
    return operando


def _plegar(cuad: Cuadrupla) -> Cuadrupla:
    if cuad.op not in _OPERACIONES_FUSIONABLES:
        return cuad
    valores_conocidos = [_valor_literal(cuad.arg1)]
    if cuad.op not in {'neg', 'not'}:
        valores_conocidos.append(_valor_literal(cuad.arg2))
    if any(valor is None for valor in valores_conocidos):
        return cuad
    try:
        valor = _evaluar(cuad.op, [item[1] for item in valores_conocidos])
    except (ArithmeticError, TypeError, ValueError):
        return cuad
    return replace(cuad, op='=', arg1=_serializar(valor), arg2='-')


def _valor_literal(operando: str):
    if _ENTERO.fullmatch(operando):
        return ('int', int(operando))
    if operando == 'true':
        return ('bool', True)
    if operando == 'false':
        return ('bool', False)
    if len(operando) >= 2 and operando[0] == '"' and operando[-1] == '"':
        return ('string', _desescapar(operando[1:-1]))
    return None


def _evaluar(op: str, valores: list):
    a = valores[0]
    b = valores[1] if len(valores) > 1 else None
    if op == 'neg':
        return a_int64(-a)
    if op == 'not':
        return not a
    if op == 'concat':
        return _a_texto(a) + _a_texto(b)
    if op == '+' and (isinstance(a, str) or isinstance(b, str)):
        return _a_texto(a) + _a_texto(b)
    if op == '+':
        return a_int64(a + b)
    if op == '-':
        return a_int64(a - b)
    if op == '*':
        return a_int64(a * b)
    if op == '/':
        if b == 0:
            raise ZeroDivisionError
        return a_int64(_division_truncada(a, b))
    if op == '%':
        if b == 0:
            raise ZeroDivisionError
        return a - b * _division_truncada(a, b)
    if op == '<':
        return a < b
    if op == '<=':
        return a <= b
    if op == '>':
        return a > b
    if op == '>=':
        return a >= b
    if op == '==':
        return a == b
    if op == '!=':
        return a != b
    if op == 'and':
        return bool(a and b)
    if op == 'or':
        return bool(a or b)
    raise ValueError(f'operador no optimizable: {op}')


def _division_truncada(a: int, b: int) -> int:
    cociente = abs(a) // abs(b)
    return cociente if (a < 0) == (b < 0) else -cociente


def _serializar(valor) -> str:
    if isinstance(valor, bool):
        return 'true' if valor else 'false'
    if isinstance(valor, str):
        return texto_literal(valor)
    return str(valor)


def _a_texto(valor) -> str:
    if isinstance(valor, bool):
        return 'true' if valor else 'false'
    return str(valor)


def _desescapar(texto: str) -> str:
    resultado = []
    i = 0
    escapes = {'n': '\n', 't': '\t', '\\': '\\', '"': '"', '{': '{', '}': '}'}
    while i < len(texto):
        if texto[i] == '\\' and i + 1 < len(texto):
            siguiente = texto[i + 1]
            resultado.append(escapes.get(siguiente, '\\' + siguiente))
            i += 2
        else:
            resultado.append(texto[i])
            i += 1
    return ''.join(resultado)


def _tipo_operando(operando: str, tipos: dict[str, str], temporales: dict[str, str]):
    literal = _valor_literal(operando)
    if literal is not None:
        return literal[0]
    return temporales.get(operando, tipos.get(operando))


def _tipo_resultado(cuad: Cuadrupla, tipo_a: str | None, tipo_b: str | None):
    if cuad.op in {'<', '<=', '>', '>=', '==', '!=', 'and', 'or', 'not'}:
        return 'bool'
    if cuad.op in {'concat'} or (cuad.op == '+' and 'string' in (tipo_a, tipo_b)):
        return 'string'
    if cuad.op in {'+', '-', '*', '/', '%', 'neg'}:
        return 'int'
    if cuad.op == '=':
        return tipo_a
    return None


def _simplificar_identidad(cuad: Cuadrupla, tipo_a=None, tipo_b=None) -> Cuadrupla | None:
    op, a, b = cuad.op, cuad.arg1, cuad.arg2
    if op == '=' and a == cuad.res:
        return None
    if op == '+' and tipo_a == 'int' and tipo_b == 'int' and b == '0':
        return replace(cuad, op='=', arg2='-')
    if op == '+' and tipo_a == 'int' and tipo_b == 'int' and a == '0':
        return replace(cuad, op='=', arg1=b, arg2='-')
    if op == '-' and b == '0':
        return replace(cuad, op='=', arg2='-')
    if op == '*' and b == '1':
        return replace(cuad, op='=', arg2='-')
    if op == '*' and a == '1':
        return replace(cuad, op='=', arg1=b, arg2='-')
    if op == '*' and (a == '0' or b == '0'):
        return replace(cuad, op='=', arg1='0', arg2='-')
    if op == '/' and b == '1':
        return replace(cuad, op='=', arg2='-')
    if op == '%' and b == '1':
        return replace(cuad, op='=', arg1='0', arg2='-')
    return cuad


def _contar_usos(codigo: list[Cuadrupla]) -> dict[str, int]:
    usos: dict[str, int] = {}
    for cuad in codigo:
        for campo in (cuad.arg1, cuad.arg2):
            if campo != '-':
                usos[campo] = usos.get(campo, 0) + 1
    return usos
