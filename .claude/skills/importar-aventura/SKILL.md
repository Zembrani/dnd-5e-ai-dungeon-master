---
name: importar-aventura
description: Prepara o mestre para rodar uma aventura oficial publicada (Curse of Strahd, Lost Mine of Phandelver, Tomb of Annihilation...). Baixa o texto integral do 5e.tools, indexa em aventuras/<slug>/ e escreve o caderno do mestre em mundo/ (plot, locais, NPCs, facções) com referência de volta ao livro. Use quando o jogador pedir para jogar um módulo pronto em vez de uma campanha original, ou quando pedirem /importar-aventura.
---

# Importar aventura publicada

Transforma um módulo oficial no caderno de mestre deste repositório, para
rodá-lo seguindo o livro sem precisar carregar o livro inteiro no contexto.

O conteúdo de `aventuras/` é **segredo do mestre**, igual a `mundo/`.
Nunca cole, resuma ou cite esses arquivos no chat com o jogador.

## Regra que não se quebra

Você conhece essas aventuras de treino — e é exatamente por isso que erra
detalhes: troca números de aposento, inventa nomes de NPC, mistura versões.
**Antes de narrar qualquer cena do módulo, leia a seção correspondente** com
`ler`. Memória não vale como fonte. Se não achou a seção, busque; se ainda não
achou, diga ao jogador (fora do personagem) que vai improvisar aquele trecho.

## Passo 1 — combinar com o jogador (fora do personagem)

Antes de baixar qualquer coisa, pergunte: qual aventura, em que nível o grupo
entra, quanto tempo quer jogar (arco inteiro ou só os primeiros capítulos),
e **linhas e véus** — módulos publicados têm horror, tortura e violência
explícitos que talvez não caibam nesta mesa. Anote o combinado; ele vira
restrição de narração, não sugestão.

## Passo 2 — importar

```
python ferramentas/aventura.py listar <parte do nome>
python ferramentas/aventura.py importar <ID>
python ferramentas/aventura.py indice <slug>
```

Se a aventura não estiver no catálogo, pare e diga ao jogador — não invente o
módulo de cabeça.

## Passo 3 — ler o que importa (não o livro todo)

Nesta ordem, com `ler`:

1. O capítulo de introdução / "Running the Adventure" — é onde o livro explica
   a lógica do módulo, o vilão, os temas e o ritmo esperado.
2. A **abertura** de cada capítulo (as seções marcadas `— abertura` no
   sumário). Dão o arco inteiro por poucos tokens.
3. As seções de recompensa/artefato e as de NPC principal.

Não leia todos os aposentos agora. Eles são consultados em jogo, um a um.

## Passo 4 — escrever o caderno em `mundo/`

Remova a marcação `<!-- TEMPLATE -->` dos arquivos que preencher. **Toda**
afirmação vinda do livro leva a referência da seção, no formato `[cos 235]`,
para você conferir depois em vez de confiar na memória.

- **`mundo/plot.md`** — o arco como o livro o apresenta: premissa, vilão e o
  que ele quer, fases/atos, condições de virada e desfechos possíveis.
  Inclua as duas seções que o `CLAUDE.md` exige:
  - *Estrutura narrativa*: aqui você **identifica** qual das 7 estruturas
    clássicas o módulo já usa (em vez de escolher uma), e registra por quê.
    Continua sendo segredo — nunca conte ao jogador.
  - *Ganchos aleatórios secretos*: role normalmente
    (`python ferramentas/roll.py 1d100` para cada um dos 3, ativa com ≤10) e
    registre. Ganchos ativos entram como conteúdo lateral **encaixado** no
    módulo, sem atropelar o arco do livro.
  Anote também os **ajustes combinados no passo 1** (nível, corte de
  capítulos, linhas e véus) numa seção "Adaptações desta mesa".
- **`mundo/locais.md`** — um item por local relevante, com a referência da
  seção, o que o grupo encontra lá e o mapa correspondente.
- **`mundo/npcs.md`** — índice dos NPCs do livro: nome, papel, referência.
  Para os que o livro deixa raso mas que vão ganhar peso na mesa, rode
  `/create-npc` e gere a ficha completa em `mundo/npcs/`.
- **`mundo/faccoes.md`** — grupos, o que querem, como reagem ao grupo.

## Passo 5 — o guia de condução

Escreva `aventuras/<slug>/guia.md`. É o arquivo que você relê ao começar
cada sessão. Deve caber em uma ou duas páginas:

```markdown
# <Aventura> — guia de condução

## Ordem esperada das cenas
<sequência de capítulos/locais com a referência de cada um e o nível sugerido>

## Pontos de decisão
<os momentos em que a escolha do jogador muda o rumo, e para onde cada
ramo leva — com a referência da seção de destino>

## Se o grupo sair do trilho
<como o mundo reage; qual gancho puxa de volta sem forçar trilhos>

## Marcos de nível
<em que ponto do módulo o grupo deve estar em cada nível>

## O que este módulo pressupõe
<itens, NPCs ou informações que o livro assume que o grupo já tem>
```

## Passo 6 — a agenda de gatilhos (obrigatório)

O `guia.md` é prosa que você escolhe reler; a agenda é mecanismo que roda
sozinho. Rode a skill `/extrair-gatilhos <slug>` para os capítulos do começo
do arco (não o livro inteiro — a extração é incremental, capítulo a capítulo,
conforme entram em jogo).

Ela compila `aventuras/<slug>/gatilhos.json`: cenas com disparo automático,
encontros garantidos, revelações condicionais e o grafo de saídas do mapa. É
disso que o radar (`ferramentas/radar.py`) vive, e é o que impede a cena "ao
sair da área" de sumir no meio de uma viagem.

Depois, crie `estado/situacao.json` a partir de `modelos/estado/situacao.json`:
`aventura` = slug, `local_atual` = onde o grupo começa, e uma entrada em
`variaveis` para cada variável que apareceu em guarda de gatilho (`null`
enquanto a mesa não a resolver). Confira com `python3 ferramentas/radar.py`.

## Passo 7 — mapas

Baixe os mapas dos primeiros capítulos já agora, versão do jogador:

```
python ferramentas/5et.py mapa <ID>                    # lista
python ferramentas/5et.py mapa <ID> "<parte do nome>"  # baixa
```

Anote em `mundo/locais.md` qual mapa serve cada local, para o
`estado/combate.json` apontar direto na hora da briga. Nunca revele ao jogador
o nome do arquivo nem de que aventura ele veio.

## Passo 8 — fechar

Diga ao jogador, em 3 linhas e sem spoiler: que a preparação está pronta, em
que ponto ele começa e o que ele sabe do mundo como personagem. Depois siga o
`CLAUDE.md` normalmente — criação de ficha se ainda não houver personagem,
`estado/atual.md`, e "posso começar?".

## Em jogo, depois da importação

- Cena nova do módulo → `radar.py local <área>` para saber o que está armado,
  `ler` a seção inteira, **então** narrar. Capítulo que entra em jogo sem
  gatilhos extraídos (`gatilhos.py stats <slug>`) → rode `/extrair-gatilhos`
  antes da cena.
- Texto marcado `> **[LER EM VOZ ALTA]**` é a narração de abertura do livro:
  traduza para o português e adapte ao tom da mesa, mas não invente por cima.
- Criatura que entra em cena → `5et.py criatura "<nome>"` para o bloco oficial,
  como sempre.
- Consequência permanente (NPC morreu, local queimou) → registre na seção
  "Mudanças em jogo" do arquivo de `mundo/`, **nunca** editando `aventuras/`:
  aquilo é a cópia do livro e fica intacta.
