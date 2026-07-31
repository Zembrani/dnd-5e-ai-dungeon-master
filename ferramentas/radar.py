#!/usr/bin/env python3
"""Radar da mesa — cruza a agenda do livro com o estado da campanha. Sem LLM.

Responde, deterministicamente, à única pergunta que o mestre erra sob pressão:
"o que está armado AQUI e o que eu tenho de ler ANTES de narrar?"

    python3 radar.py                      -> painel completo
    python3 radar.py --hook               -> versão compacta (injetada a cada turno)
    python3 radar.py local F              -> o que está armado na área F
    python3 radar.py rota E I             -> caminho + gatilhos de cada parada
    python3 radar.py pendentes            -> obrigatórios ainda não resolvidos
    python3 radar.py resolver <id> disparado|pulado|adiado "nota"
    python3 radar.py anotar <id> <local> <quando> "resumo"   -> gatilho do mestre

Lê: aventuras/<slug>/gatilhos.json (livro, imutável)
    estado/situacao.json              (onde o grupo está / variáveis de campanha)
    estado/gatilhos.json              (ledger APPEND-ONLY do que já resolveu)

Nada aqui narra. O radar aponta a seção; quem lê é o mestre.
"""
import json
import sys
from collections import deque
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).parent.parent
ESTADO = RAIZ / "estado"
SITUACAO = ESTADO / "situacao.json"
LEDGER = ESTADO / "gatilhos.json"

ARMADO, CONDICIONAL, DORMENTE = "ARMADO", "CONDICIONAL", "DORMENTE"
MAX_LINHAS_HOOK = 34


def _json(p: Path, padrao: dict) -> dict:
    if not p.exists():
        return dict(padrao)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"  (radar: {p.name} inválido — {e})", file=sys.stderr)
        return dict(padrao)


def situacao() -> dict:
    return _json(SITUACAO, {"aventura": "", "local_atual": "", "rota_planejada": [],
                            "companhia": [], "variaveis": {}})


def ledger() -> dict:
    return _json(LEDGER, {"resolucoes": [], "manuais": []})


def agenda(slug: str) -> dict:
    p = RAIZ / "aventuras" / slug.lower() / "gatilhos.json"
    dados = _json(p, {"locais": {}, "gatilhos": []})
    manuais = ledger().get("manuais", [])
    if manuais:
        dados = {**dados, "gatilhos": list(dados.get("gatilhos", [])) + manuais}
    return dados


def resolvidos() -> dict[str, dict]:
    """Última resolução de cada id (o ledger é append-only; a última manda)."""
    ultimo: dict[str, dict] = {}
    for r in ledger().get("resolucoes", []):
        ultimo[r["id"]] = r
    return ultimo


def _cav(v) -> str:
    return str(v).strip().lower()


def _var(variaveis: dict, caminho: str):
    alvo = variaveis
    for parte in caminho.split("."):
        if not isinstance(alvo, dict) or parte not in alvo:
            return None
        alvo = alvo[parte]
    return alvo


def avaliar(g: dict, sit: dict) -> tuple[str, str]:
    """(estado, motivo). CONDICIONAL = precisa do julgamento do mestre."""
    guarda = g.get("guarda")
    if not guarda:
        return ARMADO, ""
    tipo = guarda.get("tipo")
    companhia = {_cav(c) for c in sit.get("companhia", [])}

    if tipo == "variavel":
        nome = guarda.get("nome", "")
        valor = _var(sit.get("variaveis", {}), nome)
        if valor is None:
            return CONDICIONAL, f"variável {nome} indefinida"
        if "igual" in guarda:
            ok = _cav(valor) == _cav(guarda["igual"])
            return (ARMADO, f"{nome}={valor}") if ok else (DORMENTE, f"{nome}={valor}")
        return (ARMADO, f"{nome}={valor}") if valor else (DORMENTE, f"{nome}={valor}")

    if tipo in ("acompanhado_por", "nao_acompanhado_por"):
        tem = _cav(guarda.get("valor", "")) in companhia
        quer = tipo == "acompanhado_por"
        motivo = f"{guarda.get('valor')} {'na' if tem else 'fora da'} companhia"
        return (ARMADO, motivo) if tem == quer else (DORMENTE, motivo)

    if tipo == "ja_disparou":
        outro = resolvidos().get(guarda.get("valor", ""))
        ok = bool(outro) and outro.get("estado") == "disparado"
        return (ARMADO, "") if ok else (DORMENTE, f"depende de {guarda.get('valor')}")

    return CONDICIONAL, guarda.get("descricao") or f"guarda '{tipo}' — decisão de mesa"


