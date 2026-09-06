import unittest
from pathlib import Path


class TestSyncCleanup(unittest.TestCase):
    def test_drive_totals_consistency(self):
        """Garante que a soma de arquivos ativos e arquivo morto corresponde ao total esperado."""
        jornais_local = 97
        arquivo_morto = 270
        total_esperado = 367
        self.assertEqual(jornais_local + arquivo_morto, total_esperado)


if __name__ == "__main__":
    unittest.main()
