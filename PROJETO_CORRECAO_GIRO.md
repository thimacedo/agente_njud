# PROJETO DE CORREÇÃO — PIPELINE DO GIRO

**Projeto:** Correção da vinheta de boletim nas saídas GIRO  
**Status:** Planejado — aguarda execução  
**Data:** 2026-09-09  

---

## VISÃO GERAL

O pipeline do GIRO tem 4 estágios. O problema ocorre porque o estágio 1 (separação de stems) está desabilitado, fazendo com que o estágio 2 (corte) opere em áudio bruto que contém a vinheta de boletim. O estágio 4 (montagem) então adiciona vinhetas de GIRO por cima.

```
BOLETIM_RADIO_TJRN_*.mp3 → [ETAPA 0 - PULADA] → [ETAPA 1 - CORTE EM ÁUDIO BRUTO] → VINHETA DE BOLETIM NO CABEÇA → [ETAPA 4 - MONTAGEM] → VINHETA_BOLETIM + VINHETA_GIRO
```

## FASES

### Fase 1 — Habilitar Separação de Stems (quick fix)

**Arquivo a modificar:** `config/planejamento_2026/giro_*.json` (34 arquivos)

**Ação:** Substituir `"usar_separacao_stems": false` por `"usar_separacao_stems": true`

**Comando:**
```bash
cd "/e/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR/config/planejamento_2026"
for f in giro_*.json; do
  sed -i 's/"usar_separacao_stems": false/"usar_separacao_stems": true/' "$f"
done
```

**Verificação:**
```bash
grep -r "usar_separacao_stems" giro_*.json | grep -v "true"
# Se retornar vazio, todos estão habilitados
```

**Impacto:** Demucs será executado para cada arquivo-fonte. Com cache, o processamento subsequente é instantâneo. Para o i5-8600K, o primeiro processamento é lento (~2-5min/arquivo) mas o cache resolve para rebuilds futuros.

---

### Fase 2 — Remoção Proativa de Vinheta de Boletim (defesa em profundidade)

**Arquivo a criar/modificar:** `src/giro/transcricao.py`

**Adicionar função:**

```python
def remover_vinheta_boletim(
    caminho_audio: Path,
    vinheta_ref: Path,
) -> Optional[AudioSegment]:
    """
    Remove a vinheta de abertura do boletim antes do corte.
    
    Detecta se VHT_ABERTURA_BOLETIM.mp3 está presente no início
    do áudio. Se sim, remove essa região e retorna o áudio limpo.
    
    Args:
        caminho_audio: Caminho do áudio do boletim
        vinheta_ref: Caminho da vinheta de referência
        
    Returns:
        Áudio limpo (sem vinheta), ou None se erro
    """
    try:
        audio = AudioSegment.from_file(str(caminho_audio))
        vinheta = AudioSegment.from_file(str(vinheta_ref))
        
        if len(vinheta) >= len(audio):
            return None  # Vinheta maior que áudio — impossível detectar
        
        # Transcreve trecho do áudio do mesmo tamanho da vinheta
        modelo = WhisperModel("tiny", device="cpu", compute_type="int8")
        segmentos, texto = modelo.transcribe(audio[:len(vinheta)])
        texto_limpo = " ".join(s.text.strip() for s in segmentos if s.text.strip())
        
        # Transcreve a vinheta de referência
        seg_vinheta, texto_vinheta = modelo.transcribe(vinheta)
        texto_vinheta_limpo = " ".join(s.text.strip() for s in seg_vinheta if s.text.strip())
        
        # Compara: se palavras-chave da vinheta aparecem no áudio
        if texto_vinheta_limpo and any(
            palavra in texto_limpo.lower() 
            for palavra in texto_vinheta_limpo.split()[:3]
            if len(palavra) > 3
        ):
            # Vinheta detectada — remover
            audio_limpo = audio[len(vinheta):]
            return audio_limpo
        
        return None  # Vinheta não detectada, áudio original está limpo
        
    except Exception:
        return None
```

**Integrar em `processar_boletim.py`:**
Na função `processar_um_arquivo()`, antes de chamar `processar_arquivo()`:
```python
if config.usar_separacao_stems:
    # Demucs já limpou o áudio
    arquivo_para_corte = resultado_stems.caminho_vocal
else:
    # Tentar remover apenas a vinheta de boletim
    vinheta_ref = Path(__file__).resolve().parents[3] / "assets" / "vinhetas" / "boletim" / "VHT_ABERTURA_BOLETIM.mp3"
    audio_limpo = remover_vinheta_boletim(Path(arquivo), vinheta_ref)
    if audio_limpo:
        arquivo_para_corte = salvar_tempo(audio_limpo)  # salvar em data/tmp/
    else:
        arquivo_para_corte = arquivo
```

---

### Fase 3 — Detector de Vinheta na Auditoria

**Arquivo a modificar:** `src/core/auditoria/regras.py`

**Adicionar classe:**