def _linha(g: dict, estado: str, motivo: str, res: dict | None) -> str:
    marca = {"disparado": "✔", "pulado": "✗", "adiado": "…"}.get(
        (res or {}).get("estado", ""), " ")
    obr = "!" if g.get("obrigatorio") else " "
    quando = g["disparo"]["quando"]
    alvo = g["disparo"].get("alvo") or ""
    cauda = f" ({motivo})" if motivo else ""
    txt = f" {marca}{obr} [{quando} {alvo}".rstrip() + f"] {g['id']} — {estado}{cauda}"
    if g.get("resumo"):
        txt += f"\n       {g['resumo']}"
    return txt


def gatilhos_de(local: str, dados: dict, quando: tuple[str, ...] = ()) -> list[dict]:
    alvo = (local or "").upper()
    saida = []
    for g in dados.get("gatilhos", []):
        d = g["disparo"]
        casa_local = (g.get("local") or "").upper() == alvo or (d.get("alvo") or "").upper() == alvo
        if casa_local and (not quando or d["quando"] in quando):
            saida.append(g)
    return saida


def _bloco(titulo: str, itens: list[dict], sit: dict, res: dict,
           esconder_resolvidos: bool = True) -> list[str]:
    linhas = []
    for g in itens:
        r = res.get(g["id"])
        # gatilho recorrente ("sempre que chegarem em F") nunca some da lista:
        # ter disparado uma vez não o resolve — é justamente o erro que isto evita
        if (esconder_resolvidos and r and not g.get("recorrente")
                and r["estado"] in ("disparado", "pulado")):
            continue
        estado, motivo = avaliar(g, sit)
        if estado == DORMENTE:
            continue
        linhas.append(_linha(g, estado, motivo, r))
    if not linhas:
        return []
    return [titulo] + linhas


def _nome_local(dados: dict, chave: str) -> str:
    if not chave or chave == "?":
        return "REGIÃO (vale de Barovia — vale em qualquer lugar)"
    loc = dados.get("locais", {}).get((chave or "").upper())
    if not loc:
        return chave
    return f"{chave.upper()}. {loc['nome']} [{dados.get('slug','?')} {loc['ref'].split()[-1]}]"


def _grafo(dados: dict) -> dict[str, set[str]]:
    g: dict[str, set[str]] = {}
    for chave, loc in dados.get("locais", {}).items():
        g.setdefault(chave.upper(), set())
        for s in loc.get("saidas", []):
            destino = (s.get("para") or "").upper()
            if not destino:
                continue
            g[chave.upper()].add(destino)
            if not s.get("mao_unica"):
                g.setdefault(destino, set()).add(chave.upper())
    return g


def caminho(dados: dict, de: str, para: str) -> list[str]:
    de, para = de.upper(), para.upper()
    g = _grafo(dados)
    if de not in g or para not in g:
        return []
    fila, visto = deque([[de]], ), {de}
    while fila:
        rota = fila.popleft()
        if rota[-1] == para:
            return rota
        for viz in sorted(g.get(rota[-1], ())):
            if viz not in visto:
                visto.add(viz)
                fila.append(rota + [viz])
    return []


