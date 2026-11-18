"""
JARVIS v2 - sem dependências (só biblioteca padrão do Python).
Reaproveita a interface do jarvisApp.py (deixe os dois na mesma pasta).

    python jarvis_v2.py                # usa jarvisApp.py
    python jarvis_v2.py outro.py       # ou informe o nome do arquivo

Digite "ajuda" no chat para ver todos os comandos.
A pesquisa na web só funciona com o pacote ddgs instalado (opcional).
"""

import base64
import difflib
import hashlib
import html
import json
import math
import os
import re
import secrets
import subprocess
import sys
import threading
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        DDGS = None

OLLAMA = "http://localhost:11434"
MODELO = "qwen3.5:2b"          # para código, um modelo maior (ex.: qwen2.5-coder:7b) erra bem menos
PORTA = 5055
NOME = "Peter"   # nome do assistente (aparece na tela e no prompt)
USUARIO = "Bia"   # como o assistente chama você nas saudações
CIDADE = {"nome": "Aracaju", "lat": -10.9091, "lon": -37.0677}   # para a previsão do tempo
TEMA = "tech"      # "tech" (painel futurista) ou "peter" (vermelho e azul, quadrinhos)
APELIDOS = ["peter",
    "péter",
    "pêter",
    "piter",
    "pitter",
    "piiter",
    "pieter",
    "pitera",
    "pitra",
    "pítera",
    "píter",
    "piterá",
    "píter ia",
    "peter ia",
    "piti",
    "pitero",
    "petero"]   # como o reconhecimento de voz costuma escrever o nome
PASTA = Path.home() / ".jarvis"
ARQ = PASTA / "tarefas.json"
CFG = PASTA / "config.json"
CURR = PASTA / "curriculo.txt"
CAND = PASTA / "candidaturas.json"
FILA = PASTA / "fila_vagas.json"
SPOTIFY_CFG = PASTA / "spotify.json"
SPOTIFY_TOKEN = PASTA / "spotify_token.json"
BRIEF_ARQ = PASTA / "briefing.json"
PASTA_CAND = PASTA / "candidaturas"
PASTA_CAND.mkdir(parents=True, exist_ok=True)

IGNORAR = {".git", "node_modules", "bin", "obj", "dist", "build", "__pycache__", ".venv", "venv", ".idea", ".vs", ".angular"}
EXT = {".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".scss", ".cs", ".java", ".json", ".md", ".sql", ".txt", ".xml", ".yml", ".yaml", ".csproj"}
PRIORIDADE = ("readme.md", "package.json", "pom.xml", "program.cs", "main.py", "app.py", "index.html", "main.java", "main.ts")
SITES = {"github": "https://github.com", "linkedin": "https://www.linkedin.com/jobs/",
         "youtube": "https://www.youtube.com", "gmail": "https://mail.google.com",
         "stack overflow": "https://stackoverflow.com", "claude": "https://claude.ai",
         "chatgpt": "https://chatgpt.com", "google": "https://www.google.com"}
PROGRAMAS = {"vs code": "code", "vscode": "code", "visual studio code": "code", "terminal": "start powershell",
             "bloco de notas": "notepad", "calculadora": "calc", "explorador": "explorer", "chrome": "start chrome","pomodoro": r'start "" "C:\Users\Usuario\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\apps do Chrome\Pomodoro timer.lnk"'}
PROTOCOLOS = {"spotify": ("spotify:", "https://open.spotify.com"), "whatsapp": ("whatsapp:", "https://web.whatsapp.com"),
              "discord": ("discord:", "https://discord.com/app")}

BASE = (f"Você é o {NOME}, assistente pessoal de uma desenvolvedora júnior full stack. "
        "Responda sempre em português do Brasil, de forma curta e direta, como numa conversa falada "
        "(no máximo 4 frases). Quando mostrar código, use blocos ``` e explique em 1 ou 2 frases. "  
        "Você roda dentro de um programa que executa comandos como: abrir github, abrir linkedin, abrir vs code, "
        "vagas de <área>, anote tarefa <texto>. Se o usuário pedir algo assim, diga o comando "
        "exato a usar; nunca diga que não consegue abrir sites ou programas. "
        "Você não acessa internet, arquivos nem PDFs por conta própria: nunca invente vagas, empresas, salários, "
        "links ou ações que diga ter feito; se não souber, diga que não sabe.")
MODOS = {
    "dev": BASE + "Foco: ajudar a programar, depurar e explicar conceitos (Angular, React, C#, Java, Node, SQL).",
    "pesquisa": BASE + "Foco: pesquisar e resumir informações com clareza, citando o essencial.",
    "org": BASE + "Foco: organização, planejamento de estudos, priorização de tarefas e rotina.",
}

MODELO_CURRICULO = """Nome: Anna Beatriz Bastos Oliveira
Cargo: Desenvolvedora Full Stack Júnior
Formação: Tecnólogo em Análise e Desenvolvimento de Sistemas, Estácio de Sá (2023-2026)
Experiência: Estágio em Engenharia de Software, Acessa Tecnologia LTDA (2024-2025) - sistemas de gestão acadêmica com Angular, C# e PostgreSQL
Tecnologias: Angular, React, JavaScript, C#, Node.js, Java, PostgreSQL/SQL, Git/GitHub
Idiomas: Inglês intermediário
Projetos: Estoque Fácil (Java, curso Jovem Tech) - complete aqui com seus outros projetos e resultados
Contato: (e-mail, LinkedIn, GitHub)

EDITE ESTE ARQUIVO com seus dados completos. O assistente usa só o que estiver aqui.
"""
if not CURR.exists():
    CURR.write_text(MODELO_CURRICULO, "utf-8")

origem = Path(sys.argv[1] if len(sys.argv) > 1 else "peterApp.py")
HTML = re.search(r'HTML = r"""(.*?)"""', origem.read_text("utf-8"), re.S).group(1)

# ------------------------------------------------------------------ ajustes da interface
# 1) voz mais natural (prefere vozes "Natural" do Edge, como Francisca e Antonio)
VOZ_ANTIGA = 'const v=speechSynthesis.getVoices().find(v=>v.lang.startsWith("pt-BR"));if(v)u.voice=v;'
VOZ_NOVA = ('const vs=speechSynthesis.getVoices().filter(v=>v.lang.startsWith("pt"));'
            'const v=vs.find(v=>/natural/i.test(v.name)&&v.lang==="pt-BR")'
            '||vs.find(v=>/online/i.test(v.name)&&v.lang==="pt-BR")'
            '||vs.find(v=>v.lang==="pt-BR")||vs[0];'
            'if(v)u.voice=v;u.rate=1.05;')
HTML = HTML.replace(VOZ_ANTIGA, VOZ_NOVA)
# corrige o comando "abrir ..." da interface (a versão antiga não reconhecia "abrir")
HTML = HTML.replace('abr[ae]r? (?:o |a )?(.+)', 'abr(?:ir|a|e) (?:o |a )?(.+)')
# o navegador bloqueia window.open quando o comando vem da voz; quem abre os sites é o servidor
HTML = HTML.replace('if(k){window.open(SITES[k],"_blank");return resp("Abrindo "+k+".")}', '')

# 2) ativação por voz: diga "Jarvis" (sem apertar o botão)
ESCUTA_JS = r"""
/* ===== ativação por voz: diga "Jarvis" ===== */
let escuta=false,aguardando=false,pausa=false,recW=null;
const ATIVA=/\b(__ATIVA__)\b/i;
function bip(){try{const c=new AudioContext(),o=c.createOscillator(),g=c.createGain();o.frequency.value=880;g.gain.value=.08;o.connect(g);g.connect(c.destination);o.start();o.stop(c.currentTime+.12)}catch(e){}}
function retomar(){if(escuta&&!pausa&&recW){try{recW.start()}catch(e){}}}
function pausar(){pausa=true;if(recW){try{recW.stop()}catch(e){}}}
function criarEscuta(){
 recW=new SR();recW.lang="pt-BR";recW.continuous=true;recW.interimResults=false;
 recW.onresult=e=>{for(let i=e.resultIndex;i<e.results.length;i++){
  if(!e.results[i].isFinal)continue;const t=e.results[i][0].transcript.trim();if(!t)continue;
  if(aguardando){aguardando=false;enviar(t);continue}
  const m=t.match(ATIVA);if(!m)continue;
  const resto=t.slice(m.index+m[0].length).replace(/^[\s,.:;!?-]+/,"");
  bip();
  if(resto.length>2){enviar(resto)}
  else{aguardando=true;set("ouvindo","Pois não? Pode falar...");
   setTimeout(()=>{if(aguardando){aguardando=false;set()}},8000)}}};
 recW.onend=()=>{if(escuta&&!pausa)setTimeout(retomar,300)};
 recW.onerror=e=>{if(e.error==="not-allowed"||e.error==="service-not-allowed"){escuta=false;atualizar();
  bolha("Preciso da permissão do microfone. Clique no cadeado ao lado do endereço e permita o microfone.","j")}};
}
function atualizar(){const b=$("#escuta");b.classList.toggle("on",escuta);
 b.textContent=escuta?"🎙️ Ouvindo “__NOME__”":"🎙️ Ativar “__NOME__”";if(!escuta)set()}
const _set=set,_falar=falar,_ouvir=ouvir;
set=function(e,t){_set(e,t);
 if(!e){if(pausa){pausa=false;setTimeout(retomar,400)}
  if(escuta&&!aguardando)$("#estado").textContent="Diga “__NOME__”..."}};
falar=function(t){if(escuta)pausar();_falar(t)};
ouvir=function(){if(escuta)pausar();_ouvir()};
(function(){
 const b=document.createElement("button");b.className="chip";b.id="escuta";
 document.querySelector(".modos").prepend(b);
 b.onclick=()=>{
  if(!SR){bolha("Seu navegador não suporta voz. Use Chrome ou Edge.","j");return}
  escuta=!escuta;
  if(escuta){pausa=false;criarEscuta();(window.__auto?retomar():falar("Estou ouvindo. É só dizer piter."))}
  else{aguardando=false;pausa=false;try{recW.stop()}catch(e){}}
  atualizar()};
 atualizar();$("#orb").onclick=ouvir;
 setTimeout(()=>{window.__auto=true;if(!escuta)b.click();window.__auto=false},1200);
})();
"""
EXTRA_JS = r"""
/* ===== relógio, tarefas de hoje e comando "repita" ===== */
(function(){
 const r=document.createElement("div");r.id="relogio";document.querySelector("header h1").after(r);
 let dia="";
 function tick(){const d=new Date(),hoje=d.toDateString();
  r.innerHTML="<b>"+d.toLocaleTimeString("pt-BR",{hour:"2-digit",minute:"2-digit"})+"</b><span>"+
   d.toLocaleDateString("pt-BR",{weekday:"long",day:"numeric",month:"long"})+"</span>";
  if(dia&&dia!==hoje)carregar();dia=hoje}
 tick();setInterval(tick,10000);
})();
carregar=async function(){
 try{const r=await(await fetch("/api/tarefas")).json(),t=r.hoje||[];
  $("#titulo-tarefas").textContent="Tarefas de hoje · "+new Date().toLocaleDateString("pt-BR",{day:"2-digit",month:"2-digit"});
  $("#lista").innerHTML=(t.length?t.map(x=>'<div class="t'+(x.feita?" f":"")+'"><input type="checkbox" '+(x.feita?"checked":"")+
   ' onchange="alt('+x.id+')"><span>'+(x.hora?'<b class="hr">'+x.hora+"</b> ":"")+esc(x.texto)+
   '</span><button onclick="del('+x.id+')">✕</button></div>').join(""):
   '<p style="color:var(--mudo);padding:6px 0">Nada para hoje. 🎉</p>')+
   (r.outras?'<p class="outras">+'+r.outras+" em outros dias</p>":"")}catch(e){}};
const _resp=resp;resp=function(t,f){_resp(t,f);carregar()};
setInterval(carregar,60000);
let ultimaFala="",repetindo=false;
const _falarU=falar;
falar=function(t){if(!repetindo&&t&&t.replace(/```[\s\S]*?```/g,"").trim())ultimaFala=t;_falarU(t)};
const REP=/^(?:(?:voce )?(?:pode|consegue) )?(?:repit\w+|repet\w+|(?:fal\w+|dig\w+|diz\w+) (?:isso )?de novo)(?: (?:isso|de novo|por favor|a ultima (?:mensagem|resposta|fala)|o que (?:voce )?(?:disse|falou)(?: agora)?))*$|^o que (?:voce )?(?:disse|falou)$/;
const _enviar=enviar;
enviar=async function(texto){
 const n=norm(texto).replace(ATIVA,"").replace(/[.,!?]/g," ").replace(/\s+/g," ").trim();
 if(/^(?:pare|para|chega|silencio|cala a boca|fica quieto)(?: de falar| por favor)?$/.test(n)){try{speechSynthesis.cancel()}catch(e){}set();$("#txt").value="";return}
 if(REP.test(n)){$("#txt").value="";bolha(texto,"u");repetindo=true;falar(ultimaFala||"Ainda não falei nada.");repetindo=false;return}
 return _enviar(texto)};
function mostrarBriefing(b){
 $("#dica")?.remove();const d=document.createElement("div");d.className="brief";
 d.innerHTML='<div class="brief-h"><span class="pulso"></span>'+esc(b.titulo)+'</div>'+b.itens.map(i=>
  '<div class="brief-i"><b>'+esc(i.titulo)+'</b>'+((i.lista&&i.lista.length)?'<ul>'+i.lista.map(x=>'<li>'+esc(x)+'</li>').join("")+'</ul>':
  (i.texto?'<p>'+esc(i.texto)+'</p>':""))+'</div>').join("");
 $("#msgs").append(d);$("#msgs").scrollTop=1e9}
async function briefing(){
 try{set("pensando","Preparando seu briefing...");
  const b=await(await fetch("/api/briefing")).json();set();
  mostrarBriefing(b);falar(b.fala)}catch(e){set()}}
setTimeout(briefing,2200);
carregar();
"""
ESCUTA_JS = ESCUTA_JS.replace("__ATIVA__", "|".join(APELIDOS)).replace("__NOME__", NOME)
HTML = HTML.replace("</script></body></html>", ESCUTA_JS + EXTRA_JS + "</script></body></html>")

# 3) visual: tema inspirado no Peter Parker (vermelho e azul, teia, quadrinhos) e sem o modo foco
def _hud():
    """SVG de anéis de painel futurista (HUD) como data URI."""
    ticks = "".join(
        f"<line x1='{200 + 172 * math.cos(a):.1f}' y1='{200 + 172 * math.sin(a):.1f}' "
        f"x2='{200 + (184 if i % 3 else 190) * math.cos(a):.1f}' y2='{200 + (184 if i % 3 else 190) * math.sin(a):.1f}' stroke-width='1.5'/>"
        for i, a in enumerate(k * math.pi / 36 for k in range(72)))
    svg = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 400 400' fill='none' stroke='#00e5ff'>"
           "<circle cx='200' cy='200' r='196' stroke-width='1' stroke-dasharray='2 7'/>" + ticks +
           "<circle cx='200' cy='200' r='160' stroke-width='3' stroke-dasharray='70 22 10 22'/>"
           "<circle cx='200' cy='200' r='128' stroke-width='1'/>"
           "<circle cx='200' cy='200' r='100' stroke-width='6' stroke-dasharray='34 16' opacity='.7'/>"
           "<circle cx='200' cy='200' r='60' stroke-width='1' stroke-dasharray='4 4'/></svg>")
    return "data:image/svg+xml," + urllib.parse.quote(svg)


