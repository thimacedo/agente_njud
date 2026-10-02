# Processo GIRO por manifesto

Ponto de entrada: `scripts_pipeline/executar_programa.py` → `giro/processo.py`.
Não depende de `src/giro`, `src/regras` ou preflight legados. A raiz vem do script,
de `DIVISOR_BASE_DIR` ou de `--raiz` antes da ação. Não altera NJUD/BOLETIM.

## Planejamento sem produção

```powershell
python scripts_pipeline/executar_programa.py planejar --ano 2026 --mes 9
```

Imprime JSON: cinco terças de setembro, janelas [X-6,X-1], arquivos por data,
datas sem arquivos e duplicatas possíveis. Não gera cache/lock/áudio nem copia
fontes. Os defaults são `GIRO/input` e a pasta histórica `setembro`; para outros
acervos, passe `--fonte <pasta>` uma ou mais vezes. Nenhuma fonte H: é acessada
implicitamente. Nomes irregulares ficam pendentes; nunca corrigidos por suposição.
Arquivos concatenados sem ano precisam de confirmação editorial. Falta de arquivo
em um dia não prova falta de produção; a contagem de arquivos não é aprovação.

Salvar só o relatório é uma operação explícita, sem sobrescrita:

```powershell
python scripts_pipeline/executar_programa.py planejar --ano 2026 --mes 9 --salvar data/planos/GIRO/setembro-2026.json
python scripts_pipeline/executar_programa.py manifesto data/planos/GIRO/setembro-2026.json --codigo 0902 --salvar data/planos/GIRO/0902-v01.json
```

O rascunho inicia sem notas e NÃO passa pelo gate de montagem. Não migra planos
anteriores nem altera datas históricas. `gerar_planejamento.py` é um alias seguro.

## Preparação editorial e sonora

Preencher `notas` com 4–6 peças, na ordem editorial. Priorizar interior RN;
outros estados/ambíguas ficam fora. Natal exige `autorizacoes.incluir_natal: true`
e justificativa na nota. A ferramenta valida decisões explícitas; não promete
classificação geográfica automática nem transcrição automática.

Preparar LOC+OFF completo em `GIRO/output`, `data/processed/GIRO` ou
`data/output/GIRO`; não usar programas GNC anteriores. Separar concatenados pelo
fluxo adequado ao formato (decisão 19), verificar claquetes, assinatura e vinhetas
do boletim. A skill/pedido de planejamento não autoriza rodar cortes.

Cada nota tem esta estrutura (valores ilustrativos; hashes reais obrigatórios):

```json
{
  "ordem": 1,
  "pauta_id": "2026-09-03-B3-jucurutu",
  "titulo": "Recursos para projetos sociais em Jucurutu",
  "boletim": "B3",
  "data_boletim": "2026-09-03",
  "origem": "E:/acervo/03 - SET - B1-B4.mp3",
  "origem_sha256": "HASH_SHA256_REAL_DA_ORIGEM",
  "audio_nota": "E:/projeto/data/processed/GIRO/0902/nota-01.mp3",
  "audio_sha256": "HASH_SHA256_REAL_DA_NOTA",
  "evidencia_data": "Roteiro de 03/09/2026 e claquete conferidos",
  "limites": {"inicio_s": 120.0, "fim_s": 205.0, "evidencia": "Corte e bordas conferidos por escuta"},
  "geografia": {"uf": "RN", "municipio": "Jucurutu", "classificacao": "interior_rn", "evidencia": "Conteúdo da notícia e roteiro"},
  "revisao": {"aprovada": true, "responsavel": "OPERADOR_REAL", "evidencia": "Escuta e comparação ao roteiro", "loc_off_completos": true, "sem_vinhetas_boletim": true}
}
```

`origem` pode ser externa ou local; `audio_nota` deve estar na área GIRO do
projeto. Caminhos relativos são resolvidos contra a pasta do manifesto.
Calcular hashes com `(Get-FileHash -Algorithm SHA256 -LiteralPath <arquivo>).Hash.ToLower()`.
Os campos de revisão representam a avaliação realizada, nunca preencher `true`
sem ela. Datas canônicas devem concordar com o nome da origem. Duplicatas de pauta,
áudio ou cortes sobrepostos são rejeitadas. Limites devem corresponder à duração
da nota preparada e estar dentro da duração da origem.

