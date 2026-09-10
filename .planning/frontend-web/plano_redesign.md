# Plano: redesign do Programador (módulo online)

**Escopo**: melhorar intuitividade, simplicidade e objetividade do `frontend/index.html` atual, mantendo a paleta neutra-minimal e detalhes já implementados (backend badge, modal config, polling, download). O servidor (`server.py`) e os agentes existentes não mudam.

**Anti-objetivo**: não adicionar framework, não adicionar build step, não adicionar dependências externas, não adicionar função que o current already does well (upload, polling, download já funcionam).

---

## 1. Princípios de design

### 1.1. Superfície: Operate

O usuário está agindo — envia áudios, processa, baixa. Isso é um painel de operação, não uma landing page. Prioridades:

1. **O que está pronto** deve ser visível de um olhar
2. **O que está processando** deve ter progresso claro (barra + texto da etapa)
3. **O que foi feito** deve ser fácil de baixar/desprezar

Isso vem da skill `claude-design` §Surface-First: Monitor/Operate não recebe hero — recebe hierarquia de ação.

### 1.2. Paleta

Manter os tokens existentes do `index.html`, eles já estão corretos para "neutro minimal":

```
--bg: #fafafa        (fundo da página)
--surface: #fff      (cartões/work areas)
--border: #e5e5e5    (bordas leves)
--border-strong: #cfcfcf
--text: #1a1a1a      (texto primário)
--muted: #6b6b6b     (texto secundário/labels)
--faint: #9a9a9a     (placeholders/infos secundários)
--accent: #0066cc    (ação primária, progresso)
--accent-hover: #0052a3
--accent-subtle: #eef5ff (fundos acentuados)
--danger: #c0392b
--danger-bg: #fdf2f2
--success: #1a7f4f
--success-bg: #f0f8f4
--radius: 6px
--radius-sm: 4px
--font: system sans
--mono: system mono
```

Nenhuma mudança de cor proposta — só aprofundar o uso (ver §2.4).

### 1.3. Tipografia

Manter system font stack atual. Adicionar hierarquia explícita:

- `h1`: 20px, weight 600, não usado atualmente
- `h2/work-title`: 13px, weight 500, color muted — OK, manter
- corpo: 14px linha-base 1.5 — OK
- labels, badges: 12px — OK
- mono para timestamps/tamanhos: família mono — OK

### 1.4. Espaçamento

Manter base 4px grid. O atual usa 24px de padding no `.app` e 24px no `.work-area` — bom para desktop. Para mobile (<640px), 16px. Manter.

---

## 2. Módulos de interface

### 2.1. Header

**Atual**: brand + botão config (⚙) + badge backend.

**Problema identificado**: o botão config está misturado com o badge, e o modal de config precisa de um label claro do que está sendo editado.

**Mudança proposta**:
- Manter botão config, mas com tooltip explícito já existe (`title="Configurar URL do backend"`) — OK, não mudar.
- Badge backend: deixar como está (ok/not ok/desconectado) — funciona.
- Adicionar visual separação entre brand e ações de config com mais espaço.

### 2.2. Selector de modo (tabs)

**Atual**: 3 tabs horizontal com label + descrição curta em smaller text.

**Avaliação**: funciona bem — mostra os 3 modos e o que cada um faz em uma linha. Manter estrutura.

**Melhoria**: destacar visualmente melhor o modo ativo e garantir que a mudança de modo limpe os slots atuais (já implementado em `resetSlots()`).

### 2.3. Área de trabalho (work area)

**Atual**: título + instrução + grid de slots + barra de botões.

**Problemas identificados**:
1. O grid de slots muda de 1 para 2 colunas dependendo do modo — pode ser confuso visualmente quando o usuário alterna entre modos.
2. Os slots "vazios" mostram um drop zone pouco contrastante.
3. Não há indicação visual clara de quais slots são obrigatórios vs opcionais no Giro (quando já tem 4 e pode adicionar mais).

**Mudanças propostas**:
- Manter grid 1 coluna para Boletins, 2 colunas para NJUD e Giro — OK, é intuitivo.
- Melhorar drop zone: maior contraste, ícone sutil (entidade de upload), texto mais orientado à ação.
- No Giro: quando há 4+ slots preenchidos, destacar que "pode adicionar mais" com badge sutil.

### 2.4. Estado dos slots

**Atual**: borda dashed quando vazio, borda sólida verde-accent quando preenchido, vermelho quando erro.

**Melhoria**:
- Manter, mas adicionar estado "enviando" (loading) quando o upload está em andamento — feedback imediato.
- Slot preenchido: mostrar nome do arquivo, tamanho e botão remover. OK.
- Slot vazio obrigatório: destacar levemente que falta algo (borda mais forte ou pequeno indicador).

### 2.5. Botões de ação

**Atual**: Processar (primary), Limpar, hint.

**Problemas identificados**:
- "Processar" pode ser confuso quando há slots vazios — já tem disabled, OK.
- "Limpar" não tem confirmação — pode ser arriscado. Mas o user pediu simplicidade, então manter sem confirmação, mas garantir que o usuário entenda o que vai acontecer (talvez mudar label para "Limpar slots" ou adicionar hint).

**Mudanças propostas**:
- Manter botões atuais.
- Adicionar dica contextual quando o botão Processar está habilitado: "X áudio(s) pronto(s) para processar".
- Hint abaixo dos botões já existe e funciona — aprimorar texto das hints para serem mais orientadas à ação.

### 2.6. Painel de jobs

