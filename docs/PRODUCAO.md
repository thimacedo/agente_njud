# Procedimento de Produção de NJUDs

Documento genérico para produção de jornais de **qualquer mês/ano**.
Subui versões anteriores espalhadas (`PROCEDIMENTO_PRODUCAO_NJUDs_v5.md`,
`planejamento_agosto_2026.md`, etc.).

---

## 0. Parâmetros da Produção

Preencher antes de iniciar. Exemplo para Julho/Agosto 2026:

| Parâmetro | Valor | Descrição |
|-----------|-------|-----------|
| `ANO` | `2026` | Ano de referência |
| `MESES` | `["07", "08"]` | Meses a produzir (com zero) |
| `PASTAS_H` | `["07 - JUL - 26", "08 - AGO - 26"]` | Nomes das pastas em H: |
| `CSV_NJUD` | `NJUDS_VALIDOS.csv` | Mapeamento data → código NJUD |

**Caminhos derivados:**

```
FONTE_H(mes) = H:\Meu Drive\RADIO TJRN CONTEÚDO\00_PRODUCAO_<ANO>\01_BOLETINS_DIARIOS\03_AUDIOS_RADIO\<PASTA_H>
DEST_H(mes)  = H:\Meu Drive\RADIO TJRN CONTEÚDO\00_PRODUCAO_<ANO>\02_JORNAIS_NJUD\03_AUDIOS_RADIO\<PASTA_H>
JORNAIS      = E:\02_Projetos_Trabalho\Projetos_Ativos\DIVISOR\JORNAIS\<MES>
DIVIDIDOS    = E:\02_Projetos_Trabalho\Projetos_Ativos\DIVISOR\data\processed\PRODUCAO_<ANO>\JORNAIS_DIVIDIDOS
FINAL        = E:\02_Projetos_Trabalho\Projetos_Ativos\DIVISOR\data\output\JORNAIS_FINAL
ESTADO       = E:\02_Projetos_Trabalho\Projetos_Ativos\DIVISOR\data\processed\PRODUCAO_<ANO>\estado_por_arquivo
LOGS         = E:\02_Projetos_Trabalho\Projetos_Ativos\DIVISOR\logs
```

---

## 1. Regras Inegociáveis

1. **H: somente leitura** — exceto no sync final (etapa 7)
2. **1 NJUD = 4 boletins** — nunca 3, nunca 5
3. **Data do NJUD = data do CSV** — nunca data do boletim de origem
4. **Corrigir datas antes do sync** — cruzar com CSV, renomear se errado
5. **Nunca sobrescrever no H:** — se existe, pular
6. **Limpeza só após sync confirmado** — verificar H: antes de apagar local
7. **Log em toda etapa** — timestampado em `logs/`
8. **Gate por-NJUD** — só montar com 4 boletins OK
9. **Mês = data no filename** — pasta física não define o mês
10. **1 dispatcher por vez** — matar antigos antes de iniciar

---

## 2. Etapa 1 — Copiar Boletins

**Fonte:** `FONTE_H(<mes>)/`
**Destino:** `JORNAIS/<MES>/`

Copiar recursivamente todos os `.mp3`, mantendo subpastas por dia útil.

```python
import shutil
from pathlib import Path

for mes, pasta_h in zip(MESES, PASTAS_H):
    src = Path("H:/Meu Drive/RADIO TJRN CONTEUDO/00_PRODUCAO_") / ANO / "01_BOLETINS_DIARIOS" / "03_AUDIOS_RADIO" / pasta_h
    dst = Path("E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR/JORNAIS") / mes
    dst.mkdir(parents=True, exist_ok=True)
    for f in src.rglob("*.mp3"):
        rel = f.relative_to(src)
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copy2(f, target)
    print(f"{mes}: copiados {sum(1 for _ in dst.rglob('*.mp3'))} mp3s")
```

**Log:** registrar quantidade copiada por mês.

---

## 3. Etapa 2 — Cortar Boletins (Dispatcher)

```bash
python src/pipeline/dispatcher.py E:/JORNAIS data/processed/PRODUCAO_<ANO> --max-workers 2
```

- Whisper (transcrição) + Silero VAD (detecção de fala)
- Gera `_CABECA.mp3` e `_CORPO.mp3` em `DIVIDIDOS/<NJUD>/`
- Estado persistido em `ESTADO/<arquivo>.json`
- Status: `OK`, `PENDENTE`, `ESGOTADO`, `ESGOTADO_ACEITO`, `ERRO`

**Monitor (opcional):**
```bash
python src/pipeline/monitor.py data/processed/PRODUCAO_<ANO> --intervalo 5 --log
```

**Problema conhecido:** watchdog com bug na fila. Se travar, matar e rodar
novamente — arquivos OK são pulados.

---

## 4. Etapa 3 — Auditar Processamento

