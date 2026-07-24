/* Mesa RPG — lógica da interface (sem dependências). */
"use strict";
const $ = (s) => document.querySelector(s);
let ESTADO = null;
let modoOff = false;
let enviando = false;

/* =============== util =============== */
function el(tag, cls, texto) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (texto != null) e.textContent = texto;
  return e;
}
function sinal(n) { return (n >= 0 ? "+" : "") + n; }

/* =============== chat =============== */
const mensagens = $("#mensagens");

function addMsg(classe, autor, texto) {
  const t = document.getElementById("tpl-msg").content.cloneNode(true);
  const m = t.querySelector(".msg");
  m.classList.add(classe);
  m.querySelector(".autor").textContent = autor;
  m.querySelector(".conteudo").textContent = texto || "";
  mensagens.appendChild(m);
  mensagens.scrollTop = mensagens.scrollHeight;
  return m;
}

async function enviar(texto, classeLocal = "jogador") {
  if (!texto.trim() || enviando) return;
  enviando = true;
  addMsg(classeLocal, "você", texto);
  const msgMestre = addMsg("mestre", "mestre", "");
  const cont = msgMestre.querySelector(".conteudo");
  $("#status-mestre").classList.remove("oculto");
  try {
    const resp = await fetch("/api/chat", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mensagem: texto }),
    });
    const leitor = resp.body.getReader();
    const dec = new TextDecoder();
    let resto = "";
    for (;;) {
      const { done, value } = await leitor.read();
      if (done) break;
      resto += dec.decode(value, { stream: true });
      const blocos = resto.split("\n\n");
      resto = blocos.pop();
      for (const b of blocos) {
        if (!b.startsWith("data: ")) continue;
        let ev; try { ev = JSON.parse(b.slice(6)); } catch { continue; }
        if (ev.tipo === "texto") {
          cont.textContent += ev.t;
        } else if (ev.tipo === "ferramenta") {
          const f = el("div", "ferramenta",
            `⚙ ${ev.nome}${ev.detalhe ? " · " + ev.detalhe : ""}`);
          msgMestre.appendChild(f);
          $("#status-texto").textContent = rotuloFerramenta(ev);
        } else if (ev.tipo === "erro") {
          cont.textContent += `\n⚠ ${ev.msg}`;
        }
        mensagens.scrollTop = mensagens.scrollHeight;
      }
    }
  } catch (e) {
    cont.textContent += `\n⚠ Falha de conexão com o servidor (${e.message}).`;
  }
  $("#status-mestre").classList.add("oculto");
  $("#status-texto").textContent = "o mestre escreve…";
  enviando = false;
  carregarEstado();
}
function rotuloFerramenta(ev) {
  if (ev.nome === "Bash" && /roll\.py/.test(ev.detalhe)) return "o mestre rola os dados…";
  if (ev.nome === "Bash" && /5et\.py/.test(ev.detalhe)) return "o mestre consulta os tomos…";
  if (/Edit|Write/.test(ev.nome)) return "o mestre anota no caderno…";
  if (/Read|Glob|Grep/.test(ev.nome)) return "o mestre relê as notas…";
  return "o mestre pondera…";
}

const entrada = $("#entrada");
function enviarDaCaixa() {
  const t = entrada.value.trim();
  if (!t) return;
  entrada.value = ""; entrada.style.height = "auto";
  enviar(modoOff ? `(off) ${t}` : t);
}
$("#btn-enviar").addEventListener("click", enviarDaCaixa);
entrada.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); enviarDaCaixa(); }
});
entrada.addEventListener("input", () => {
  entrada.style.height = "auto";
  entrada.style.height = Math.min(entrada.scrollHeight, 140) + "px";
});
$("#btn-off").addEventListener("click", () => {
  modoOff = !modoOff;
  $("#btn-off").classList.toggle("ligado", modoOff);
  entrada.placeholder = modoOff ? "Fora do personagem…" : "O que você faz?";
});
$("#btn-salvar").addEventListener("click", () => enviar("salvar"));
$("#btn-recap").addEventListener("click", () => enviar("recap"));
$("#btn-nova-sessao").addEventListener("click", async () => {
  if (!confirm("Começar uma conversa nova? O estado da campanha fica salvo nos arquivos.")) return;
  await fetch("/api/nova-sessao", { method: "POST" });
  addMsg("dado", "", "— nova sessão iniciada —");
});

