# Aprendizado da preparação dos Giros de setembro de 2026

Registro baseado em arquivos e verificações de 02/10/2026. Não representa escuta humana ou aprovação dos programas.

## Falhas observadas e prevenção

1. A última frase transcrita pode ser a vinheta vocal de encerramento do boletim. No Giro0902 N2, o limite85.60 incluía encerramento81.16–85.44. A assinatura da notícia terminava76.36; uma nova peça foi preparada até76.50. Identificar assinatura e primeiro enunciado do encerramento separadamente, sem escolher automaticamente o último segmento ASR.
2. Assinaturas podem ter limites diferentes na transcrição integral e na voz isolada. Giro0904 N4 passou de100.56 para101.15 após transcrição isolada apontar assinatura até100.98 e pausa101.08–101.22. Confrontar timestamps de palavras e energia, preservando a frase completa. Pausa de100ms abaixo de-38dBFS é um indicador, não aprovação.
3. Bordas contíguas exigem escuta. Em Giro0905 N1, Rodrigues termina90.66 e Você começa90.68 na transcrição isolada. Em N2, Almeida e Você compartilham66.32. Manter essas situações pendentes até revisão efetiva; não resolver por fade que apague fonemas.
4. Nomes e anos podem ser transcritos incorretamente. A triagem de Mossoró escreveu2016, enquanto o roteiro original informa2026. Guardar ambas as evidências e comparar a locução antes de decidir se o erro é do reconhecimento ou do áudio.
5. Conferir duração com vinhetas próprias antes de montar. O Giro0901 com quatro notas teria292.448s, abaixo dos300s. Foi selecionada uma quinta pauta de Mossoró na janela correta. Não repetir notas, esticar silêncios ou acelerar fala para enquadrar duração.
6. Datas de criação de documentos não provam publicação de editais. Triunfo informa dez dias úteis da publicação sem data absoluta; Serrinha não informa prazo. Registrar a incerteza editorial sem inventar data final.
7. Executar ASR e Demucs sequencialmente. A tentativa small da triagem complementar falhou na alocação MKL antes de copiar fontes. A retomada base/int8/CPU1 concluiu; seus resultados são triagem e exigem confirmação dos termos sensíveis.

## Regra de retomada e rastreabilidade

Preservar fonte, stem, transcrição e versão anterior; usar diretórios exclusivos. Confirmar processo e status terminal antes de retomar. Reutilizar stems pelo hash da fonte. Registrar retrabalho com hash da nova peça e motivo. A aprovação de cortes precisa corresponder ao áudio efetivamente revisado; não pode ser herdada da autorização de produção ou da revisão de outro programa.

Os cinco manifestos de revisão e23 peças estão em data/processed/GIRO/revisao_pre_montagem_20261002_v02. Todos mantêm revisão.aprovada=false. Validar, montar e sincronizar apenas após cumprir os gates do procedimento PRODUCAO_GIRO_MANIFESTO.md. Manter LOC+OFF; abertura, passagem entre notas e encerramento próprios do GIRO.

## Roteiros consultados

- Mossoró,27/08 B8: https://docs.google.com/document/d/1YyY0uYr7q9ACYQ-AL0I0xbFtPIHElU3Dy5n_9JKwNPY/edit
- Triunfo Potiguar,28/09 B10: https://docs.google.com/document/d/1vm_dckfZZNWuZOovnWQMMCRkg71yH6w-n2e_AWMVakQ/edit
- Serrinha dos Pintos,25/09 B1: https://docs.google.com/document/d/1e7snNwP1Pdit9SgFhhJMN2n1Gyhzm4QknyI_hbPjfao/edit
