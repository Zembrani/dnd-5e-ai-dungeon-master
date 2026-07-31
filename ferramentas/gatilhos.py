#!/usr/bin/env python3
"""Agenda de gatilhos de uma aventura publicada — esquema, validação e mesclagem.

`aventuras/<slug>/gatilhos.json` é a MÁQUINA DE ESTADOS do módulo: cada cena
com gatilho, encontro garantido, revelação, timer e saída de mapa, com a
referência da seção que a estabelece. É derivado do livro — regenerável,
nunca editado à mão em jogo. O que a campanha resolveu vive em
`estado/gatilhos.json` (append-only), nunca aqui.

    python3 gatilhos.py esquema              -> esquema + vocabulários fechados
    python3 gatilhos.py validar cos cand.json-> checa candidato sem gravar
    python3 gatilhos.py mesclar cos cand.json-> valida e funde no gatilhos.json
    python3 gatilhos.py stats cos            -> cobertura por capítulo
    python3 gatilhos.py ver cos [local]      -> lista os gatilhos já extraídos

A trava anti-alucinação é mecânica: todo gatilho carrega `verbatim`, e a
validação exige que essa frase EXISTA no texto da seção citada. Gatilho que
não passa no substring check é rejeitado — modelo nenhum inventa gatilho.
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).parent.parent
AVENTURAS = RAIZ / "aventuras"

# --------------------------------------------------------------------------
# vocabulários FECHADOS — é o que permite o radar decidir sem LLM
# --------------------------------------------------------------------------
TIPOS = {
    "cena":       "acontecimento narrativo que o livro manda encenar",
    "encontro":   "combate ou checagem de encontro aleatório",
    "revelacao":  "informação que o livro entrega em condição específica",
    "timer":      "algo que acontece com a passagem do tempo",
    "recompensa": "tesouro/item cuja existência depende de condição",
    "regra_local":"regra que vale enquanto o grupo está na área/região",
    "nivel":      "marco de progressão previsto pelo livro",
}
QUANDO = {
    "ao_chegar":    "quando o grupo entra na área `alvo`",
    "ao_sair":      "quando o grupo deixa a área `alvo`",
    "ao_anoitecer": "na virada para a noite (ou amanhecer, ver `nota`)",
    "apos_dias":    "N dias depois de um marco; `dias` obrigatório",
    "se_variavel":  "quando a guarda de variável passa a ser verdadeira",
    "ao_nivel":     "quando o grupo atinge o nível `nivel`",
    "manual":       "só o mestre decide; o radar apenas lembra que existe",
}
GUARDAS = {
    "variavel":            "{nome: 'tarokka.tesouro', igual: 'F'} — estado de campanha",
    "nao_acompanhado_por": "{valor: 'vistani'} — o radar marca CONDICIONAL",
    "acompanhado_por":     "{valor: 'ireena'}",
    "ja_disparou":         "{valor: '<id de outro gatilho>'}",
    "julgamento":          "{descricao: '...'} — só o mestre avalia em cena",
}
ESTADOS = ("disparado", "pulado", "adiado")

OBRIGATORIOS_GATILHO = ("id", "ref", "tipo", "disparo", "obrigatorio", "verbatim")


def _norm_texto(s: str) -> str:
    """Achata para comparação: sem acento de markdown, espaço colapsado, minúsculo."""
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"[*_>#`]", " ", s)
    s = re.sub(r"[‘’“”]", "'", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip().lower()


def _abrir_meta(slug: str) -> tuple[Path, dict]:
    pasta = AVENTURAS / slug.lower()
    meta = pasta / "meta.json"
    if not meta.exists():
        sys.exit(f"Aventura '{slug}' não importada. "
                 f"Veja: python3 ferramentas/aventura.py importadas")
    return pasta, json.loads(meta.read_text(encoding="utf-8"))


def _corpo_secao(pasta: Path, secao: dict) -> str:
    caminho = pasta / "texto" / secao["arquivo"]
    return caminho.read_text(encoding="utf-8") if caminho.exists() else ""


def _ref_num(ref: str) -> str:
    """'cos 033' | '033' | 33 -> '033'."""
    m = re.search(r"(\d{1,3})", str(ref))
    return f"{int(m.group(1)):03d}" if m else str(ref)


def caminho_agenda(slug: str) -> Path:
    return AVENTURAS / slug.lower() / "gatilhos.json"


def carregar(slug: str) -> dict:
    p = caminho_agenda(slug)
    if not p.exists():
        return {"slug": slug.lower(), "locais": {}, "gatilhos": []}
    return json.loads(p.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# validação
# --------------------------------------------------------------------------
def _checar_verbatim(trecho: str, corpo: str) -> bool:
    """Cada fragmento separado por reticências deve aparecer, em ordem."""
    alvo = _norm_texto(corpo)
    partes = [p for p in re.split(r"\.{3}|…", trecho) if p.strip()]
    pos = 0
    for parte in partes:
        achou = alvo.find(_norm_texto(parte), pos)
        if achou < 0:
            return False
        pos = achou + 1
    return True


def validar(slug: str, dados: dict) -> tuple[list[str], list[str]]:
    """Devolve (erros, avisos). Erro = rejeita o gatilho. Aviso = segue."""
    pasta, meta = _abrir_meta(slug)
    por_ref = {s["ref"]: s for s in meta["secoes"]}
    erros: list[str] = []
    avisos: list[str] = []

    locais = dados.get("locais") or {}
    gatilhos = dados.get("gatilhos") or []
    if not isinstance(locais, dict) or not isinstance(gatilhos, list):
        return ["Estrutura inválida: esperado {locais:{}, gatilhos:[]}"], []

    # --- locais e grafo de saídas
    for chave, loc in locais.items():
        onde = f"local {chave}"
        if not isinstance(loc, dict):
            erros.append(f"{onde}: não é objeto")
            continue
        for campo in ("nome", "ref"):
            if not loc.get(campo):
                erros.append(f"{onde}: falta '{campo}'")
        ref = _ref_num(loc.get("ref", ""))
        if ref not in por_ref:
            erros.append(f"{onde}: ref '{loc.get('ref')}' não existe em {slug}")
        for saida in loc.get("saidas", []):
            destino = saida.get("para")
            if not destino:
                erros.append(f"{onde}: saída sem 'para'")
            elif destino not in locais:
                # extração é incremental: destino pode vir num capítulo futuro
                avisos.append(f"{onde}: saída para '{destino}' ainda não extraído")

    # --- gatilhos
    vistos: set[str] = set()
    cache: dict[str, str] = {}
    for g in gatilhos:
        gid = g.get("id", "?")
        onde = f"gatilho {gid}"
        faltando = [c for c in OBRIGATORIOS_GATILHO if g.get(c) is None]
        if faltando:
            erros.append(f"{onde}: faltam campos {faltando}")
            continue
        if gid in vistos:
            erros.append(f"{onde}: id duplicado")
        vistos.add(gid)
        if not gid.startswith(f"{slug.lower()}-"):
            erros.append(f"{onde}: id deve começar com '{slug.lower()}-'")
        if g["tipo"] not in TIPOS:
            erros.append(f"{onde}: tipo '{g['tipo']}' fora do vocabulário {sorted(TIPOS)}")
        if not isinstance(g["obrigatorio"], bool):
            erros.append(f"{onde}: 'obrigatorio' deve ser booleano")

        disparo = g["disparo"]
        if not isinstance(disparo, dict) or disparo.get("quando") not in QUANDO:
            erros.append(f"{onde}: disparo.quando fora do vocabulário {sorted(QUANDO)}")
        else:
            quando = disparo["quando"]
            if quando in ("ao_chegar", "ao_sair") and not disparo.get("alvo"):
                erros.append(f"{onde}: disparo '{quando}' exige 'alvo'")
            if quando == "apos_dias" and not isinstance(disparo.get("dias"), int):
                erros.append(f"{onde}: disparo 'apos_dias' exige 'dias' inteiro")
            if quando == "ao_nivel" and not isinstance(disparo.get("nivel"), int):
                erros.append(f"{onde}: disparo 'ao_nivel' exige 'nivel' inteiro")
            alvo = disparo.get("alvo")
            if alvo and alvo not in locais and alvo not in (dados.get("_locais_conhecidos") or []):
                avisos.append(f"{onde}: alvo '{alvo}' não está entre os locais deste lote")

        guarda = g.get("guarda")
        if guarda is not None:
            if not isinstance(guarda, dict) or guarda.get("tipo") not in GUARDAS:
                erros.append(f"{onde}: guarda.tipo fora do vocabulário {sorted(GUARDAS)}")
            elif guarda["tipo"] == "variavel" and not guarda.get("nome"):
                erros.append(f"{onde}: guarda 'variavel' exige 'nome'")

        # --- a trava: o verbatim tem de existir no livro
        ref = _ref_num(g["ref"])
        if ref not in por_ref:
            erros.append(f"{onde}: ref '{g['ref']}' não existe em {slug}")
            continue
        if ref not in cache:
            cache[ref] = _corpo_secao(pasta, por_ref[ref])
        if not _checar_verbatim(g["verbatim"], cache[ref]):
            erros.append(f"{onde}: verbatim NÃO encontrado em [{slug} {ref}] — "
                         f"citação inventada ou seção errada: {g['verbatim'][:70]!r}")

    return erros, avisos


def mesclar(slug: str, dados: dict) -> None:
    erros, avisos = validar(slug, dados)
    for a in avisos:
        print(f"  aviso: {a}")
    if erros:
        for e in erros:
            print(f"  ERRO: {e}")
        sys.exit(f"\n{len(erros)} erro(s). Nada foi gravado.")

    agenda = carregar(slug)
    agenda["slug"] = slug.lower()
    agenda.setdefault("locais", {}).update(dados.get("locais") or {})

    por_id = {g["id"]: g for g in agenda.get("gatilhos", [])}
    novos = substituidos = 0
    for g in dados.get("gatilhos") or []:
        if g["id"] in por_id:
            substituidos += 1
        else:
            novos += 1
        por_id[g["id"]] = g
    agenda["gatilhos"] = sorted(por_id.values(), key=lambda g: (_ref_num(g["ref"]), g["id"]))

    destino = caminho_agenda(slug)
    destino.write_text(json.dumps(agenda, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
    print(f"OK — {novos} novo(s), {substituidos} atualizado(s), "
          f"{len(agenda['gatilhos'])} gatilhos e {len(agenda['locais'])} locais em {destino}")


def stats(slug: str) -> None:
    _, meta = _abrir_meta(slug)
    agenda = carregar(slug)
    refs_extraidas = {_ref_num(g["ref"]) for g in agenda["gatilhos"]}
    por_cap: dict[str, list[int]] = {}
    for s in meta["secoes"]:
        cap = s.get("cap") or "—"
        d = por_cap.setdefault(cap, [0, 0])
        d[0] += 1
        if s["ref"] in refs_extraidas:
            d[1] += 1
    print(f"{meta['nome']} — {len(agenda['gatilhos'])} gatilhos, "
          f"{len(agenda['locais'])} locais\n")
    print(f"{'capítulo':<44} {'seções':>7} {'c/ gatilho':>11}")
    for cap, (total, com) in por_cap.items():
        marca = "  ·" if com else "   "
        print(f"{marca} {cap[:41]:<41} {total:>7} {com:>11}")
    tipos: dict[str, int] = {}
    for g in agenda["gatilhos"]:
        tipos[g["tipo"]] = tipos.get(g["tipo"], 0) + 1
    if tipos:
        print("\npor tipo: " + " · ".join(f"{k} {v}" for k, v in sorted(tipos.items())))


def ver(slug: str, local: str = "") -> None:
    agenda = carregar(slug)
    itens = agenda["gatilhos"]
    if local:
        alvo = local.upper()
        itens = [g for g in itens
                 if (g.get("local") or "").upper() == alvo
                 or (g["disparo"].get("alvo") or "").upper() == alvo]
        loc = agenda["locais"].get(alvo)
        if loc:
            saidas = " · ".join(f"{s['para']} ({s.get('direcao','?')})"
                                for s in loc.get("saidas", []))
            print(f"# {alvo}. {loc['nome']} [{slug} {_ref_num(loc['ref'])}]")
            print(f"  saídas: {saidas or '—'}\n")
    for g in itens:
        obr = "OBRIGATÓRIO" if g["obrigatorio"] else "opcional"
        guarda = g.get("guarda")
        cond = f" · se {guarda['tipo']}" if guarda else ""
        print(f"[{_ref_num(g['ref'])}] {g['id']}")
        print(f"      {g['disparo']['quando']}"
              f"{' ' + str(g['disparo'].get('alvo')) if g['disparo'].get('alvo') else ''}"
              f" · {g['tipo']} · {obr}{cond}")
        if g.get("resumo"):
            print(f"      {g['resumo']}")


def esquema() -> None:
    print(__doc__)
    print("\n## Estrutura\n")
    print(json.dumps({
        "slug": "cos",
        "locais": {
            "F": {"nome": "River Ivlis Crossroads", "ref": "cos 033",
                  "saidas": [{"para": "G", "direcao": "noroeste", "nota": "desce até o rio"},
                             {"para": "H", "direcao": "sudoeste"},
                             {"para": "E", "direcao": "leste", "nota": "ponte de pedra"}]}
        },
        "gatilhos": [{
            "id": "cos-f-enforcado",
            "ref": "cos 033",
            "local": "F",
            "titulo": "The Hanged One",
            "tipo": "cena",
            "disparo": {"quando": "ao_sair", "alvo": "F"},
            "guarda": None,
            "obrigatorio": True,
            "recorrente": False,
            "rola_dado": False,
            "leitura_obrigatoria": ["cos 033"],
            "resumo": "Corpo cinzento surge na forca; um personagem vê a si mesmo.",
            "verbatim": "As the characters leave the area, read:"
        }]
    }, ensure_ascii=False, indent=2))

    for titulo, vocab in (("tipo", TIPOS), ("disparo.quando", QUANDO), ("guarda.tipo", GUARDAS)):
        print(f"\n## {titulo} (vocabulário FECHADO)\n")
        for k, v in vocab.items():
            print(f"  {k:<22} {v}")

    print("""
