#!/usr/bin/env python3
"""Aventuras oficiais publicadas — importação, índice e consulta.

Baixa o texto integral de uma aventura oficial do 5e.tools, quebra em seções
legíveis e permite consultar sob demanda, sem jogar o livro inteiro no contexto.

    python aventura.py listar                 -> aventuras oficiais disponíveis
    python aventura.py listar strahd          -> filtra a lista
    python aventura.py importar CoS           -> baixa, renderiza e indexa
    python aventura.py importadas             -> o que já está neste repositório

    python aventura.py indice cos             -> sumário navegável
    python aventura.py indice cos 4           -> sumário só do capítulo 4
    python aventura.py buscar cos "tarokka"   -> seções mais relevantes + trechos
    python aventura.py ler cos 037            -> texto integral de uma seção
    python aventura.py ler cos 037-039        -> várias seções seguidas

O texto vai para aventuras/<slug>/texto/NNN-<nome>.md — conteúdo do mestre,
nunca mostre ao jogador.
"""
import json
import math
import re
import sys
import unicodedata
import urllib.request
from collections import Counter
from pathlib import Path

BASE = "https://raw.githubusercontent.com/5etools-mirror-3/5etools-src/main/data"
RAIZ = Path(__file__).parent.parent
AVENTURAS = RAIZ / "aventuras"

# uma seção deste tamanho já é um bom pedaço para ler de uma vez (~3k tokens)
LIMITE_SECAO = 12000
PROF_MAX = 3


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "mesa-rpg/1.0"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read()


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9 ]", " ", s.lower()).strip()


def _slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return (s or "secao")[:48]


# --------------------------------------------------------------------------
# tags {@...} do formato 5etools
# --------------------------------------------------------------------------
# a maioria segue {@tag nome|fonte|textoExibido}: o campo 2 manda quando existe
CAMPO2 = {
    "creature", "spell", "item", "condition", "skill", "sense", "race", "deck",
    "variantrule", "background", "feat", "reward", "hazard", "status", "table",
    "recipe", "deity", "object", "trap", "disease", "language", "action",
    "optfeature", "classfeature", "subclassfeature", "class", "filter", "vehicle",
    "psionic", "charoption", "cult", "boon",
}
# estes usam o primeiro campo como texto (o resto é rota interna do site)
CAMPO0 = {"area", "adventure", "book", "card", "note", "footnote", "5etools",
          "homebrew", "loader", "link"}
ATAQUES = {"mw": "Melee Weapon Attack:", "rw": "Ranged Weapon Attack:",
           "ms": "Melee Spell Attack:", "rs": "Ranged Spell Attack:"}
TAG_RE = re.compile(r"\{@(\w+)(?: ([^{}]*))?\}")


def _tag(m: re.Match) -> str:
    tag = m.group(1).lower()
    campos = (m.group(2) or "").split("|")
    p0 = campos[0].strip()

    if tag in ("b", "bold"):
        return f"**{p0}**"
    if tag in ("i", "italic"):
        return f"*{p0}*"
    if tag in ("s", "strike"):
        return f"~~{p0}~~"
    if tag == "dc":
        return f"DC {p0}"
    if tag in ("dice", "damage", "scaledice", "scaledamage", "autodice"):
        return campos[1].strip() if len(campos) > 1 and campos[1].strip() else p0
    if tag == "hit":
        return f"+{p0}" if not p0.startswith(("+", "-")) else p0
    if tag == "chance":
        return f"{p0} percent"
    if tag == "recharge":
        return f"(Recharge {p0}-6)" if p0 else "(Recharge 6)"
    if tag == "h":
        return "Hit: "
    if tag == "atk":
        return ATAQUES.get(p0, p0)
    if tag == "quickref":
        uteis = [c.strip() for c in campos if c.strip()]
        return uteis[-1] if len(uteis) > 1 else p0
    if tag in CAMPO0:
        return p0
    if tag in CAMPO2 and len(campos) > 2 and campos[2].strip():
        return campos[2].strip()
    return p0