# --------------------------------------------------------------------------
# painéis
# --------------------------------------------------------------------------
def painel(compacto: bool = False) -> list[str]:
    sit = situacao()
    slug = sit.get("aventura") or ""
    if not slug:
        return ["(radar: estado/situacao.json sem 'aventura' — campanha original, "
                "sem agenda de módulo)"]
    dados = agenda(slug)
    if not dados.get("gatilhos"):
        return [f"(radar: aventuras/{slug}/gatilhos.json vazio — rode /extrair-gatilhos)"]
    res = resolvidos()
    atual = (sit.get("local_atual") or "").upper()
    out = [f"=== RADAR DA MESA · {slug.upper()} (determinístico, não é narração) ==="]

    cabecalho = f"Local: {_nome_local(dados, atual)}"
    extras = []
    if sit.get("nivel"):
        extras.append(f"nível {sit['nivel']}")
    if sit.get("dia_no_mundo"):
        extras.append(f"dia {sit['dia_no_mundo']} {sit.get('momento','')}".strip())
    if sit.get("companhia"):
        extras.append("com " + ", ".join(sit["companhia"]))
    out.append(cabecalho + (" · " + " · ".join(extras) if extras else ""))

    loc = dados.get("locais", {}).get(atual)
    if loc:
        saidas = " · ".join(f"{s['para']} ({s.get('direcao','?')})"
                            for s in loc.get("saidas", []))
        out.append(f"Saídas: {saidas or '—'}")
        out.append(f"LER ANTES DE NARRAR: {loc['ref']}")

    out += _bloco("AQUI (ao chegar / enquanto está):",
                  gatilhos_de(atual, dados, ("ao_chegar", "se_variavel", "ao_anoitecer",
                                             "manual", "ao_nivel")), sit, res)
    saindo = _bloco("AO SAIR DAQUI — dispara sozinho, não é opcional:",
                    gatilhos_de(atual, dados, ("ao_sair",)), sit, res)
    out += saindo

    rota = [r.upper() for r in sit.get("rota_planejada", []) if r.upper() != atual]
    if rota:
        prox = rota[0]
        out.append(f"PRÓXIMA PARADA: {_nome_local(dados, prox)}"
                   f"{'  (rota: ' + ' → '.join(rota) + ')' if len(rota) > 1 else ''}")
        out += _bloco("  armado lá:", gatilhos_de(prox, dados,
                                                  ("ao_chegar", "se_variavel")), sit, res)

    globais = [g for g in dados["gatilhos"] if not g.get("local")]
    if globais:
        out.append("REGRAS PERMANENTES DA REGIÃO (valem em qualquer lugar):")
        for g in globais:
            out.append(f"    · {g.get('titulo') or g['id']} [{g['ref']}] — "
                       f"{(g.get('resumo') or '')[:96]}")

    indefinidas = []
    for g in dados["gatilhos"]:
        guarda = g.get("guarda") or {}
        if guarda.get("tipo") == "variavel":
            nome = guarda.get("nome", "")
            if _var(sit.get("variaveis", {}), nome) is None and nome not in indefinidas:
                indefinidas.append(nome)
    if indefinidas:
        out.append("VARIÁVEIS INDEFINIDAS (o livro depende delas): "
                   + ", ".join(indefinidas[:6]))

    pend = [g for g in dados["gatilhos"]
            if g.get("obrigatorio") and g["id"] not in res
            and g.get("local") and not g.get("recorrente")
            and g["local"].upper() != atual
            and avaliar(g, sit)[0] == ARMADO]
    if pend:
        out.append(f"PENDENTES obrigatórios em outros locais: {len(pend)} "
                   f"(python3 ferramentas/radar.py pendentes)")

    if compacto and len(out) > MAX_LINHAS_HOOK:
        out = out[:MAX_LINHAS_HOOK] + [f"… (+{len(out)-MAX_LINHAS_HOOK} linhas: "
                                       f"python3 ferramentas/radar.py)"]
    return out


def painel_local(chave: str) -> list[str]:
    sit = situacao()
    dados = agenda(sit.get("aventura", ""))
    res = resolvidos()
    out = [f"# {_nome_local(dados, chave)}"]
    loc = dados.get("locais", {}).get(chave.upper())
    if loc:
        out.append("saídas: " + (" · ".join(f"{s['para']} ({s.get('direcao','?')})"
                                            for s in loc.get("saidas", [])) or "—"))
    itens = gatilhos_de(chave, dados)
    if not itens:
        out.append("(nenhum gatilho extraído para este local)")
    for g in itens:
        estado, motivo = avaliar(g, sit)
        out.append(_linha(g, estado, motivo, res.get(g["id"])))
        out.append(f"       ler: {', '.join(g.get('leitura_obrigatoria') or [g['ref']])}")
    return out


def painel_rota(de: str, para: str) -> list[str]:
    sit = situacao()
    dados = agenda(sit.get("aventura", ""))
    res = resolvidos()
    rota = caminho(dados, de, para)
    if not rota:
        return [f"Sem caminho conhecido de {de.upper()} a {para.upper()} no grafo extraído. "
                f"Confira o mapa antes de narrar a viagem."]
    out = [f"ROTA {' → '.join(rota)}  ({len(rota)-1} pernas)",
           "Nenhuma parada pode ser narrada como cenário de passagem: descreva e "
           "devolva a vez ao jogador.", ""]
    for i, chave in enumerate(rota):
        out.append(f"--- {i+1}. {_nome_local(dados, chave)}")
        quando = ("ao_chegar", "se_variavel") if i else ("ao_sair",)
        if i and i < len(rota) - 1:
            quando = ("ao_chegar", "se_variavel", "ao_sair")
        for g in gatilhos_de(chave, dados, quando):
            estado, motivo = avaliar(g, sit)
            if estado == DORMENTE:
                continue
            out.append(_linha(g, estado, motivo, res.get(g["id"])))
    return out


