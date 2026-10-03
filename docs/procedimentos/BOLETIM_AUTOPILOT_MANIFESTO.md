# BOLETIM — produção por manifesto auditado

Atualização: 02/10/2026. Escopo desta execução: boletins pendentes de setembro e outubro de 2026 até os insumos disponíveis em 02/10. O usuário autorizou autopilot, entrega no Drive e dispensou auditoria humana de áudio. Essa dispensa não substitui as verificações automáticas. NJUD e GIRO conservam processos próprios.

1. Confrontar planilha, documentos atuais e arquivos publicados. Campos de edição vazios ou planilha desatualizada não provam falta de áudio; conferir diretamente cada pasta de destino.
2. Copiar exclusivamente as fontes necessárias para staging BOLETIM e registrar SHA-256 da origem e da cópia. Nunca apagar, mover ou substituir fontes do espelho.
3. Transcrever os offs concatenados com palavras e tempos. Não presumir quantidade de notas por gravação. Neste computador, small/int8/CPU/1 thread/beam 1 funcionou; threads/modelos simultâneos provocaram falhas de memória. Processar serialmente, preservar caches válidos e usar temporários em E:.
4. Selecionar cabeça e off em intervalos explícitos, confrontando texto, roteiro, tentativas abandonadas e retomadas. Nunca estimar cabeça pelo número de palavras. Conferir primeiro e último vocábulo de cada emenda e fim da frase. Excluir claquetes e assinatura institucional conforme receita BOLETIM vigente.
5. Retranscrever a voz recortada antes da montagem. Divergência entre reconhecedores exige exame de trecho curto da fonte e da emenda; uma transcrição isolada não prova erro de fala. Nesta execução: corrigidos 45/425 mutuários, repetição de anos 2007/2009, instruções residuais em B3/B10 de 30/09; trecho curto confirmou 280 clientes em B4.
6. Bloquear divergências editoriais confirmadas na gravação. Não sintetizar nem montar sílabas para alterar valores ou órgãos. Em 01/10 B5, off diz 2ª Vara Cível e roteiro 2ª Câmara Cível. Em 02/10 B2, cabeça diz R$53 mil, mas roteiro/corpo indicam R$53,5 mil. Exigem correção da gravação.
7. Rodar `scripts_pipeline/boletim/processar_boletim_canonico.py --manifesto <JSON> --saida <pasta nova>`. O módulo `boletim.controle_manifesto` valida fonte/roteiro/transcrição/auditoria por hash, intervalos ordenados, programa, data, número, autorização e liberação. A auditoria deve pertencer exatamente à fonte e aos cortes; instruções residuais bloqueiam. Usar nova versão de staging/auditoria/saída após mudar intervalos.
8. Manter receita oficial BOLETIM: abertura, cabeça, passagem, off com BG/ducking, encerramento. Cabeça recebe duração real. Não herdar BG ou divisão do NJUD/GIRO. Exportar MP3 192 kbps/44,1 kHz; medir decodificação integral, duração prevista, LUFS e true peak. Nesta operação: LUFS entre -17,5 e -14,5; true peak no máximo -1 dBTP; tolerância de duração 0,25 s. Registro não declara escuta humana.
9. Entregar apenas masters liberados, com nome `BOLETIM_RADIO_TJRN_DD_MM_AAAA_Bn__RETRANCA.mp3`. Conferir destino antes de criar/enviar. Usar upload único pelo conector e relistar nomes/tamanhos/IDs; não fazer upload e cópia sincronizada simultâneos, evitando duplicatas. Hash local comprova integridade local; nome/tamanho no Drive não constitui verificação remota SHA-256. Se copiar ao espelho, usar somente `sincronizar_boletim`, com reserva exclusiva e hashes.
10. Documentar pendências concretas, diferenças entre versão gravada e escrita, hashes, uploads, retrabalho e verificações. Não declarar mês futuro completo se seus insumos ainda não existem. Aviso externo somente ao destinatário explicitamente identificado e mediante autorização do usuário.

Testes específicos: 12 passaram; incluem fonte alterada, corte sobreposto, autorização ausente, programa incorreto e auditoria de versão anterior. No piloto, montagem, duração, decodificação e loudness passaram antes da expansão do lote.


## Reauditoria solicitada em 02/10/2026 após relato de “repete”

- A ausência de uma palavra em ASR não comprova sua ausência sonora. Trechos com BG produziram transcrições incompletas e erros de reconhecimento; tais resultados são inconclusivos para liberar conteúdo.
- Conferir em conjunto master com vinhetas/BG, voz antes da mixagem e offs originais. Usar etapas sequenciais para evitar pressão de memória. Preservar os masters atuais até confirmar a ocorrência e o corte substituto.
- Procurar também “repetir”, “repita”, “repeti”, “repetindo”, “refaz”, “refazer” e “claquete”. O controle de montagem passa a examinar o texto da auditoria diretamente, além da lista antiga de ocorrências. Termos legítimos como “repetição de indébito” não são instruções de gravação. Os 17 testes específicos passaram após essa ampliação.
- Na voz, executar também passagem sem VAD: fala curta não deve ser descartada automaticamente como silêncio. Trechos próximos de comandos exigem conferência curta normalizada para análise, com reconhecedores distintos quando houver dúvida. Normalização para análise não altera a fonte ou o master.
- Nesta execução, B1 e B8 de 30/09 foram examinados porque as instruções terminavam a aproximadamente 40/60 ms dos cortes, segundo o primeiro ASR. Os trechos atuais foram reconhecidos como fala editorial por base/small. Isso não identifica nem invalida a ocorrência relatada pelo usuário em outro ponto.
- Uma ocorrência relatada pelo usuário permanece aberta até ser localizada no arquivo/tempo correspondente e corrigida com nova evidência. Se o rastreamento automático não a localizar, solicitar nome do arquivo e posição aproximada; não declarar “zero erros” nem alterar cortes por suposição.


## Auditoria dos 200 boletins anteriores — 03/10/2026

O auditor existente `scripts_pipeline/boletim/auditar_boletins.py` recebeu `--auditoria-acervo --saida-auditoria <pasta externa à origem> --modelo base`. O modo recursivo recusa escrita dentro da origem, mantém cópias exclusivas e caches por SHA-256, verifica decodificação, registra duração/loudness e procura instruções e frases consecutivas repetidas com tempos. CPU/int8/1 thread; ASR sem VAD. Resultados negativos não comprovam ausência de falhas, e suspeitas não são correções confirmadas. O lote inicial de três arquivos foi executado antes de ampliar para os 200.

Evidências e continuidade: `data/processed/BOLETIM/auditoria_acervo_setembro_20261003_v01`. A automação `auditar-boletins-anteriores-de-setembro` acompanha a execução autorizada e deve ser pausada após relatório e encaminhamentos possíveis. Não relançar processo com base apenas em estado.json; confirmar o handle ou PID/linha de comando. Retomar caches somente quando comprovada a ausência da execução original.