TEMA_TECH_CSS = """
:root{--bg:#02060f;--card:#071426;--borda:#0f3b57;--azul:#00e5ff;--ok:#00ff9d;--ouro:#ffb300;--txt:#dff6ff;--mudo:#6f95ad;--rubro:#00e5ff;--azulesc:#0a4f7a}
body{background:linear-gradient(#00e5ff0b 1px,transparent 1px) 0 0/44px 44px,linear-gradient(90deg,#00e5ff0b 1px,transparent 1px) 0 0/44px 44px,
 radial-gradient(1000px 600px at 12% -10%,#0a3a5f77,transparent 60%),radial-gradient(900px 600px at 100% 110%,#5b2bff33,transparent 60%),var(--bg)}
body::before,body::after{content:"";position:fixed;width:600px;height:600px;pointer-events:none;z-index:0;opacity:.2;transform:none;
 background:url("__HUD__") center/contain no-repeat}
body::before{top:-250px;left:-250px;right:auto;bottom:auto;animation:gira 140s linear infinite reverse}
body::after{right:-230px;bottom:-230px;left:auto;top:auto;animation:gira 100s linear infinite}
header{border-bottom:1px solid #00e5ff55;box-shadow:0 2px 22px #00e5ff26;background:linear-gradient(90deg,#00e5ff16,transparent 55%)}
h1{font:600 20px "Cascadia Mono",Consolas,monospace;letter-spacing:.45em;color:var(--azul);text-shadow:0 0 14px #00e5ffcc;transform:none}
.chip{border:1px solid #00e5ff66;color:var(--azul);border-radius:0;background:#00e5ff0d;font:600 11px "Cascadia Mono",Consolas,monospace;letter-spacing:.14em;
 clip-path:polygon(8px 0,100% 0,100% calc(100% - 8px),calc(100% - 8px) 100%,0 100%,0 8px)}
.chip:hover{background:#00e5ff2b;color:#fff;border-color:var(--azul);transform:none}
.chip.on{background:var(--azul);color:#001018;border-color:var(--azul);box-shadow:none}
.card{position:relative;background:#071426d9;backdrop-filter:blur(8px);border:1px solid #00e5ff33;border-radius:2px;box-shadow:0 0 24px #00e5ff1c,inset 0 0 28px #00e5ff0b}
.card::before,.card::after,.brief::before,.brief::after{content:"";position:absolute;width:14px;height:14px;border:2px solid var(--azul);pointer-events:none}
.card::before,.brief::before{top:-1px;left:-1px;border-right:0;border-bottom:0}
.card::after,.brief::after{bottom:-1px;right:-1px;border-left:0;border-top:0}
h2{font:600 11px "Cascadia Mono",Consolas,monospace;letter-spacing:.32em;color:var(--azul);text-shadow:0 0 8px #00e5ff88}
.m{border-radius:2px;border:1px solid #0f3b57;box-shadow:none}
.m.u{background:#0a2a44;border-color:#00e5ff;box-shadow:0 0 14px #00e5ff33;color:#fff}
.m.j{background:#071426d9;border:1px solid #0f3b57;border-left:3px solid var(--azul)}
.m pre{border:1px solid #0f3b57;background:#02060f;color:#7df3ff}
.m a{color:#59e9ff}
.brief{position:relative;background:#071426d9;backdrop-filter:blur(8px);border:1px solid #00e5ff44;border-radius:2px;box-shadow:0 0 26px #00e5ff22,inset 0 0 30px #00e5ff0b}
.brief-h{font:600 12px "Cascadia Mono",Consolas,monospace;letter-spacing:.2em;color:var(--azul);text-shadow:0 0 10px #00e5ff88}
.brief-i{border-top:1px solid #00e5ff22}
.brief-i b{font:600 10px "Cascadia Mono",Consolas,monospace;letter-spacing:.3em;color:var(--azul);opacity:.8}
.orb{border:2px solid var(--azul);background:radial-gradient(circle,#ffffff 0,#b8f8ff 12%,var(--azul) 26%,#04526b 62%,#02101a 100%);
 box-shadow:0 0 0 3px #00e5ff33,0 0 34px #00e5ffaa,inset 0 0 22px #00e5ff77}
.orb::before{content:"";position:absolute;inset:9px;border-radius:50%;border:2px dotted #00e5ffbb;animation:gira 7s linear infinite reverse}
.orb::after{border:2px dashed #00e5ff66}
.orb.ouvindo{border-color:var(--ok);background:radial-gradient(circle,#fff 0,#c9ffe6 12%,var(--ok) 26%,#006b45 62%,#021a10 100%);box-shadow:0 0 0 3px #00ff9d44,0 0 44px #00ff9dcc,inset 0 0 22px #00ff9d77}
.orb.pensando{border-color:var(--ouro);background:radial-gradient(circle,#fff 0,#ffe2a1 12%,var(--ouro) 26%,#6b4a00 62%,#1a1002 100%);box-shadow:0 0 0 3px #ffb30044,0 0 34px #ffb300aa}
.orb.pensando::after{border-color:var(--ouro)}
.orb.falando{border-color:#b388ff;background:radial-gradient(circle,#fff 0,#e3d4ff 12%,#b388ff 26%,#40258a 62%,#0e0620 100%);box-shadow:0 0 0 3px #b388ff44,0 0 44px #b388ffcc}
.entrada{border:1px solid #00e5ff55;border-radius:2px;background:#071426d9}
.entrada:focus-within{border-color:var(--azul);box-shadow:0 0 16px #00e5ff44}
.btn{background:var(--azul);color:#001018;border:0;border-radius:2px;font:700 11px "Cascadia Mono",Consolas,monospace;letter-spacing:.16em}
.btn.web{background:transparent;color:var(--mudo);border:1px solid #00e5ff44}
.btn.web.on{background:#00e5ff22;color:var(--azul);border-color:var(--azul)}
.t input[type=checkbox]{accent-color:var(--azul)}
.t{border-bottom:1px solid #0f3b57}
#relogio{border-left:2px solid var(--azul)}
#relogio b{font:500 28px "Cascadia Mono",Consolas,monospace;font-style:normal;color:var(--azul);text-shadow:0 0 16px #00e5ffbb}
#relogio span{font-family:"Cascadia Mono",Consolas,monospace;font-size:11px;letter-spacing:.08em}
.hr{color:var(--azul);font:600 13px "Cascadia Mono",Consolas,monospace}
.dica p:first-child{font:600 24px "Cascadia Mono",Consolas,monospace;letter-spacing:.12em;color:#fff;text-shadow:0 0 16px #00e5ff}
input::placeholder{color:#4f7890}
::-webkit-scrollbar{width:8px}::-webkit-scrollbar-thumb{background:#00e5ff44}::-webkit-scrollbar-track{background:transparent}
"""
TEMA_TECH_CSS = TEMA_TECH_CSS.replace("__HUD__", _hud())


