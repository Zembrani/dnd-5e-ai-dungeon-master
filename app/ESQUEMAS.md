# Esquemas de estado — referência do mestre

O app renderiza `estado/personagem.json` e `estado/combate.json` diretamente.
Siga estes esquemas à risca: campo errado = painel quebrado para o jogador.
JSON sempre válido (sem comentários, sem vírgula sobrando).

## estado/personagem.json

```json
{
  "personagens": [
    {
      "nome": "Kael", "raca": "Meio-elfo", "classe": "Patrulheiro",
      "nivel": 3, "antecedente": "Forasteiro",
      "hp": { "atual": 24, "max": 28, "temp": 0 },
      "ca": 15, "deslocamento": "9 m", "iniciativa": 3, "prof": 2,
      "atributos": { "for": {"valor": 12, "mod": 1}, "des": {"valor": 16, "mod": 3},
                     "con": {"valor": 14, "mod": 2}, "int": {"valor": 10, "mod": 0},
                     "sab": {"valor": 14, "mod": 2}, "car": {"valor": 11, "mod": 0} },
      "salvaguardas": { "for": {"mod": 3, "prof": true}, "des": {"mod": 5, "prof": true},
                        "con": {"mod": 2, "prof": false}, "int": {"mod": 0, "prof": false},
                        "sab": {"mod": 2, "prof": false}, "car": {"mod": 0, "prof": false} },
      "pericias": [ { "nome": "Percepção", "mod": 4, "prof": true } ],
      "ataques": [ { "nome": "Arco longo", "bonus": 5, "dano": "1d8+3", "tipo": "perfurante" } ],
      "magias": {
        "cd": 12, "ataque": 4,
        "slots": { "1": { "usados": 1, "total": 3 } },
        "conhecidas": [
          { "nome": "Marca do Caçador", "nivel": 1 },
          { "nome": "Curar Ferimentos", "nivel": 1, "rolagem": "1d8+2" }
        ]
      },
      "recursos": [ { "nome": "Inspiração", "usados": 0, "total": 1 } ],
      "xp": { "atual": 900, "proximo": 2700 },
      "moedas": { "po": 35, "pp": 8, "pc": 20 },
      "inventario": [ "Corda (15 m)", "Poção de cura" ],
      "condicoes": []
    }
  ]
}
```

Regras:
- `mod` são valores JÁ CALCULADOS (atributo + proficiência quando aplicável).
- `ataques[].dano` e `magias.conhecidas[].rolagem` vão direto para o roll.py:
  podem somar vários grupos de dado (`2d8+1d8+6`, `4d6+2d8-1d4`). Não é mais
  preciso juntar dados do mesmo tipo à mão.
- `magias` pode ser `null` para classes não conjuradoras.
- `magias.conhecidas[].rolagem` é opcional: se presente (dano/cura), a magia
  vira clicável no app.
- `condicoes` usa nomes de condição 5e em português ("caído", "agarrado"...).
- Atualize HP, slots, recursos, XP, moedas e inventário a CADA checkpoint.

## estado/combate.json

```json
{
  "ativo": true,
  "rodada": 2,
  "turno": "Goblin A",
  "cenario": "Salão de entrada da caverna, tochas apagadas.",
  "mapa": {
    "imagem": "midia/mapas/Cragmaw Hideout (Player).webp",
    "grid": { "cols": 18, "rows": 12, "escala_pes": 5 }
  },
  "zonas": [
    { "id": "Z1", "nome": "Portão", "descricao": "entrada, meia-luz" }
  ],
  "combatentes": [
    { "id": "pc-kael", "nome": "Kael", "tipo": "jogador",
      "iniciativa": 15, "hp": { "atual": 24, "max": 28 }, "ca": 15,
      "pos": { "x": 3, "y": 5 }, "zona": "Z1", "tamanho": 1,
      "token": "midia/tokens/pc-kael.webp", "condicoes": [] },
    { "id": "gob-a", "nome": "Goblin A", "tipo": "inimigo",
      "iniciativa": 12, "hp": { "atual": 7, "max": 7 }, "ca": 15,
      "pos": { "x": 8, "y": 4 }, "zona": "Z1", "tamanho": 1,
      "token": "midia/tokens/MM-Goblin.webp", "condicoes": [] }
  ],
  "fora": [ { "nome": "Goblin B", "estado": "morto", "rodada": 1 } ],
  "movimentos_do_jogador": []
}
```

Regras:
- `ativo`: `true` ao rolar iniciativa; ao fim do combate, restaure o arquivo
  inteiro para o modelo vazio (`ativo: false`, listas vazias).
- `mapa.imagem`: caminho relativo à raiz do repo, dentro de `midia/`.
  Sem mapa adequado? Use `"mapa": { "imagem": null, "grid": {...} }` — o app
  desenha um grid abstrato. `grid.cols/rows` = células do mapa (1 célula = 5 pés).
- `pos`: coordenadas de célula com origem no canto superior esquerdo
  (x=0..cols-1, y=0..rows-1). O app exibe como "C5" (coluna-letra + linha).
- `tipo`: `"jogador"` (token verde, arrastável) ou `"inimigo"` / `"aliado"`.
- `hp` de inimigos: o app mostra ao jogador apenas ileso/ferido/grave/caído —
  pode preencher o valor real sem medo de metagame.
- `tamanho`: 1 = Médio, 2 = Grande (2×2), 3 = Enorme, 4 = Descomunal.
- `movimentos_do_jogador`: o app adiciona entradas quando o jogador arrasta o
  próprio token. LEIA e ESVAZIE esta lista no início de cada turno seu:
  valide o movimento (deslocamento, terreno, oportunidade) e narre; se o
  movimento for ilegal, corrija `pos` e explique.

## Mídia (mapas e tokens)

- `python ferramentas/5et.py mapa <ID> <nome>` baixa mapas oficiais (versão
  Player, sem segredos) para `midia/mapas/`.
- `python ferramentas/5et.py token <criatura>` baixa tokens para `midia/tokens/`.
- Uploads do jogador pelo app caem em `midia/uploads/`.
- Ao preparar um local em `mundo/locais.md`, já anote o mapa/tokens escolhidos
  e baixe-os com antecedência (sem anunciar qual aventura é a fonte — evite
  spoiler até do nome do arquivo ao falar com o jogador).