/* =============== rolagens =============== */
/* modo rascunho: acumula rolagens (ex.: multiataque + dano de cada acerto)
   e o jogador envia tudo numa mensagem só. */
let modoRascunho = false;
const rascunho = [];

async function rolar(rotulo, expr, modo) {
  if (enviando && !modoRascunho) return;
  const r = await fetch("/api/rolar", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ expr: modo ? `${expr} ${modo}` : expr }),
  }).then((x) => x.json());
  if (r.erro) return addMsg("dado", "", `⚠ ${r.erro}`);
  if (modoRascunho) {
    rascunho.push({ rotulo, resultado: r.resultado });
    return renderRascunho();
  }
  addMsg("dado", "", `🎲 ${rotulo} — ${r.resultado}`);
  enviar(`🎲 [rolagem pelo app] ${rotulo}: ${r.resultado}`, "dado-eco");
}

function renderRascunho() {
  const caixa = $("#rascunho");
  caixa.classList.toggle("oculto", !modoRascunho && !rascunho.length);
  $("#rascunho-conta").textContent = String(rascunho.length);
  const ol = $("#rascunho-lista");
  ol.innerHTML = "";
  rascunho.forEach((item, i) => {
    const li = el("li");
    li.appendChild(el("span", "r-texto", `${item.rotulo} — ${item.resultado}`));
    const x = el("button", "r-tirar", "✕");
    x.title = "Descartar esta rolagem";
    x.addEventListener("click", () => { rascunho.splice(i, 1); renderRascunho(); });
    li.appendChild(x);
    ol.appendChild(li);
  });
}

function enviarRascunho() {
  if (!rascunho.length) return;
  if (enviando)
    return addMsg("dado", "", "⚠ o mestre ainda responde — envie a sequência em seguida.");
  const linhas = rascunho.map((r) => `• ${r.rotulo}: ${r.resultado}`).join("\n");
  rascunho.length = 0;
  renderRascunho();
  addMsg("dado", "", `🎲 sequência enviada:\n${linhas}`);
  enviar(`🎲 [rolagem pelo app] Sequência de rolagens:\n${linhas}`, "dado-eco");
}

$("#btn-rascunho-modo").addEventListener("click", () => {
  modoRascunho = !modoRascunho;
  $("#btn-rascunho-modo").classList.toggle("ligado", modoRascunho);
  renderRascunho();
});
$("#btn-rascunho-enviar").addEventListener("click", enviarRascunho);
$("#btn-rascunho-limpar").addEventListener("click", () => {
  rascunho.length = 0; renderRascunho();
});
// eco silencioso: não repete a bolha do jogador para rolagens
const _addMsg = addMsg;
addMsg = function (classe, autor, texto) {
  if (classe === "dado-eco") return { querySelector: () => ({ textContent: "" }) };
  return _addMsg(classe, autor, texto);
};

/* =============== ficha =============== */
const NOMES_ATR = { for: "FOR", des: "DES", con: "CON", int: "INT", sab: "SAB", car: "CAR" };

