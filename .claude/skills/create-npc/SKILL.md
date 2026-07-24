---
name: create-npc
description: Cria um NPC completo e jogável para a campanha de D&D 5e — personalidade, objetivos, qualidades, falhas, segredos, humor atual e como interpretá-lo — seguindo o capítulo de NPCs do Livro do Mestre. Use quando o mestre precisar de um NPC novo (taverneiro, capitão da guarda, vilão secundário, contato, mercador...), quando o jogador interagir com alguém que ainda não tem ficha, ou quando pedirem /create-npc. Salva o NPC em arquivo próprio em mundo/npcs/.
---

# Criar NPC

Gera um NPC pronto para interpretar na mesa e o grava em arquivo próprio.
Conteúdo de `mundo/` é **segredo do mestre**: nunca mostre o arquivo no chat.

## Entrada

Formato livre, ou os quatro campos separados por `|`:

```
/create-npc <nome> | <classe ou profissão> | <adjetivo de personalidade> | <objetivo na história>
```

Ex.: `/create-npc Berta Malhaverde | taverneira | desconfiada | esconde o filho desertor no porão`

Campos ausentes você mesmo preenche — role nas tabelas de
[referencias/tabelas-dmg.md](referencias/tabelas-dmg.md) com
`python ferramentas/roll.py 1d20` (ou o dado indicado na tabela) e **aceite o
resultado**, mesmo torto: NPC estranho é NPC memorável. Nome ausente: invente
um coerente com a região/cultura do local em `mundo/locais.md`.

## Passos

1. **Leia o contexto antes de inventar**: `mundo/plot.md` (arco e fase atual),
   `mundo/locais.md` (onde o NPC vive), `mundo/faccoes.md` (a quem responde) e
   `mundo/npcs.md` (para não repetir nome, papel ou maneirismo já em uso).
2. **Role o que não foi especificado** nas tabelas de referência: aparência,
   talento, maneirismo, traço de interação, vínculo, falha/segredo, atributo
   alto e baixo, e o **humor atual** (1d6). Não role o que o pedido já definiu.
3. **Amarre ao plot.** O objetivo do NPC precisa de uma consequência concreta
   se ele o alcançar ou falhar, e de pelo menos um ponto de contato com o arco
   atual — mesmo que indireto (rumor, parente, dívida, lealdade a uma facção).
4. **Ficha de combate:** escolha um bloco oficial como base
   (`python ferramentas/5et.py criatura "commoner"`, `"guard"`, `"bandit
   captain"`, `"priest"`, `"veteran"`, `"archmage"`…) e anote o nome exato do
   bloco + os ajustes que você fizer. Não invente números do zero.
   NPC puramente social pode ficar só com "commoner" anotado.
5. **Escreva** `mundo/npcs/<slug>.md` no modelo abaixo. `<slug>` = nome em
   minúsculas, sem acentos, com hífens (`berta-malhaverde.md`).
6. **Indexe** em `mundo/npcs.md`: uma linha só, no grupo/facção certo,
   apontando para o arquivo. Se `mundo/npcs.md` ainda estiver com a marcação
   `<!-- TEMPLATE -->`, remova-a ao gravar a primeira entrada real.
7. **Relate ao mestre em 3 linhas** (fora do personagem): nome, papel, gancho
   principal e como puxar o NPC para a cena. Nunca cole o arquivo no chat.

## Modelo do arquivo

```markdown
# <Nome>

<uma linha: quem é, onde é encontrado, por que importa>

- **Papel na história:** <função concreta: dá a missão, guarda a chave, mente sobre X>
- **Facção/lealdade:** <de mundo/faccoes.md, ou "nenhuma">
- **Local usual:** <de mundo/locais.md>
- **Atitude inicial com o grupo:** hostil | indiferente | amigável
- **Humor agora (1d6):** <resultado + o que isso muda no primeiro diálogo>

## Como interpretar
- **Voz e ritmo:** <tom, velocidade, vocabulário — dá pra imitar em 1 segundo>
- **Maneirismo:** <o tique físico ou verbal repetido>
- **Traço de interação:** <curioso, arrogante, ranzinza…>
- **Primeira fala típica:** "<uma frase que já mostra tudo isso>"

## O que quer
- **Objetivo declarado:** <o que ele admite querer>
- **Objetivo real:** <o que ele quer de verdade, se for diferente>
- **Se conseguir:** <consequência no mundo>
- **Se falhar:** <consequência no mundo>

## Qualidades e falhas
- **Qualidade / talento:** <o que ele faz bem — útil ao grupo>
- **Atributo alto / baixo:** <ex.: SAB alta, CAR baixo>
- **Falha:** <o defeito que o coloca em apuros>
- **Vínculo:** <pessoa, lugar ou coisa por que ele arrisca tudo>

## Segredos
- **Sabe:** <informação útil que ele pode entregar — e o preço/teste para obtê-la>
- **Esconde:** <o segredo; CD e perícia para desconfiar, e o que o faz confessar>

## Ficha
- **Bloco base:** <nome oficial do stat block> (<fonte>)
- **Ajustes:** <mudanças, itens relevantes, magias>

## Ganchos
1. <como esse NPC puxa o grupo para uma cena>
2. <o que acontece com ele se o grupo o ignorar>

## Mudanças em jogo
<!-- registre aqui o que acontecer na mesa: morreu, virou aliado, revelou o segredo -->
```

## Regras da casa

- Antagonista de plot tem alinhamento e disposição **fixos**: não role humor
  nem atitude para ele — defina com intenção.
- Nada de NPC neutro e sem atrito. Se o rascunho não tem nem um desejo nem uma
  falha que atrapalhe o grupo, refaça.
- Um segredo por NPC secundário é suficiente. Ele precisa ser **descobrível**:
  sempre anote a perícia e a CD, ou o NPC/documento que entrega a pista.
- Ao criar vários NPCs de uma vez, varie maneirismo e traço de interação entre
  eles — role de novo se repetir.