def limpar(texto: str) -> str:
    """Resolve as tags {@...}, inclusive aninhadas."""
    for _ in range(5):
        novo = TAG_RE.sub(_tag, texto)
        if novo == texto:
            break
        texto = novo
    return texto


# --------------------------------------------------------------------------
# JSON de aventura -> markdown
# --------------------------------------------------------------------------
def _celula(c) -> str:
    if isinstance(c, str):
        return limpar(c).replace("\n", " ")
    if isinstance(c, dict):
        r = c.get("roll") or {}
        if "exact" in r:
            return str(r["exact"])
        if "min" in r or "max" in r:
            return f"{r.get('min', '')}-{r.get('max', '')}"
        if c.get("entries"):
            return " ".join(_celula(e) for e in c["entries"])
        if c.get("entry"):
            return _celula(c["entry"])
    return str(c)


def _tabela(e: dict, saida: list) -> None:
    if e.get("caption"):
        saida.append(f"**{limpar(e['caption'])}**\n")
    cols = e.get("colLabels") or []
    linhas = e.get("rows") or []
    if not cols and linhas:
        cols = [""] * len(linhas[0])
    if cols:
        saida.append("| " + " | ".join(limpar(str(c)) for c in cols) + " |")
        saida.append("|" + "|".join(["---"] * len(cols)) + "|")
    for linha in linhas:
        if isinstance(linha, dict):
            linha = linha.get("row", [])
        saida.append("| " + " | ".join(_celula(c) for c in linha) + " |")
    saida.append("")


def render(entrada, saida: list, nivel: int = 3) -> None:
    """Converte uma entrada do formato 5etools em markdown, acumulando em `saida`."""
    if isinstance(entrada, str):
        saida.append(limpar(entrada) + "\n")
        return
    if isinstance(entrada, list):
        for e in entrada:
            render(e, saida, nivel)
        return
    if not isinstance(entrada, dict):
        return

    tipo = entrada.get("type", "entries")

    if tipo == "image":
        href = entrada.get("href") or {}
        titulo = entrada.get("title") or Path(href.get("path", "")).stem
        marca = {"map": "MAPA (versão do mestre)", "mapPlayer": "MAPA (versão do jogador)"}
        rotulo = marca.get(entrada.get("imageType", ""), "Ilustração")
        saida.append(f"*[{rotulo}: {limpar(titulo)}]*\n")
        return
    if tipo == "gallery":
        for img in entrada.get("images", []):
            render(img, saida, nivel)
        return
    if tipo == "table":
        _tabela(entrada, saida)
        return
    if tipo in ("list",):
        for it in entrada.get("items", []):
            if isinstance(it, str):
                saida.append(f"- {limpar(it)}")
            elif isinstance(it, dict) and it.get("name"):
                corpo = []
                render(it.get("entries") or it.get("entry") or [], corpo, nivel + 1)
                texto = " ".join(x.strip() for x in corpo if x.strip())
                saida.append(f"- **{limpar(it['name'])}.** {texto}")
            else:
                render(it, saida, nivel)
        saida.append("")
        return
    if tipo == "quote":
        corpo = []
        render(entrada.get("entries", []), corpo, nivel)
        for linha in "\n".join(corpo).split("\n"):
            saida.append(f"> {linha}" if linha.strip() else ">")
        if entrada.get("by"):
            saida.append(f"> — {limpar(entrada['by'])}")
        saida.append("")
        return
    if tipo in ("inset", "insetReadaloud"):
        rotulo = ("LER EM VOZ ALTA" if tipo == "insetReadaloud"
                  else "QUADRO" + (f": {limpar(entrada['name'])}" if entrada.get("name") else ""))
        corpo = []
        render(entrada.get("entries", []), corpo, nivel)
        saida.append(f"> **[{rotulo}]**")
        for linha in "\n".join(corpo).split("\n"):
            saida.append(f"> {linha}" if linha.strip() else ">")
        saida.append("")
        return

    # entries / section / internal / none / item / demais contêineres
    if entrada.get("name"):
        saida.append(f"{'#' * min(nivel, 6)} {limpar(entrada['name'])}\n")
    if entrada.get("entry"):
        render(entrada["entry"], saida, nivel + 1)
    render(entrada.get("entries", []), saida, nivel + 1)


