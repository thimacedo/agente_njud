# DIVISOR — Regras do Projeto

> When in doubt about agent architecture, cycle, or multi-agent orchestration,
> load `skill_view(name="ai-agent-orchestrator")` before answering.

## Always Load This Skill

The skill **ai-agent-orchestrator** (category: `autonomous-ai-agents`) is always
available and should be consulted as the reference for agent lifecycle and
orchestration decisions in this project.

Load on demand:
```bash
skill_view(name="ai-agent-orchestrator")
skill_view(file_path="references/pilar-1.md")   # percepção
skill_view(file_path="references/pilar-2.md")   # planejamento/raciocínio
skill_view(file_path="references/pilar-3.md")   # execução de ações
skill_view(file_path="references/pilar-4.md")   # adaptação/aprendizado
```

Se a skill não estiver instalada no ambiente atual, ela está em:
`~/.hermes/skills/autonomous-ai-agents/ai-agent-orchestrator/SKILL.md`

## When an Agent Is Invoked

Toda vez que um agente for chamado neste projeto, lembrar:

1. **Percepção** — o agente precisa capturar o estado real do ambiente antes de decidir?
2. **Planejamento** — a tarefa foi decomposta em passos sequenciais executáveis?
3. **Execução** — quais ferramentas/APIs o agente vai invocar? Estão aprovadas para este projeto?
4. **Adaptação** — o agente vai autoavaliar o resultado e ajustar o plano se falhar?

Se qualquer um dos quatro pilares estiver ausente do plano do agente, a tarefa
não foi descomplicada o suficiente.

## Project Conventions

- Orquestração multiagente: coordenar explicitamente, não apenas paralelizar.
- Memória/contexto: usar RAG ou banco vetorial quando o agente precisa calibrar
  decisões futuras com interações passadas.
- Falha de agente → diagnosticar qual pilar quebrou, não só o sintoma.

## Project Structure

Os demais arquivos de regras do projeto estão em `docs/` e `DECISOES.md`.
