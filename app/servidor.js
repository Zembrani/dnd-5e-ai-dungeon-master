#!/usr/bin/env node
/* Mesa RPG — servidor local.
 * Roda o Claude Code em modo headless sobre o repositório da campanha.
 * Sem dependências: apenas Node.js >= 18.
 * Uso: node app/servidor.js   (a partir da raiz do repositório)
 */
const http = require("http");
const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");

const RAIZ = path.resolve(__dirname, "..");
const PUBLICO = path.join(__dirname, "publico");
const ESTADO = path.join(RAIZ, "estado");
const MIDIA = path.join(RAIZ, "midia");
const SESSAO_ARQ = path.join(RAIZ, ".sessao-app.json");
const PORTA = process.env.MESA_PORTA || 3333;

for (const d of ["mapas", "tokens", "uploads"])
  fs.mkdirSync(path.join(MIDIA, d), { recursive: true });

const MIME = {
  ".html": "text/html; charset=utf-8", ".js": "text/javascript",
  ".css": "text/css", ".json": "application/json",
  ".webp": "image/webp", ".png": "image/png", ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg", ".svg": "image/svg+xml", ".gif": "image/gif",
};

function lerJson(arq, padrao) {
  try { return JSON.parse(fs.readFileSync(arq, "utf8")); }
  catch { return padrao; }
}
function corpo(req) {
  return new Promise((res, rej) => {
    const partes = [];
    req.on("data", (c) => partes.push(c));
    req.on("end", () => res(Buffer.concat(partes)));
    req.on("error", rej);
  });
}
function json(res, obj, status = 200) {
  res.writeHead(status, { "Content-Type": "application/json" });
  res.end(JSON.stringify(obj));
}

/* ---------- Claude Code headless ---------- */
let processoAtivo = null;

function argsClaude(mensagem) {
  const args = ["-p", mensagem,
    "--model", "claude-sonnet-5",
    "--output-format", "stream-json", "--verbose",
    "--include-partial-messages"];
  const sessao = lerJson(SESSAO_ARQ, {}).sessao;
  if (sessao) args.push("--resume", sessao);
  if (process.env.MESA_SKIP_PERMISSIONS === "1") {
    args.push("--dangerously-skip-permissions");
  } else {
    args.push("--permission-mode", "acceptEdits",
      "--allowedTools",
      "Bash(python *),Bash(python3 *),Bash(ls *),Bash(mkdir *),Read,Write,Edit,Glob,Grep,Skill");
  }
  return args;
}

function conversar(mensagem, res) {
  res.writeHead(200, {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache", Connection: "keep-alive",
  });
  const manda = (obj) => {
    if (!res.writableEnded) res.write(`data: ${JSON.stringify(obj)}\n\n`);
  };
  const fecha = () => { if (!res.writableEnded) res.end(); };

  if (processoAtivo) {
    manda({ tipo: "erro", msg: "O mestre ainda está respondendo a mensagem anterior." });
    return res.end();
  }
  const proc = spawn("claude", argsClaude(mensagem), { cwd: RAIZ });
  processoAtivo = proc;
  let resto = "", viuDelta = false, sessao = null, viuTexto = false;

  proc.stdout.on("data", (dado) => {
    resto += dado.toString();
    const linhas = resto.split("\n");
    resto = linhas.pop();
    for (const linha of linhas) {
      if (!linha.trim()) continue;
      let ev; try { ev = JSON.parse(linha); } catch { continue; }
      if (ev.type === "system" && ev.subtype === "init") {
        sessao = ev.session_id;
      } else if (ev.type === "stream_event") {
        const d = ev.event && ev.event.delta;
        if (d && d.type === "text_delta" && d.text) {
          viuDelta = true; viuTexto = true;
          manda({ tipo: "texto", t: d.text });
        }
      } else if (ev.type === "assistant") {
        const blocos = (ev.message && ev.message.content) || [];
        for (const b of blocos) {
          if (b.type === "tool_use") {
            manda({ tipo: "ferramenta", nome: b.name, detalhe: resumoFerramenta(b) });
          } else if (b.type === "text" && b.text && !viuDelta) {
            viuTexto = true;
            manda({ tipo: "texto", t: b.text });
          }
        }
      } else if (ev.type === "result") {
        if (!viuTexto && ev.result) manda({ tipo: "texto", t: ev.result });
        if (ev.is_error) manda({ tipo: "erro", msg: String(ev.result || "erro") });
      }
    }
  });
  proc.stderr.on("data", (d) => process.stderr.write(d));
  proc.on("error", (e) => {
    manda({ tipo: "erro", msg: `Não consegui executar o comando 'claude' (${e.message}). O Claude Code está instalado e logado?` });
    processoAtivo = null; fecha();
  });
  proc.on("close", () => {
    if (sessao) fs.writeFileSync(SESSAO_ARQ, JSON.stringify({ sessao }));
    manda({ tipo: "fim" });
    processoAtivo = null; fecha();
  });
  req_abort(res, proc);
}
function req_abort(res, proc) {
  res.on("close", () => { /* cliente saiu: deixa o mestre terminar de salvar */ });
}
function resumoFerramenta(b) {
  const i = b.input || {};
  if (b.name === "Bash") return (i.command || "").slice(0, 90);
  if (i.file_path) return path.relative(RAIZ, i.file_path);
  if (i.pattern) return i.pattern;
  return "";
}

