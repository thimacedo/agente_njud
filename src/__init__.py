"""
DIVISOR — Pipeline de Boletins de Rádio TJRN
=============================================

Estrutura reorganizada:

src/
├── cli/          # Pontos de entrada (iniciar_ciclo, monitor, dashboard)
├── core/         # Motor principal (dispatcher, divisor_boletins, processo_unico)
├── services/     # Integração com dados e Drive (gerar_plano, copiar, sincronizar)
├── utils/        # Ferramentas auxiliares (monitoramento, auditoria, testes)
└── scripts/      # Scripts de tarefa única (.sh)
"""

__version__ = "2026.08.24"
