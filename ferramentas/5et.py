#!/usr/bin/env python3
"""Consulta local aos dados oficiais de D&D 5e (mesmos dados do 5e.tools).

Primeiro uso (baixa os dados, ~30 MB):
    python 5et.py baixar

Consultas (busca por nome, sem diferenciar maiúsculas/acentos do inglês):
    python 5et.py magia fireball
    python 5et.py criatura "adult red dragon"
    python 5et.py item "bag of holding"
    python 5et.py condicao grappled
    python 5et.py talento sentinel

Opções:
    --fonte PHB          limita a uma fonte (PHB, XGE, TCE, MM, DMG...)
    --lista              mostra só os nomes encontrados, sem o JSON
    python 5et.py fontes  -> lista as siglas de fontes disponíveis

Imagens (baixadas sob demanda do espelho oficial de imagens):
    python 5et.py token goblin              -> baixa o token da criatura (webp)
    python 5et.py token "goblin boss" --fonte MM
    python 5et.py mapa --aventuras          -> lista as 99 aventuras oficiais
    python 5et.py mapa --aventuras strahd   -> filtra a lista por nome
    python 5et.py mapa CoS                  -> lista os mapas da aventura
    python 5et.py mapa CoS castelo          -> baixa mapas cujo nome contém o termo
    python 5et.py mapa CoS castelo --mestre -> versão do mestre (padrão: Player)
Tokens vão para midia/tokens/ e mapas para midia/mapas/ (servidos pelo app).

A saída é o JSON oficial da entrada — o mestre interpreta as regras a partir dele.
"""
import json
import re
import sys
import unicodedata
import urllib.request
from pathlib import Path
from urllib.parse import quote

BASE = "https://raw.githubusercontent.com/5etools-mirror-3/5etools-src/main/data"
IMG = "https://raw.githubusercontent.com/5etools-mirror-3/5etools-img/main"
DADOS = Path(__file__).parent / "dados-5et"

CATEGORIAS = {
    "magia": ("spell", "spells"),
    "criatura": ("monster", "bestiary"),
    "item": ("item", None),
    "condicao": ("condition", None),
    "talento": ("feat", None),
}
ALIASES = {"spell": "magia", "monster": "criatura", "monstro": "criatura",
           "feat": "talento", "condition": "condicao", "condição": "condicao"}


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "mesa-rpg/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def baixar() -> None:
    DADOS.mkdir(exist_ok=True)
    # Pastas com index.json (um arquivo por fonte)
    for pasta in ("spells", "bestiary"):
        destino = DADOS / pasta
        destino.mkdir(exist_ok=True)
        idx = json.loads(_get(f"{BASE}/{pasta}/index.json"))
        (destino / "index.json").write_bytes(json.dumps(idx).encode())
        print(f"[{pasta}] {len(idx)} fontes...")
        for fonte, arquivo in idx.items():
            try:
                (destino / arquivo).write_bytes(_get(f"{BASE}/{pasta}/{arquivo}"))
            except Exception as e:
                print(f"  aviso: {fonte} falhou ({e})")
    # Arquivos únicos
    for arquivo in ("items.json", "items-base.json", "conditionsdiseases.json",
                    "feats.json"):
        try:
            (DADOS / arquivo).write_bytes(_get(f"{BASE}/{arquivo}"))
            print(f"[{arquivo}] ok")
        except Exception as e:
            print(f"  aviso: {arquivo} falhou ({e})")
    print("\nDados baixados em", DADOS)
    print("Rode 'python 5et.py baixar' de novo no futuro para atualizar.")


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


def _carregar(categoria: str):
    """Gera todas as entradas (dict) da categoria."""
    chave, pasta = CATEGORIAS[categoria]
    if pasta:  # spells / bestiary
        base = DADOS / pasta
        idx = json.loads((base / "index.json").read_text())
        for arquivo in idx.values():
            p = base / arquivo
            if not p.exists():
                continue
            for e in json.loads(p.read_text()).get(chave, []):
                yield e
    elif categoria == "item":
        for arquivo in ("items.json", "items-base.json"):
            p = DADOS / arquivo
            if p.exists():
                dados = json.loads(p.read_text())
                for k in ("item", "baseitem"):
                    for e in dados.get(k, []):
                        yield e
    elif categoria == "condicao":
        dados = json.loads((DADOS / "conditionsdiseases.json").read_text())
        for k in ("condition", "disease", "status"):
            for e in dados.get(k, []):
                yield e
    elif categoria == "talento":
        for e in json.loads((DADOS / "feats.json").read_text()).get("feat", []):
            yield e


def buscar(categoria: str, termo: str, fonte: str | None, so_lista: bool) -> None:
    if not DADOS.exists():
        sys.exit("Dados não encontrados. Rode primeiro: python 5et.py baixar")
    alvo = _norm(termo)
    exatos, parciais = [], []
    for e in _carregar(categoria):
        if fonte and e.get("source", "").upper() != fonte.upper():
            continue
        nome = _norm(e.get("name", ""))
        if nome == alvo:
            exatos.append(e)
        elif alvo in nome:
            parciais.append(e)
    achados = exatos or parciais
    if not achados:
        print(f"Nada encontrado para '{termo}' em {categoria}."
              " Tente parte do nome em inglês.")
        return
    if so_lista or (len(achados) > 3 and not exatos):
        print(f"{len(achados)} resultado(s):")
        for e in achados:
            print(f"  - {e.get('name')} [{e.get('source')}]")
        if not so_lista:
            print("\nRefine o nome ou use --fonte para ver o JSON completo.")
        return
    for e in achados[:3]:
        print(f"\n===== {e.get('name')} [{e.get('source')}] =====")
        print(json.dumps(e, indent=2, ensure_ascii=False))


