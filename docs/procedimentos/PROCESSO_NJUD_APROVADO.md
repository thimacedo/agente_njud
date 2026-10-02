# Processo NJUD aprovado — 01/10/2026

Piloto 1950, edição 03/09/2026, v04 aprovado expressamente pelo usuário. Cópia do master arquivada sem alterar candidatos ou fontes.

Fluxo: inventário e cópia com hash → transcrição/marcação → stems nos boletins individuais → revisão dos limites na voz isolada, incluindo últimas palavras → quatro cabeças/quatro corpos em WAV → montagem canônica com BG apenas na escalada e passagens NJUD → normalização → decodificação/duração → auditoria do lote → retrabalho em versão nova.

Stems: scripts_pipeline/njud/stems_runner.py com config/njud_stems_runtime.json. Preparação: njud.controle_producao. Montagem: montagem_jornais.py. Não usar o montador auxiliar antigo nem o fallback proporcional. Ordem, número e data de edição vêm do manifesto. A receita validada inclui respiro após as notas e BG terminando antes dos corpos. Limite destas edições: cinco minutos; não cortar frases para caber.

Lote 1: 1949 (02/09), 1951 (04/09), 1952 (08/09), 1953 (09/09). O 1950 já está aprovado. Lote 2: 1954–1958. Primeira etapa do lote 1: transcrição e stems das 16 notas, usando os módulos existentes. Limites são propostas até a revisão da voz isolada. Não aprovar automaticamente as próximas edições pela aprovação do piloto.

Um registro por edição acompanha estágio, arquivos, hashes, medidas e falhas. Causas de retrabalho e aprovações são gravadas por versão no aprendizado. Fontes, stems, intermediários e versões anteriores são preservados. A sincronização/publicação não faz parte desta execução.

O registro src/registro_programas.py citado em documentos históricos não existe na árvore ativa; foi localizado apenas em _legado. A rotina NJUD confirmada está em scripts_pipeline/njud e montagem_jornais.py, conforme decisões 22/23 e aprovação v04. Nenhum caminho GIRO/BOLETIM foi usado para montagem.