def _texto_de(entrada, sem_nome: bool = False) -> str:
    # o nome vira o título do arquivo da seção; repeti-lo no corpo só polui
    if sem_nome and isinstance(entrada, dict) and entrada.get("name"):
        entrada = {k: v for k, v in entrada.items() if k != "name"}
    saida: list = []
    render(entrada, saida, 3)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(saida)).strip()


def _quebrar(no: dict, cap: str, prof: int) -> list[dict]:
    """Quebra um capítulo em seções de tamanho consultável."""
    texto = _texto_de(no, sem_nome=True)
    nome = no.get("name") or "(sem título)"
    if len(texto) <= LIMITE_SECAO or prof >= PROF_MAX:
        return [{"titulo": nome, "cap": cap, "texto": texto}]

    filhos = [e for e in no.get("entries", [])
              if isinstance(e, dict) and e.get("name") and e.get("entries")]
    if not filhos:
        return [{"titulo": nome, "cap": cap, "texto": texto}]

    secoes = []
    # o que vem antes do primeiro filho nomeado é a abertura do capítulo
    corte = no["entries"].index(filhos[0])
    abertura = _texto_de({"type": "entries", "entries": no["entries"][:corte]})
    if abertura.strip():
        secoes.append({"titulo": f"{nome} — abertura", "cap": cap, "texto": abertura})
    for f in filhos:
        secoes += _quebrar(f, cap, prof + 1)
    return secoes


# --------------------------------------------------------------------------
# importar
# --------------------------------------------------------------------------
def _catalogo() -> list[dict]:
    return json.loads(_get(f"{BASE}/adventures.json"))["adventure"]


def listar(filtro: str) -> None:
    alvo = _norm(filtro)
    achou = 0
    for a in _catalogo():
        if alvo and alvo not in _norm(a["name"]) and alvo not in _norm(a["id"]):
            continue
        achou += 1
        print(f"  {a['id']:14} {a['name']}")
    if not achou:
        print(f"Nenhuma aventura com '{filtro}'.")
    else:
        print(f"\nImporte com: python ferramentas/aventura.py importar <ID>")


def importar(aid: str) -> None:
    catalogo = {a["id"].lower(): a for a in _catalogo()}
    meta = catalogo.get(aid.lower())
    if not meta:
        sys.exit(f"Aventura '{aid}' não existe. Liste com: "
                 "python ferramentas/aventura.py listar")
    print(f"Baixando {meta['name']} [{meta['id']}]...")
    bruto = _get(f"{BASE}/adventure/adventure-{meta['id'].lower()}.json")
    dados = json.loads(bruto)

    slug = _slug(meta["id"])
    pasta = AVENTURAS / slug
    (pasta / "texto").mkdir(parents=True, exist_ok=True)
    for antigo in (pasta / "texto").glob("*.md"):
        antigo.unlink()
    (pasta / "fonte.json").write_bytes(bruto)

    secoes: list[dict] = []
    for cap in dados["data"]:
        secoes += _quebrar(cap, cap.get("name") or "(sem título)", 1)

    indice = [f"# {meta['name']} — sumário", "",
              f"Fonte: 5e.tools · id `{meta['id']}` · {len(secoes)} seções.",
              "Leia uma seção com `python ferramentas/aventura.py ler "
              f"{slug} <ref>`.", "",
              "| ref | capítulo | seção | chars |", "|---|---|---|---|"]
    cap_atual = None
    for i, s in enumerate(secoes, 1):
        ref = f"{i:03d}"
        s["ref"] = ref
        arquivo = pasta / "texto" / f"{ref}-{_slug(s['titulo'])}.md"
        cabecalho = (f"<!-- {meta['name']} · seção {ref} · capítulo: {s['cap']} -->\n"
                     f"# [{ref}] {s['titulo']}\n")
        arquivo.write_text(f"{cabecalho}\n{s['texto']}\n", encoding="utf-8")
        s["arquivo"] = arquivo.name
        cap = s["cap"] if s["cap"] != cap_atual else ""
        cap_atual = s["cap"]
        indice.append(f"| {ref} | {cap} | {s['titulo']} | {len(s['texto'])} |")

    (pasta / "indice.md").write_text("\n".join(indice) + "\n", encoding="utf-8")
    (pasta / "meta.json").write_text(json.dumps(
        {"id": meta["id"], "nome": meta["name"], "slug": slug,
         "secoes": [{k: s[k] for k in ("ref", "titulo", "cap", "arquivo")}
                    for s in secoes]},
        ensure_ascii=False, indent=2), encoding="utf-8")

    chars = sum(len(s["texto"]) for s in secoes)
    print(f"\n{len(secoes)} seções · {chars:,} caracteres (~{chars // 4:,} tokens)"
          .replace(",", "."))
    print(f"Gravado em aventuras/{slug}/")
    print(f"\nSumário:  python ferramentas/aventura.py indice {slug}")
    print(f"Busca:    python ferramentas/aventura.py buscar {slug} \"<termo>\"")