## Regras de ouro

1. `verbatim` é a frase do livro que ESTABELECE o gatilho, copiada literal em
   inglês. A validação exige que ela exista na seção citada. Use `…` para
   elidir miolo ("If the characters…read:"); cada fragmento é conferido em ordem.
2. `id`: <slug>-<local em minúscula>-<apelido>. Estável entre regenerações —
   o ledger da campanha aponta para ele.
3. `resumo` em português, 1 linha, sem spoiler de mecânica; é o que o radar
   mostra. O texto de verdade fica no livro, apontado por `leitura_obrigatoria`.
4. NÃO entra aqui: descrição de aposento, bloco de estatística, corpo do texto
   de leitura em voz alta, tabela de tesouro. Isto é AGENDA, não cópia do livro.
5. Na dúvida entre "é gatilho" e "é descrição": só é gatilho se o livro amarra
   a uma CONDIÇÃO (chegar, sair, anoitecer, N dias, uma variável, um nível).
6. `recorrente: true` quando o livro diz "always" / "whenever" / "each time":
   dispara em TODA visita. O ledger registra a última vez, mas o radar nunca
   esconde o gatilho — ter rolado uma vez não o resolve.

## Campos opcionais

  local                 área do mapa; ausente/null = vale na região inteira
  titulo                nome da subseção no livro (em inglês)
  recorrente            bool, ver regra 6 (padrão: false)
  rola_dado             bool, sinaliza que o gatilho exige rolagem
  leitura_obrigatoria   lista de refs a LER antes de narrar (padrão: [ref])
  nota                  ressalva do mestre (contradição do livro, erratum...)
