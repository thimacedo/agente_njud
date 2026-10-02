# Aprendizado e processo melhorado — NJUD setembro 2026

Atualizado em 01/10/2026. A avaliação é iterativa: a v03 foi encaminhada a retrabalho após escuta do usuário; a v04 está pendente de aprovação sonora/editorial. Não é possível garantir ausência absoluta de erros: o processo impede falhas conhecidas de avançarem silenciosamente e mantém meios para detectar e refazer as demais.

## Correção após a auditoria do usuário — v04

A v03 foi encaminhada a retrabalho por resíduo nas cabeças, fim de frase cortado e música durante as notícias. Isso mostra que correlação da vinheta e decodificação sem erros não bastam para aprovar a edição.

A v04 usa stems de voz dos quatro boletins individuais, antes de recortar e montar. Voz e acompanhamento foram preservados em WAV, com hashes de origem/modelo e sem mudança de duração. O BG e as passagens NJUD são adicionados depois. O sistema não aceita novos boletins misturados para produção sem stems; o método de referência permanece disponível apenas para fontes explicitamente confirmadas sem BG.

As cabeças foram marcadas pela energia da voz isolada e ampliadas até o término das palavras. O final da última nota passou de 97,690s para 98,165s na origem: a nova transcrição identifica “2025” até 97,890s, e a forma de onda ainda contém fala depois desse tempo. A v04 corta na pausa anterior à assinatura, com respiro de 120ms antes das vinhetas. As demais transições também foram revistas. Marcações numéricas continuam candidatas até escuta: não são garantia perceptiva.

A rotina limita o BG à escalada, com saída suave nos 80ms finais. Um teste com áudio sintético confirma, por igualdade das amostras, que o BG não é somado aos corpos das notícias. Foram aprovados 36 testes de regressão; o novo bloqueio de fontes sem stems também foi conferido. A exportação real da v04 foi decodificada sem erro, em 285,189s (4min45,2s). Não é master aprovado.

Reprodução: scripts_pipeline/njud/stems_runner.py executa a separação no ambiente isolado de config/njud_stems_runtime.json, sem alterar .venv_pipeline. O módulo njud.stems faz a separação e registra os stems; njud.controle_producao prepara os cortes de voz; montagem_jornais.py gera o candidato. Manifesto de exemplo: manifesto_piloto_canonico_v04.json. Arquivos de auditoria: canonico_v04/correcoes.json, canonico_v04/medicoes_residuos.json e stems_v04/B*_fim_refinado.json.

As três causas reportadas na v03 foram gravadas como eventos de retrabalho no aprendizado. O resumo deve separar aprovação técnica de aprovação sonora. Nunca expandir um lote por métricas apenas; verificar também entradas/saídas das cabeças e corpos, a frase final, ausência de BG durante notas e artefatos do separador.

## Histórico: evidências dos pilotos anteriores

- Dez edições locais, 1949–1958, com quarenta boletins copiados e decodificados sem erro. Fontes preservadas e cópias conferidas por SHA-256.
- A marcação da fala deixou restos da passagem dos boletins no início de três notícias. A cauda identificada alcançava cerca de 0,54–0,57 s após o começo marcado da fala; no quarto boletim, cerca de 0,08 s.
- A passagem de referência apresentou correlação normalizada de 0,956–0,974 nos quatro boletins. Seu cancelamento alinhado reduziu a energia das janelas instrumentais de calibração em 23,84–26,63 dB. Isso mede a limpeza nesses intervalos, não comprova sozinho a qualidade perceptiva da voz.
- A limpeza ocorreu nos boletins individuais, antes dos cortes e da montagem. O BG da escalada e as passagens NJUD foram adicionados depois.
- Pilotos v01/v02 preservados. A versão v03 foi gerada pela rotina canônica melhorada, em 284,5 s, exportada e decodificada sem erro.
- Foram encontrados: corte proporcional de 30% sem evidência, montador auxiliar que repetia boletins inteiros, ordenação numérica divergente da ordem editorial e uso da data dos boletins como data da edição. Essas rotas foram bloqueadas/substituídas na entrada canônica.

## Processo para replicar