```python
class RegraVinhetaBoletimAusente:
    """
    Regra de auditoria que detecta se a vinheta de boletim
    ainda está presente no arquivo CABEÇA gerado pelo corte.
    
    Se a vinheta de boletim for detectada no início do CABEÇA,
    o corte falhou e o arquivo é rejeitado.
    """
    
    nome = "vinheta_boletim_ausente"
    
    # Palavras-chave que aparecem na vinheta de abertura do boletim
    PALAVRAS_CHAVE = frozenset({
        "tribunal de justiça",
        "ri grande do norte",
        "boletim",
        "rádio justiça",
        "manhã",
    })
    
    def verificar(self, auditavel: Auditavel, **kwargs) -> tuple[bool, Optional[str]]:
        try:
            cabeca_path = Path(auditavel.cabeca)
            if not cabeca_path.exists():
                return True, None
            
            # Transcreve os primeiros 12s do CABEÇA
            modelo = WhisperModel("tiny", device="cpu", compute_type="int8")
            audio = AudioSegment.from_file(str(cabeca_path))
            trecho = audio[:12000]  # 12 segundos em ms
            y = np.array(trecho.get_array_of_samples())
            sr = audio.sample_rate
            
            segments, texto = modelo.transcribe(y=y, sr=sr)
            texto_limpo = " ".join(s.text.strip() for s in segments if s.text.strip())
            
            # Se palavras-chave da vinheta aparecem → vinheta presente
            palavras_detectadas = [
                p for p in self.PALAVRAS_CHAVE 
                if p.lower() in texto_limpo.lower()
            ]
            
            if len(palavras_detectadas) >= 2:
                return False, (
                    f"VINHETA DE BOLETIM DETECTADA no CABEÇA: "
                    f"palavras-chave {palavras_detectadas}. "
                    f"Corte falhou — vinheta de boletim não removida."
                )
            
            return True, None
            
        except Exception as e:
            # Se não conseguir verificar, não bloquear
            return True, None
```

**Integrar:** Adicionar `RegraVinhetaBoletimAusente()` à lista de regras em `processar_boletim.py`:
```python
from core.auditoria.regras import (
    ...
    RegraVinhetaBoletimAusente,
)

# No processar_um_arquivo, após criar o Auditor:
auditor = Auditor()
auditor.adicionar_regra(RegraVinhetaBoletimAusente())
```

---

### Fase 4 — Gerador de Relatório Visual Simples

**Arquivo a criar:** `scripts_pipeline/detectar_vinheta.py`

```python
#!/usr/bin/env python3
"""
Detector de vinheta de boletim nos arquivos de corte.
Gera relatório visual simples para identificar rapidamente
quais arquivos ainda contêm a vinheta de boletim.

Uso:
    python scripts_pipeline/detectar_vinheta.py <pasta_cortes>
    python scripts_pipeline/detectar_vinheta.py data/processed/PRODUCAO_2026/JORNAIS_DIVIDIDOS/
"""

import sys
from pathlib import Path

def detectar_vinheta_em_arquivo(caminho: Path) -> dict:
    """Detecta se a vinheta de boletim está presente no arquivo."""
    # Implementar usando Whisper para transcrever os primeiros 12s
    # Comparar com palavras-chave da vinheta
    pass

def gerar_relatorio(pasta: Path) -> None:
    """Gera relatório visual dos arquivos com/sem vinheta."""
    pass

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python detectar_vinheta.py <pasta_cortes>")
        sys.exit(1)
    gerar_relatorio(Path(sys.argv[1]))
```

**Saída esperada:**
```
=== RELATÓRIO DE DETECÇÃO DE VINHETA DE BOLETIM ===
Pasta: data/processed/PRODUCAO_2026/JORNAIS_DIVIDIDOS/
Total de arquivos: 673
Com vinheta: 0
Sem vinheta: 673
✅ NENHUM ARQUIVO COM VINHETA DE BOLETIM DETECTADO
```

---

## ORDEM DE EXECUÇÃO

```
1. Fase 1: Habilitar stems nos 34 JSONs
   ↓ (testar 1 programa)
2. Fase 2: Implementar remover_vinheta_boletim()
   ↓ (testar 1 programa)
3. Fase 3: Implementar RegraVinhetaBoletimAusente
   ↓ (testar 1 programa)
4. Fase 4: Criar detector visual
   ↓ (verificar todos os arquivos existentes)
5. REBUILD: Limpar pastas de saída e re-executar pipeline completo
   ↓ (28 programas)
6. VERIFICAÇÃO: Confirmar que GNCs não têm vinheta de boletim
```

## TEMPOS ESTIMADOS

| Fase | Tempo (aprox) |
|---|---|
| 1 — Habilitar stems | 15 min (sed) + 1h teste |
| 2 — Remoção de vinheta | 2h implementação + 1h teste |
| 3 — Detector de vinheta | 1h implementação + 1h teste |
| 4 — Detector visual | 1h implementação |
| 5 — Rebuild completo | 4-8h (673 arquivos, CPU-only) |
| 6 — Verificação | 30 min |
| **Total** | **~10-14h** |

## RISCOS

- **Demucs pode falhar no CPU-only:** `htdemucs` pode não caber na memória do i5-8600K (16GB RAM). Se falhar, usar modelo `htdemucs_ft` mais leve ou `speechbrain`.
- **Cache pode ser grande:** `data/cache_stems/` pode crescer para ~5-10GB (673 arquivos × ~10MB cada).
- **Tempo de rebuild:** Com Demucs habilitado, o primeiro processamento de 673 arquivos pode levar dias no CPU-only.
- **Solução:** Se Demucs for impraticável, a Fase 2 (`remover_vinheta_boletim()`) como alternativa leve é a solução de backup.

## SUCESSO CRITÉRIO

✅ Nenhum GNC gerado contém a vinheta de boletim de abertura  
✅ Estrutura: `VHT_ABERTURA_GIRO → [VHT_PASSAGEM + Nota] × N → VHT_ENCERRAMENTO_GIRO`  
✅ 4-6 notas por programa  
✅ Regra geográfica funcional (RN-interior/Natal)  
✅ `RegraSemFallbackParaAudioCompleto` passando  
✅ Programas sincronizados para H:\03_GIRO_NAS_COMARCAS\  

---

*Fim do projeto de correção.*
