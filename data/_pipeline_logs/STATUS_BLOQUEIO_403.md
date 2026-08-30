# Status de Bloqueio - Recuperação Jun/Jul/Ago 2026

## Data/Hora
2026-08-26

## Bloqueio Confirmado
O site do TJRN retornou `403 Forbidden` tanto para scraping HTML quanto para RSS:
- HTML: https://tjrn.jus.br/tjrnplay/programastv/noticias-da-hora/
- RSS: https://tjrn.jus.br/tjrnplay/programastv/noticias-da-hora/?format=feed&type=rss

## Estado do Repositório
Os seguintes artefatos **não existem** no repositório atual:
- `src/sanear_drive.py`
- `src/gerar_relatorio_pos_download.py`
- `data/_pipeline_logs/alvos_recuperacao.csv`
- `data/_pipeline_logs/STATUS_BLOQUEIO_403.md` (criado agora para registro)

Arquivos modificados no working tree:
- `data/plano_alocacao.csv`
- `src/downloader_tjrn.py`

## Conclusão
O fluxo completo **não pode ser executado** porque:
1. O acesso ao TJRN está bloqueado (`403`).
2. Os scripts de saneamento e relatório ainda não foram criados no repositório.