def _teia(cx, cy, a0, a1, n, aneis, comp, caixa, cor="white", larg=1.3):
    """SVG de teia de aranha (setores ou círculo completo) como data URI."""
    ang = [a0 + (a1 - a0) * i / n for i in range(n + 1)]
    d = "".join(f"M{cx:.1f},{cy:.1f}L{cx + comp * math.cos(a):.1f},{cy + comp * math.sin(a):.1f}" for a in ang)
    for r in aneis:
        for p_, q_ in zip(ang, ang[1:]):
            m = (p_ + q_) / 2
            d += (f"M{cx + r * math.cos(p_):.1f},{cy + r * math.sin(p_):.1f}"
                  f"Q{cx + r * 0.8 * math.cos(m):.1f},{cy + r * 0.8 * math.sin(m):.1f} "
                  f"{cx + r * math.cos(q_):.1f},{cy + r * math.sin(q_):.1f}")
    svg = (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {caixa} {caixa}'><path d='{d}' fill='none' "
           f"stroke='{cor}' stroke-width='{larg}' stroke-linecap='round'/></svg>")
    return "data:image/svg+xml," + urllib.parse.quote(svg)


TEMA_CSS = """
:root{--bg:#060a1c;--card:#0f1838;--borda:#2a3a7a;--azul:#4d8dff;--ok:#4d8dff;--ouro:#ff4d5e;--txt:#eef2ff;--mudo:#93a0cf;--rubro:#e62429;--azulesc:#1b3fa8}
body{background:radial-gradient(900px 520px at 90% -10%,#1b2f8a66,transparent 60%),radial-gradient(800px 520px at 0% 110%,#e6242940,transparent 60%),var(--bg)}
body::before,body::after{content:"";position:fixed;width:440px;height:440px;pointer-events:none;opacity:.2;z-index:0;
 background:url("__TEIA__") no-repeat top left/contain}
body::before{top:0;right:0;transform:scaleX(-1)}
body::after{bottom:0;left:0;transform:scaleY(-1)}
header,main{position:relative;z-index:1}
header{border-bottom:3px solid var(--rubro);padding:12px 22px;
 background:linear-gradient(90deg,var(--bg) 40%,transparent),radial-gradient(circle,#e62429 1.3px,transparent 1.8px) 0 0/8px 8px,var(--bg)}
h1{font:italic 900 28px Impact,"Arial Black",sans-serif;letter-spacing:5px;color:var(--rubro);
 text-shadow:2px 2px 0 var(--azulesc),4px 4px 0 #000;transform:skew(-6deg)}
.chip{border:2px solid var(--borda);color:var(--txt);border-radius:8px;font-weight:700;font-size:12px;text-transform:uppercase;letter-spacing:.6px}
.chip:hover{border-color:var(--rubro);background:#e6242933;color:#fff;transform:translateY(-1px)}
.chip.on{background:var(--rubro);border-color:#fff;color:#fff;box-shadow:3px 3px 0 var(--azulesc)}
.card{border:2px solid var(--borda);box-shadow:5px 5px 0 #e6242966;border-radius:12px}
h2{font:italic 900 15px Impact,"Arial Black",sans-serif;letter-spacing:2px;color:var(--rubro)}
.m{border:2px solid #000}
.m.u{background:linear-gradient(135deg,#2f63ff,var(--azulesc));border-color:#0b1a5c;box-shadow:4px 4px 0 var(--rubro)}
.m.j{background:#121c45;border:2px solid var(--rubro);box-shadow:4px 4px 0 var(--azulesc)}
.m pre{background:#060a1c;border:2px solid var(--borda);color:#cfe0ff}
.m a{color:#8fb4ff}
.orb{border:3px solid #fff;background:url("__ORB__") center/cover,radial-gradient(circle at 35% 30%,#ff7a80 0,var(--rubro) 38%,#8f0f14 100%);
 box-shadow:0 0 0 4px var(--azulesc),0 0 28px #e6242999}
.orb::after{border:2px dashed #4d8dff99}
.orb.ouvindo{border-color:#fff;background:url("__ORB__") center/cover,radial-gradient(circle at 35% 30%,#a9c8ff 0,var(--azul) 38%,var(--azulesc) 100%);
 box-shadow:0 0 0 4px var(--azul),0 0 46px #4d8dffcc}
.orb.pensando::after{border-color:#fff}
.orb.falando{box-shadow:0 0 0 4px #fff,0 0 46px #e62429dd}
.entrada{border:2px solid var(--borda)}
.entrada:focus-within{border-color:var(--rubro)}
.btn{background:var(--rubro);color:#fff;border:2px solid #fff;text-transform:uppercase;font-weight:800;letter-spacing:.5px}
.btn.web{background:transparent;color:var(--mudo);border:2px solid var(--borda);font-weight:700}
.btn.web.on{background:var(--azulesc);color:#fff;border-color:var(--azul)}
.t input[type=checkbox]{accent-color:var(--rubro)}
.t{border-bottom:1px solid #1d2a5c}
input::placeholder{color:#6f7db0}
.t input[type=checkbox]{flex:none;width:16px;height:16px}
.m pre{padding-top:28px;min-width:260px}
#relogio{display:flex;flex-direction:column;line-height:1.1;margin-left:20px;padding-left:16px;border-left:3px solid var(--rubro)}
#relogio b{font:italic 900 24px Impact,"Arial Black",sans-serif;color:#fff;text-shadow:2px 2px 0 var(--azulesc)}
#relogio span{font-size:12px;color:var(--mudo)}
#relogio span::first-letter{text-transform:uppercase}
.hr{color:var(--rubro);font:italic 900 14px Impact,"Arial Black",sans-serif;margin-right:4px}
.outras{color:var(--mudo);font-size:12px;margin-top:8px}
.brief{align-self:stretch;background:#0b1430;border:2px solid var(--rubro);border-radius:12px;padding:14px 16px;animation:subir .3s}
.brief-h{font:italic 900 14px Impact,"Arial Black",sans-serif;letter-spacing:2px;color:var(--rubro);margin-bottom:6px;display:flex;align-items:center;gap:8px;text-transform:uppercase}
.brief-i{padding:8px 0;border-top:1px solid #ffffff14}
.brief-i b{display:block;font-size:11px;letter-spacing:2px;text-transform:uppercase;color:var(--mudo);margin-bottom:2px}
.brief-i p{margin:0}.brief-i ul{margin:2px 0 0 18px;padding:0}.brief-i li{margin:3px 0}
.pulso{width:8px;height:8px;border-radius:50%;background:var(--ok);box-shadow:0 0 8px var(--ok);animation:pulso 1.4s infinite}
.dica p:first-child{color:#fff;font:italic 900 34px Impact,"Arial Black",sans-serif;letter-spacing:2px;text-shadow:3px 3px 0 var(--rubro)}
"""
TEMA_CSS = (TEMA_CSS.replace("__TEIA__", _teia(0, 0, 0, math.pi / 2, 8, (55, 115, 185, 265, 355), 440, 440))
            .replace("__ORB__", _teia(50, 50, 0, 2 * math.pi, 10, (13, 25, 37, 48), 50, 100, cor="black", larg=1.6)))
HTML = HTML.replace("</head>", "<style>" + TEMA_CSS + (TEMA_TECH_CSS if TEMA == "tech" else "") + "</style></head>")
HTML = re.sub(r'<div class="card"><h2>Foco</h2>.*?</div>\s*<div class="row">.*?</div></div>', "", HTML, flags=re.S)
HTML = HTML.replace('<button class="chip" data-s="Foco de 25 minutos">Modo foco</button>', "")
HTML = re.sub(r'if\(m=n\.match\(/foco \(\?:de \)\?\(\\d\+\)/\)\)\{.*?\}\n', "", HTML)
HTML = HTML.replace("Olá! Como posso ajudar?", "E aí! Bora codar?")
HTML = HTML.replace("<h2>Tarefas</h2>", '<h2 id="titulo-tarefas">Tarefas</h2>')
_ini = HTML.index("if(m=n.match(/(?:anote|anotar|adicione|criar|crie)")
_fim = HTML.index('return resp("Tarefa anotada: "+m[1]+".")}', _ini) + len('return resp("Tarefa anotada: "+m[1]+".")}')
HTML = HTML[:_ini] + HTML[_fim:]
HTML = re.sub(r"<h1>.*?</h1>", "<h1>" + ".".join(NOME.upper()) + "</h1>", HTML)
HTML = re.sub(r"<title>.*?</title>", f"<title>{NOME}</title>", HTML)

ESTADO = {"pendente": None}


# ------------------------------------------------------------------ utilidades
def R(texto, fontes=None):
    return {"resposta": texto, "fontes": fontes or []}


def ler(arq=ARQ):
    return json.loads(arq.read_text("utf-8")) if arq.exists() else []


def gravar(t, arq=ARQ):
    arq.write_text(json.dumps(t, ensure_ascii=False, indent=2), "utf-8")


def bloco(txt, lim=3500):
    corte = "\n... (cortado)" if len(txt) > lim else ""
    return "```text\n" + txt[:lim].replace("```", "'''") + corte + "\n```"


def so_codigo(t):
    m = re.search(r"```[\w+#.-]*\n(.*?)```", t, re.S)
    return (m.group(1) if m else t).strip("\n") + "\n"


def ollama(msgs, system, tokens=350, ctx=4096):
    corpo = json.dumps({"model": MODELO, "stream": False, "think": False, "keep_alive": "30m",
                        "options": {"num_ctx": ctx, "num_predict": tokens},
                        "messages": [{"role": "system", "content": system}] + msgs}).encode()
    req = urllib.request.Request(f"{OLLAMA}/api/chat", corpo, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())["message"]["content"].strip()


def projeto():
    cfg = json.loads(CFG.read_text("utf-8")) if CFG.exists() else {}
    return Path(cfg["projeto"]) if cfg.get("projeto") else None


def caminho(rel):
    raiz = projeto()
    if not raiz:
        raise ValueError("Defina um projeto primeiro, por exemplo: usar projeto D:\\codigos\\meu-app")
    p = (raiz / rel.strip("\"'")).resolve()
    try:
        p.relative_to(raiz.resolve())
    except ValueError:
        raise ValueError("Esse caminho está fora do projeto, então não vou mexer nele.")
    return p


def arquivos(raiz, limite=300):
    achados = []
    for dp, dn, fn in os.walk(raiz):
        dn[:] = sorted(d for d in dn if d not in IGNORAR)
        achados += [Path(dp) / f for f in sorted(fn) if Path(f).suffix.lower() in EXT]
        if len(achados) >= limite:
            break
    return achados


def _sem_acento(t):
    return "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")


_APPS = {}


def apps_iniciar():
    """(nome, appid) de todos os aplicativos do menu Iniciar, inclusive apps da Microsoft Store e apps web."""
    if not _APPS.get("lista"):
        try:
            saida = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "[Console]::OutputEncoding=[Text.Encoding]::UTF8; Get-StartApps | ConvertTo-Json"],
                capture_output=True, timeout=25, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            ).stdout.decode("utf-8", errors="replace")
            dados = json.loads(saida) if saida.strip() else []
            _APPS["lista"] = [(d["Name"], d["AppID"]) for d in ([dados] if isinstance(dados, dict) else dados)]
        except Exception:
            _APPS["lista"] = []
    return _APPS["lista"]


