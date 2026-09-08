# Diagnóstico de Sujeira no Drive H: e Workspace

## 🔍 Fontes de escrita no Drive H: identificadas

### 1. `src/sync/drive.py` — Sincronizador NJUD (programas montados)
- **O que faz**: Copia `NJUD_*.mp3` de `data/output/JORNAIS_FINAL/` para `H:\...\02_JORNAIS_NJUD\03_AUDIOS_RADIO\MM - MES - AA\`
- **Quando roda**: Manualmente via `python src/sync/drive.py` ou via `tools/executar_reprocessamento.py`
- **Risco**: Baixo — só copia programas montados com padrão `NJUD_XXXX_DD-MM-AAAA.mp3`

### 2. `src/giro/sync_drive.py` — Sincronizador GIRO (programas montados)
- **O que faz**: Copia `GNC_mmss_DD-MM-AA.mp3` de `data/output/GIRO_COMARCAS/` para `H:\...\03_GIRO_NAS_COMARCAS\`
- **Quando roda**: Manualmente via `python src/giro/sync_drive.py`
- **Risco**: Baixo — só copia programas montados

### 3. `src/tools/executar_reprocessamento.py` — Reprocessamento NJUD
- **O que faz**: Copia jornais para `settings.DIR_DRIVE_JORNAIS` após montagem
- **Quando roda**: Manualmente
- **Risco**: Médio — copia direto para pastas mensais no Drive

### 4. `src/tools/sanear_drive.py` — Saneamento (pasta quarentena)
- **O que faz**: Copia duplicatas para `00_QUARENTENA` no Drive
- **Quando roda**: Manualmente
- **Risco**: Baixo — só roda sob demanda

### 5. `src/tools/mover_orfaos_drive.py` — Move órfãos
- **O que faz**: Move arquivos órfãos para `_arquivo_morto` no Drive
- **Quando roda**: Manualmente
- **Risco**: Baixo — só roda sob demanda

### 6. `src/divisor_boletins/montagem.py` — Cópia temporária local
- **O que faz**: `shutil.copy2(mp3, pasta_njud / mp3.name)` — cópia LOCAL para pasta temporária de montagem
- **Risco**: Nenhum para o Drive — é só workspace local

---

## 🚨 Sujeira encontrada no workspace local (25 MB)

```
data/processed/GIRO_COMARCAS/  → 257 MB (133 MP3s de notas)
data/output/GIRO_COMARCAS/     → 171 MB (programas montados)
data/cache/transcricoes/       → 117 MB (cache JSON de transcrições)
TOTAL                          → 545 MB
```

### Origem da sujeira:
- **133 MP3s em `data/processed/GIRO_COMARCAS/`**: Notas geradas por múltiplos runs do pipeline GIRO durante testes (programas 0102, 0103, 0201, 0202, 0203). Cada run gerava notas porque o pipeline estava sendo calibrado.
- **Programas em `data/output/GIRO_COMARCAS/`**: Programas montados durante testes.
- **Cache de transcrições**: Cache em disco das transcrições Whisper — pode ser limpo sempre.

---

## 📋 Regras de Operação (Fail-Closed)

### Para o Drive H: (espaço limitado — não é para entulhar)

1. **NUNCA copiar boletins individuais para o Drive** — só programas montados (finais)
2. **NUNCA deixar notas cortadas no Drive** — notas ficam só no workspace local
3. **Sincronização é via script dedicado** (`sync/drive.py` ou `giro/sync_drive.py`) — nunca via `cp` ou `shutil.copy` direto no código de processamento
4. **Validação antes de copiar**: só copiar arquivos com padrão canônico (`NJUD_XXXX_DD-MM-AAAA.mp3` ou `GNC_mmss_DD-MM-AA.mp3`)
5. **Overwrite silencioso**: se arquivo existe no Drive, sobrescrever (não criar `_old` ou duplicatas)

### Para o workspace local

1. **Cache de transcrições pode ser limpo** — é regenerável
2. **Notas cortadas (`data/processed/GIRO_COMARCAS/`)** — podem ser limpas após montagem bem-sucedida
3. **Programas montados (`data/output/GIRO_COMARCAS/`)** — manter até sync com Drive, depois podem ser removidos
4. **Logs** — rotacionar periodicamente

---

## 🧹 Limpeza necessária

### Workspace local (seguro limpar):
- [ ] `data/cache/transcricoes/` — 117 MB (regenerável)
- [ ] `data/processed/GIRO_COMARCAS/` — 257 MB (notas já montadas podem ser removidas)
- [ ] `data/output/GIRO_COMARCAS/` — 171 MB (após sync com Drive)

### Drive H: (verificar quando montado):
- [ ] Arquivos fora do padrão canônico
- [ ] Pastas `00_QUARENTENA` com duplicatas
- [ ] Arquivos em `_arquivo_morto` que podem ser removidos
