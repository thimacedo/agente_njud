# BLOQUEADO - 2026-09-09
# Este script viola a Regra #1 do PROCEDIMENTO_PADRAO.md:
# "Drive H: é somente leitura para todo o pipeline, EXCETO src/sync/drive.py"
# Este script Move-Item e Remove-Item diretamente no H:.
# NÃO EXECUTAR. Ver DECISOES.md Item 15 e AUDITORIA_SISTEMA_2026-09-09.md

exit 1