**Atual**: lista de jobs com status, barra de progresso, etapa, botões cancelar/desprezar/baixar.

**Melhorias**:
- Ordenação: job em andamento aparece primeiro — OK (já implementado).
- Job concluído: destaque mais claro (borda verde, fundo suave verde) — OK.
- Adicionar tempo de duração quando concluído — OK (já existe `duration`).
- Botão "Baixar" abre em nova aba — OK.
- "Desprezar" remove da lista — OK.

**Novo**: adicionar indicador de quantos jobs do mesmo tipo estão em andamento (ex: "2 NJUDs processando") — opcional, pode ser overkill.

### 2.7. Feedback de backend

**Atual**: badge no header mostra status do backend (ok/not ok/desconectado), com atualização a cada 8s.

**Problemas identificados**: quando o backend está desconectado e o usuário clica em processar, o erro aparece apenas no hint de baixo. Pode ser melhor dar feedback mais imediato.

**Mudança proposta**: quando backend está desconectado, desabilitar botão Processar e mostrar hint claro "Backend offline — configure a URL no ícone ⚙".

---

## 3. Flows de interação

### 3.1. Fluxo Boletins

1. Usuário abre página → modo Boletins selecionado por padrão
2. 1 slot aparece (obrigatório)
3. Usuário clica no drop zone → escolhe arquivo
4. Slot preenche com nome+tamanho, borda fica verde
5. Botão "Processar" habilita
6. User clica → upload → job criado → polling
7. Job aparece na lista com progresso
8. Ao concluir: botão "Baixar" disponível

**Melhorias**:
- Quando o slot é preenchido, focus automático no próximo slot vazio (se houver) — opcional.
- Feedback visual de upload em andamento no slot (spinner ou "enviando…").

### 3.2. Fluxo NJUD

1. 4 slots aparecem (todos obrigatórios)
2. Usuário preenche um por um
3. Quando os 4 estão preenchidos, Processar habilita
4. Fluxo igual ao Boletins

**Melhorias**:
- Indicar claramente que são 4 boletins necessários (ex: "Boletim 1/4", "Boletim 2/4"...)
- Slot vazio mostra "Boletim 1 — obrigatório" em vez de apenas "Áudio opcional"

### 3.3. Fluxo Giro

1. 4 slots aparecem (todos obrigatórios inicialmente)
2. User pode adicionar mais com botão "+"
3. Quando 4 estão preenchidos, Processar habilita (mesmo que haja slots vazios extras)
4. Fluxo igual aos outros

**Mudanças propostas**:
- Quando todos os 4 iniciais estão preenchidos, destacar que pode adicionar mais (botão "+" mais visível)
- Slot "adicionado" mostra visualmente que é extra (ex: label "Boletim extra #5")

---

## 4. Acessibilidade e usabilidade

### 4.1. Estados de erro

- Formato não suportado → mensagem no slot, slot fica vermelho
- Backend offline → hint claro + botão processar disabled
- Upload falhou → hint com erro
- Job falhou → job aparece com estado error, botão desprezar

### 4.2. Keyboard

- Tabs entre slots e botões — deve funcionar naturalmente pelo HTML sem tabindex manual
- Enter em drop zone deve abrir file picker — implementar se não funcionar nativamente

### 4.3. Mobile

- Grid 2 colunas vira 1 coluna em telas < 640px — OK, já implementado
- Botões grandes o suficiente — OK (padding 9px 16px, font 13px)
- Touch targets min 44px — verificar

---

## 5. Estado persistem vs estado volátil

**Estado volátil (perda na recarga)**:
- Arquivos nos slots (file objects)
- Jobs em andamento na UI (perdem polling)

**Estado persistente**:
- Backend URL (localStorage)
- Jobs concluídos (persistem no backend via `data/jobs_state.json`)

**Decisão**: não adicionar persistência de jobs na UI — o backend já persiste. A UI recarrega os jobs ao iniciar via `GET /api/jobs`.

---

## 6. Checklist de implementação

- [ ] Melhorar drop zone visual (mais contraste, orientação à ação)
- [ ] Indicar contagem nos slots NJUD ("Boletim 1/4")
- [ ] Giro: destacar que pode adicionar slots quando os 4 iniciais estão preenchidos
- [ ] Feedback de upload em andamento no slot (spinner ou texto)
- [ ] Quando backend offline: desabilitar Processar + hint claro
- [ ] Hints mais orientadas à ação ("X áudio(s) pronto(s)")
- [ ] Verificar touch target sizes no mobile
- [ ] Testar fluxo completo em cada modo (simulado)

---

## 7. Ferramentas e referências

- `frontend/index.html` — arquivo a modificar
- `frontend/server.py` — backend (não muda, só usamos como serviço)
- `frontend/vercel.json` — deploy (não muda)
- Design reference: `popular-web-designs/templates/linear.app.md` (para tokens/components se necessário)
- Design process: skill `claude-design` §Surface-First
- Layout pattern: skill `frontend-layout-voice-editor` (para padrões de layout que já funcionam)

---

## 8. Direção de execução

1. Primeiro: ler `popular-web-designs/templates/linear.app.md` para extrair tokens se necessário
2. Depois: modificar `index.html` com as melhorias do §2 e §3
3. Terceiro: testar visualmente se houver browser tool disponível (ou validar por leitura do HTML)

Não é necessário criar variantes — o user já tem um design funcional, quer aprimorar a clareza. Uma única iteração focada nos pontos do checklist deve ser suficiente.