/* ---------- observar estado/ ---------- */
const ouvintes = new Set();
let temporizador = null;
try {
  fs.watch(ESTADO, () => {
    clearTimeout(temporizador);
    temporizador = setTimeout(() => {
      for (const r of ouvintes) r.write(`data: {"tipo":"estado"}\n\n`);
    }, 400);
  });
} catch { /* estado/ pode não existir ainda */ }

/* ---------- servidor ---------- */
const servidor = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://x`);
  const rota = url.pathname;

  if (rota === "/api/estado") {
    return json(res, {
      campanha: path.basename(RAIZ),
      personagem: lerJson(path.join(ESTADO, "personagem.json"), null),
      combate: lerJson(path.join(ESTADO, "combate.json"), { ativo: false }),
      mestreOcupado: !!processoAtivo,
    });
  }
  if (rota === "/api/eventos") {
    res.writeHead(200, { "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache", Connection: "keep-alive" });
    res.write(": olá\n\n");
    ouvintes.add(res);
    req.on("close", () => ouvintes.delete(res));
    return;
  }
  if (rota === "/api/chat" && req.method === "POST") {
    const { mensagem } = JSON.parse((await corpo(req)).toString() || "{}");
    if (!mensagem) return json(res, { erro: "mensagem vazia" }, 400);
    return conversar(mensagem, res);
  }
  if (rota === "/api/nova-sessao" && req.method === "POST") {
    try { fs.unlinkSync(SESSAO_ARQ); } catch {}
    return json(res, { ok: true });
  }
  if (rota === "/api/rolar" && req.method === "POST") {
    const { expr } = JSON.parse((await corpo(req)).toString() || "{}");
    // aceita grupos compostos (2d8+1d8+6), kY / klY, e o sufixo adv|dis
    if (!/^[0-9dkl+\- ]+(adv|dis)?$/i.test(expr || ""))
      return json(res, { erro: "expressão inválida" }, 400);
    const py = spawn("python3", [path.join(RAIZ, "ferramentas", "roll.py"),
      ...expr.split(" ")], { cwd: RAIZ });
    let saida = "";
    py.stdout.on("data", (d) => (saida += d));
    py.on("error", () => json(res, { erro: "python3 não encontrado" }, 500));
    py.on("close", () => json(res, { resultado: saida.trim() }));
    return;
  }
  if (rota === "/api/mover" && req.method === "POST") {
    const { id, x, y } = JSON.parse((await corpo(req)).toString() || "{}");
    const arq = path.join(ESTADO, "combate.json");
    const c = lerJson(arq, null);
    if (!c || !c.ativo) return json(res, { erro: "sem combate ativo" }, 400);
    const alvo = (c.combatentes || []).find((k) => k.id === id);
    if (!alvo || alvo.tipo !== "jogador")
      return json(res, { erro: "só é possível mover o próprio token" }, 403);
    const de = alvo.pos ? { ...alvo.pos } : null;
    alvo.pos = { x, y };
    c.movimentos_do_jogador = c.movimentos_do_jogador || [];
    c.movimentos_do_jogador.push({ id, de, para: { x, y }, quando: new Date().toISOString() });
    fs.writeFileSync(arq, JSON.stringify(c, null, 2));
    return json(res, { ok: true });
  }
  if (rota === "/api/upload" && req.method === "POST") {
    const nome = (url.searchParams.get("nome") || "arquivo")
      .replace(/[^\w.\- ()]/g, "_");
    const destino = path.join(MIDIA, "uploads", nome);
    fs.writeFileSync(destino, await corpo(req));
    return json(res, { ok: true, caminho: `midia/uploads/${nome}` });
  }
  if (rota.startsWith("/midia/")) {
    const arq = path.join(RAIZ, decodeURIComponent(rota));
    if (!path.resolve(arq).startsWith(MIDIA) || !fs.existsSync(arq))
      return json(res, { erro: "não encontrado" }, 404);
    res.writeHead(200, { "Content-Type": MIME[path.extname(arq).toLowerCase()] || "application/octet-stream" });
    return fs.createReadStream(arq).pipe(res);
  }
  // estáticos
  let arq = path.join(PUBLICO, rota === "/" ? "index.html" : rota);
  if (!path.resolve(arq).startsWith(PUBLICO) || !fs.existsSync(arq))
    return json(res, { erro: "não encontrado" }, 404);
  res.writeHead(200, { "Content-Type": MIME[path.extname(arq).toLowerCase()] || "text/plain" });
  fs.createReadStream(arq).pipe(res);
});

servidor.listen(PORTA, () => {
  console.log(`\n  🎲 Mesa aberta em  http://localhost:${PORTA}\n`);
  console.log(`  Campanha: ${path.basename(RAIZ)}`);
  console.log(`  Permissões do mestre: ${process.env.MESA_SKIP_PERMISSIONS === "1"
    ? "totais (MESA_SKIP_PERMISSIONS=1)" : "acceptEdits + python/ls"}\n`);
});
