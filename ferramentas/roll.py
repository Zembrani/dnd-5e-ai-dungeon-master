#!/usr/bin/env python3
"""Rolagem de dados honesta para a mesa.

Uso:
    python roll.py 1d20+5
    python roll.py 2d6+3
    python roll.py 4d6k3        # rola 4d6, mantém os 3 maiores (atributos)
    python roll.py 2d20kl1      # mantém o menor (desvantagem manual)
    python roll.py 2d8+1d8+6    # vários grupos de dado na mesma expressão
    python roll.py 4d6+2d8-1d4  # somas e subtrações de grupos
    python roll.py 1d20 adv     # vantagem (rola 2d20, pega o maior)
    python roll.py 1d20+7 dis   # desvantagem (rola 2d20, pega o menor)
    python roll.py 8d6 1d4+2    # várias expressões de uma vez
"""
import random
import re
import sys

DADO_RE = re.compile(r"^(\d*)d(\d+)(?:k(l?)(\d+))?$", re.IGNORECASE)
AJUDA = ("use NdX, NdX+M, NdXkY, NdXklY "
         "ou somas de grupos como 2d8+1d8+6")


class ExprInvalida(Exception):
    pass


def analisar(expr: str) -> list[dict]:
    """Quebra uma expressão em termos (grupos de dado e constantes)."""
    s = expr.replace(" ", "")
    if not s:
        raise ExprInvalida("expressão vazia")
    if s[0] not in "+-":
        s = "+" + s
    partes = re.findall(r"[+-][^+-]*", s)
    if "".join(partes) != s:
        raise ExprInvalida("expressão inválida")

    termos: list[dict] = []
    for parte in partes:
        sinal = -1 if parte[0] == "-" else 1
        corpo = parte[1:]
        if not corpo:
            raise ExprInvalida("expressão inválida")
        if corpo.isdigit():
            termos.append({"tipo": "const", "sinal": sinal, "valor": int(corpo)})
            continue
        m = DADO_RE.match(corpo)
        if not m:
            raise ExprInvalida(f"termo inválido '{corpo}'")
        n = int(m.group(1) or 1)
        faces = int(m.group(2))
        menor = (m.group(3) or "").lower() == "l"
        manter = int(m.group(4)) if m.group(4) else None
        if n < 1 or n > 100 or faces < 2 or faces > 1000:
            raise ExprInvalida("fora dos limites (1-100 dados, d2-d1000)")
        if manter is not None and not 1 <= manter <= n:
            raise ExprInvalida(f"k{manter} inválido para {n} dado(s)")
        termos.append({"tipo": "dado", "sinal": sinal, "n": n, "faces": faces,
                       "manter": manter, "menor": menor})

    if not any(t["tipo"] == "dado" for t in termos):
        raise ExprInvalida("nenhum dado na expressão")
    if sum(t["n"] for t in termos if t["tipo"] == "dado") > 100:
        raise ExprInvalida("mais de 100 dados na expressão")
    return termos


def rolar_grupo(t: dict, modo: str | None = None) -> tuple[int, dict]:
    """Rola um grupo de dados. Devolve (soma dos usados, detalhe)."""
    if modo in ("adv", "dis") and t["n"] == 1:
        rolls = [random.randint(1, t["faces"]) for _ in range(2)]
        escolhido = max(rolls) if modo == "adv" else min(rolls)
        rotulo = "vantagem" if modo == "adv" else "desvantagem"
        return escolhido, {"rolls": rolls, "usados": [escolhido], "modo": rotulo}

    rolls = [random.randint(1, t["faces"]) for _ in range(t["n"])]
    if t["manter"]:
        ordenados = sorted(rolls) if t["menor"] else sorted(rolls, reverse=True)
        usados = ordenados[:t["manter"]]
    else:
        usados = list(rolls)
    return sum(usados), {"rolls": rolls, "usados": usados, "modo": None}


def rotulo_grupo(t: dict) -> str:
    r = f"{t['n']}d{t['faces']}"
    if t["manter"]:
        r += f"k{'l' if t['menor'] else ''}{t['manter']}"
    return r


def roll_expr(expr: str, mode: str | None = None) -> str:
    expr = expr.strip()
    try:
        termos = analisar(expr)
    except ExprInvalida as e:
        return f"{expr}: {e} ({AJUDA})"

    mod = sum(t["sinal"] * t["valor"] for t in termos if t["tipo"] == "const")
    total = mod
    resultados = []
    for t in termos:
        if t["tipo"] != "dado":
            continue
        # vantagem/desvantagem só valem para o primeiro grupo, e só se for 1 dado
        modo = mode if (not resultados and t["n"] == 1) else None
        soma, det = rolar_grupo(t, modo)
        resultados.append((t, det))
        total += t["sinal"] * soma

    # crítico: apenas o primeiro grupo, quando é um único d20
    crit = ""
    t0, det0 = resultados[0]
    if t0["faces"] == 20 and len(det0["usados"]) == 1:
        v = det0["usados"][0]
        crit = (" ** CRÍTICO! **" if v == 20
                else " ** FALHA CRÍTICA! **" if v == 1 else "")

    mod_s = f"{mod:+d}" if mod else ""

    # um único grupo: formato clássico
    if len(resultados) == 1:
        t, det = resultados[0]
        if det["modo"]:
            return (f"{expr} ({det['modo']}): rolagens {det['rolls']} "
                    f"-> usa {det['usados'][0]}{mod_s} = {total}{crit}")
        mantidos = f" -> mantém {det['usados']}" if t["manter"] else ""
        return f"{expr}: {det['rolls']}{mantidos}{mod_s} = {total}{crit}"

    # vários grupos: mostra cada um separadamente
    pedacos = []
    for i, (t, det) in enumerate(resultados):
        if i == 0:
            sinal = "" if t["sinal"] > 0 else "-"
        else:
            sinal = " + " if t["sinal"] > 0 else " - "
        corpo = ", ".join(str(r) for r in det["rolls"])
        if det["modo"]:
            corpo += f" -> {det['modo']} {det['usados'][0]}"
        elif t["manter"]:
            corpo += " -> mantém " + ", ".join(str(r) for r in det["usados"])
        pedacos.append(f"{sinal}{rotulo_grupo(t)}[{corpo}]")
    texto = "".join(pedacos)
    if mod:
        texto += f" {'+' if mod > 0 else '-'} {abs(mod)}"
    return f"{expr}: {texto} = {total}{crit}"


def main() -> None:
    args = [a for a in sys.argv[1:]]
    if not args:
        print(__doc__)
        return
    mode = None
    if args and args[-1].lower() in ("adv", "dis"):
        mode = args.pop().lower()
    for expr in args:
        print(roll_expr(expr, mode))


if __name__ == "__main__":
    main()
