---
name: extrair-gatilhos
description: Compila uma aventura publicada importada em agenda de gatilhos (aventuras/<slug>/gatilhos.json) — cenas com disparo automático, encontros garantidos, revelações condicionais, timers e o grafo de saídas do mapa. É o que faz o radar da mesa saber, a cada turno, o que está armado no local e o que precisa ser lido antes de narrar. Use depois de /importar-aventura, ou quando um capítulo novo entrar em jogo e `gatilhos.py stats` mostrar zero gatilhos nele.
---

# Extrair a agenda de gatilhos de um módulo

Roda UMA vez por capítulo, fora de cena (é trabalho de preparação, não de mesa).
Produz o artefato caro-de-fazer e barato-de-consultar: a máquina de estados do
módulo. O texto do livro continua sendo a fonte da prosa — a agenda só diz
**o que existe, quando dispara e qual seção ler**.

## Por que existe

O mestre esquece gatilho sob pressão de narrar. Não por burrice: ler 8 KB de
livro no meio da cena é caro e quebra o ritmo, então a decisão de consultar
sempre perde para a decisão de continuar. A agenda inverte isso — o radar
injeta as pendências do local a cada turno, de graça, sem depender de escolha.

## Passada A — extração, um lote por vez

1. `python3 ferramentas/gatilhos.py esquema` — leia inteiro. Vocabulários são
   FECHADOS; qualquer valor fora deles é rejeitado na validação.
2. `python3 ferramentas/aventura.py indice <slug> <capítulo>` — recorte o lote.
   Um lote = um capítulo, ou ~20 seções. Não tente o livro inteiro de uma vez.
3. Para cada seção do lote, **`ler` a seção completa** (nunca `buscar`: ele
   trunca e o `verbatim` sai errado, o que reprova na validação).
4. Escreva o candidato em `<scratch>/<slug>-<lote>.json`.

Lotes independentes podem ir para subagentes em paralelo — o contexto de cada
um é descartável e não polui a mesa. Prompt do subagente:

> Leia `python3 ferramentas/gatilhos.py esquema` e as seções NNN-NNN de <slug>
> com `python3 ferramentas/aventura.py ler <slug> <ref>` (uma a uma, texto
> completo). Extraia a agenda de gatilhos dessas seções no esquema, e grave em
> <caminho>.json. `verbatim` deve ser copiado LITERALMENTE do texto em inglês
> — é conferido por substring contra o arquivo da seção. Não resuma o livro,
> não inclua descrição de aposento nem bloco de estatística. Rode
> `python3 ferramentas/gatilhos.py validar <slug> <caminho>.json` e conserte
> até dar zero erro. Não rode `mesclar`.

### O que é gatilho (e o que não é)

É gatilho quando o livro amarra algo a uma CONDIÇÃO:

- "*whenever the characters reach area F*" → `ao_chegar`, e `recorrente: true`
- "*As the characters leave the area, read*" → `ao_sair` **obrigatório**
- "*If your card reading reveals…*" → `se_variavel` com guarda de variável
- "*unless they are accompanied by Vistani*" → guarda `nao_acompanhado_por`
- "*After the party rests for the third time…*" → `apos_dias`

Não é gatilho: descrição de sala, estatística, texto de leitura em voz alta
(o corpo dele fica no livro; a agenda só aponta a seção), tabela de tesouro
sem condição de existência.

### Grafo de saídas

Toda área ganha `saidas` com direção. Só registre a aresta que o texto sustenta.
Aresta que você deduziu do mapa vai com `"nota": "não citado na seção; conferir
mapa"`. Contradição interna do livro (acontece) vai na `nota` do local, não
"corrigida" em silêncio — o mestre precisa saber antes de narrar a viagem.

## Passada B — validar, mesclar, conferir

```
python3 ferramentas/gatilhos.py validar <slug> <candidato>.json   # zero erros
python3 ferramentas/gatilhos.py mesclar <slug> <candidato>.json
python3 ferramentas/gatilhos.py stats <slug>
python3 ferramentas/radar.py local <área>                         # olho vivo
```

`mesclar` é idempotente por `id`: reextrair um capítulo atualiza no lugar, sem
duplicar, e sem tocar no ledger da campanha (`estado/gatilhos.json`).

Erro de `verbatim` na validação quer dizer uma de duas coisas, ambas graves:
a citação foi inventada, ou a seção citada está errada. Nos dois casos, **volte
ao livro** — não ajuste a citação de memória até "passar".

## Depois

- Confira `python3 ferramentas/radar.py` com o local atual da campanha.
- Variáveis novas que apareceram em guardas (`tarokka.aliado`, etc.) precisam
  existir em `estado/situacao.json`, com `null` enquanto indefinidas — é assim
  que o radar avisa que o módulo depende de algo que a mesa ainda não resolveu.
- Gatilho que o livro estabelece em prosa corrida, sem marcar condição, não sai
  na extração. Isso é esperado: anote à mão com
  `python3 ferramentas/radar.py anotar <id> <local> <quando> "<resumo>"`.
  Não force a extração a "achar" — gatilho inventado é pior que gatilho faltando.