## Montagem local

```powershell
python scripts_pipeline/executar_programa.py validar data/planos/GIRO/0902-v01.json
python scripts_pipeline/executar_programa.py montar data/planos/GIRO/0902-v01.json
python scripts_pipeline/executar_programa.py montar data/planos/GIRO/0902-v01.json --apply
```

As duas primeiras ações não escrevem nem geram áudio. A terceira exige todos os
gates; gera `data/output/GIRO/0902/v01/GNC_0902_08-09-2026.mp3` e `candidato.json`.
Receita: abertura → nota 1 → passagem ENTRE notas → encerramento. Faixa 5–15min;
não completa tempo com repetição nem corta texto para enquadrar. Sem trilha NJUD.
Exige ffprobe, ffmpeg e pydub somente na validação/montagem, não no planejamento.

Versões existentes são bloqueadas. Corrigir o manifesto e usar nova `versao`
(`v02`, etc.); não usar limpeza global. O MP3 permanece candidato para escuta
editorial/sonora. O relatório contém hashes do áudio, manifesto e vinhetas.

## Sincronização separada

Criar revisão JSON com `aprovada: true`, `editorial_ok: true`, `sonoro_ok: true`,
`responsavel`, `evidencia_escuta`, `candidato_sha256` (hash de candidato.json) e
`arquivo_sha256` (hash do MP3). Só após a revisão efetivamente realizada:

```powershell
python scripts_pipeline/executar_programa.py sync data/output/GIRO/0902/v01/candidato.json --revisao data/planos/GIRO/revisao-0902-v01.json --destino "H:/DESTINO_GIRO_CONFIRMADO" --apply
```

O destino deve existir, ser explicitamente confirmado e estar fora do projeto.
A ação copia somente esse MP3, verifica hashes, não sobrescreve nem varre outros
GNCs. O relatório local não é alterado; o caminho retornado comprova a operação
da chamada, não uma publicação antecipada. Não chamar wrappers antigos para
contornar gates. `giro_sync_drive.sh` delega exclusivamente a esta ação.

## Compatibilidade e limites

Aliases GIRO encaminham ao processo canônico; `processar` no orquestrador
compartilhado significa planejamento. O executor não aceita silenciosamente
JSONs antigos como ordens de produção. O upload GIRO no backend fica bloqueado
sem manifesto, até a interface suportar a seleção e revisão.

O novo controle não restaura o registry dos outros programas nem muda suas
receitas. A preparação dos cortes continua operação separada, com ferramentas
de processamento já existentes; a revisão humana resolve geografia e conteúdo.

## Montagem local autorizada antes da revisão sonora final

Uma autorização humana explícita de montagem pode ser registrada em `autorizacao_montagem_local`, com `autorizada:true`, `responsavel`, `mensagem` literal e `hashes_notas` correspondentes às peças atuais na ordem do manifesto. Essa autorização permite gerar candidatos locais mantendo `revisao.aprovada:false`; não é declaração de escuta nem aprovação editorial/sonora. A validação estrita continua rejeitando notas sem revisão. A montagem e seu dry-run aceitam essa autorização apenas para os mesmos hashes e preservam todos os gates de data, janela, geografia, duplicatas, limites, integridade e duração. O relatório registra separadamente autorização e revisão pendente.

A sincronização continua exigindo revisão final efetiva do candidato, com hashes correspondentes, editorial_ok, sonoro_ok e evidencia_escuta. Autorizar montagem não autoriza marcar esses campos como aprovados.

A exportação usa192kbps,44.1kHz e loudnorm com alvo-16LUFS e pico verdadeiro-2dBTP. Medir novamente o MP3 exportado: os alvos não comprovam por si só o volume final. Preservar versão anterior, criar nova versão e registrar hashes no retrabalho. O primeiro Giro0901 v01 mediu-11.85LUFS e+0.42dBTP; v02 aplica margem para reduzir o risco de distorção.