def painel_pendentes() -> list[str]:
    sit = situacao()
    dados = agenda(sit.get("aventura", ""))
    res = resolvidos()
    out, por_local = ["PENDÊNCIAS — gatilhos do livro ainda sem resolução"], {}
    for g in dados.get("gatilhos", []):
        # recorrentes e regras permanentes da região não são "pendência":
        # aparecem sempre no painel do local, não nesta lista
        if g["id"] in res or g.get("recorrente") or not g.get("local"):
            continue
        estado, motivo = avaliar(g, sit)
        if estado == DORMENTE:
            continue
        por_local.setdefault((g.get("local") or "?").upper(), []).append((g, estado, motivo))
    for chave in sorted(por_local):
        obrig = [x for x in por_local[chave] if x[0].get("obrigatorio")]
        if not obrig:
            continue
        out.append(f"\n{_nome_local(dados, chave)}")
        for g, estado, motivo in obrig:
            out.append(_linha(g, estado, motivo, None))
    if len(out) == 1:
        out.append("(nada obrigatório em aberto)")
    out.append("\nResolver: python3 ferramentas/radar.py resolver <id> "
               "disparado|pulado|adiado \"nota\"")
    return out


# --------------------------------------------------------------------------
# escrita no ledger (append-only)
# --------------------------------------------------------------------------
def resolver(gid: str, estado: str, nota: str = "") -> None:
    if estado not in ("disparado", "pulado", "adiado"):
        sys.exit("Estado deve ser: disparado | pulado | adiado")
    sit = situacao()
    dados = agenda(sit.get("aventura", ""))
    if gid not in {g["id"] for g in dados.get("gatilhos", [])}:
        sys.exit(f"Gatilho '{gid}' não existe na agenda. "
                 f"Veja: python3 ferramentas/radar.py pendentes")
    reg = ledger()
    reg.setdefault("resolucoes", []).append({
        "id": gid, "estado": estado, "nota": nota,
        "sessao": sit.get("sessao"), "dia_no_mundo": sit.get("dia_no_mundo"),
        "registrado_em": date.today().isoformat(),
    })
    LEDGER.write_text(json.dumps(reg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Ledger: {gid} → {estado}. ({len(reg['resolucoes'])} resoluções registradas)")


def anotar(gid: str, local: str, quando: str, resumo: str) -> None:
    """Gatilho que o LIVRO não marca explicitamente, mas o mestre quer rastrear."""
    reg = ledger()
    if any(g["id"] == gid for g in reg.get("manuais", [])):
        sys.exit(f"Já existe gatilho manual '{gid}'.")
    reg.setdefault("manuais", []).append({
        "id": gid, "ref": "—", "local": local.upper(), "tipo": "cena",
        "disparo": {"quando": quando, "alvo": local.upper()},
        "guarda": None, "obrigatorio": True, "origem": "mestre",
        "resumo": resumo, "verbatim": "",
    })
    LEDGER.write_text(json.dumps(reg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Gatilho manual '{gid}' anotado em {local.upper()} ({quando}).")


def main() -> None:
    args = sys.argv[1:]
    cmd = args[0].lower() if args else ""

    if cmd == "--hook":
        try:
            linhas = painel(compacto=True)
            if len(linhas) > 1:
                print("\n".join(linhas))
        except Exception as e:  # hook NUNCA pode derrubar o turno
            print(f"(radar indisponível: {e})")
        return
    if not args:
        print("\n".join(painel()))
    elif cmd == "local" and len(args) > 1:
        print("\n".join(painel_local(args[1])))
    elif cmd == "rota" and len(args) > 2:
        print("\n".join(painel_rota(args[1], args[2])))
    elif cmd == "pendentes":
        print("\n".join(painel_pendentes()))
    elif cmd == "resolver" and len(args) > 2:
        resolver(args[1], args[2], " ".join(args[3:]))
    elif cmd == "anotar" and len(args) > 4:
        anotar(args[1], args[2], args[3], " ".join(args[4:]))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
