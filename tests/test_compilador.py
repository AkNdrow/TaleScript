import unittest
from pathlib import Path

from talescriptc.backend.generador_x86_64 import GeneradorX86_64
from talescriptc.intermedio.cuadrupla import Cuadrupla, dividir_por_node
from talescriptc.optimizador.optimizador import Optimizador
from talescriptc.parser.parser import parsear
from talescriptc.semantica.tabla_simbolos import TablaSimbolos


ROOT = Path(__file__).parent


class CompiladorTests(unittest.TestCase):
    def test_semantic_fixtures_report_their_named_code(self):
        fixtures = sorted((ROOT / 'semantic').glob('test_*.ts'))
        self.assertEqual(len(fixtures), 13)

        for fixture in fixtures:
            with self.subTest(fixture=fixture.name):
                expected = fixture.stem.split('_')[1]
                result = parsear(fixture.read_text(encoding='utf-8'))
                codes = result.gestor_errores.codigos()
                self.assertIn(expected, codes)
                self.assertNotIn('S01', codes)

    def test_execution_programs_parse_without_errors(self):
        for fixture in sorted((ROOT / 'execution').glob('*.ts')):
            with self.subTest(fixture=fixture.name):
                result = parsear(fixture.read_text(encoding='utf-8'))
                self.assertTrue(result.exito, result.gestor_errores.dump())

    def test_execution_tac_is_supported_by_backend_at_both_optimization_levels(self):
        for fixture in sorted((ROOT / 'execution').glob('*.ts')):
            result = parsear(fixture.read_text(encoding='utf-8'))
            for level, codigo in (
                ('O0', result.codigo_tac),
                ('O1', Optimizador().optimizar(result.codigo_tac, result.tabla_simbolos)),
            ):
                with self.subTest(fixture=fixture.name, level=level):
                    asm = GeneradorX86_64().generar(
                        codigo, result.tabla_cadenas, result.tabla_simbolos
                    )
                    self.assertNotIn('[WARN] Operador no reconocido', asm)

    def test_reference_fight_optimizes_from_31_to_25_quads(self):
        source = (ROOT / 'intermediate' / 'referencia_inicio_pelea.ts').read_text(encoding='utf-8')
        result = parsear(source)
        self.assertTrue(result.exito, result.gestor_errores.dump())

        GeneradorX86_64().generar(
            result.codigo_tac, result.tabla_cadenas, result.tabla_simbolos
        )
        marco_inicio_o0 = result.tabla_simbolos.obtener_nodo('inicio').tamano_marco
        original = dividir_por_node(result.codigo_tac)
        codigo_optimizado = Optimizador().optimizar(result.codigo_tac, result.tabla_simbolos)
        optimized = dividir_por_node(codigo_optimizado)
        self.assertEqual(dict((name, len(body)) for name, body in original)['pelea'], 31)
        pelea = dict((name, body) for name, body in optimized)['pelea']
        self.assertEqual(len(pelea), 25)
        self.assertFalse(any(cuad.res == 'nivel' for cuad in optimized[0][1]))
        self.assertFalse(any(cuad.op == 'not' for cuad in pelea))
        inicio = result.tabla_simbolos.obtener_nodo('inicio')
        self.assertNotIn('nivel', inicio.tabla_local)
        GeneradorX86_64().generar(
            codigo_optimizado,
            result.tabla_cadenas,
            result.tabla_simbolos,
        )
        self.assertLess(inicio.tamano_marco, marco_inicio_o0)

    def test_constant_folding_uses_signed_64_bit_and_truncating_division(self):
        codigo = [
            Cuadrupla('+', '9223372036854775807', '1', 't4'),
            Cuadrupla('say', 't4', '-', '-'),
            Cuadrupla('/', '-7', '3', 't5'),
            Cuadrupla('say', 't5', '-', '-'),
            Cuadrupla('%', '-7', '3', 't6'),
            Cuadrupla('say', 't6', '-', '-'),
        ]

        optimized = Optimizador().optimizar(codigo)
        self.assertEqual(
            [cuad.arg1 for cuad in optimized if cuad.op == 'say'],
            ['-9223372036854775808', '-2', '-1'],
        )

    def test_call_starts_a_new_block_and_prevents_stale_copy_propagation(self):
        codigo = [
            Cuadrupla('=', '5', '-', 'valor'),
            Cuadrupla('call', '-', '-', 'otro'),
            Cuadrupla('say', 'valor', '-', '-'),
        ]

        optimized = Optimizador().optimizar(codigo)
        say = next(cuad for cuad in optimized if cuad.op == 'say')
        self.assertEqual(say.arg1, 'valor')

    def test_string_addition_is_not_simplified_as_integer_addition(self):
        tabla = TablaSimbolos()
        tabla.entrar_node('inicio')
        tabla.insertar('texto', 'string', 1)
        tabla.salir_node()
        codigo = [
            Cuadrupla('node', '-', '-', 'inicio'),
            Cuadrupla('+', 'texto', '0', 't1'),
            Cuadrupla('say', 't1', '-', '-'),
        ]

        optimized = Optimizador().optimizar(codigo, tabla)
        self.assertTrue(any(cuad.op == '+' for cuad in optimized))

    def test_unreachable_instructions_after_goto_are_removed(self):
        codigo = [
            Cuadrupla('goto', '-', '-', 'L1'),
            Cuadrupla('say', '"inalcanzable"', '-', '-'),
            Cuadrupla('label', '-', '-', 'L1'),
            Cuadrupla('say', '"alcanzable"', '-', '-'),
        ]

        optimized = Optimizador().optimizar(codigo)
        self.assertEqual([cuad.arg1 for cuad in optimized if cuad.op == 'say'], ['"alcanzable"'])


if __name__ == '__main__':
    unittest.main()