def fontes() -> None:
    vistos = {}
    for cat in CATEGORIAS:
        try:
            for e in _carregar(cat):
                vistos.setdefault(e.get("source", "?"), 0)
                vistos[e.get("source", "?")] += 1
        except FileNotFoundError:
            pass
    for s in sorted(vistos):
        print(f"  {s:12} {vistos[s]} entradas")


def _salvar(url: str, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(_get(url))
    print(f"salvo: {destino}")


def token(termo: str, fonte: str | None) -> None:
    if not DADOS.exists():
        sys.exit("Dados não encontrados. Rode primeiro: python 5et.py baixar")
    alvo = _norm(termo)
    achados = []
    for e in _carregar("criatura"):
        if fonte and e.get("source", "").upper() != fonte.upper():
            continue
        nome = _norm(e.get("name", ""))
        if nome == alvo:
            achados.insert(0, e)
        elif alvo in nome:
            achados.append(e)
    exatos = [e for e in achados if _norm(e["name"]) == alvo]
    achados = exatos or achados
    if not achados:
        print(f"Criatura '{termo}' não encontrada.")
        return
    if len(achados) > 4:
        print(f"{len(achados)} criaturas — refine o nome ou use --fonte:")
        for e in achados[:20]:
            print(f"  - {e['name']} [{e['source']}]")
        return
    for e in achados:
        t = e.get("token") or {}
        nome = t.get("name", e["name"])
        src = t.get("source", e["source"])
        url = f"{IMG}/bestiary/tokens/{quote(src)}/{quote(nome)}.webp"
        destino = Path(__file__).parent.parent / "midia" / "tokens" / f"{src}-{nome}.webp"
        try:
            _salvar(url, destino)
        except Exception as ex:
            print(f"sem token para {nome} [{src}] ({ex})")


def _imagens_da_aventura(dados) -> list[tuple[str, str, str]]:
    """Retorna (imageType, path, título) de todas as imagens do JSON."""
    achadas = []

    def anda(obj):
        if isinstance(obj, dict):
            href = obj.get("href")
            if obj.get("type") == "image" and isinstance(href, dict):
                achadas.append((obj.get("imageType", ""),
                                href.get("path", ""),
                                obj.get("title", Path(href.get("path", "")).stem)))
            for v in obj.values():
                anda(v)
        elif isinstance(obj, list):
            for v in obj:
                anda(v)

    anda(dados)
    return achadas


def mapa(args: list[str], mestre: bool) -> None:
    if not args or args[0] == "--aventuras":
        idx = json.loads(_get(f"{BASE}/adventures.json"))["adventure"]
        filtro = _norm(" ".join(args[1:])) if len(args) > 1 else ""
        for a in idx:
            if filtro and filtro not in _norm(a["name"]) \
                    and filtro not in _norm(a["id"]):
                continue
            print(f"  {a['id']:14} {a['name']}")
        return
    aid = args[0]
    filtro = _norm(" ".join(args[1:])) if len(args) > 1 else ""
    try:
        dados = json.loads(_get(f"{BASE}/adventure/adventure-{aid.lower()}.json"))
    except Exception:
        sys.exit(f"Aventura '{aid}' não encontrada. "
                 "Liste com: python 5et.py mapa --aventuras")
    tipo = "map" if mestre else "mapPlayer"
    mapas = [(p, t) for it, p, t in _imagens_da_aventura(dados) if it == tipo]
    if not mapas and not mestre:  # aventura sem versão Player: cai na do mestre
        mapas = [(p, t) for it, p, t in _imagens_da_aventura(dados) if it == "map"]
    if filtro:
        mapas = [(p, t) for p, t in mapas if filtro in _norm(t) or filtro in _norm(p)]
    if not mapas:
        print("Nenhum mapa encontrado com esse filtro.")
        return
    if len(args) == 1:  # só listar
        print(f"{len(mapas)} mapa(s) em {aid}:")
        for p, t in mapas:
            nome = Path(p).stem if t in ("", "Player Version") else t
            print(f"  - {nome}")
        print("\nBaixe com: python 5et.py mapa", aid, "<parte do nome>")
        return
    for p, _ in mapas:
        destino = Path(__file__).parent.parent / "midia" / "mapas" / Path(p).name
        try:
            _salvar(f"{IMG}/{quote(p)}", destino)
        except Exception as ex:
            print(f"falhou {p} ({ex})")


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    cmd = ALIASES.get(args[0].lower(), args[0].lower())
    if cmd in ("baixar", "atualizar"):
        baixar()
        return
    if cmd == "fontes":
        fontes()
        return
    if cmd == "token":
        resto = [a for a in args[1:]]
        fonte = None
        if "--fonte" in resto:
            i = resto.index("--fonte")
            fonte = resto[i + 1]
            del resto[i:i + 2]
        if not resto:
            sys.exit("Informe a criatura. Ex.: python 5et.py token goblin")
        token(" ".join(resto), fonte)
        return
    if cmd in ("mapa", "mapas"):
        resto = [a for a in args[1:]]
        mestre = "--mestre" in resto
        resto = [a for a in resto if a != "--mestre"]
        mapa(resto, mestre)
        return
    if cmd not in CATEGORIAS:
        sys.exit(f"Categoria desconhecida: {cmd}. "
                 f"Use: {', '.join(CATEGORIAS)}, token, mapa")
    fonte = None
    so_lista = "--lista" in args
    args = [a for a in args[1:] if a != "--lista"]
    if "--fonte" in args:
        i = args.index("--fonte")
        fonte = args[i + 1]
        del args[i:i + 2]
    if not args:
        sys.exit("Informe o nome a buscar. Ex.: python 5et.py magia fireball")
    buscar(cmd, " ".join(args), fonte, so_lista)


if __name__ == "__main__":
    main()
