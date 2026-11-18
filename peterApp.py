"""
PETER - interface visual (Flask + navegador + Ollama)

Instalação:
    pip install flask requests ddgs
    ollama pull qwen3.5:2b

Uso:
    python jarvis_app.py     # abre http://localhost:5055 no navegador (use Chrome ou Edge)
"""

import json
import threading
import webbrowser
from pathlib import Path

import requests
from flask import Flask, jsonify, request

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

OLLAMA = "http://localhost:11434"
MODELO = "qwen3.5:2b"   # para código, um modelo maior (ex.: qwen2.5-coder:7b) ajuda muito
PORTA = 5055
PASTA = Path.home() / ".jarvis"
ARQ = PASTA / "tarefas.json"
PASTA.mkdir(exist_ok=True)

BASE = ("Você é o PETER, assistente pessoal de uma desenvolvedora júnior full stack. "
        "Responda sempre em português do Brasil, de forma curta e direta, como numa conversa falada "
        "(no máximo 4 frases). Quando mostrar código, use blocos ``` e explique em 1 ou 2 frases. ")
MODOS = {
    "dev": BASE + "Foco: ajudar a programar, depurar e explicar conceitos (Angular, React, C#, Java, Node, SQL).",
    "pesquisa": BASE + "Foco: pesquisar e resumir informações com clareza, citando o essencial.",
    "org": BASE + "Foco: organização, planejamento de estudos, priorização de tarefas e rotina.",
}

app = Flask(__name__)


def ler():
    return json.loads(ARQ.read_text("utf-8")) if ARQ.exists() else []


def gravar(t):
    ARQ.write_text(json.dumps(t, ensure_ascii=False, indent=2), "utf-8")


@app.get("/")
def home():
    return HTML


@app.post("/api/chat")
def chat():
    d = request.get_json()
    msgs = d.get("mensagens", [])[-12:]
    fontes = []
    if d.get("pesquisar") and msgs:
        try:
            res = DDGS().text(msgs[-1]["content"], region="br-pt", max_results=5)
            fontes = [{"titulo": r["title"], "url": r["href"]} for r in res]
            ctx = "\n".join(f"- {r['title']}: {r['body']}" for r in res)
            msgs[-1] = {"role": "user", "content":
                        msgs[-1]["content"] + "\n\nResultados da web:\n" + ctx + "\n\nResuma de forma útil."}
        except Exception:
            fontes = []
    try:
        r = requests.post(f"{OLLAMA}/api/chat", timeout=180, json={
            "model": MODELO, "stream": False, "think": False,
            "messages": [{"role": "system", "content": MODOS.get(d.get("modo"), MODOS["dev"])}] + msgs})
        r.raise_for_status()
        return jsonify(resposta=r.json()["message"]["content"].strip(), fontes=fontes)
    except requests.exceptions.ConnectionError:
        return jsonify(resposta="Não consegui falar com o Ollama. Verifique se ele está aberto.", fontes=[])
    except Exception as e:
        return jsonify(resposta=f"Erro no modelo: {e}", fontes=[])


@app.get("/api/tarefas")
def tarefas():
    return jsonify(ler())


@app.post("/api/tarefas")
def nova_tarefa():
    t = ler()
    t.append({"texto": request.get_json()["texto"], "feita": False})
    gravar(t)
    return jsonify(t)


@app.post("/api/tarefas/<int:i>/alternar")
def alternar(i):
    t = ler()
    if 0 <= i < len(t):
        t[i]["feita"] = not t[i]["feita"]
        gravar(t)
    return jsonify(t)


@app.delete("/api/tarefas/<int:i>")
def apagar(i):
    t = ler()
    if 0 <= i < len(t):
        t.pop(i)
        gravar(t)
    return jsonify(t)