# --------------------------------------------------------------------------
# consultar
# --------------------------------------------------------------------------
def _abrir(slug: str) -> tuple[Path, dict]:
    pasta = AVENTURAS / slug.lower()
    arq = pasta / "meta.json"
    if not arq.exists():
        disponiveis = [p.name for p in AVENTURAS.glob("*") if (p / "meta.json").exists()]
        sys.exit(f"Aventura '{slug}' não importada. "
                 + (f"Importadas: {', '.join(disponiveis)}" if disponiveis
                    else "Importe com: python ferramentas/aventura.py importar <ID>"))
    return pasta, json.loads(arq.read_text(encoding="utf-8"))


def importadas() -> None:
    achou = False
    for p in sorted(AVENTURAS.glob("*")):
        if not (p / "meta.json").exists():
            continue
        m = json.loads((p / "meta.json").read_text(encoding="utf-8"))
        print(f"  {m['slug']:10} {m['nome']} ({len(m['secoes'])} seções)")
        achou = True
    if not achou:
        print("Nenhuma aventura importada ainda.")


def indice(slug: str, filtro: str) -> None:
    pasta, meta = _abrir(slug)
    alvo = _norm(filtro)
    cap_atual = None
    mostrou = 0
    for s in meta["secoes"]:
        if alvo and alvo not in _norm(s["cap"]) and alvo not in _norm(s["titulo"]):
            continue
        if s["cap"] != cap_atual:
            print(f"\n{s['cap']}")
            cap_atual = s["cap"]
        print(f"  [{s['ref']}] {s['titulo']}")
        mostrou += 1
    if not mostrou:
        print(f"Nada no sumário de {meta['nome']} com '{filtro}'.")
    else:
        print(f"\n{mostrou} seção(ões). Leia com: "
              f"python ferramentas/aventura.py ler {meta['slug']} <ref>")


def _corpo(pasta: Path, s: dict) -> str:
    return (pasta / "texto" / s["arquivo"]).read_text(encoding="utf-8")


def _sem_cabecalho(texto: str) -> str:
    """Tira o comentário e o título do arquivo — o trecho da busca é do corpo."""
    return re.sub(r"\A(<!--.*?-->\n)?(# \[\d+\].*\n)?", "", texto).strip()


def buscar(slug: str, termo: str, quantas: int) -> None:
    pasta, meta = _abrir(slug)
    palavras = [p for p in _norm(termo).split() if len(p) > 1]
    if not palavras:
        sys.exit("Informe um termo de busca.")

    docs, textos = [], []
    for s in meta["secoes"]:
        bruto = _corpo(pasta, s)
        textos.append(_sem_cabecalho(bruto))
        docs.append(Counter(_norm(bruto).split()))

    n = len(docs)
    media = sum(sum(d.values()) for d in docs) / max(n, 1)
    df = {p: sum(1 for d in docs if d[p]) for p in palavras}

    notas = []
    for i, d in enumerate(docs):
        tam = sum(d.values()) or 1
        nota = 0.0
        for p in palavras:
            if not d[p]:
                continue
            idf = math.log(1 + (n - df[p] + 0.5) / (df[p] + 0.5))
            tf = d[p]
            nota += idf * tf * 2.5 / (tf + 1.5 * (0.25 + 0.75 * tam / media))
        if nota:
            notas.append((nota, i))
    notas.sort(reverse=True)

    if not notas:
        print(f"Nada encontrado para '{termo}' em {meta['nome']}.")
        return
    print(f"{len(notas)} seção(ões) de {n} — busca: {termo}\n")
    for nota, i in notas[:quantas]:
        s = meta["secoes"][i]
        print(f"[{s['ref']}] {s['cap']} › {s['titulo']}  (relevância {nota:.1f})")
        print(f"      {_trecho(textos[i], palavras)}\n")
    print(f"Leia com: python ferramentas/aventura.py ler {meta['slug']} "
          f"{notas[0][1] + 1:03d}")