""")


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    cmd, resto = args[0].lower(), args[1:]

    if cmd == "esquema":
        esquema()
    elif cmd in ("validar", "mesclar"):
        if len(resto) < 2:
            sys.exit(f"Uso: python3 ferramentas/gatilhos.py {cmd} <slug> <candidato.json>")
        arquivo = Path(resto[1])
        if not arquivo.exists():
            sys.exit(f"Arquivo não encontrado: {arquivo}")
        try:
            dados = json.loads(arquivo.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            sys.exit(f"JSON inválido em {arquivo}: {e}")
        if cmd == "validar":
            erros, avisos = validar(resto[0], dados)
            for a in avisos:
                print(f"  aviso: {a}")
            for e in erros:
                print(f"  ERRO: {e}")
            n = len(dados.get("gatilhos") or [])
            print(f"\n{n} gatilho(s) · {len(erros)} erro(s) · {len(avisos)} aviso(s)")
            sys.exit(1 if erros else 0)
        mesclar(resto[0], dados)
    elif cmd == "stats":
        if not resto:
            sys.exit("Uso: python3 ferramentas/gatilhos.py stats <slug>")
        stats(resto[0])
    elif cmd == "ver":
        if not resto:
            sys.exit("Uso: python3 ferramentas/gatilhos.py ver <slug> [local]")
        ver(resto[0], resto[1] if len(resto) > 1 else "")
    else:
        sys.exit(f"Comando desconhecido: {cmd}\n{__doc__}")


if __name__ == "__main__":
    main()