function renderFicha(dados) {
  const caixa = $("#ficha");
  caixa.innerHTML = "";
  const p = dados && dados.personagens && dados.personagens[0];
  $("#ficha-vazia").classList.toggle("oculto", !!p);
  if (!p) return;

  caixa.appendChild(el("div", "f-nome", p.nome || "Sem nome"));
  caixa.appendChild(el("div", "f-sub",
    [p.raca, p.classe && `${p.classe} nível ${p.nivel}`, p.antecedente]
      .filter(Boolean).join(" · ")));

  // HP + XP
  const vit = el("div", "f-secao");
  vit.appendChild(el("div", "f-titulo", "Vitalidade"));
  const hp = p.hp || { atual: 0, max: 1 };
  const bhp = el("div", "barra");
  const ihp = el("i"); ihp.style.width = Math.max(0, 100 * hp.atual / hp.max) + "%";
  bhp.appendChild(ihp);
  bhp.appendChild(el("span", null, `HP ${hp.atual}/${hp.max}${hp.temp ? ` (+${hp.temp})` : ""}`));
  vit.appendChild(bhp);
  if (p.xp) {
    const bxp = el("div", "barra xp"); bxp.style.marginTop = "6px";
    const ixp = el("i");
    ixp.style.width = Math.min(100, 100 * p.xp.atual / (p.xp.proximo || 1)) + "%";
    bxp.appendChild(ixp);
    bxp.appendChild(el("span", null, `XP ${p.xp.atual}/${p.xp.proximo}`));
    vit.appendChild(bxp);
  }
  const linhas = [["CA", p.ca], ["Iniciativa", sinal(p.iniciativa ?? 0)],
    ["Deslocamento", p.deslocamento], ["Proficiência", sinal(p.prof ?? 2)]];
  for (const [r, v] of linhas) {
    if (v == null) continue;
    const l = el("div", "f-linha");
    l.appendChild(el("span", "rotulo", r)); l.appendChild(el("span", null, String(v)));
    vit.appendChild(l);
  }
  if ((p.condicoes || []).length) {
    const c = el("div"); c.style.marginTop = "6px";
    for (const cond of p.condicoes) c.appendChild(el("span", "condicao", cond));
    vit.appendChild(c);
  }
  caixa.appendChild(vit);

  // atributos
  const sa = el("div", "f-secao");
  sa.appendChild(el("div", "f-titulo", "Atributos · clique para rolar"));
  const grid = el("div", "atributos");
  for (const [k, nome] of Object.entries(NOMES_ATR)) {
    const a = (p.atributos || {})[k]; if (!a) continue;
    const c = el("div", "atributo");
    c.appendChild(el("div", "sigla", nome));
    c.appendChild(el("div", "mod", sinal(a.mod)));
    c.appendChild(el("div", "valor", String(a.valor)));
    c.addEventListener("click", () => rolar(`Teste de ${nome}`, `1d20${sinal(a.mod)}`));
    grid.appendChild(c);
  }
  sa.appendChild(grid);
  caixa.appendChild(sa);

  // salvaguardas
  if (p.salvaguardas) {
    const s = el("div", "f-secao");
    s.appendChild(el("div", "f-titulo", "Salvaguardas"));
    for (const [k, sv] of Object.entries(p.salvaguardas)) {
      const linha = el("div", "rolavel");
      const nome = el("span");
      if (sv.prof) nome.appendChild(el("span", "prof", "◆"));
      nome.appendChild(document.createTextNode(NOMES_ATR[k] || k));
      linha.appendChild(nome);
      linha.appendChild(el("span", "mod", sinal(sv.mod)));
      linha.addEventListener("click", () =>
        rolar(`Salvaguarda de ${NOMES_ATR[k] || k}`, `1d20${sinal(sv.mod)}`));
      s.appendChild(linha);
    }
    caixa.appendChild(s);
  }

  // perícias
  if ((p.pericias || []).length) {
    const s = el("div", "f-secao");
    s.appendChild(el("div", "f-titulo", "Perícias"));
    for (const pe of p.pericias) {
      const linha = el("div", "rolavel");
      const nome = el("span");
      if (pe.prof) nome.appendChild(el("span", "prof", "◆"));
      nome.appendChild(document.createTextNode(pe.nome));
      linha.appendChild(nome);
      linha.appendChild(el("span", "mod", sinal(pe.mod)));
      linha.addEventListener("click", () => rolar(pe.nome, `1d20${sinal(pe.mod)}`));
      s.appendChild(linha);
    }
    caixa.appendChild(s);
  }

  // ataques
  if ((p.ataques || []).length) {
    const s = el("div", "f-secao");
    s.appendChild(el("div", "f-titulo", "Ataques · ▲ vantagem · ▼ desvantagem"));
    for (const at of p.ataques) {
      const c = el("div", "ataque");
      c.appendChild(el("div", "nome",
        `${at.nome}${at.tipo ? ` · ${at.tipo}` : ""}`));
      const b = el("div", "botoes");
      const dado = `1d20${sinal(at.bonus)}`;
      const b1 = el("button", null, `ataque ${sinal(at.bonus)}`);
      b1.addEventListener("click", () => rolar(`Ataque — ${at.nome}`, dado));
      const bv = el("button", "mini", "▲");
      bv.title = "Ataque com vantagem";
      bv.addEventListener("click", () =>
        rolar(`Ataque com vantagem — ${at.nome}`, dado, "adv"));
      const bd = el("button", "mini", "▼");
      bd.title = "Ataque com desvantagem";
      bd.addEventListener("click", () =>
        rolar(`Ataque com desvantagem — ${at.nome}`, dado, "dis"));
      const b2 = el("button", null, `dano ${at.dano}`);
      b2.addEventListener("click", () => rolar(`Dano — ${at.nome}`, at.dano));
      b.appendChild(b1); b.appendChild(bv); b.appendChild(bd); b.appendChild(b2);
      c.appendChild(b);
      s.appendChild(c);
    }
    caixa.appendChild(s);
  }

  // magias
  if (p.magias && (p.magias.slots || p.magias.conhecidas)) {
    const s = el("div", "f-secao");
    s.appendChild(el("div", "f-titulo", "Magias"));
    if (p.magias.cd != null) {
      const l = el("div", "f-linha");
      l.appendChild(el("span", "rotulo", "CD / ataque mágico"));
      l.appendChild(el("span", null, `${p.magias.cd} / ${sinal(p.magias.ataque ?? 0)}`));
      s.appendChild(l);
    }
    for (const [nivel, sl] of Object.entries(p.magias.slots || {})) {
      const linha = el("div", "slots");
      linha.appendChild(el("span", "rotulo", `nível ${nivel}: `));
      for (let i = 0; i < sl.total; i++) {
        linha.appendChild(el("span", "slot" + (i < sl.total - sl.usados ? " cheio" : "")));
      }
      s.appendChild(linha);
    }
    for (const m of p.magias.conhecidas || []) {
      const linha = el("div", "rolavel");
      linha.appendChild(el("span", null, `${m.nome} (${m.nivel === 0 ? "truque" : "nv " + m.nivel})`));
      if (m.rolagem) {
        linha.appendChild(el("span", "mod", m.rolagem));
        linha.addEventListener("click", () => rolar(m.nome, m.rolagem));
      } else {
        linha.style.cursor = "default";
      }
      s.appendChild(linha);
    }
    caixa.appendChild(s);
  }

  // recursos, moedas, inventário
  if ((p.recursos || []).length) {
    const s = el("div", "f-secao");
    s.appendChild(el("div", "f-titulo", "Recursos"));
    for (const r of p.recursos) {
      const linha = el("div", "slots");
      linha.appendChild(el("span", "rotulo", `${r.nome}: `));
      for (let i = 0; i < r.total; i++)
        linha.appendChild(el("span", "slot" + (i < r.total - r.usados ? " cheio" : "")));
      s.appendChild(linha);
    }
    caixa.appendChild(s);
  }
  const inv = el("div", "f-secao");
  inv.appendChild(el("div", "f-titulo", "Inventário"));
  if (p.moedas) {
    const l = el("div", "f-linha");
    l.appendChild(el("span", "rotulo", "Moedas"));
    l.appendChild(el("span", null,
      `${p.moedas.po ?? 0} PO · ${p.moedas.pp ?? 0} PP · ${p.moedas.pc ?? 0} PC`));
    inv.appendChild(l);
  }
  const ul = el("ul", "inventario");
  for (const item of p.inventario || []) ul.appendChild(el("li", null, item));
  inv.appendChild(ul);
  caixa.appendChild(inv);
}