1. Conferir a grade: uma edição por data; manter data de edição e data dos boletins separadas. Escolher somente um roteiro para 01/09.
2. Copiar e conferir fontes; registrar hash, origem, referência de passagem e versão. Nunca mover, excluir ou sobrescrever a origem.
3. Transcrever e marcar os limites da manchete, corpo e assinatura com evidência. Marcações propostas exigem revisão; nenhuma proporção fixa será usada como substituto.
4. Detectar a passagem na transição marcada. Para referência correspondente, usar correlação >= 0,90, ganho estimado em pelo menos 200 ms sem voz e redução instrumental >= 15 dB. Esses limites são uma política inicial conservadora, validada neste piloto; não são garantia universal.
5. Se a referência não corresponder, faltar janela instrumental ou a limpeza falhar, registrar retrabalho. Testar stems no boletim individual ou no trecho com contexto, antes da montagem, preservando voz e acompanhamento para comparação. A separação de stems está integrada na política njud-pre-montagem-2; fontes misturadas exigem essa etapa antes dos cortes.
6. Gerar boletins limpos e cortes em WAV. Conferir as primeiras/últimas palavras e resíduo musical. Hashes dos cortes vinculam as peças ao manifesto.
7. Montar pelo manifesto na ordem editorial, incluindo BG, abertura, passagens entre corpos e encerramento do NJUD. A data do arquivo vem da edição. O montador é único: montagem_jornais.py.
8. Exportar como CANDIDATO, versão nova, limite de cinco minutos, verificar decodificação e preservar intermediário. Nenhum candidato vira master automaticamente.
9. Auditar integralmente cada programa: cortes, voz, resíduo, conteúdo, ordem, data, apresentação do roteiro e duração. Se houver falha, registrar causa e gerar nova versão só das peças afetadas.
10. Auditar o conjunto ao final, revisando duplicidades, faltas, pendências e versões. A revisão editorial da apresentação continua necessária no piloto; ele não incorpora a apresentação específica do roteiro.

## Aprendizado do sistema

A revisão grava eventos imutáveis com hash do áudio, resultado, auditor, motivo, verificações, data e política. A reclamação sobre resíduos da v01 já foi registrada como retrabalho, atribuída ao relato do usuário. Não há aprovação sonora fictícia.

O resumo agrega causas de retrabalho e aprovações. Ao encontrar causa recorrente, revisar a política, criar versão nova e validar em piloto antes de ampliar. O sistema não altera parâmetros sozinho nem treina modelos neste mecanismo. A aprendizagem é operacional e auditável, sustentada por correções verificadas.

## Uso da rotina

Na raiz DIVISOR, usar o Python de .venv_pipeline com scripts_pipeline no PYTHONPATH (ou o wrapper existente). Preparação: módulo njud.controle_producao, comando preparar, manifesto de entrada e pasta nova NJUD_numero. Montagem: montagem_jornais.py, pasta preparada e pasta de saída. Revisão: njud.controle_producao revisar com arquivo, pasta de eventos, auditor, resultado e motivo; aprovação também exige um arquivo de verificações completo. Resumo: comando aprendizado seguido da pasta de eventos.

Exemplos reais estão em manifesto_piloto_canonico_v03.json e canonico_v03/NJUD_1950/manifesto_producao.json dentro deste lote. O módulo informa erros e interrompe casos sem evidência; o comando de montagem devolve falha se qualquer edição do lote falhar.

## Verificação e limites

36 testes passaram, cobrindo a nova limpeza e os bloqueios, detecção de assinatura, integração do backend e roteiros em ordem invertida. Piloto real executado do manifesto até o MP3 candidato. Os testes não substituem escuta, nem avaliam todos os boletins do mês. Os demais lotes seguem preparados e devem passar pela mesma etapa de marcação/limpeza/auditoria.

A entrada canônica agora exige manifesto_producao.json. Chamadas antigas sem esse arquivo são bloqueadas, inclusive as feitas por processos auxiliares/backend; devem ser precedidas da preparação. O montador auxiliar que duplicava os áudios foi desativado. Alterações anteriores existentes no projeto foram preservadas; cópias das principais rotinas anteriores à melhoria ficam em backup_rotinas_antes_melhoria.