```python
import json, glob
from collections import defaultdict

estado_por_njud = defaultdict(list)
for f in glob.glob(f"data/processed/PRODUCAO_<ANO>/estado_por_arquivo/*.json"):
    data = json.load(open(f))
    estado_por_njud[data["njud"]].append(data["status"])

completos = [n for n, s in estado_por_njud.items() if s.count("OK") >= 4]
pendentes = [n for n, s in estado_por_njud.items() if s.count("OK") < 4]
print(f"Completos: {len(completos)}, Pendentes: {len(pendentes)}")
```

**Resultado:** lista de NJUDs prontos para montagem.

---

## 5. Etapa 4 — Montar Jornais

```python
from divisor_boletins.montagem import montar_todos_jornais

montar_todos_jornais(
    "data/processed/PRODUCAO_<ANO>/JORNAIS_DIVIDIDOS",
    "data/output/JORNAIS_FINAL"
)
```

Saída: `FINAL/<NJUD>/<NJUD>_<DD-MM-AAAA>.mp3`

---

## 6. Etapa 5 — Auditoria de Montagem

Para cada `FINAL/<NJUD>/<NJUD>_*.mp3`:

| Critério | Mín | Máx |
|----------|-----|-----|
| Tamanho | 1 MB | — |
| Duração | 3 min | 8 min |
| Validez | MP3 legível (ffprobe) | — |
| Data no nome | Deve bater com CSV | — |

Rejeitar fora desses critérios.

---

## 7. Etapa 6 — Corrigir Datas

**Problema:** montagem usa data do arquivo de corte. Se o corte veio de
boletim de outro mês, a data fica errada.

**Solução:** cruzar com CSV e renomear.

```python
import csv, os
from pathlib import Path

csv_map = {}
with open("NJUDS_VALIDOS.csv") as f:
    for row in csv.reader(f):
        if len(row) >= 3 and row[2].strip():
            data = row[0].strip()
            cod = row[2].strip()
            csv_map[cod] = data.replace("/", "-")

for njud_dir in sorted(os.listdir("data/output/JORNAIS_FINAL")):
    njud = njud_dir.replace("NJUD_", "")
    if njud not in csv_map:
        continue
    data_correta = csv_map[njud]
    njud_path = Path("data/output/JORNAIS_FINAL") / njud_dir
    for f in njud_path.glob("*.mp3"):
        partes = f.stem.split("_")
        data_atual = partes[-1]
        if data_atual != data_correta:
            novo_nome = f"{f.stem.replace(data_atual, data_correta)}.mp3"
            print(f"RENOMEAR: {f.name} -> {novo_nome}")
            f.rename(f.with_name(novo_nome))
```

---

## 8. Etapa 7 — Sync com H:

**Única escrita permitida no H:.**

```python
import shutil
from pathlib import Path

for mes, pasta_h in zip(MESES, PASTAS_H):
    dst_base = Path("H:/Meu Drive/RADIO TJRN CONTEUDO/00_PRODUCAO_") / ANO / "02_JORNAIS_NJUD" / "03_AUDIOS_RADIO" / pasta_h
    copiados = 0
    pulados = 0
    for njud_dir in Path("data/output/JORNAIS_FINAL").iterdir():
        if not njud_dir.is_dir():
            continue
        for f in njud_dir.glob("*.mp3"):
            dst = dst_base / f.name
            if dst.exists():
                pulados += 1
                continue
            shutil.copy2(f, dst)
            copiados += 1
    print(f"{mes}: {copiados} copiados, {pulados} pulados")
```

---

## 9. Etapa 8 — Limpeza Local

**Somente após confirmar H:.**

```python
import shutil

for mes in MESES:
    shutil.rmtree(f"JORNAIS/{mes}", ignore_errors=True)

shutil.rmtree("data/output/JORNAIS_FINAL", ignore_errors=True)
print("Limpeza concluida")
```

**NUNCA apagar:** `logs/`, `data/processed/PRODUCAO_<ANO>/estado_por_arquivo/`

---

## 10. Etapa 9 — Relatório Final

Gerar `logs/relatorio_final_<YYYYMMDD_HHMMSS>.md`:

- NJUDs produzidos (código, data, tamanho, duração)
- Datas corrigidas (quantas e quais)
- Total copiado para H: por mês
- Erros e pendências
- Status: `OK` / `PENDENTES` / `ERROS`

---

## Problemas Conhecidos

| Problema | Causa | Solução |
|----------|-------|---------|
| Datas erradas | Cortes de boletins de outro mês | Etapa 7 (renomear) |
| Watchdog trava | Bug na fila do dispatcher | Matar e rodar novamente |
| execute_code falha | Bug sandbox Singularity | `hermes config set terminal.backend local` |
| Worker morre (OOM) | Memória insuficiente | Reduzir `--max-workers` para 1 |
| Boletins sem NJUD | Sem correspondência no CSV | Reportar pendência |

---

*v2 — 2026-09-05. Documento genérico consolidado.*