/* =============== combate =============== */
function renderCombate(c) {
  const ativo = c && c.ativo;
  $("#sem-combate").classList.toggle("oculto", !!ativo);
  $("#combate").classList.toggle("oculto", !ativo);
  if (!ativo) return;

  const cab = $("#combate-cabecalho");
  cab.innerHTML = "";
  cab.appendChild(el("div", "rodada",
    `Rodada ${c.rodada || 1}${c.turno ? ` — turno de ${c.turno}` : ""}`));
  if (c.cenario) cab.appendChild(el("div", "cenario", c.cenario));

  // mapa
  const caixa = $("#mapa-caixa");
  caixa.innerHTML = "";
  const grid = (c.mapa && c.mapa.grid) || { cols: 12, rows: 9 };
  let largura = caixa.clientWidth || 348;
  let cel, alturaMapa;
  const monta = () => {
    cel = largura / grid.cols;
    alturaMapa = cel * grid.rows;
    const g = el("div"); g.id = "grade";
    g.style.height = alturaMapa + "px";
    g.style.backgroundImage =
      "linear-gradient(rgba(233,220,195,.12) 1px, transparent 1px)," +
      "linear-gradient(90deg, rgba(233,220,195,.12) 1px, transparent 1px)";
    g.style.backgroundSize = `${cel}px ${cel}px`;
    caixa.appendChild(g);
    if (!(c.mapa && c.mapa.imagem)) caixa.style.height = alturaMapa + "px";
    desenharTokens(c, caixa, cel);
  };
  if (c.mapa && c.mapa.imagem) {
    const img = new Image();
    img.className = "fundo";
    img.src = "/" + c.mapa.imagem.replace(/^\//, "");
    img.onload = monta;
    img.onerror = monta;
    caixa.appendChild(img);
  } else {
    caixa.style.position = "relative";
    monta();
  }

  // iniciativa
  const ol = $("#iniciativa");
  ol.innerHTML = "";
  const ordem = [...(c.combatentes || [])]
    .sort((a, b) => (b.iniciativa || 0) - (a.iniciativa || 0));
  for (const k of ordem) {
    const li = el("li");
    if (c.turno && k.nome === c.turno) li.classList.add("ativo-turno");
    if (k.hp && k.hp.atual <= 0) li.classList.add("caido");
    li.appendChild(el("div", "ini", String(k.iniciativa ?? "—")));
    const quem = el("div", "quem");
    quem.appendChild(el("span", "nome", k.nome));
    const extras = [k.ca != null ? `CA ${k.ca}` : null, k.zona,
      ...(k.condicoes || [])].filter(Boolean).join(" · ");
    if (extras) quem.appendChild(el("span", "extras", extras));
    li.appendChild(quem);
    const hp = el("div", "hp");
    if (k.hp) {
      hp.appendChild(document.createTextNode(
        k.tipo === "jogador" ? `${k.hp.atual}/${k.hp.max}` : vidaAproximada(k.hp)));
      const b = el("div", "barra"); const i = el("i");
      i.style.width = Math.max(0, 100 * k.hp.atual / k.hp.max) + "%";
      b.appendChild(i); hp.appendChild(b);
    }
    li.appendChild(hp);
    ol.appendChild(li);
  }
}
function vidaAproximada(hp) {
  const r = hp.atual / hp.max;
  if (hp.atual <= 0) return "caído";
  if (r > 0.75) return "ileso";
  if (r > 0.4) return "ferido";
  return "grave";
}

function desenharTokens(c, caixa, cel) {
  for (const k of c.combatentes || []) {
    if (!k.pos || (k.hp && k.hp.atual <= 0 && k.tipo !== "jogador")) continue;
    const t = el("div", "token " + (k.tipo === "jogador" ? "jogador" : "inimigo"));
    if (k.hp && k.hp.atual <= 0) t.classList.add("caido");
    if (c.turno && k.nome === c.turno) t.classList.add("ativo-turno");
    const tam = Math.max(18, cel * (k.tamanho || 1) - 6);
    t.style.width = t.style.height = tam + "px";
    t.style.left = k.pos.x * cel + (cel - tam) / 2 + "px";
    t.style.top = k.pos.y * cel + (cel - tam) / 2 + "px";
    if (k.token) t.style.backgroundImage = `url(/${k.token.replace(/^\//, "")})`;
    else t.textContent = (k.nome || "?").slice(0, 2).toUpperCase();
    t.title = `${k.nome} (${String.fromCharCode(65 + k.pos.x)}${k.pos.y + 1})`;
    if (k.tipo === "jogador") arrastavel(t, k, caixa, cel, c);
    caixa.appendChild(t);
  }
}
function arrastavel(t, k, caixa, cel, c) {
  t.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    t.setPointerCapture(e.pointerId);
    t.classList.add("arrastando");
    const caixaRect = caixa.getBoundingClientRect();
    const mover = (ev) => {
      t.style.left = ev.clientX - caixaRect.left - t.offsetWidth / 2 + "px";
      t.style.top = ev.clientY - caixaRect.top - t.offsetHeight / 2 + "px";
    };
    const soltar = async (ev) => {
      t.removeEventListener("pointermove", mover);
      t.removeEventListener("pointerup", soltar);
      t.classList.remove("arrastando");
      const grid = (c.mapa && c.mapa.grid) || { cols: 12, rows: 9 };
      const x = Math.min(grid.cols - 1, Math.max(0,
        Math.floor((ev.clientX - caixaRect.left) / cel)));
      const y = Math.min(grid.rows - 1, Math.max(0,
        Math.floor((ev.clientY - caixaRect.top) / cel)));
      const tam = t.offsetWidth;
      t.style.left = x * cel + (cel - tam) / 2 + "px";
      t.style.top = y * cel + (cel - tam) / 2 + "px";
      const r = await fetch("/api/mover", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: k.id, x, y }),
      }).then((z) => z.json());
      if (r.ok) addMsg("dado", "",
        `🥾 ${k.nome} → ${String.fromCharCode(65 + x)}${y + 1} (o mestre verá no próximo turno)`);
    };
    t.addEventListener("pointermove", mover);
    t.addEventListener("pointerup", soltar);
  });
}