def achar_app(alvo):
    palavras = [w for w in _sem_acento(alvo).split() if w not in ("o", "a", "meu", "minha", "app", "aplicativo")]
    if not palavras or len(" ".join(palavras)) < 3:
        return None
    achados = [(n, i) for n, i in apps_iniciar()
               if all(w in _sem_acento(n) for w in palavras) and not re.search(r"uninstall|desinstal", _sem_acento(n))]
    return min(achados, key=lambda a: len(a[0])) if achados else None


def achar_atalho(alvo):
    """Procura no menu Iniciar um atalho (.lnk) cujo nome contenha todas as palavras de alvo."""
    palavras = [w for w in _sem_acento(alvo).split() if w not in ("o", "a", "meu", "minha", "app", "aplicativo")]
    if not palavras or len(" ".join(palavras)) < 3:
        return None
    pastas = [Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
              Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft/Windows/Start Menu/Programs"]
    achados = []
    for pasta in pastas:
        if pasta.is_dir():
            for lnk in pasta.rglob("*.lnk"):
                nome = _sem_acento(lnk.stem)
                if all(w in nome for w in palavras) and not re.search(r"uninstall|desinstal", nome):
                    achados.append(lnk)
    return min(achados, key=lambda l: len(l.stem)) if achados else None


BUSCAS = {"youtube": "https://www.youtube.com/results?search_query=", "google": "https://www.google.com/search?q=",
          "github": "https://github.com/search?q=", "stack overflow": "https://stackoverflow.com/search?q=",
          "spotify": "https://open.spotify.com/search/", "wikipedia": "https://pt.wikipedia.org/w/index.php?search=",
          "linkedin": "https://www.linkedin.com/jobs/search/?keywords="}
TECLAS_MIDIA = {"play": 0xB3, "proxima": 0xB0, "anterior": 0xB1, "vol+": 0xAF, "vol-": 0xAE, "mudo": 0xAD}


def tecla_midia(nome, vezes=1):
    """Envia teclas de mídia do Windows (funciona com Spotify, YouTube e qualquer player ativo)."""
    try:
        import ctypes
        for _ in range(vezes):
            ctypes.windll.user32.keybd_event(TECLAS_MIDIA[nome], 0, 0, 0)
            ctypes.windll.user32.keybd_event(TECLAS_MIDIA[nome], 0, 2, 0)
        return True
    except Exception:
        return False


def buscar_em(site, termo, tocar=False):
    if tocar and site == "spotify":
        try:
            os.startfile("spotify:search:" + urllib.parse.quote(termo))
            return R(f"Abri a busca de {termo} no Spotify. Escolha a faixa e dê play.")
        except OSError:
            pass
    webbrowser.open(BUSCAS[site] + urllib.parse.quote(termo))
    return R(f"Busquei {termo} no {site}.")


DIAS_SEMANA = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
         "novembro", "dezembro"]
SEMANA = {"segunda": 0, "terca": 1, "quarta": 2, "quinta": 3, "sexta": 4, "sabado": 5, "domingo": 6}
NUMEROS = {"um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5, "seis": 6, "sete": 7,
           "oito": 8, "nove": 9, "dez": 10}


def data_extenso(d):
    return f"{DIAS_SEMANA[d.weekday()]}, {d.day} de {MESES[d.month - 1]} de {d.year}"


def interpretar_tarefa(texto):
    """Separa o texto da tarefa da data e da hora ditas na frase. Retorna (texto, data 'AAAA-MM-DD', hora 'HH:MM' ou '')."""
    original = texto.strip()
    f = _sem_acento(original)
    if len(f) != len(original):
        original = f
    hoje = datetime.now().date()
    data, hora, cortes = hoje, "", []

    m = None
    if m := re.search(r"\bdepois de amanha\b", f):
        data = hoje + timedelta(days=2)
    elif m := re.search(r"\bamanha\b", f):
        data = hoje + timedelta(days=1)
    elif m := re.search(r"\bhoje\b", f):
        pass
    elif m := re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", f):
        try:
            ano_txt = m.group(3)
            ano = (int(ano_txt) + (2000 if len(ano_txt) == 2 else 0)) if ano_txt else hoje.year
            alvo = date(ano, int(m.group(2)), int(m.group(1)))
            if not ano_txt and alvo < hoje:
                alvo = date(ano + 1, int(m.group(2)), int(m.group(1)))
            data = alvo
        except ValueError:
            m = None
    elif m := re.search(r"\bdia (\d{1,2})\b", f):
        try:
            alvo = hoje.replace(day=int(m.group(1)))
            if alvo < hoje:
                alvo = (hoje.replace(day=1) + timedelta(days=32)).replace(day=int(m.group(1)))
            data = alvo
        except ValueError:
            m = None
    elif m := re.search(r"\b(segunda|terca|quarta|quinta|sexta|sabado|domingo)(?:-feira)?\b", f):
        data = hoje + timedelta(days=(SEMANA[m.group(1)] - hoje.weekday()) % 7 or 7)
    if m:
        cortes.append(m.span())

    def periodo(h, p):
        return h + 12 if p in ("tarde", "noite") and h < 12 else h

    h = None
    if m := re.search(r"\bmeio[- ]dia\b", f):
        h, hora = m, "12:00"
    elif m := re.search(r"\bas\s+(\d{1,2})(?:(?::|h)(\d{2}))?(?:\s*(?:h|horas?))?(?:\s+da\s+(manha|tarde|noite))?\b", f):
        simples = not re.search(r"h|:|manha|tarde|noite", m.group(0)[2:])
        resto = re.match(r"\s*([a-z]+)", f[m.end():])
        if not (simples and resto and resto.group(1) not in ("e", "do", "da", "de", "para", "hoje", "amanha")):
            hh, mm = periodo(int(m.group(1)), m.group(3)), int(m.group(2) or 0)
            if hh <= 23 and mm <= 59:
                h, hora = m, f"{hh:02d}:{mm:02d}"
    if not h and (m := re.search(r"\b(\d{1,2})(?::(\d{2})|h(\d{2})?|\s*horas?)(?:\s+da\s+(manha|tarde|noite))?\b", f)):
        hh, mm = periodo(int(m.group(1)), m.group(4)), int(m.group(2) or m.group(3) or 0)
        if hh <= 23 and mm <= 59:
            h, hora = m, f"{hh:02d}:{mm:02d}"
    if h:
        cortes.append(h.span())

    limpo = original
    for a, b in sorted(cortes, reverse=True):
        limpo = limpo[:a] + " " + limpo[b:]
    limpo = re.sub(r"\s+", " ", limpo).strip(" ,.;:-")
    for _ in range(3):
        limpo = re.sub(r"^(?:para|de|em|no|na|as|às|dia|do|da|a|o|ao|à)\s+", "", limpo, flags=re.I)
        limpo = re.sub(r"\s+(?:para|de|em|no|na|as|às|dia|do|da|a|o|e|ao|à)$", "", limpo, flags=re.I)
    return (limpo.strip(" ,.;:-") or original), data.isoformat(), hora


def tarefas_do_dia(dia=None):
    """Tarefas do dia (padrão: hoje), na ordem mostrada na tela, com o número (id) de cada uma."""
    hoje = f"{datetime.now():%Y-%m-%d}"
    t = ler()
    if any("data" not in x for x in t):          # tarefas antigas, de antes das datas
        for x in t:
            x.setdefault("data", hoje)
            x.setdefault("hora", "")
        gravar(t)
    itens = [dict(x, id=i) for i, x in enumerate(t) if x["data"] == (dia or hoje)]
    itens.sort(key=lambda x: (x["feita"], x.get("hora") or "99:99"))
    return itens, sum(1 for x in t if x["data"] != hoje and not x["feita"])


def quando(data_iso, hora=""):
    d = date.fromisoformat(data_iso)
    hoje = datetime.now().date()
    rotulo = "hoje" if d == hoje else "amanhã" if d == hoje + timedelta(days=1) else f"{d:%d/%m}"
    return rotulo + (f" às {hora}" if hora else "")


def listar_tarefas(dia=None):
    itens, _ = tarefas_do_dia(dia)
    hoje = f"{datetime.now():%Y-%m-%d}"
    outras = sum(1 for x in ler() if x["data"] != (dia or hoje) and not x["feita"])
    rotulo = "hoje" if not dia or dia == hoje else quando(dia)
    pendentes = [x for x in itens if not x["feita"]]
    if not itens:
        return R(f"Você não tem tarefas para {rotulo}." + (f" Há {outras} em outros dias." if outras else ""))
    partes = [f"{n}: {x['texto']}" + (f" às {x['hora']}" if x.get("hora") else "") + (" (feita)" if x["feita"] else "")
              for n, x in enumerate(itens, 1)]
    return R(f"Para {rotulo} você tem {len(pendentes)} pendente{'s' if len(pendentes) != 1 else ''}. " + ". ".join(partes)
             + ("." + (f" Há mais {outras} em outros dias." if outras else "")))


def playlists_spotify():
    if SPOTIFY_CFG.exists():
        return json.loads(SPOTIFY_CFG.read_text("utf-8"))
    return {"padrao": "vibe", "playlists": {}}


def salvar_playlist(nome, link):
    nome = _sem_acento(nome).strip()
    m = (re.search(r"open\.spotify\.com/(?:intl-\w+/)?(playlist|album|track|artist)/([A-Za-z0-9]+)", link)
         or re.match(r"spotify:(playlist|album|track|artist):([A-Za-z0-9]+)", link))
    if not m:
        return R("Não reconheci esse link do Spotify. No app: botão direito na playlist, Compartilhar, Copiar link.")
    tipo, ident = m.groups()
    cfg = playlists_spotify()
    cfg["playlists"][nome] = {"uri": f"spotify:{tipo}:{ident}", "web": f"https://open.spotify.com/{tipo}/{ident}"}
    if nome == "vibe" or not cfg.get("padrao") or cfg["padrao"] not in cfg["playlists"]:
        cfg["padrao"] = nome
    SPOTIFY_CFG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), "utf-8")
    return R(f"Playlist {nome} salva. Agora é só dizer: toque música.")


def spotify_rodando():
    try:
        saida = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Spotify.exe"], capture_output=True, text=True,
                               timeout=10, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
        return "Spotify.exe" in saida
    except Exception:
        return False


SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_ESCOPOS = "user-modify-playback-state user-read-playback-state"
AJUDA_SPOTIFY = """Para o Peter dar play sozinho no Spotify (precisa de conta Premium):
1. Entre em developer.spotify.com/dashboard e clique em Create app.
2. Em Redirect URI coloque exatamente: http://127.0.0.1:{porta}/callback
   Marque Web API e salve.
3. Em Settings, copie o Client ID (não use o Client Secret).
   Em User management, confira se o seu nome e e-mail estão na lista.
4. Aqui no Peter, digite: conectar spotify SEU_CLIENT_ID
5. Aceite no navegador. Depois é só dizer: toque música."""


def _http(url, dados=None, metodo=None, cab=None, corpo_json=None):
    """Requisição simples. Retorna (status, resposta em dict/texto)."""
    corpo, cab = None, dict(cab or {})
    if corpo_json is not None:
        corpo, cab["Content-Type"] = json.dumps(corpo_json).encode(), "application/json"
    elif dados is not None:
        corpo, cab["Content-Type"] = urllib.parse.urlencode(dados).encode(), "application/x-www-form-urlencoded"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, corpo, cab, method=metodo), timeout=20) as r:
            status, txt = r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        status, txt = e.code, e.read().decode("utf-8", "replace")
    try:
        return status, (json.loads(txt) if txt.strip() else {})
    except ValueError:
        return status, txt


