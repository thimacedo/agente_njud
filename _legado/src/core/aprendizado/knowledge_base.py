"""
core/aprendizado/knowledge_base.py

Base de conhecimento (KB) que registra o resultado de cada auditoria e
alimenta o Analisador (core/decisao/analisador.py) no PRÓXIMO ciclo de
decisão — nunca no processamento em curso.

Regra de ouro (ver ARQUITETURA_AGENTES_2026.md, seção 7):
    - Só o auditor_service escreve na KB (nunca o agente produtor).
    - O Analisador só LÊ um snapshot no início de um lote.
    - Isso evita: (a) o agente em produção ser interrompido por
      aprendizado, (b) race condition entre escrever e ler.

Armazenamento: SQLite (mesmo padrão de estado_por_arquivo/*.json, porém
centralizado e consultável por agregação).
"""

from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

DB_PADRAO = Path("data/aprendizado/knowledge_base.sqlite3")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS registros (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    decisao_id         TEXT NOT NULL,
    programa           TEXT NOT NULL,           -- njud | giro | boletim
    features_audio     TEXT NOT NULL,           -- JSON: duracao, silencio_inicial, etc.
    estrategia_usada   TEXT NOT NULL,
    usou_stems         INTEGER NOT NULL,
    resultado          TEXT NOT NULL,           -- aprovado | reprovado
    motivo_reprovacao  TEXT,
    versao_regra_auditoria TEXT NOT NULL,
    timestamp          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_kb_programa_estrategia
    ON registros (programa, estrategia_usada);
"""


@dataclass
class RegistroAprendizado:
    decisao_id: str
    programa: str
    features_audio: dict[str, Any]
    estrategia_usada: str
    usou_stems: bool
    resultado: str  # "aprovado" | "reprovado"
    motivo_reprovacao: Optional[str] = None
    versao_regra_auditoria: str = "1"


@dataclass
class EstatisticaEstrategia:
    """Snapshot agregado, consumido pelo Analisador para decidir."""
    programa: str
    estrategia: str
    total: int = 0
    aprovados: int = 0

    @property
    def taxa_sucesso(self) -> float:
        return self.aprovados / self.total if self.total else 0.0


class KnowledgeBase:
    def __init__(self, caminho_db: Path = DB_PADRAO):
        self.caminho_db = Path(caminho_db)
        self.caminho_db.parent.mkdir(parents=True, exist_ok=True)
        with self._conexao() as con:
            con.executescript(_SCHEMA)

    @contextmanager
    def _conexao(self):
        con = sqlite3.connect(str(self.caminho_db), timeout=30)
        try:
            yield con
            con.commit()
        finally:
            con.close()

    def registrar(self, registro: RegistroAprendizado) -> None:
        """
        Chamado exclusivamente pelo auditor_service, de forma assíncrona
        em relação ao agente que produziu o artefato original.
        """
        with self._conexao() as con:
            con.execute(
                """
                INSERT INTO registros
                    (decisao_id, programa, features_audio, estrategia_usada,
                     usou_stems, resultado, motivo_reprovacao,
                     versao_regra_auditoria, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    registro.decisao_id,
                    registro.programa,
                    json.dumps(registro.features_audio, ensure_ascii=False),
                    registro.estrategia_usada,
                    int(registro.usou_stems),
                    registro.resultado,
                    registro.motivo_reprovacao,
                    registro.versao_regra_auditoria,
                    time.strftime("%Y-%m-%dT%H:%M:%S"),
                ),
            )

    def snapshot_estrategias(self, programa: str) -> list[EstatisticaEstrategia]:
        """
        Lido pelo Analisador UMA VEZ por lote (nunca por arquivo), para
        não criar dependência de leitura constante durante o processamento.
        """
        with self._conexao() as con:
            cur = con.execute(
                """
                SELECT estrategia_usada,
                       COUNT(*) AS total,
                       SUM(CASE WHEN resultado = 'aprovado' THEN 1 ELSE 0 END) AS aprovados
                FROM registros
                WHERE programa = ?
                GROUP BY estrategia_usada
                """,
                (programa,),
            )
            return [
                EstatisticaEstrategia(programa=programa, estrategia=row[0], total=row[1], aprovados=row[2])
                for row in cur.fetchall()
            ]

    def motivos_reprovacao_recentes(self, programa: str, limite: int = 50) -> list[str]:
        """Usado por relatórios e pelo processo de consolidação de heurísticas."""
        with self._conexao() as con:
            cur = con.execute(
                """
                SELECT motivo_reprovacao FROM registros
                WHERE programa = ? AND resultado = 'reprovado'
                ORDER BY timestamp DESC LIMIT ?
                """,
                (programa, limite),
            )
            return [row[0] for row in cur.fetchall() if row[0]]
