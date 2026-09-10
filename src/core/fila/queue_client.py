"""
core/fila/queue_client.py

Abstração única sobre a fila usada entre agente produtor, serviço de
auditoria e sincronização com H:. Implementação em SQLite (sem
dependência externa, mesmo padrão já usado em estado_por_arquivo/*.json,
mas centralizado e consultável).

Se no futuro for necessário trocar por pgmq/Postgres (Sentinela já usa
pgmq em outro projeto do Thiago), só este arquivo muda — nenhum agente
ou serviço que o consome precisa ser alterado.

Filas usadas pela arquitetura (ver ARQUITETURA_AGENTES_2026.md):
    - "pendente_auditoria"   : publicado pelo agente produtor
    - "pronto_para_sync"     : publicado pelo auditor_service quando aprova
    - "requeue"              : publicado pelo auditor_service quando reprova
    - "aprendizado_pendente" : publicado pelo auditor_service, consumido
                               de forma assíncrona pela knowledge_base
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

DB_PADRAO = Path("data/fila/fila.sqlite3")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS mensagens (
    id            TEXT PRIMARY KEY,
    fila          TEXT NOT NULL,
    payload       TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'pendente',  -- pendente | em_processo | concluida
    criada_em     TEXT NOT NULL,
    consumida_em  TEXT
);
CREATE INDEX IF NOT EXISTS idx_fila_status ON mensagens (fila, status);
"""


@dataclass
class Mensagem:
    id: str
    fila: str
    payload: dict[str, Any]
    criada_em: str


class FilaClient:
    """
    Cliente simples de fila com semântica "at-least-once".

    Uso típico do produtor:
        fila = FilaClient()
        fila.publicar("pendente_auditoria", {"artefato": ..., "decisao_id": ...})

    Uso típico do consumidor (serviço de auditoria, roda em processo separado):
        fila = FilaClient()
        for msg in fila.consumir("pendente_auditoria"):
            resultado = auditar(msg.payload)
            fila.confirmar(msg.id)
    """

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

    def publicar(self, fila: str, payload: dict[str, Any]) -> str:
        """Publica uma mensagem na fila. Não bloqueia o chamador."""
        msg_id = uuid.uuid4().hex
        with self._conexao() as con:
            con.execute(
                "INSERT INTO mensagens (id, fila, payload, status, criada_em) "
                "VALUES (?, ?, ?, 'pendente', ?)",
                (msg_id, fila, json.dumps(payload, ensure_ascii=False), _agora()),
            )
        return msg_id

    def consumir(self, fila: str, lote: int = 20) -> list[Mensagem]:
        """
        Reserva até `lote` mensagens pendentes da fila (marca como
        'em_processo') e as retorna. Chamado pelo processo consumidor,
        de forma independente e assíncrona em relação ao produtor.
        """
        with self._conexao() as con:
            cur = con.execute(
                "SELECT id, fila, payload, criada_em FROM mensagens "
                "WHERE fila = ? AND status = 'pendente' "
                "ORDER BY criada_em ASC LIMIT ?",
                (fila, lote),
            )
            linhas = cur.fetchall()
            ids = [linha[0] for linha in linhas]
            if ids:
                con.executemany(
                    "UPDATE mensagens SET status = 'em_processo' WHERE id = ?",
                    [(i,) for i in ids],
                )
        return [
            Mensagem(id=i, fila=f, payload=json.loads(p), criada_em=c)
            for (i, f, p, c) in linhas
        ]

    def confirmar(self, msg_id: str) -> None:
        """Marca mensagem como concluída (removida do fluxo ativo)."""
        with self._conexao() as con:
            con.execute(
                "UPDATE mensagens SET status = 'concluida', consumida_em = ? WHERE id = ?",
                (_agora(), msg_id),
            )

    def devolver(self, msg_id: str) -> None:
        """Devolve uma mensagem reservada de volta para 'pendente' (ex: erro no consumo)."""
        with self._conexao() as con:
            con.execute(
                "UPDATE mensagens SET status = 'pendente' WHERE id = ?",
                (msg_id,),
            )

    def tamanho(self, fila: str, status: str = "pendente") -> int:
        with self._conexao() as con:
            cur = con.execute(
                "SELECT COUNT(*) FROM mensagens WHERE fila = ? AND status = ?",
                (fila, status),
            )
            return cur.fetchone()[0]


def _agora() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")