def spotify_iniciar_login(client_id):
    verificador = secrets.token_urlsafe(64)
    desafio = base64.urlsafe_b64encode(hashlib.sha256(verificador.encode()).digest()).rstrip(b"=").decode()
    estado = secrets.token_urlsafe(12)
    ESTADO["spotify_login"] = {"verificador": verificador, "estado": estado, "client_id": client_id}
    webbrowser.open("https://accounts.spotify.com/authorize?" + urllib.parse.urlencode({
        "client_id": client_id, "response_type": "code", "redirect_uri": f"http://127.0.0.1:{PORTA}/callback",
        "scope": SPOTIFY_ESCOPOS, "code_challenge_method": "S256", "code_challenge": desafio, "state": estado}))


def _guardar_token(d, client_id, antigo=None):
    tok = {"client_id": client_id, "access_token": d["access_token"],
           "refresh_token": d.get("refresh_token") or (antigo or {}).get("refresh_token"),
           "expira": time.time() + d.get("expires_in", 3600) - 60}
    SPOTIFY_TOKEN.write_text(json.dumps(tok), "utf-8")
    return tok


def spotify_callback(params):
    """Chamado quando o Spotify devolve o navegador para http://127.0.0.1:PORTA/callback."""
    login = ESTADO.get("spotify_login")
    if not login or params.get("state", [""])[0] != login["estado"]:
        return "Login inválido ou expirado. Volte ao Peter e digite: conectar spotify SEU_CLIENT_ID"
    if "error" in params:
        return "O Spotify não autorizou: " + params["error"][0]
    status, d = _http(SPOTIFY_TOKEN_URL, dados={
        "grant_type": "authorization_code", "code": params.get("code", [""])[0],
        "redirect_uri": f"http://127.0.0.1:{PORTA}/callback", "client_id": login["client_id"],
        "code_verifier": login["verificador"]})
    if status != 200 or not isinstance(d, dict) or "access_token" not in d:
        return f"Não consegui concluir o login no Spotify (erro {status})."
    _guardar_token(d, login["client_id"])
    ESTADO["spotify_login"] = None
    return "Spotify conectado! Pode fechar esta aba e voltar ao Peter."


def spotify_token():
    if not SPOTIFY_TOKEN.exists():
        return None
    tok = json.loads(SPOTIFY_TOKEN.read_text("utf-8"))
    if time.time() >= tok["expira"]:
        status, d = _http(SPOTIFY_TOKEN_URL, dados={"grant_type": "refresh_token",
                                                    "refresh_token": tok["refresh_token"], "client_id": tok["client_id"]})
        if status != 200 or not isinstance(d, dict) or "access_token" not in d:
            return None
        tok = _guardar_token(d, tok["client_id"], tok)
    return tok["access_token"]


def spotify_api_tocar(uri):
    """Toca a playlist pela API. Retorna None (sem login), (True, '') ou (False, motivo)."""
    token = spotify_token()
    if not token:
        return None
    cab = {"Authorization": "Bearer " + token}
    disp = None
    for _ in range(20):                      # espera o aplicativo aparecer como dispositivo
        status, d = _http("https://api.spotify.com/v1/me/player/devices", cab=cab)
        if status == 401:
            return False, "O login do Spotify expirou. Digite: conectar spotify SEU_CLIENT_ID"
        lista = d.get("devices", []) if isinstance(d, dict) else []
        if lista:
            disp = next((x for x in lista if x.get("is_active")), None) or \
                next((x for x in lista if x.get("type") == "Computer"), lista[0])
            break
        time.sleep(1)
    if not disp:
        return False, "O Spotify abriu, mas não apareceu como dispositivo. Toque qualquer música nele uma vez e tente de novo."
    status, d = _http(f"https://api.spotify.com/v1/me/player/play?device_id={urllib.parse.quote(disp['id'])}",
                      metodo="PUT", cab=cab, corpo_json={"context_uri": uri})
    if status in (200, 202, 204):
        return True, ""
    if status == 403:
        return False, "O Spotify recusou: o controle de reprodução exige conta Premium."
    return False, f"O Spotify respondeu com o erro {status}."


def tocar_spotify(item, nome):
    """Abre o Spotify (se estiver fechado) e toca a playlist. Diz a verdade sobre o resultado."""
    try:
        if not spotify_rodando():
            os.startfile("spotify:")
            for _ in range(24):
                time.sleep(0.5)
                if spotify_rodando():
                    break
            time.sleep(2)
    except OSError:
        webbrowser.open(item["web"])
        return R("Não achei o aplicativo do Spotify instalado, então abri a playlist na web. É só clicar em play.")
    resultado = spotify_api_tocar(item["uri"])
    if resultado and resultado[0]:
        return R(f"Tocando a playlist {nome} no Spotify.")
    try:
        os.startfile(item["uri"])
    except OSError:
        webbrowser.open(item["web"])
    if resultado is None:
        return R(f"Abri a playlist {nome}, mas o play automático ainda não está configurado. "
                 "Digite: ajuda spotify")
    return R(f"Abri a playlist {nome}. {resultado[1]}")


