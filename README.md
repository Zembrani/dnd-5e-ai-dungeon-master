# dnd-5e-ai-dungeon-master

Uma mesa de D&D 5e em que o **Claude Code é o mestre**. O repositório é o
caderno dele: o comportamento está em `CLAUDE.md` (lido automaticamente em
toda sessão), o estado da campanha em arquivos versionáveis, e há um app local
de três painéis — chat, ficha e combate com mapa.

Roda pela sua assinatura do Claude Code, em modo headless. Sem custo de API.

## O que ele faz

- **Conduz a campanha**: entrevista você na Sessão 0, escolhe em segredo uma
  das 7 estruturas narrativas clássicas, escreve o plot e conduz as sessões.
- **Rola dados de verdade.** Nunca inventa resultado — toda rolagem passa por
  `ferramentas/roll.py`, inclusive as ocultas. Sem fudging: a letalidade é a
  padrão do 5e.
- **Consulta as regras oficiais** em vez de confiar na memória —
  `ferramentas/5et.py` lê o JSON oficial de magias, criaturas, itens,
  condições e talentos.
- **Roda módulos publicados.** `ferramentas/aventura.py` importa o texto
  integral de aventuras oficiais, indexa em seções e o mestre consulta a
  seção exata antes de narrar cada cena.
- **Mantém memória entre sessões** com checkpoints em `estado/` e resumos
  por sessão.

## Requisitos

Node.js 18+, Python 3, e o Claude Code instalado e logado (`claude`
funcionando no terminal). Sem `npm install` — o servidor é Node puro.

## Começar

```bash
git clone https://github.com/Zembrani/dnd-5e-ai-dungeon-master.git
cd dnd-5e-ai-dungeon-master

# cria sua campanha a partir dos modelos em branco (não sobrescreve nada)
cp -rn modelos/. .

# baixa os dados oficiais para consulta offline (~30 MB, uma vez só)
python ferramentas/5et.py baixar

node app/servidor.js
```

Abra <http://localhost:3333> e diga **"vamos preparar a campanha"**.

Sem o app também funciona: abra o Claude Code na pasta e converse normalmente.

## Os três painéis

- **Mesa** — o chat com o mestre. Botões `salvar`, `recap` e `nova sessão`.
- **Ficha** — renderizada de `estado/personagem.json`. Clique em atributo,
  perícia, salvaguarda, ataque ou magia para rolar de verdade; o resultado vai
  direto ao mestre. `▲`/`▼` rolam com vantagem/desvantagem, e o botão `🎲+`
  acumula um multiataque inteiro num rascunho para enviar de uma vez.
- **Combate** — ordem de iniciativa, mapa e tokens, lidos de
  `estado/combate.json`. Arraste o seu token para se mover; o mestre valida no
  turno seguinte. O HP dos inimigos aparece só como ileso/ferido/grave.

Variáveis: `MESA_PORTA=4000` muda a porta. `MESA_SKIP_PERMISSIONS=1` dá
permissões totais ao mestre dentro da pasta (por sua conta e risco).

## Rodar uma aventura publicada

```bash
python ferramentas/aventura.py listar strahd
python ferramentas/aventura.py importar CoS
```

Depois peça ao mestre: **"vamos jogar Curse of Strahd"**. Ele usa a skill
`importar-aventura` para transformar o módulo no caderno de mestre, e durante
o jogo consulta a seção exata antes de narrar — o que evita o erro clássico de
um LLM narrar um módulo "de memória" e trocar aposentos e nomes.

