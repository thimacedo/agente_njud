# PLANEJAMENTO GIRO - JANEIRO 2026

## Visão Geral

- **Programa:** GIRO nas Comarcas (GNC)
- **Mês de referência:** Janeiro 2026
- **Total de programas:** 4
- **Pasta base dos boletins:** `H:\Meu Drive\RADIO TJRN CONTEÚDO\00_PRODUCAO_2026\01_BOLETINS_DIARIOS\03_AUDIOS_RADIO\01 - JAN - 26`
- **Padrão de nomenclatura de saída:** `GNC_mmss_DD-MM-AA.mp3`

---

## Programas

### Programa 1: 0102
- **Data de exibição:** 13/01/2026 (terça-feira)
- **Período das notícias:** 04/01/2026 (segunda) a 10/01/2026 (domingo)
- **Arquivo de saída:** `GNC_0102_13-01-26.mp3`
- **Previsão de notícias:** 4-6
- **Observações:** Primeiro programa do ano - validar vinhetas de abertura/encerramento

### Programa 2: 0103
- **Data de exibição:** 20/01/2026 (terça-feira)
- **Período das notícias:** 11/01/2026 (segunda) a 17/01/2026 (domingo)
- **Arquivo de saída:** `GNC_0103_20-01-26.mp3`
- **Previsão de notícias:** 4-6

### Programa 3: 0104
- **Data de exibição:** 27/01/2026 (terça-feira)
- **Período das notícias:** 18/01/2026 (segunda) a 24/01/2026 (domingo)
- **Arquivo de saída:** `GNC_0104_27-01-26.mp3`
- **Previsão de notícias:** 4-6

### Programa 4: 0201
- **Data de exibição:** 03/02/2026 (terça-feira)
- **Período das notícias:** 25/01/2026 (segunda) a 31/01/2026 (domingo)
- **Arquivo de saída:** `GNC_0201_03-02-26.mp3`
- **Previsão de notícias:** 4-6
- **Observações:** Último programa com boletins de janeiro - atenção ao fechamento do mês

---

## Regras de Negócio

### Estrutura do GIRO
- Cada programa usa boletins de uma semana específica (segunda a domingo)
- O programa é exibido na terça-feira seguinte
- Cada mês tem 4 programas (01, 02, 03, 04)
- O 4º programa pode usar boletins que atravessam o mês

### Filtro Geográfico
- ✅ **INEGOCIÁVEL:** Excluir notícias de outros estados (fora RN)
- ⚠️ **AJUSTÁVEL:** Evitar notas sobre Natal (capital)

### Formato CABEÇA/CORPO
- Cada nota tem dois segmentos: CABEÇA (locutor) + CORPO (off)
- Detecção por silêncio de ~1 segundo entre os segmentos
- Vinhetas específicas do GIRO (abertura, passagem, encerramento)

---

## Próximos Passos

1. [ ] Validar disponibilidade dos boletins na pasta de origem
2. [ ] Executar transcricao dos boletins selecionados
3. [ ] Aplicar filtro geográfico (RN vs outros estados)
4. [ ] Identificar pares CABEÇA/CORPO por detecção de silêncio
5. [ ] Cortar e auditar cada nota
6. [ ] Montar programa com vinhetas do GIRO
7. [ ] Auditoria final antes da exportação

---

**Gerado em:** 2026-01-XX  
**Plano JSON:** `/workspace/data/plano_giro_janeiro_2026.json`