def copiar(texto):
    try:
        subprocess.run(["clip"], input=("\ufeff" + texto).encode("utf-16le"), timeout=10,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return True
    except Exception:
        return False


CODIGOS_TEMPO = {0: "céu limpo", 1: "céu quase limpo", 2: "parcialmente nublado", 3: "nublado", 45: "neblina", 48: "neblina",
                 51: "garoa fraca", 53: "garoa", 55: "garoa forte", 61: "chuva fraca", 63: "chuva", 65: "chuva forte",
                 80: "pancadas de chuva fracas", 81: "pancadas de chuva", 82: "pancadas de chuva fortes",
                 95: "trovoadas", 96: "trovoadas com granizo", 99: "trovoadas com granizo"}
FEEDS = {"mundo": ["https://feeds.bbci.co.uk/portuguese/rss.xml", "https://g1.globo.com/rss/g1/mundo/"],
         "tecnologia": ["https://tecnoblog.net/feed/", "https://g1.globo.com/rss/g1/tecnologia/",
                        "https://olhardigital.com.br/feed/"]}


def periodo_do_dia(hora=None):
    hora = datetime.now().hour if hora is None else hora
    return "manha" if 5 <= hora < 12 else "tarde" if 12 <= hora < 18 else "noite"


def saudacao(periodo, hora):
    base = {"manha": "Bom dia", "tarde": "Boa tarde", "noite": "Boa noite"}[periodo] + f", {USUARIO}!"
    extra = {"manha": " Vamos começar o dia com tudo.", "tarde": " Espero que a tarde esteja produtiva.",
             "noite": " Espero que o seu dia tenha sido bom."}[periodo]
    if periodo == "noite" and (hora >= 22 or hora < 5):
        extra = " Já é tarde, não se esqueça de descansar."
    return base + extra


def previsao():
    """Previsão de hoje para a cidade configurada (Open-Meteo, sem chave). None se falhar."""
    try:
        status, d = _http("https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode({
            "latitude": CIDADE["lat"], "longitude": CIDADE["lon"], "timezone": "auto", "forecast_days": 1,
            "current": "temperature_2m,weather_code",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max"}))
        if status != 200 or not isinstance(d, dict):
            return None
        atual, dia = d["current"], d["daily"]
        chuva = dia["precipitation_probability_max"][0] or 0
        texto = (f"Em {CIDADE['nome']} agora faz {round(atual['temperature_2m'])} graus, "
                 f"{CODIGOS_TEMPO.get(atual['weather_code'], 'tempo variável')}. Hoje a máxima é de "
                 f"{round(dia['temperature_2m_max'][0])} e a mínima de {round(dia['temperature_2m_min'][0])} graus, "
                 f"com {chuva}% de chance de chuva.")
        return texto + (" Leve o guarda-chuva." if chuva >= 50 else "")
    except Exception:
        return None


def manchetes(categoria, n=3):
    """Primeiras manchetes de feeds RSS (usa o primeiro feed que responder)."""
    for url in FEEDS[categoria]:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 Peter"})
            with urllib.request.urlopen(req, timeout=8) as r:
                raiz = ET.fromstring(r.read())
            titulos = [html.unescape(i.findtext("title").strip()) for i in raiz.iter("item") if i.findtext("title")]
            if titulos:
                return titulos[:n]
        except Exception:
            continue
    return []


def tarefas_pendentes_hoje():
    itens, _ = tarefas_do_dia()
    return [(f"{x['hora']} " if x.get("hora") else "") + x["texto"] for x in itens if not x["feita"]]


def montar_briefing(forcar=False):
    agora = datetime.now()
    p, hoje = periodo_do_dia(agora.hour), f"{agora:%Y-%m-%d}"
    ja_deu = BRIEF_ARQ.exists() and json.loads(BRIEF_ARQ.read_text("utf-8")).get("data") == hoje
    completo = forcar or (p == "manha" and not ja_deu)
    itens = [{"titulo": {"manha": "Bom dia", "tarde": "Boa tarde", "noite": "Boa noite"}[p],
              "texto": saudacao(p, agora.hour), "fala": saudacao(p, agora.hour)}]
    if completo:
        with ThreadPoolExecutor(3) as ex:
            f_t, f_m, f_x = ex.submit(previsao), ex.submit(manchetes, "mundo"), ex.submit(manchetes, "tecnologia")
            tempo, mundo, tech = f_t.result(), f_m.result(), f_x.result()
        itens.append({"titulo": "Previsão do tempo", "texto": tempo or "Não consegui a previsão do tempo agora.",
                      "fala": tempo or "Não consegui a previsão do tempo agora."})
        for chave, titulo, lista in (("No mundo", "Mundo", mundo), ("Em tecnologia", "Tecnologia", tech)):
            itens.append({"titulo": titulo, "lista": lista,
                          "texto": "" if lista else f"Não consegui carregar as notícias de {titulo.lower()} agora.",
                          "fala": f"{chave}: " + "; ".join(lista) + "." if lista else
                          f"Não consegui carregar as notícias de {titulo.lower()} agora."})
        BRIEF_ARQ.write_text(json.dumps({"data": hoje}), "utf-8")
    pend = tarefas_pendentes_hoje()
    fala_t = (f"Você tem {len(pend)} tarefa{'s' if len(pend) != 1 else ''} pendente{'s' if len(pend) != 1 else ''} hoje: "
              + "; ".join(pend) + ".") if pend else "Você não tem tarefas pendentes hoje."
    itens.append({"titulo": "Tarefas de hoje", "lista": pend, "texto": "" if pend else fala_t, "fala": fala_t})
    nomes = {"manha": "manhã", "tarde": "tarde", "noite": "noite"}
    return {"titulo": f"Briefing da {nomes[p]} · {DIAS_SEMANA[agora.weekday()]}, {agora.day} de {MESES[agora.month - 1]}",
            "itens": itens, "fala": " ".join(i["fala"] for i in itens), "completo": completo}


def abrir_site(nome, url):
    ESTADO["site"] = (nome, url)
    if webbrowser.open(url):
        return R(f"Abrindo {nome} no seu navegador.")
    return R(f"Não consegui abrir o navegador. O endereço é {url}")


def cargo_padrao():
    for linha in CURR.read_text("utf-8").splitlines():
        if linha.lower().startswith("cargo:"):
            return linha.split(":", 1)[1].strip().replace("Desenvolvedora", "Desenvolvedor") or "desenvolvedor júnior"
    return "desenvolvedor júnior"


def ler_pdf(ref):
    pdf = Path(urllib.parse.unquote(ref.replace("file:///", "", 1)))
    if not pdf.exists():
        return R("Não encontrei esse PDF. Confira o caminho do arquivo.")
    try:
        from pypdf import PdfReader
    except ImportError:
        return R("Para ler PDF eu preciso do pacote pypdf: rode pip install pypdf quando a internet estiver estável. "
                 "Enquanto isso, diga abrir meu currículo e cole o texto do seu PDF no arquivo que vai abrir.")
    texto = "\n".join((pg.extract_text() or "") for pg in PdfReader(str(pdf)).pages).strip()
    if not texto:
        return R("Não consegui extrair texto desse PDF (talvez ele seja uma imagem).")
    ESTADO["pendente"] = {"caminho": CURR, "conteudo": texto + "\n"}
    return R("Li o PDF. Vou salvar este texto como o seu currículo (o atual vira .bak). Diga confirmar ou cancelar.\n"
             + bloco(texto, 2500))


def vagas(busca):
    ESTADO["vagas"] = True
    busca = re.sub(r"\s+(?:no|na|do|em|pelo)\s+linkedin\b", "", busca, flags=re.I).strip() or busca
    q = urllib.parse.urlencode({"keywords": busca, "location": "Brasil", "f_AL": "true", "f_E": "1,2"})
    webbrowser.open("https://www.linkedin.com/jobs/search/?" + q)
    fontes = []
    if DDGS:
        try:
            res = DDGS().text(f"site:linkedin.com/jobs {busca} júnior", region="br-pt", max_results=6)
            fontes = [{"titulo": r["title"], "url": r["href"]} for r in res]
        except Exception:
            pass
    return R(f"Abri a busca de vagas de {busca} no LinkedIn, já filtrada para júnior e candidatura simplificada. "
             "Quando achar uma vaga, diga: carta para vaga, e cole a descrição, que eu preparo seu material.", fontes)


def adaptar(descricao):
    sistema = ("Você é especialista em recrutamento de TI. Responda em português do Brasil. Com base SOMENTE no "
               "currículo abaixo (nunca invente experiências), gere para a vaga: 1) resumo profissional de 3 linhas; "
               "2) 5 destaques do currículo mais relevantes para a vaga; 3) mensagem curta ao recrutador.\n\n"
               "CURRÍCULO:\n" + CURR.read_text("utf-8")[:6000])
    saida = ollama([{"role": "user", "content": "Vaga:\n" + descricao[:4000]}], sistema, tokens=900, ctx=6144)
    arq = PASTA_CAND / f"{datetime.now():%Y-%m-%d_%H%M}_vaga.txt"
    arq.write_text("VAGA:\n" + descricao + "\n\n---\n\n" + saida, "utf-8")
    ESTADO["carta"] = saida
    return R(f"Preparei o material para essa vaga e salvei em {arq.name}.\n" + bloco(saida, 5000))


AJUDA = """Comandos (digite ou fale):
PROJETO
 usar projeto D:\\codigos\\meu-app
 listar arquivos | analisar projeto
 ler arquivo src\\app.py | analisar arquivo src\\app.py
 criar arquivo src\\util.py com <descrição>
 editar arquivo src\\app.py: <o que mudar>   (mostra a diferença e pede confirmação)
TAREFAS E HORÁRIO
 resumo do dia | previsão do tempo | notícias de tecnologia | pare (para de falar)
 anote tarefa estudar Angular amanhã às 15h | minhas tarefas | concluir tarefa 2 | apagar tarefa 2
 que horas são | que dia é hoje | repita (repete por voz a última fala)
PROGRAMAS
 abrir vs code | terminal | calculadora | bloco de notas | pasta | projeto
MÚSICA
 conectar spotify <client id> (play automático, veja: ajuda spotify)
 salvar playlist vibe <link da playlist> | toque música | toque a vibe | pausar música | próxima música
VAGAS E CURRÍCULO
 salvar vaga <link> <título> | próxima vaga | fila de vagas | copiar carta
 vagas de desenvolvedor angular
 carta para vaga: <cole a descrição da vaga>
 abrir meu currículo | abrir vaga <link>
 registrar candidatura <empresa - vaga> | minhas candidaturas
Para salvar mudanças em arquivos, responda: confirmar (ou cancelar)."""


# ------------------------------------------------------------------ roteador de comandos
def comandos(texto):
    t = re.sub(r"^\s*(?:" + "|".join(APELIDOS) + r")\b[\s,.:;!?-]*", "", texto.strip(), flags=re.I)
    if not t:
        return R("Pois não?")
    pend = ESTADO["pendente"]
    if pend:
        r = t.lower().strip(" .!")
        if r in ("confirmar", "confirmo", "sim", "salvar", "pode salvar", "pode"):
            ESTADO["pendente"] = None
            p = pend["caminho"]
            p.parent.mkdir(parents=True, exist_ok=True)
            if p.exists():
                p.with_suffix(p.suffix + ".bak").write_text(p.read_text("utf-8", errors="replace"), "utf-8")
            p.write_text(pend["conteudo"], "utf-8")
            return R(f"Pronto! Arquivo salvo: {p.name}. Se existia, o original ficou em {p.name}.bak.")
        if r in ("cancelar", "cancela", "cancelo", "nao", "não"):
            ESTADO["pendente"] = None
            return R("Cancelado. Nada foi alterado.")

    if re.match(r"^(ajuda(?!\s+spotify)|comandos|o que voc[eê] (faz|sabe))", t, re.I):
        return R(AJUDA.split("\n")[0] + "\n" + bloco(AJUDA))

    if m := re.search(r"(?:anote|anotar|adicione|adicionar|criar|crie|agende|agendar)(?: uma| um| a)? (?:tarefa|lembrete|compromisso)(?: de| para)?:?\s*(.+)", t, re.I):
        texto_t, dia, hora = interpretar_tarefa(m.group(1))
        tarefas = ler()
        tarefas.append({"texto": texto_t, "feita": False, "data": dia, "hora": hora,
                        "criada": datetime.now().isoformat(timespec="minutes")})
        gravar(tarefas)
        return R(f"Tarefa anotada para {quando(dia, hora)}: {texto_t}.")

    if re.search(r"(?:minhas|listar|quais|ler|mostrar).*(?:tarefas|pendencias|pendências)|o que (?:eu )?tenho (?:pra|para) fazer|^\s*(?:as\s+)?tarefas(?:\s+(?:de|para|do)\s+.+)?[.!?]*$", t, re.I):
        return listar_tarefas(interpretar_tarefa(t)[1] if re.search(r"amanh|dia \d|\d/\d|depois de", t, re.I) else None)

    if m := re.search(r"(?:conclu\w+|finaliz\w+|terminei)\s+(?:a\s+)?tarefa\s+(\w+)", t, re.I):
        itens, _ = tarefas_do_dia()
        n_ = int(m.group(1)) if m.group(1).isdigit() else NUMEROS.get(_sem_acento(m.group(1)), 0)
        if not 1 <= n_ <= len(itens):
            return R("Não encontrei essa tarefa na lista de hoje.")
        tarefas = ler()
        tarefas[itens[n_ - 1]["id"]]["feita"] = True
        gravar(tarefas)
        return R(f"Tarefa {n_} concluída. Parabéns!")

    if m := re.search(r"(?:apag\w+|remov\w+|exclu\w+)\s+(?:a\s+)?tarefa\s+(\w+)", t, re.I):
        itens, _ = tarefas_do_dia()
        n_ = int(m.group(1)) if m.group(1).isdigit() else NUMEROS.get(_sem_acento(m.group(1)), 0)
        if not 1 <= n_ <= len(itens):
            return R("Não encontrei essa tarefa na lista de hoje.")
        tarefas = ler()
        removida = tarefas.pop(itens[n_ - 1]["id"])
        gravar(tarefas)
        return R(f"Tarefa removida: {removida['texto']}.")

    hn = _sem_acento(t)
    hp = re.sub(r"\s+", " ", re.sub(r"[,;:.!?]", " ", hn)).strip()
    if len(hp.split()) <= 7:
        if re.search(r"\b(?:resumo do dia|briefing|resumo da manha|me atualize)\b", hp):
            return R("\n".join(i["fala"] for i in montar_briefing(forcar=True)["itens"]))
        if re.search(r"\b(?:previsao do tempo|previsao|como esta o tempo|vai chover|clima)\b", hp):
            return R(previsao() or "Não consegui a previsão do tempo agora. Confira a internet.")
        if re.search(r"\b(?:noticias|manchetes)\b", hp):
            quer_tech, quer_mundo = re.search(r"\b(?:tecnologia|tech)\b", hp), re.search(r"\bmundo\b", hp)
            partes = []
            if quer_mundo or not quer_tech:
                lista = manchetes("mundo", 4)
                partes += ["No mundo: " + "; ".join(lista) + "."] if lista else []
            if quer_tech or not quer_mundo:
                lista = manchetes("tecnologia", 4)
                partes += ["Em tecnologia: " + "; ".join(lista) + "."] if lista else []
            return R("\n".join(partes) if partes else "Não consegui carregar as notícias agora. Confira a internet.")
        if re.match(r"^(?:bom dia|boa tarde|boa noite)\b", hp):
            return R(saudacao(periodo_do_dia(), datetime.now().hour))
    if re.search(r"\bque horas\b|\bhoras sao\b|\bme (?:diga|fala|fale) (?:a )?hora\b", hn):
        return R(f"Agora são {datetime.now():%H:%M}.")
    if re.search(r"\bque dia\b.*\bhoje\b|\bdata de hoje\b|\bque data\b|\bque dia da semana\b|\bqual (?:e )?a data\b", hn):
        return R(f"Hoje é {data_extenso(datetime.now().date())}.")

    if m := re.search(r"(?:listar|mostrar|quais)\s+(?:os\s+)?(?:apps|aplicativos)\s*(?:com|de|chamados?|que tenho)?\s*(.*)", t, re.I):
        termo = _sem_acento(m.group(1)).strip(" .?!")
        todos = apps_iniciar()
        if not todos:
            return R("Não consegui consultar os aplicativos do menu Iniciar (o PowerShell não respondeu).")
        nomes = sorted(n for n, _ in todos if termo in _sem_acento(n))
        if not nomes:
            return R("Não encontrei nenhum aplicativo com esse nome no menu Iniciar.")
        return R(f"Encontrei {len(nomes)} aplicativos.\n" + bloco("\n".join(nomes[:60])))

    if m := re.search(r"(?:usar|definir|trocar)(?: o)? projeto\s+(.+)", t, re.I):
        p = Path(m.group(1).strip().strip("\"'"))
        if not p.is_dir():
            return R("Não encontrei essa pasta. Confira o caminho completo, por exemplo D:\\codigos\\meu-app.")
        gravar_cfg = {"projeto": str(p)}
        CFG.write_text(json.dumps(gravar_cfg), "utf-8")
        return R(f"Projeto definido: {p.name}. Agora posso listar, ler, analisar e editar arquivos dele.")

    if re.search(r"qual (?:é )?o projeto", t, re.I):
        return R(f"O projeto atual é {projeto()}." if projeto() else "Nenhum projeto definido ainda.")

    if re.search(r"listar (?:os )?arquivos|mostrar (?:a )?estrutura", t, re.I):
        raiz = projeto()
        if not raiz:
            return R("Defina um projeto primeiro: usar projeto D:\\codigos\\meu-app")
        lista = [str(a.relative_to(raiz)) for a in arquivos(raiz)]
        return R(f"Encontrei {len(lista)} arquivos de código no projeto.\n" + bloco("\n".join(lista[:100])))

    if m := re.search(r"ler (?:o )?arquivo\s+(\S+)", t, re.I):
        p = caminho(m.group(1))
        return R(f"Aqui está {p.name}.\n" + bloco(p.read_text("utf-8", errors="replace"), 6000))

    if m := re.search(r"analis\w+ (?:o )?arquivo\s+(\S+)", t, re.I):
        p = caminho(m.group(1))
        conteudo = p.read_text("utf-8", errors="replace")[:8000]
        return R(ollama([{"role": "user", "content": f"Analise este arquivo ({p.name}): possíveis bugs, "
                          f"melhorias e boas práticas, em até 5 pontos curtos.\n\n{conteudo}"}], MODOS["dev"], tokens=500, ctx=6144))

    if re.search(r"(?:analis\w+|explic\w+) (?:o )?projeto", t, re.I):
        raiz = projeto()
        if not raiz:
            return R("Defina um projeto primeiro: usar projeto D:\\codigos\\meu-app")
        todos = arquivos(raiz)
        chave = sorted(todos, key=lambda a: (a.name.lower() not in PRIORIDADE, a.stat().st_size))[:6]
        resumo = "Estrutura:\n" + "\n".join(str(a.relative_to(raiz)) for a in todos[:60]) + "\n\nTrechos:\n"
        for a in chave:
            resumo += f"\n### {a.relative_to(raiz)}\n{a.read_text('utf-8', errors='replace')[:1200]}\n"
        return R(ollama([{"role": "user", "content": "Explique o propósito e a estrutura deste projeto e sugira "
                          "3 melhorias.\n\n" + resumo}], MODOS["dev"], tokens=500, ctx=6144))

    if m := re.search(r"criar (?:o )?arquivo\s+(\S+)\s*(?:com|que|para|:)?\s*(.*)", t, re.I):
        p = caminho(m.group(1))
        if p.exists():
            return R("Esse arquivo já existe. Use: editar arquivo <nome>: <o que mudar>")
        if not m.group(2).strip():
            return R("Descreva o que o arquivo deve conter, por exemplo: criar arquivo util.py com funções de data.")
        novo = so_codigo(ollama([{"role": "user", "content": f"Crie o arquivo {p.name}: {m.group(2)}"}],
                                "Responda SOMENTE com o conteúdo completo do arquivo, sem explicações.", tokens=2000))
        ESTADO["pendente"] = {"caminho": p, "conteudo": novo}
        return R(f"Vou criar {p.name} com este conteúdo. Diga confirmar para salvar ou cancelar.\n" + bloco(novo))

    if m := re.search(r"edit\w+ (?:o )?arquivo\s+(\S+?)\s*[:,]\s*(.+)", t, re.I) or \
            re.search(r"edit\w+ (?:o )?arquivo\s+(\S+)\s+(.+)", t, re.I):
        p = caminho(m.group(1))
        if not p.is_file():
            return R("Não encontrei esse arquivo no projeto.")
        velho = p.read_text("utf-8", errors="replace")
        if len(velho) > 20000:
            return R("Esse arquivo é grande demais para eu editar com segurança. Peça para editar um menor.")
        novo = so_codigo(ollama([{"role": "user", "content": f"Arquivo {p.name}:\n{velho}\n\nMudança pedida: {m.group(2)}"}],
                                "Responda SOMENTE com o arquivo completo já modificado, sem explicações e sem cortar nada.", tokens=4000, ctx=8192))
        dif = "".join(difflib.unified_diff(velho.splitlines(True), novo.splitlines(True), "antes", "depois"))
        if not dif:
            return R("Não houve nenhuma mudança no arquivo.")
        ESTADO["pendente"] = {"caminho": p, "conteudo": novo}
        return R(f"Preparei a edição de {p.name}. Veja as mudanças e diga confirmar para salvar ou cancelar.\n"
                 + bloco(dif, 3500))

    if re.search(r"abr(?:ir|a|e) (?:o )?projeto", t, re.I):
        raiz = projeto()
        if not raiz:
            return R("Defina um projeto primeiro: usar projeto D:\\codigos\\meu-app")
        subprocess.Popen(f'code "{raiz}"', shell=True)
        return R("Abrindo o projeto no VS Code.")
    if re.search(r"abr(?:ir|a|e) (?:a )?pasta", t, re.I) and projeto():
        os.startfile(projeto())
        return R("Abrindo a pasta do projeto.")
    if re.search(r"abr(?:ir|a|e) (?:o )?(?:meu )?curr[ií]culo", t, re.I):
        os.startfile(CURR)
        return R("Abri seu currículo. Edite, salve, e eu uso a versão atualizada nas próximas cartas.")
    if m := re.search(r"abr(?:ir|a|e) (?:a )?vaga\s+(https?://\S+)", t, re.I):
        webbrowser.open(m.group(1))
        return R("Abri a vaga. Se tiver candidatura simplificada, é só clicar em Candidatar-se e anexar seu currículo.")
    if (m := re.search(r"abr(?:ir|a|e) (?:o |a )?(.+)", t, re.I)) and len(re.findall(r"\w+", t)) <= 6:
        alvo = m.group(1).lower()
        for nome, (proto, web) in PROTOCOLOS.items():
            if nome in alvo:
                try:
                    os.startfile(proto)
                    return R(f"Abrindo o {nome}.")
                except OSError:
                    webbrowser.open(web)
                    return R(f"Não achei o aplicativo {nome} instalado, então abri a versão na web.")
        for nome, cmd in PROGRAMAS.items():
            if nome in alvo:
                subprocess.Popen(cmd, shell=True)
                return R(f"Abrindo {nome}.")
        busca = re.sub(r"[^\w\s]", " ", alvo)
        app = achar_app(busca)
        if app:
            subprocess.Popen(["explorer.exe", "shell:AppsFolder\\" + app[1]])
            return R(f"Abrindo {app[0]}.")
        atalho = achar_atalho(busca)
        if atalho:
            os.startfile(atalho)
            return R(f"Abrindo {atalho.stem}.")

    if m := re.search(r"(?:curr[ií]culo|carta)[^:]{0,40}vaga:?\s+(.{40,})", t, re.I | re.S):
        return adaptar(m.group(1))
    if re.search(r"(?:carta|adaptar curr[ií]culo)[^:]{0,30}vaga", t, re.I):
        return R("Cole a descrição da vaga logo depois, na mesma mensagem: carta para vaga: <descrição>")
    if m := re.search(r"vagas? (?:de|para|em) (.+)", t, re.I):
        return vagas(m.group(1).strip(" .?"))
    if m := re.search(r"(?:salvar|guardar|cadastrar|definir)\s+(?:a\s+)?(?:minha\s+)?playlist\s+(.+?)\s+(https?://open\.spotify\.com/\S+|spotify:\S+)", t, re.I):
        return salvar_playlist(m.group(1), m.group(2))
    sn = re.sub(r"\s+", " ", re.sub(r"[,;:.!?]", " ", _sem_acento(t))).strip()
    if m := re.search(r"\bconectar\s+(?:o\s+)?spotify\s+([A-Za-z0-9]{20,40})\b", t, re.I):
        spotify_iniciar_login(m.group(1))
        return R("Abri o navegador para você autorizar o Peter no Spotify. Depois de aceitar, é só voltar aqui.")
    if re.search(r"\bajuda spotify\b|\b(?:conectar|configurar)\s+(?:o\s+)?spotify\b|como (?:conectar|configurar) (?:o )?spotify", sn):
        return R("Passo a passo para o play automático.\n" + bloco(AJUDA_SPOTIFY.format(porta=PORTA)))
    if re.search(r"\b(?:minhas|quais)\s+playlists\b", sn):
        nomes = list(playlists_spotify()["playlists"])
        return R("Playlists salvas: " + ", ".join(nomes) + "." if nomes else
                 "Nenhuma playlist salva ainda. Digite: salvar playlist vibe <link da playlist>")
    if (m := re.match(r"^(?:por favor\s+)?(?:toqu\w+|toca\w*|coloqu\w+|coloca\w*)\s+(.+)$", sn)) and \
            not re.search(r"\b(?:no|na|em)\s+(?:spotify|youtube|google|github|stack|wikipedia|linkedin)\b", sn):
        alvo = re.sub(r"^(?:(?:uma|um|a|o|minha)\s+)+", "", m.group(1))
        alvo = re.sub(r"^playlist\s+", "", alvo).strip()
        cfg = playlists_spotify()
        if alvo in ("musica", "musicas", "som", "playlist"):
            alvo = cfg.get("padrao") or "vibe"
            if alvo not in cfg["playlists"]:
                return R(f"Ainda não tenho a playlist {alvo} salva. No Spotify, clique com o botão direito nela, "
                         f"Compartilhar, Copiar link, e digite aqui: salvar playlist {alvo} <link>")
        if alvo in cfg["playlists"]:
            return tocar_spotify(cfg["playlists"][alvo], alvo)
        if re.search(r"\b(?:musica|musicas|som|playlist|spotify)\b", sn):
            salvas = ", ".join(cfg["playlists"]) or "nenhuma"
            return R(f"Não tenho a playlist {alvo} salva. Playlists salvas: {salvas}. Diga: toque música.")

    if m := re.search(r"(?:salvar|guardar|adicionar)\s+(?:a\s+)?vaga\s+(https?://\S+)\s*(.*)", t, re.I):
        fila = ler(FILA)
        fila.append({"link": m.group(1), "titulo": m.group(2).strip() or m.group(1)[:60],
                     "salva": f"{datetime.now():%d/%m %H:%M}"})
        gravar(fila, FILA)
        return R(f"Vaga salva na fila. Total: {len(fila)}.")
    if re.search(r"pr[oó]xima vaga", t, re.I):
        fila = ler(FILA)
        if not fila:
            return R("A fila de vagas está vazia. Salve com: salvar vaga <link> <título>")
        vaga = fila.pop(0)
        gravar(fila, FILA)
        webbrowser.open(vaga["link"])
        return R(f"Abri a vaga {vaga['titulo']}. Faltam {len(fila)} na fila. Você revisa e clica em Candidatar-se.")
    if re.search(r"vagas salvas|fila de vagas", t, re.I):
        fila = ler(FILA)
        return R("A fila de vagas está vazia." if not fila else f"Você tem {len(fila)} vaga{'s' if len(fila) != 1 else ''} na fila.\n" +
                 bloco("\n".join(f"{i}. {v['titulo']}" for i, v in enumerate(fila, 1))))
    if re.search(r"copiar (?:a )?(?:carta|mensagem|texto)", t, re.I):
        if not ESTADO.get("carta"):
            return R("Ainda não preparei nenhum texto. Use: carta para vaga: <descrição da vaga>")
        return R("Texto copiado. É só colar no campo de mensagem da vaga." if copiar(ESTADO["carta"])
                 else "Não consegui copiar para a área de transferência.")

    if re.search(r"(?:adicion|envi|mand|cadastr|candidat)\w*\s+(?:(?:o|meu|minha)\s+)*(?:curr[ií]culo|cv)\b", t, re.I):
        return R("Não consigo enviar candidaturas sozinho: o LinkedIn não permite automação, e você poderia perder a conta. "
                 "O que eu faço: 'vagas de <área>' abre a busca com candidatura simplificada; 'carta para vaga: <descrição>' "
                 "prepara o texto; você clica em Candidatar-se e anexa o PDF.")
    if re.search(r"\b(?:procur|busc|busqu|encontr|mostr)\w*\s+(?:(?:as|minhas|algumas)\s+)*vagas?\b|^\s*vagas?\s*[.!?]?\s*$", t, re.I):
        return vagas(cargo_padrao())
    if m := re.search(r"(file:///\S+?\.pdf|[A-Za-z]:\\[^\"<>|?*\n]+?\.pdf)", t, re.I):
        return ler_pdf(m.group(1))
    if ESTADO.get("vagas") and re.search(r"\b(?:relevantes|melhores|principais)\b", t, re.I):
        return R("Eu não consigo ver o que aparece na página do LinkedIn, então não vou inventar vagas. Os resultados "
                 "reais estão na janela do LinkedIn, que você pode ordenar por relevância. Quando escolher uma vaga, "
                 "diga: carta para vaga, e cole a descrição.")
    if m := re.search(r"registrar candidatura\s+(?:em |na |no |para )?(.+)", t, re.I):
        c = ler(CAND)
        c.append({"vaga": m.group(1), "data": f"{datetime.now():%d/%m/%Y}", "status": "enviada"})
        gravar(c, CAND)
        return R(f"Candidatura registrada: {m.group(1)}. Total: {len(c)}.")
    if re.search(r"minhas candidaturas", t, re.I):
        c = ler(CAND)
        if not c:
            return R("Você ainda não registrou candidaturas.")
        return R(f"Você tem {len(c)} candidaturas registradas.\n" +
                 bloco("\n".join(f"{x['data']} - {x['vaga']} ({x['status']})" for x in c)))
    n = "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")
    n = re.sub(r"\s+", " ", re.sub(r"[,;:]", " ", n))
    palavras = re.findall(r"\w+", n)
    if len(palavras) <= 6:
        musica = bool(re.search(r"\b(?:musica|som|spotify|player|faixa)\b", n)) or len(palavras) <= 2
        if musica and re.search(r"\b(?:paus\w+|continu\w+|retom\w+|play|toca)\b", n) and not re.search(r"\bpausa de\b", n):
            return R("Ok.") if tecla_midia("play") else R("Não consegui enviar a tecla de mídia.")
        if musica and re.search(r"\b(?:proxima|pular|passar|avancar)\b", n):
            return R("Próxima.") if tecla_midia("proxima") else R("Não consegui enviar a tecla de mídia.")
        if musica and re.search(r"\b(?:anterior|voltar)\b", n):
            return R("Anterior.") if tecla_midia("anterior") else R("Não consegui enviar a tecla de mídia.")
        if re.search(r"\b(?:aument\w+|mais|sub\w*)\b.*\bvolume\b|\bvolume\b.*\b(?:mais alto|maior)\b", n):
            return R("Volume aumentado.") if tecla_midia("vol+", 5) else R("Não consegui mexer no volume.")
        if re.search(r"\b(?:diminu\w+|abaix\w+|menos|baix\w+)\b.*\bvolume\b|\bvolume\b.*\b(?:mais baixo|menor)\b", n):
            return R("Volume diminuído.") if tecla_midia("vol-", 5) else R("Não consegui mexer no volume.")
        if re.search(r"\b(?:mudo|silenciar|silencio)\b", n):
            return R("Ok.") if tecla_midia("mudo") else R("Não consegui mexer no volume.")
    if m := re.search(r"\b(pesquis\w+|busc\w+|busqu\w+|procur\w+|toc\w+|toqu\w+|coloc\w+|coloqu\w+)\s+(.+?)\s+(?:no|na|em)\s+(" + "|".join(BUSCAS) + r")\b", n):
        termo = re.sub(r"^(?:a|o|as|os|um|uma|musica|video|sobre)\s+", "", m.group(2)).strip()
        return buscar_em(m.group(3), termo, tocar=m.group(1).startswith(("toc", "toqu", "coloc", "coloqu")))
    if len(palavras) <= 8:
        for nome, url in SITES.items():
            verbo = rf"\b(?:abr(?:ir|a|e)|acess\w+|ir para|va para|me leve para|mostr\w+)\s+(?:(?:o|a|no|na|para|do|da|site|pagina)\s+)*{re.escape(nome)}\b"
            if re.search(verbo, n) or (nome in n and len(palavras) <= len(nome.split()) + 1):
                return abrir_site(nome, url)
        if ESTADO.get("site") and re.search(r"\b(?:abr(?:ir|a|e)|mostr\w+|acess\w+)\b.*\b(?:site|pagina|link)\b", n):
            nome, url = ESTADO["site"]
            return abrir_site(nome, url)
        if re.fullmatch(r"(?:voce (?:pode|consegue) )?abr(?:ir|a|e) (?:o |a )?[\w ]{1,40}[.!?]*", n.strip()):
            return R("Não achei esse aplicativo no menu Iniciar. Também posso abrir: " + ", ".join(list(SITES) + list(PROTOCOLOS) + list(PROGRAMAS)) + ".")
        if ESTADO.get("site") and re.search(r"\b(?:conseguiu|abriu|deu certo|funcionou)\b", n):
            return R(f"Mandei abrir o {ESTADO['site'][0]} no seu navegador padrão. Se não apareceu, olhe a barra de "
                     f"tarefas: a página pode ter aberto atrás da janela do {NOME}.")
    return None


def conversar(d):
    msgs = d.get("mensagens", [])[-8:]
    fontes = []
    if d.get("pesquisar") and msgs and DDGS:
        try:
            res = DDGS().text(msgs[-1]["content"], region="br-pt", max_results=5)
            fontes = [{"titulo": r["title"], "url": r["href"]} for r in res]
            ctx = "\n".join(f"- {r['title']}: {r['body']}" for r in res)
            msgs[-1] = {"role": "user", "content":
                        msgs[-1]["content"] + "\n\nResultados da web:\n" + ctx + "\n\nResuma de forma útil."}
        except Exception:
            fontes = []
    return R(ollama(msgs, MODOS.get(d.get("modo"), MODOS["dev"])), fontes)


def responder(d):
    msgs = d.get("mensagens", [])
    try:
        return (comandos(msgs[-1]["content"]) if msgs else None) or conversar(d)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return R(f"O Ollama está aberto, mas o modelo {MODELO} não está baixado. "
                     f"Rode no PowerShell: ollama pull {MODELO}")
        return R(f"O Ollama respondeu com o erro {e.code}.")
    except urllib.error.URLError:
        return R("Não consegui falar com o Ollama. Verifique se ele está aberto.")
    except Exception as e:
        return R(f"Não consegui concluir: {e}")


# ------------------------------------------------------------------ servidor
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def enviar(self, conteudo, tipo="application/json"):
        corpo = conteudo.encode() if isinstance(conteudo, str) else json.dumps(conteudo, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", tipo + "; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):
        rota = urllib.parse.urlparse(self.path)
        if rota.path == "/callback":
            msg = html.escape(spotify_callback(urllib.parse.parse_qs(rota.query)))
            return self.enviar("<meta charset='utf-8'><body style='font:22px sans-serif;background:#060a1c;color:#fff;"
                               f"padding:40px'><h2>{msg}</h2></body>", "text/html")
        if rota.path == "/api/briefing":
            return self.enviar(montar_briefing())
        if self.path == "/api/tarefas":
            itens, outras = tarefas_do_dia()
            return self.enviar({"hoje": itens, "outras": outras})
        self.enviar(HTML, "text/html")

    def do_POST(self):
        dados = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        if self.path == "/api/chat":
            return self.enviar(responder(dados))
        t = ler()
        if self.path == "/api/tarefas":
            texto_t, dia, hora = interpretar_tarefa(dados["texto"])
            t.append({"texto": texto_t, "feita": False, "data": dia, "hora": hora,
                      "criada": datetime.now().isoformat(timespec="minutes")})
        elif m := re.fullmatch(r"/api/tarefas/(\d+)/alternar", self.path):
            if int(m.group(1)) < len(t):
                t[int(m.group(1))]["feita"] = not t[int(m.group(1))]["feita"]
        gravar(t)
        self.enviar(t)

    def do_DELETE(self):
        t = ler()
        if (m := re.fullmatch(r"/api/tarefas/(\d+)", self.path)) and int(m.group(1)) < len(t):
            t.pop(int(m.group(1)))
            gravar(t)
        self.enviar(t)


def garantir_ollama():
    """Abre o Ollama se não estiver rodando e deixa o modelo carregado na memória."""
    def no_ar():
        try:
            urllib.request.urlopen(OLLAMA, timeout=2)
            return True
        except Exception:
            return False

    if not no_ar():
        print("Ollama fechado, iniciando...")
        iniciado = False
        try:
            subprocess.Popen(["ollama", "serve"], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            iniciado = True
        except OSError:
            app = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama app.exe"
            if app.exists():
                os.startfile(app)
                iniciado = True
        if not iniciado:
            print("Não encontrei o Ollama. Instale em https://ollama.com/download e abra o programa uma vez.")
            return
        for _ in range(30):
            time.sleep(1)
            if no_ar():
                break
        else:
            print("O Ollama não respondeu. Abra o programa Ollama pelo menu Iniciar.")
            return
    print("Ollama pronto. Carregando o modelo na memória...")
    try:
        ollama([{"role": "user", "content": "oi"}], "Responda apenas: ok", tokens=1)
        print(f"Modelo carregado. Pode falar com o {NOME}!")
    except urllib.error.HTTPError:
        print(f"O modelo {MODELO} não está baixado. Rode: ollama pull {MODELO}")
    except Exception as e:
        print(f"Não consegui carregar o modelo: {e}")


def abrir_janela():
    """Abre o Jarvis em janela própria (Edge/Chrome) com microfone e voz liberados."""
    url = f"http://localhost:{PORTA}"
    pf, pf86, local = (os.environ.get(k, "") for k in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"))
    candidatos = [(pf86, "Microsoft/Edge/Application/msedge.exe"), (pf, "Microsoft/Edge/Application/msedge.exe"),
                  (pf, "Google/Chrome/Application/chrome.exe"), (pf86, "Google/Chrome/Application/chrome.exe"),
                  (local, "Google/Chrome/Application/chrome.exe")]
    for base, rel in candidatos:
        exe = Path(base) / rel if base else None
        if exe and exe.exists():
            subprocess.Popen([str(exe), f"--app={url}", "--autoplay-policy=no-user-gesture-required",
                              f"--user-data-dir={PASTA / 'perfil'}", "--no-first-run", "--no-default-browser-check"])
            return
    webbrowser.open(url)


if __name__ == "__main__":
    print(f"JARVIS v2 rodando em http://localhost:{PORTA}  (Ctrl+C para sair)")
    threading.Thread(target=garantir_ollama, daemon=True).start()
    threading.Thread(target=apps_iniciar, daemon=True).start()
    threading.Timer(1.2, abrir_janela).start()
    ThreadingHTTPServer(("127.0.0.1", PORTA), Handler).serve_forever()