O texto importado fica em `aventuras/`, que é ignorado pelo git. Veja
[Conteúdo protegido](#conteúdo-protegido).

### O radar da mesa

Consultar o livro é caro no meio de uma cena, então a decisão de consultar
sempre perde para a de continuar narrando — e é assim que um módulo perde
gancho, cena obrigatória e às vezes um arco inteiro. Regra escrita não
resolve isso; mecanismo resolve.

`/extrair-gatilhos` compila o módulo numa **agenda**: cada cena com disparo
automático ("ao sair da área…"), encontro garantido, revelação condicional e
o grafo de saídas do mapa, cada uma com a citação literal do livro que a
estabelece — a validação rejeita gatilho cuja citação não exista no texto, de
modo que nenhum é inventado.

Daí em diante `ferramentas/radar.py` cruza essa agenda com o estado da
campanha e injeta, **a cada turno**, o que está armado no local atual e qual
seção precisa ser lida antes de narrar. Sem LLM no meio: é comparação de
arquivo. O que já disparou (ou foi pulado de propósito) vai para um ledger
append-only em `estado/gatilhos.json`, que ao contrário de `estado/atual.md`
nunca é sobrescrito.

```bash
python ferramentas/radar.py                 # o que está armado aqui
python ferramentas/radar.py rota E I        # trajeto + gatilhos de cada parada
python ferramentas/radar.py pendentes       # obrigatórios ainda em aberto
```

## Comandos na mesa

| Comando      | Efeito |
|--------------|--------|
| `salvar`     | Checkpoint imediato (grava o estado nos arquivos) |
| `recap`      | Resumo do estado atual |
| `off` / `on` | Entrar/sair de conversa fora do personagem |
| `ficha`      | Mostra sua ficha atual |
| `encerrar`   | Salva tudo, escreve o resumo da sessão e fecha com gancho |

## Skills

| Skill | O que faz |
|-------|-----------|
| `/create-npc` | Gera um NPC completo — voz, objetivos, falhas, segredos com CD, humor atual — rolando nas tabelas do Livro do Mestre o que não for informado. |
| `/importar-aventura` | Prepara o mestre para rodar um módulo oficial publicado. |
| `/extrair-gatilhos` | Compila um módulo importado na agenda de gatilhos que alimenta o radar da mesa. |

Dois subagentes trabalham na fronteira das cenas, sem gastar o contexto da
mesa: `bibliotecario` acha e devolve as seções do livro na íntegra (nunca
resume, nunca opina), e `auditor-continuidade` roda nos checkpoints e reporta
gatilho perdido e divergência entre o que foi narrado e o que o livro diz.

## Estrutura

```
CLAUDE.md              contrato de comportamento do mestre
.claude/skills/        skills do projeto
.claude/agents/        subagentes (bibliotecário, auditor de continuidade)
.claude/settings.json  hook que injeta o radar a cada turno
app/                   servidor local + interface de 3 painéis
app/ESQUEMAS.md        esquema dos JSONs que o app renderiza
ferramentas/roll.py    dados honestos
ferramentas/5et.py     consulta às regras oficiais
ferramentas/aventura.py  importa e consulta aventuras publicadas
ferramentas/gatilhos.py  compila e valida a agenda de gatilhos do módulo
ferramentas/radar.py     o que está armado aqui e o que ler antes de narrar
modelos/               modelos em branco de uma campanha nova

           ↓ criados a partir de modelos/, ignorados pelo git ↓
CAMPANHA.md            pitch da sua campanha
mundo/                 SEGREDO DO MESTRE: plot, NPCs, locais, facções
estado/                memória de trabalho, sobrescrita a cada checkpoint
sessoes/               um resumo curto por sessão
campanhas-passadas/    arcos concluídos, arquivados
aventuras/             módulos publicados importados
midia/                 mapas, tokens e uploads
```

## Regra de ouro (para o jogador)

**Não leia a pasta `mundo/`.** É o caderno secreto do mestre — plot, segredos
dos NPCs e reviravoltas. Ler é dar spoiler na própria diversão. O resto
(`estado/`, `sessoes/`) é seu e pode ler à vontade.

## Conteúdo protegido

O `.gitignore` mantém fora do repositório tudo que é material da Wizards of
the Coast: os dados baixados em `ferramentas/dados-5et/`, o texto de módulos
publicados em `aventuras/`, e mapas e tokens oficiais em `midia/`. Nada disso
é redistribuído aqui — cada pessoa gera localmente a partir das ferramentas.
Mantenha assim ao contribuir.

Este projeto não é afiliado à Wizards of the Coast.

## Reaproveitar entre campanhas

Ao concluir um arco, peça ao mestre para iniciar uma nova campanha (CLAUDE.md
§1, "Reiniciar para uma nova campanha"). Ele arquiva a crônica em
`campanhas-passadas/`, reseta `mundo/` e o estado de mesa, e **mantém a ficha**
— nível, itens, ouro e XP atravessam campanhas.
