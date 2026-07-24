# Melhorias do app da mesa

Backlog de ideias pra evoluir o app (`app/servidor.js` + front). Sem ordem de
prioridade fixa; marcar `[x]` quando feito.

## Rolagem

- [x] **Ataques: escolher vantagem/desvantagem.** Cada ataque da ficha agora
  tem os botões `▲` (vantagem) e `▼` (desvantagem) ao lado do botão de ataque
  normal; o app manda `1d20+N adv` / `dis` pro roll.py e o rótulo da rolagem
  já avisa o mestre qual foi.
- [x] **Ataques múltiplos antes de enviar.** Botão `🎲+` ao lado do `off`
  liga o **modo rascunho**: as rolagens param de ir pro mestre e vão se
  acumulando numa caixa acima da entrada de texto (cada linha pode ser
  descartada no `✕`). "enviar tudo" manda a sequência inteira numa mensagem
  só (`🎲 [rolagem pelo app] Sequência de rolagens:` + linhas `•`), que o
  mestre resolve de uma vez.
- [x] **Dano com múltiplos grupos de dado.** O `roll.py` passou a aceitar
  expressões compostas (`2d8+1d8+6`, `4d6+2d8-1d4`) e `NdXklY` (mantém os
  menores). Formato de saída dos casos antigos ficou igual. O campo `dano` da
  ficha pode ir direto, sem juntar dados do mesmo tipo na mão.
- [x] Criar NPCs através de subagentes ou skill. Feito como skill de projeto:
  `.claude/skills/create-npc/` — `/create-npc <nome> | <profissão> |
  <adjetivo> | <objetivo na história>`. Rola nas tabelas do Livro do Mestre
  (aparência, talento, maneirismo, traço de interação, vínculo, falha/segredo,
  atributo alto/baixo, humor atual) o que não for informado, amarra o NPC ao
  plot e grava a ficha completa — como interpretar, objetivos declarado e
  real, qualidades, falhas, segredos com CD, bloco de combate base e ganchos —
  em `mundo/npcs/<slug>.md`, indexada em `mundo/npcs.md`.

## Próximas ideias

- [ ] Dano crítico em um clique (dobrar os dados do ataque que criticou).
- [ ] Vantagem/desvantagem também em perícias e salvaguardas (hoje só ataques).