HTML = r"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PETER</title>
<style>
:root{--bg:#050b14;--card:#0b1626;--borda:#17334f;--azul:#38e1ff;--ouro:#ffb547;--ok:#4ade80;--txt:#d7e8f7;--mudo:#7f97ad}
*{box-sizing:border-box;margin:0}
body{font:15px/1.5 "Segoe UI",system-ui,sans-serif;color:var(--txt);height:100vh;display:flex;flex-direction:column;
background:radial-gradient(1200px 600px at 50% -10%,#0d2a47 0,var(--bg) 60%)}
header{display:flex;align-items:center;gap:16px;padding:14px 22px;border-bottom:1px solid var(--borda);flex-wrap:wrap}
h1{font-size:18px;letter-spacing:6px;color:var(--azul);text-shadow:0 0 14px #38e1ff88}
.modos{display:flex;gap:6px;margin-left:auto}
.chip{background:transparent;border:1px solid var(--borda);color:var(--mudo);padding:6px 14px;border-radius:99px;cursor:pointer;font:inherit;font-size:13px;transition:.2s}
.chip:hover{border-color:var(--azul);color:var(--txt)}
.chip.on{background:#38e1ff1a;border-color:var(--azul);color:var(--azul)}
main{flex:1;display:grid;grid-template-columns:1fr 310px;gap:18px;padding:18px 22px;min-height:0}
.col{display:flex;flex-direction:column;min-height:0;gap:14px}
.card{background:var(--card);border:1px solid var(--borda);border-radius:16px;padding:16px}
#msgs{flex:1;overflow-y:auto;display:flex;flex-direction:column;gap:12px;padding:4px 4px 4px 0}
.m{max-width:84%;padding:10px 14px;border-radius:14px;animation:subir .25s ease}
.m.u{align-self:flex-end;background:#12406a;border-bottom-right-radius:4px}
.m.j{align-self:flex-start;background:var(--card);border:1px solid var(--borda);border-bottom-left-radius:4px}
.m pre{background:#030811;border:1px solid var(--borda);border-radius:10px;padding:10px;margin:8px 0 2px;overflow-x:auto;position:relative;font:13px Consolas,monospace;color:#9be8ff}
.m pre button{position:absolute;top:6px;right:6px;background:var(--borda);color:var(--txt);border:0;border-radius:6px;padding:2px 8px;cursor:pointer;font-size:11px}
.m a{color:var(--azul);font-size:12px;display:block;margin-top:4px}
.dica{text-align:center;color:var(--mudo);margin:auto}
.dica .chip{margin:4px}
.controle{display:flex;align-items:center;gap:14px}
.orb{width:84px;height:84px;border-radius:50%;border:2px solid var(--azul);cursor:pointer;flex:none;position:relative;
background:radial-gradient(circle,#c8f6ff 0,var(--azul) 22%,#0a4a6e 60%,#06182a 100%);box-shadow:0 0 28px #38e1ff77,inset 0 0 18px #38e1ff55;transition:.3s}
.orb::after{content:"";position:absolute;inset:-9px;border-radius:50%;border:2px dashed #38e1ff55;animation:gira 14s linear infinite}
.orb:hover{transform:scale(1.05)}
.orb.ouvindo{border-color:var(--ok);box-shadow:0 0 40px #4ade80aa,inset 0 0 22px #4ade8077;animation:pulso 1s infinite}
.orb.pensando::after{border-color:var(--ouro);animation:gira 1.2s linear infinite}
.orb.falando{border-color:var(--ouro);box-shadow:0 0 40px #ffb547aa;animation:pulso 1.6s infinite}
#estado{font-size:12px;color:var(--mudo);margin-top:6px;text-align:center}
.entrada{flex:1;display:flex;gap:8px;align-items:center;background:var(--card);border:1px solid var(--borda);border-radius:99px;padding:6px 6px 6px 18px}
.entrada:focus-within{border-color:var(--azul)}
input{background:transparent;border:0;outline:0;color:var(--txt);font:inherit;flex:1;min-width:0}
.btn{background:var(--azul);color:#032;border:0;border-radius:99px;padding:8px 18px;font-weight:600;cursor:pointer}
.btn.web{background:transparent;color:var(--mudo);border:1px solid var(--borda);font-weight:400;padding:7px 12px}
.btn.web.on{color:var(--azul);border-color:var(--azul);background:#38e1ff1a}
h2{font-size:12px;letter-spacing:2px;text-transform:uppercase;color:var(--mudo);margin-bottom:10px}
.t{display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid #12263b}
.t input[type=checkbox]{accent-color:var(--azul)}
.t span{flex:1}.t.f span{text-decoration:line-through;color:var(--mudo)}
.t button{background:none;border:0;color:var(--mudo);cursor:pointer}
#lista{max-height:34vh;overflow-y:auto;margin-top:8px}
#tempo{font-size:34px;font-weight:300;letter-spacing:3px;color:var(--ouro);text-align:center;margin:4px 0 10px}
.row{display:flex;gap:6px;justify-content:center;flex-wrap:wrap}
@keyframes gira{to{transform:rotate(360deg)}}
@keyframes pulso{50%{transform:scale(1.08)}}
@keyframes subir{from{opacity:0;transform:translateY(8px)}}
@media(max-width:820px){main{grid-template-columns:1fr;overflow-y:auto}body{height:auto;min-height:100vh}#msgs{min-height:50vh}}
</style></head><body>
<header><h1>P.E.T.E.R.</h1>
<div class="modos">
<button class="chip on" data-m="dev">💻 Código</button>
<button class="chip" data-m="pesquisa">🔎 Pesquisa</button>
<button class="chip" data-m="org">📋 Organização</button></div></header>
<main>
<section class="col">
<div id="msgs"><div class="dica" id="dica">
<p style="font-size:20px;margin-bottom:6px">Olá! Como posso ajudar?</p>
<p>Clique na esfera (ou aperte <b>Espaço</b>) e fale. Ou experimente:</p>
<div style="margin-top:10px">
<button class="chip" data-s="Explique o que é injeção de dependência no Angular">Explique um conceito</button>
<button class="chip" data-s="Anote tarefa estudar C# hoje">Anotar tarefa</button>
<button class="chip" data-s="Foco de 25 minutos">Modo foco</button>
<button class="chip" data-s="Abrir GitHub">Abrir GitHub</button></div></div></div>
<div class="controle">
<div><div class="orb" id="orb" title="Falar (Espaço)"></div><div id="estado">Pronto</div></div>
<div class="entrada"><input id="txt" placeholder="Ou digite aqui e aperte Enter..." autocomplete="off">
<button class="btn web" id="web" title="Buscar na web antes de responder">🌐 Web</button>
<button class="btn" id="env">Enviar</button></div></div>
</section>
<aside class="col">
<div class="card"><h2>Tarefas</h2>
<input id="nt" placeholder="+ nova tarefa (Enter)" style="width:100%;border-bottom:1px solid var(--borda);padding:4px 0">
<div id="lista"></div></div>
<div class="card"><h2>Foco</h2><div id="tempo">00:00</div>
<div class="row"><button class="chip" data-f="15">15 min</button><button class="chip" data-f="25">25 min</button>
<button class="chip" data-f="50">50 min</button><button class="chip" data-f="0">Parar</button></div></div>
</aside></main>
<script>
const $=s=>document.querySelector(s);
let hist=[],modo="dev",pesq=false,estado="",rec=null,ouvindo=false,timer=null;
const SITES={github:"https://github.com",linkedin:"https://www.linkedin.com/jobs/",youtube:"https://www.youtube.com",gmail:"https://mail.google.com","stack overflow":"https://stackoverflow.com",claude:"https://claude.ai"};
const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
function set(e,t){["ouvindo","pensando","falando"].forEach(c=>$("#orb").classList.remove(c));
 if(e)$("#orb").classList.add(e);$("#estado").textContent=t||"Pronto";estado=e}
function esc(t){return t.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")}
function fmt(t){return t.split("```").map((p,i)=>i%2?
 '<pre><button onclick="navigator.clipboard.writeText(this.nextSibling.textContent)">Copiar</button><code>'+esc(p.replace(/^\w*\n/,""))+"</code></pre>":
 esc(p).replace(/\*\*(.+?)\*\*/g,"<b>$1</b>").replace(/\n/g,"<br>")).join("")}
function bolha(t,q,fontes){$("#dica")?.remove();const d=document.createElement("div");d.className="m "+q;
 d.innerHTML=fmt(t)+(fontes||[]).map(f=>'<a href="'+f.url+'" target="_blank">🔗 '+esc(f.titulo)+"</a>").join("");
 $("#msgs").append(d);$("#msgs").scrollTop=1e9;return d}
function falar(t){const s=t.replace(/```[\s\S]*?```/g," O código está na tela. ").replace(/[*#`_>]/g,"").trim();
 if(!s||!window.speechSynthesis){set();return}
 speechSynthesis.cancel();

const u = new SpeechSynthesisUtterance(s);
u.lang = "pt-BR";

const vs = speechSynthesis.getVoices();

const v = vs.find(v =>
    v.name.includes("Antônio") && v.lang === "pt-BR"
);

if (v) u.voice = v;

u.rate = 1.08;
u.pitch = 1.05;
 u.onstart=()=>set("falando","Falando...");u.onend=u.onerror=()=>set();speechSynthesis.speak(u)}
function resp(t,fontes){bolha(t,"j",fontes);falar(t)}
const norm=t=>t.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g,"");
async function enviar(texto){texto=texto.trim();if(!texto)return;$("#txt").value="";bolha(texto,"u");
 const n=norm(texto);let m;
 if(m=n.match(/(?:anote|anotar|adicione|criar|crie)(?: uma| a)? (?:tarefa|lembrete)(?: de| para)?:? (.+)/)){
  await fetch("/api/tarefas",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({texto:m[1]})});
  carregar();return resp("Tarefa anotada: "+m[1]+".")}
 if(m=n.match(/foco (?:de )?(\d+)/)){foco(+m[1]);return resp("Modo foco de "+m[1]+" minutos iniciado. Bom trabalho!")}
 if(m=n.match(/abr[ae]r? (?:o |a )?(.+)/)){const k=Object.keys(SITES).find(k=>m[1].includes(k));
  if(k){window.open(SITES[k],"_blank");return resp("Abrindo "+k+".")}}
 hist.push({role:"user",content:texto});set("pensando","Pensando...");
 const usaWeb=pesq||modo==="pesquisa"||/^(pesquise|pesquisar|busque|procure|vagas)/.test(n);
 try{const r=await(await fetch("/api/chat",{method:"POST",headers:{"Content-Type":"application/json"},
  body:JSON.stringify({mensagens:hist,modo,pesquisar:usaWeb})})).json();
  hist.push({role:"assistant",content:r.resposta});resp(r.resposta,r.fontes)}
 catch(e){set();bolha("Erro de conexão com o servidor.","j")}}
function ouvir(){if(!SR){bolha("Seu navegador não suporta voz. Use Chrome ou Edge.","j");return}
 if(ouvindo){rec.stop();return}speechSynthesis.cancel();
 rec=new SR();rec.lang="pt-BR";rec.interimResults=true;let final="";
 rec.onstart=()=>{ouvindo=true;set("ouvindo","Ouvindo...")};
 rec.onresult=e=>{final="";let tmp="";for(const r of e.results)(r.isFinal?final+=r[0].transcript:tmp+=r[0].transcript);
  $("#txt").value=final||tmp};
 rec.onend=()=>{ouvindo=false;if(estado==="ouvindo")set();if(final)enviar(final);else $("#txt").value=""};
 rec.onerror=()=>{ouvindo=false;set()};rec.start()}
async function carregar(){const t=await(await fetch("/api/tarefas")).json();
 $("#lista").innerHTML=t.length?t.map((x,i)=>'<div class="t'+(x.feita?" f":"")+'"><input type="checkbox" '+(x.feita?"checked":"")+
 ' onchange="alt('+i+')"><span>'+esc(x.texto)+'</span><button onclick="del('+i+')">✕</button></div>').join(""):
 '<p style="color:var(--mudo);padding:6px 0">Nenhuma tarefa ainda.</p>'}
window.alt=async i=>{await fetch("/api/tarefas/"+i+"/alternar",{method:"POST"});carregar()};
window.del=async i=>{await fetch("/api/tarefas/"+i,{method:"DELETE"});carregar()};
function foco(min){clearInterval(timer);if(!min){$("#tempo").textContent="00:00";return}
 let s=min*60;const mostra=()=>$("#tempo").textContent=String(Math.floor(s/60)).padStart(2,"0")+":"+String(s%60).padStart(2,"0");
 mostra();timer=setInterval(()=>{if(--s<=0){clearInterval(timer);$("#tempo").textContent="00:00";
  resp("Os "+min+" minutos de foco terminaram. Hora de uma pausa!")}else mostra()},1000)}
$("#orb").onclick=ouvir;$("#env").onclick=()=>enviar($("#txt").value);
$("#txt").onkeydown=e=>{if(e.key==="Enter")enviar($("#txt").value)};
$("#nt").onkeydown=async e=>{if(e.key==="Enter"&&e.target.value.trim()){
 await fetch("/api/tarefas",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({texto:e.target.value})});
 e.target.value="";carregar()}};
$("#web").onclick=e=>{pesq=!pesq;e.currentTarget.classList.toggle("on",pesq)};
document.querySelectorAll("[data-m]").forEach(b=>b.onclick=()=>{modo=b.dataset.m;
 document.querySelectorAll("[data-m]").forEach(x=>x.classList.toggle("on",x===b))});
document.querySelectorAll("[data-s]").forEach(b=>b.onclick=()=>enviar(b.dataset.s));
document.querySelectorAll("[data-f]").forEach(b=>b.onclick=()=>foco(+b.dataset.f));
document.addEventListener("keydown",e=>{if(e.code==="Space"&&document.activeElement.tagName!=="INPUT"){e.preventDefault();ouvir()}});
speechSynthesis.onvoiceschanged=()=>{};carregar();
</script></body></html>
"""

if __name__ == "__main__":
    threading.Timer(1.2, lambda: webbrowser.open(f"http://localhost:{PORTA}")).start()
    app.run(port=PORTA)