def _trecho(texto: str, palavras: list[str], largura: int = 260) -> str:
    plano = re.sub(r"\s+", " ", texto)
    alvo = _norm(plano)
    melhor, pos = -1, 0
    for m in re.finditer(r"\w+", alvo):
        if m.group(0) not in palavras:
            continue
        janela = alvo[m.start():m.start() + largura]
        conta = sum(janela.count(p) for p in palavras)
        if conta > melhor:
            melhor, pos = conta, m.start()
    ini = max(0, pos - 60)
    corte = plano[ini:ini + largura].strip()
    return ("…" if ini else "") + corte + "…"


def ler(slug: str, refs: str) -> None:
    pasta, meta = _abrir(slug)
    por_ref = {s["ref"]: s for s in meta["secoes"]}
    ordem = [s["ref"] for s in meta["secoes"]]

    alvos: list[str] = []
    for pedaco in refs.split(","):
        pedaco = pedaco.strip()
        if "-" in pedaco and all(x.strip().isdigit() for x in pedaco.split("-", 1)):
            a, b = (x.strip() for x in pedaco.split("-", 1))
            alvos += [r for r in ordem if int(a) <= int(r) <= int(b)]
        elif pedaco.isdigit():
            alvos.append(f"{int(pedaco):03d}")
        else:  # busca por nome da seção
            alvo = _norm(pedaco)
            alvos += [s["ref"] for s in meta["secoes"] if alvo in _norm(s["titulo"])]

    alvos = [r for r in dict.fromkeys(alvos) if r in por_ref]
    if not alvos:
        sys.exit(f"Nenhuma seção '{refs}' em {meta['nome']}. "
                 f"Veja: python ferramentas/aventura.py indice {meta['slug']}")

    for ref in alvos:
        print(_corpo(pasta, por_ref[ref]))
        i = ordem.index(ref)
        antes = ordem[i - 1] if i else "—"
        depois = ordem[i + 1] if i + 1 < len(ordem) else "—"
        print(f"\n<!-- seção anterior: {antes} · próxima: {depois} -->\n")


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    cmd = args[0].lower()
    resto = args[1:]

    if cmd == "listar":
        listar(" ".join(resto))
    elif cmd == "importar":
        if not resto:
            sys.exit("Informe o ID. Ex.: python aventura.py importar CoS")
        importar(resto[0])
    elif cmd == "importadas":
        importadas()
    elif cmd == "indice":
        if not resto:
            sys.exit("Informe a aventura. Ex.: python aventura.py indice cos")
        indice(resto[0], " ".join(resto[1:]))
    elif cmd == "buscar":
        if len(resto) < 2:
            sys.exit("Uso: python aventura.py buscar <aventura> \"<termo>\"")
        quantas = 5
        if "--n" in resto:
            i = resto.index("--n")
            quantas = int(resto[i + 1])
            del resto[i:i + 2]
        buscar(resto[0], " ".join(resto[1:]), quantas)
    elif cmd == "ler":
        if len(resto) < 2:
            sys.exit("Uso: python aventura.py ler <aventura> <ref>")
        ler(resto[0], " ".join(resto[1:]))
    else:
        sys.exit(f"Comando desconhecido: {cmd}\n{__doc__}")


if __name__ == "__main__":
    main()