/* =============== upload =============== */
async function subir(input) {
  const arq = input.files[0];
  if (!arq) return;
  const r = await fetch(`/api/upload?nome=${encodeURIComponent(arq.name)}`, {
    method: "POST", body: arq,
  }).then((x) => x.json());
  input.value = "";
  if (r.ok) {
    const ok = $("#upload-ok"); if (ok) ok.textContent = `enviado: ${r.caminho}`;
    enviar(`(off) Enviei um arquivo de imagem para você usar como mapa ou token: ${r.caminho}`);
  }
}
$("#upload").addEventListener("change", (e) => subir(e.target));
$("#upload2").addEventListener("change", (e) => subir(e.target));

/* abrir mapa grande em nova aba (mesma janela reutilizada) */
$("#btn-mapa-tab").addEventListener("click", () =>
  window.open("/mapa.html", "mapa-mesa"));

/* =============== estado + abas =============== */
async function carregarEstado() {
  try {
    ESTADO = await fetch("/api/estado").then((r) => r.json());
    document.title = `Mesa — ${ESTADO.campanha}`;
    $("#nome-campanha").textContent = ESTADO.campanha;
    renderFicha(ESTADO.personagem);
    renderCombate(ESTADO.combate);
  } catch { /* servidor caiu */ }
}
new EventSource("/api/eventos").addEventListener("message", (e) => {
  try { if (JSON.parse(e.data).tipo === "estado") carregarEstado(); } catch {}
});
document.querySelectorAll(".aba").forEach((b) =>
  b.addEventListener("click", () => {
    document.querySelectorAll(".aba").forEach((x) => x.classList.remove("ativa"));
    document.querySelectorAll(".painel").forEach((x) => x.classList.remove("ativo"));
    b.classList.add("ativa");
    $("#painel-" + b.dataset.aba).classList.add("ativo");
    carregarEstado();
  }));

carregarEstado();
addMsg("dado", "", "— mesa aberta · diga algo ao mestre para começar —");
