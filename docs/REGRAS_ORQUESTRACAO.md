# REGAS DE ORQUESTRAÇÃO — Pipeline DIVISO

## 1. Princípios (KISS, YAGNI, DRY)

**KISS (Keep It Simple, Stupid):**
- Um dispatcher por vez. Sempre.
- Um worker por vez (quando recursos limitados).
- Um subagente por tarefa. Sem fan-out desnecessário.
- Se está funcionando, não mexa.

**YAGNI (You Ain't Gonna Need It):**
- Não crie heartbeat system, monitor, ou watchdog se um simples `tasklist | findstr` resolve.
- Não use subagentes para tarefas que `execute_code` resolve em 1 linha.
- Não reinicie processos automaticamente — pergunte ao orquestrador primeiro.

**DRY (Don't Repeat Yourself):**
- O dispatcher já tem estado persistido (`estado_por_arquivo/*.json`). Use-o como fonte de verdade.
- Não crie sistemas paralelos de monitoramento.
- Não repita verificações — uma verificação bem feita basta.

---

## 2. Regras Inegociáveis de Orquestração

### R1 — Processo único
**Nunca mais de 1 instância do dispatcher rodando.**
Como verificar:
```
tasklist | findstr dispatcher
```
Se houver mais de 1, matar todos e reiniciar apenas 1.

### R2 — Verificação de vida (heartbeat simples)
A cada 5 minutos, verificar:
```
tasklist | findstr dispatcher
```
Se não houver dispatcher → reportar ao orquestrador → aguardar decisão.

### R3 — Estado persistente é fonte de verdade
Não confie em logs ou memória. O estado está em:
```
data/processed/PRODUCAO_2026/estado_por_arquivo/*.json
```
Para verificar progresso:
```python
import json, glob
status = {}
for f in glob.glob("data/processed/PRODUCAO_2026/estado_por_arquivo/*.json"):
    d = json.load(open(f))
    s = d.get("status", "?")
    status[s] = status.get(s, 0) + 1
```

### R4 — Subagentes reportam estado a cada ação
Cada subagente DEVE:
1. Reportar o que vai fazer ANTES de fazer
2. Reportar o resultado DEPOIS de cada ação
3. Reportar erro IMEDIATAMENTE (não tentar consertar sozinho)
4. NUNCA iniciar processos em background sem confirmar com o orquestrador

### R5 — Orquestrador decide, subagente executa
- **Orquestrador (eu):** decide quando iniciar, parar, reiniciar
- **Subagente:** executa exatamente o que foi pedido, nada mais
- Subagente NÃO reinicia processos sozinho
- Subagente NÃO muda configurações sozinho

### R6 — Fail-closed
Se algo falhar:
1. Parar
2. Reportar
3. Aguardar decisão
NUNCA tentar consertar automaticamente.

### R7 — Uma tarefa por subagente
- Subagente de cópia: SÓ copia
- Subagente de dispatcher: SÓ roda o dispatcher (1 vez)
- Subagente de montagem: SÓ monta
- NUNCA um subagente faz múltiplas tarefas

---

## 3. Protocolo de Resposta Constante

### Para cada processo longo, o subagente DEVE:
1. Iniciar o processo em background (`start /B` ou `subprocess.Popen`)
2. Reportar o PID
3. A cada 5 minutos, reportar:
   - Processo ainda está rodando? (PID existe?)
   - Quantos arquivos processados desde última verificação?
   - Algum erro novo?
4. Quando terminar, reportar resultado final

### Template de resposta do subagente:
```
[HEARTBEAT] PID: 1234 | Progresso: 45/406 (11%) | Erros: 0 | Status: rodando
[HEARTBEAT] PID: 1234 | Progresso: 67/406 (16%) | Erros: 0 | Status: rodando
[ERRO FATAL] PID: 1234 morreu. Ultimo progresso: 89/406. Aguardando instrucoes.
```

---

## 4. Comandos de Verificação (sempre usar estes)

### Verificar se dispatcher está rodando:
```bash
tasklist | findstr dispatcher
```

### Verificar progresso:
```python
import json, glob
status = {}
for f in glob.glob("data/processed/PRODUCAO_2026/estado_por_arquivo/*.json"):
    d = json.load(open(f))
    s = d.get("status", "?")
    status[s] = status.get(s, 0) + 1
print(status)
```

### Matar todos os dispatchers:
```bash
taskkill /F /IM python.exe /FI "WINDOWTITLE eq *dispatcher*"
```
(Cuidado: prefira matar por PID específico)

---

## 5. Lições Aprendidas (não reverter)

| Data | Problema | Causa | Solução |
|------|----------|-------|---------|
| 2026-09-05 | 10 dispatchers simultâneos | Subagentes reiniciaram sem verificar | R1 + R5 |
| 2026-09-05 | Dispatcher morreu silenciosamente | Sem heartbeat | R2 |
| 2026-09-05 | Subagente não reportou estado | Sem protocolo de resposta | R4 + Protocolo |
| 2026-09-05 | Arquivos JUL/AGO não processados | Estrutura errada (dia vs NJUD) | Verificar estrutura ANTES de rodar dispatcher |
| 2026-09-05 | OOM (Out of Memory) | Modelo Whisper `small` + 5.6GB livres | Mudar para `tiny` |
| 2026-09-05 | Thread exhaustion | Muitos workers acumulando threads | `--max-workers 1` |

---

*v1 — 2026-09-05. Criado após múltiplas falhas de orquestração.*
