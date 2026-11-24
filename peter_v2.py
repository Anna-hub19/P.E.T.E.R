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
import shutil
import socket
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
import zipfile
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
APELIDOS = ["peter", "péter", "pêter", "piter", "pitter", "piiter", "pieter", "pitera", "pitra", "pítera", "píter",
            "piterá", "píter ia", "peter ia", "piti", "pitero", "petero", "pitty"]   # como o reconhecimento de voz costuma escrever o nome
FONETICA = ["piter", "peter"]   # base do reconhecimento aproximado do nome (aceita variações de 1 letra)
NOME_FALA = "Píter"             # como a voz deve pronunciar o nome
VOZES_MASCULINAS = ["antonio", "donato", "humberto", "fabio", "julio", "daniel", "ricardo"]   # português (Edge: "Antonio" é a mais natural)
VOZES_MASCULINAS_EN = ["guy", "andrew", "davis", "jason", "tony", "eric", "brian", "christopher", "david", "mark"]   # modo inglês
VOZES_FEMININAS = "francisca|thalita|maria|luciana|heloisa|vitoria|leila|helena|yara|manuela|brenda|giovanna|fernanda|camila|raquel|elza|valentina|google|zira|jenny|aria|samantha"
FECHAR_OLLAMA = True            # ao fechar o Peter, fecha também o Ollama (ponha False se usa o Ollama em outros programas)
FECHAR_JANELA = True            # ao fechar o Peter, encerra também o Edge do Peter
VOZ_VELOCIDADE = 1.05           # 1 = normal
VOZ_TOM = 1.06                  # um pouco mais agudo = voz mais jovem (use 1 para o tom original)
ESPERA_FALA_MS = 2300           # silêncio (em ms) esperado antes de enviar o que você falou; aumente se ainda cortar frases longas
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
         "chatgpt": "https://chatgpt.com", "google": "https://www.google.com", "whatsapp": "https://web.whatsapp.com/",
         "netflix": "https://www.netflix.com/browse"}
APENAS_SITE = ["whatsapp", "netflix"]   # não tenho o aplicativo: abre sempre o site
ALIAS_SITES = {"whatsapp": ["whats app", "whatsap", "watsapp", "uatsapp", "zap zap", "zapzap", "zap"],
               "youtube": ["you tube"], "linkedin": ["linked in"], "github": ["git hub"], "chatgpt": ["chat gpt"],
               "stack overflow": ["stackoverflow"], "netflix": ["netflis"]}
PROGRAMAS = {"vs code": "code", "vscode": "code", "visual studio code": "code", "terminal": "start powershell",
             "bloco de notas": "notepad", "calculadora": "calc", "explorador": "explorer", "chrome": "start chrome",
             "pomodoro": r'start "" "C:\Users\Usuario\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\apps do Chrome\Pomodoro timer.lnk"'}
PROTOCOLOS = {"spotify": ("spotify:", "https://open.spotify.com"),
              "discord": ("discord:", "https://discord.com/app")}

BASE = (f"Você é o {NOME}, assistente pessoal de uma desenvolvedora júnior full stack. "
        "Responda sempre em português do Brasil, de forma curta e direta, como numa conversa falada "
        "(no máximo 4 frases). Quando mostrar código, use blocos ``` e explique em 1 ou 2 frases. "
        "Você roda dentro de um programa que executa comandos como: abrir github, abrir linkedin, abrir vs code, "
        "vagas de <área>, anote tarefa <texto>. Se o usuário pedir algo assim, diga o comando "
        "exato a usar; nunca diga que não consegue abrir sites ou programas. "
        "Você não acessa internet, arquivos nem PDFs por conta própria: nunca invente vagas, empresas, salários, "
        "links ou ações que diga ter feito; se não souber, diga que não sabe. Quem marca tarefas, anota ou abre coisas é só o programa, "
        "que confirma com mensagens curtas: nunca diga que concluiu, marcou ou anotou algo.")
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

_args = sys.argv[1:]
HORA_TESTE = None          # python jarvis_v2.py --hora 8   (simula 8h da manhã para testar o briefing)
if "--hora" in _args:
    _i = _args.index("--hora")
    HORA_TESTE = int(_args[_i + 1]) % 24
    del _args[_i:_i + 2]
origem = Path(_args[0] if _args else "peterApp.py")
HTML = re.search(r'HTML = r"""(.*?)"""', origem.read_text("utf-8"), re.S).group(1)

# ------------------------------------------------------------------ ajustes da interface
# 1) voz mais natural (prefere vozes "Natural" do Edge, como Francisca e Antonio)
VOZ_ANTIGA = 'const v=speechSynthesis.getVoices().find(v=>v.lang.startsWith("pt-BR"));if(v)u.voice=v;'
VOZ_NOVA = ('const v=escolherVoz();if(window.__lang==="en")u.lang="en-US";if(v){u.voice=v;u.lang=v.lang}u.rate=VOZ_VEL;u.pitch=VOZ_TOM;')
HTML = HTML.replace(VOZ_ANTIGA, VOZ_NOVA)
# corrige o comando "abrir ..." da interface (a versão antiga não reconhecia "abrir")
HTML = HTML.replace('abr[ae]r? (?:o |a )?(.+)', 'abr(?:ir|a|e) (?:o |a )?(.+)')
# o navegador bloqueia window.open quando o comando vem da voz; quem abre os sites é o servidor
HTML = HTML.replace('if(k){window.open(SITES[k],"_blank");return resp("Abrindo "+k+".")}', '')

# o botão da esfera também espera mais tempo de silêncio antes de enviar
HTML = HTML.replace('rec=new SR();rec.lang="pt-BR";rec.interimResults=true;let final="";',
                    'rec=new SR();rec.lang=window.__lang==="en"?"en-US":"pt-BR";rec.interimResults=true;rec.continuous=true;let final="";')
HTML = HTML.replace('rec.onstart=()=>{ouvindo=true;set("ouvindo","Ouvindo...")};',
                    'rec.onstart=()=>{ouvindo=true;set("ouvindo","Ouvindo...");clearTimeout(window.__sil);window.__sil=setTimeout(()=>{try{rec.stop()}catch(x){}},9000)};')
HTML = HTML.replace('rec.onresult=e=>{final="";', 'rec.onresult=e=>{clearTimeout(window.__sil);window.__sil=setTimeout(()=>{try{rec.stop()}catch(x){}},ESPERA);final="";')
# o chat passa a vir em partes (o Peter fala frase por frase enquanto o modelo escreve)
HTML = re.sub(r'await\(await fetch\("/api/chat",\{method:"POST".*?\.json\(\)', 'await chatStream({mensagens:hist,modo,pesquisar:usaWeb})', HTML, flags=re.S)

# 2) ativação por voz: diga "PETER" (sem apertar o botão)
ESCUTA_JS = r"""
/* ===== ativação por voz: diga "PETER" ===== */
let escuta=false,aguardando=false,pausa=false,recW=null;
const ATIVA=/\b(__ATIVA__)\b/i;
function bip(){try{const c=new AudioContext(),o=c.createOscillator(),g=c.createGain();o.frequency.value=880;g.gain.value=.08;o.connect(g);g.connect(c.destination);o.start();o.stop(c.currentTime+.12)}catch(e){}}
function retomar(){if(escuta&&!pausa&&recW){try{recW.start()}catch(e){}}}
function pausar(){pausa=true;if(recW){try{recW.stop()}catch(e){}}}
const VOZ_M=__VOZ_M__,VOZ_M_EN=__VOZ_M_EN__,VOZ_F=/__VOZ_F__/i,VOZ_VEL=__VOZ_VEL__,VOZ_TOM=__VOZ_TOM__;
function vozesLingua(){const L=window.__lang==="en"?"en":"pt";return speechSynthesis.getVoices().filter(v=>v.lang.startsWith(L))}
function vozesMasc(){const vs=vozesLingua(),pref=window.__lang==="en"?VOZ_M_EN:VOZ_M,out=[];
 for(const n of pref)vs.filter(v=>norm(v.name).includes(n)&&!out.includes(v)).forEach(v=>out.push(v));
 vs.filter(v=>!VOZ_F.test(norm(v.name))&&!out.includes(v)).sort((a,b)=>(b.lang==="pt-BR"||b.lang==="en-US")-(a.lang==="pt-BR"||a.lang==="en-US")).forEach(v=>out.push(v));
 return out}
let vozFixa={},vozesOk=false;
function escolherVoz(){const L=window.__lang==="en"?"en":"pt",ms=vozesMasc();let salvo=null;try{salvo=localStorage.getItem("peterVoz_"+L)}catch(e){}
 let v=ms.find(x=>x.name===(salvo||vozFixa[L]));
 if(!v){v=ms[0]||vozesLingua()[0]||null;if(v)vozFixa[L]=v.name}
 return v}
function vozesProntas(){return new Promise(res=>{if(vozesOk)return res();let ok=false;
 const f=()=>{if(!ok){ok=true;vozesOk=true;res()}};speechSynthesis.addEventListener("voiceschanged",f,{once:true});
 setTimeout(f,speechSynthesis.getVoices().length?900:2500)})}
function falarLongo(txt){const s=txt.replace(/```[\s\S]*?```/g," O código está na tela. ").replace(/[*#`_>]/g,"").trim();if(!s){set();return}
 try{speechSynthesis.cancel()}catch(e){}
 const partes=s.match(/[^.!?…\n]+[.!?…]*\s*/g)||[s],grupos=[];let atual="";
 for(const p of partes){if((atual+p).length>220&&atual){grupos.push(atual);atual=p}else atual+=p}
 if(atual.trim())grupos.push(atual);
 window.__streamFim=true;_set("falando","Falando...");grupos.forEach(g=>falarParte(g))}
vozesProntas().then(()=>{const pref=window.__lang==="en"?VOZ_M_EN:VOZ_M;
 if(!vozesLingua().some(v=>pref.some(n=>norm(v.name).includes(n))))
  setTimeout(()=>bolha("Não encontrei uma voz masculina em português neste navegador. Abra o Peter no Microsoft Edge (voz Antonio) ou instale uma voz masculina em Configurações > Hora e idioma > Fala.","j"),2500)});
const FON=__FONETICA__;
function lev(a,b){const d=[];for(let i=0;i<=a.length;i++)d[i]=[i];for(let j=1;j<=b.length;j++)d[0][j]=j;
 for(let i=1;i<=a.length;i++)for(let j=1;j<=b.length;j++)d[i][j]=Math.min(d[i-1][j]+1,d[i][j-1]+1,d[i-1][j-1]+(a[i-1]===b[j-1]?0:1));
 return d[a.length][b.length]}
const letras=w=>norm(w).replace(/[^a-z]/g,"");
function parecido(w){return w.length>=4&&w.length<=8&&w[0]==="p"&&FON.some(f=>lev(w,f)<=1)}
function achaNome(t){
 const ps=t.split(/\s+/).filter(Boolean),ns=ps.map(letras);
 for(let i=0;i<ps.length;i++){
  if(parecido(ns[i]))return{fim:i+1};
  if(i+1<ps.length&&ns[i][0]==="p"&&parecido(ns[i]+ns[i+1]))return{fim:i+2}}
 const m=t.match(ATIVA);return m?{resto:t.slice(m.index+m[0].length)}:null}
function textoApos(a,r){return r.resto!==undefined?r.resto:a.split(/\s+/).filter(Boolean).slice(r.fim).join(" ")}
const ESPERA=__ESPERA__;
let coletando=false,buf="",bufT=null,janelaT=null,ditado=false;
function enviarBuf(){coletando=false;const t=buf.trim();buf="";if(t.length>2)enviar(t);else set()}
function iniciarColeta(t){buf=t;coletando=true;set("ouvindo","Ouvindo...");clearTimeout(bufT);bufT=setTimeout(enviarBuf,ESPERA)}
function abrirJanela(){if(!escuta||!window.__conversa)return;window.__conversa=false;aguardando=true;set("ouvindo","Pode continuar falando...");
 clearTimeout(janelaT);janelaT=setTimeout(()=>{if(aguardando&&!coletando){aguardando=false;set()}},8000)}
function criarEscuta(){
 recW=new SR();recW.lang=window.__lang==="en"?"en-US":"pt-BR";recW.continuous=true;recW.interimResults=true;recW.maxAlternatives=5;
 recW.onresult=e=>{
  if(coletando){clearTimeout(bufT);bufT=setTimeout(enviarBuf,ESPERA)}
  for(let i=e.resultIndex;i<e.results.length;i++){
  if(!e.results[i].isFinal)continue;
  const alts=[];for(let j=0;j<e.results[i].length;j++)alts.push(e.results[i][j].transcript.trim());
  const t=alts[0];if(!t)continue;
  if(ditado){if(/\b(?:parar|encerrar|fim d[oe]) (?:o )?(?:modo )?ditado\b/.test(norm(t))){ditado=false;$("#estado").textContent="Ditado desligado";bolha("Modo ditado desligado.","j")}
   else fetch("/api/ditar",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({texto:t})});continue}
  if(coletando){buf+=" "+t;continue}
  if(aguardando){aguardando=false;clearTimeout(janelaT);iniciarColeta(t);continue}
  let resto=null;
  for(const a of alts){const r=achaNome(a);if(r){resto=textoApos(a,r);break}}
  if(resto===null){clearTimeout(window.__ouvT);$("#estado").textContent="Ouvi: “"+t.slice(0,38)+"”";
   window.__ouvT=setTimeout(()=>{if(escuta&&!aguardando&&!coletando)$("#estado").textContent="Diga “__NOME__”..."},4000);continue}
  resto=resto.replace(/^[\s,.:;!?-]+/,"").replace(/^(?:ia|i a)\b[\s,.:;!?-]*/i,"");
  bip();
  if(resto.length>2){iniciarColeta(resto)}
  else{aguardando=true;set("ouvindo","Pois não? Pode falar...");clearTimeout(janelaT);
   janelaT=setTimeout(()=>{if(aguardando&&!coletando){aguardando=false;set()}},8000)}}};
 recW.onend=()=>{if(escuta&&!pausa)setTimeout(retomar,300)};
 recW.onerror=e=>{if(e.error==="not-allowed"||e.error==="service-not-allowed"){escuta=false;atualizar();
  bolha("Preciso da permissão do microfone. Clique no cadeado ao lado do endereço e permita o microfone.","j")}};
}
function atualizar(){const b=$("#escuta");b.classList.toggle("on",escuta);
 b.textContent=escuta?"🎙️ Ouvindo “__NOME__”":"🎙️ Ativar “__NOME__”";if(!escuta)set()}
const _set=set,_falar=falar,_ouvir=ouvir;
set=function(e,t){_set(e,t);
 if(!e){if(pausa){pausa=false;setTimeout(retomar,400);setTimeout(abrirJanela,450)}
  if(escuta&&!aguardando&&!coletando)$("#estado").textContent="Diga “__NOME__”..."}};
falar=function(t){if(window.__mudo){set();return}if(escuta)pausar();vozesProntas().then(()=>{const x=(t||"").replace(/\bpeter\b/gi,"__NOME_FALA__");if(x.replace(/```[\s\S]*?```/g,"").length>260)falarLongo(x);else _falar(x)})};
ouvir=function(){if(escuta)pausar();_ouvir()};
(function(){
 const b=document.createElement("button");b.className="chip";b.id="escuta";
 document.querySelector(".modos").prepend(b);
 b.onclick=()=>{
  if(!SR){bolha("Seu navegador não suporta voz. Use Chrome ou Edge.","j");return}
  escuta=!escuta;
  if(escuta){pausa=false;criarEscuta();(window.__auto?retomar():falar("Estou ouvindo. É só dizer __NOME__."))}
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
const _resp=resp;resp=function(t,f){if(window.__jaMostrado){window.__jaMostrado=false;carregar();return}window.__conversa=true;_resp(t,f);carregar()};
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
  '<div class="brief-i"><b>'+esc(i.titulo)+'</b>'+((i.noticias&&i.noticias.length)?i.noticias.map(n=>
   '<div class="nb">'+(n.link?'<a href="'+n.link.replace(/"/g,"&quot;")+'" target="_blank" rel="noopener">'+esc(n.titulo)+'</a>':'<span class="nt">'+esc(n.titulo)+'</span>')+
   (n.resumo?'<p>'+esc(n.resumo)+'</p>':"")+(n.fonte?'<small>'+esc(n.fonte)+'</small>':"")+'</div>').join(""):
  ((i.lista&&i.lista.length)?'<ul>'+i.lista.map(x=>'<li>'+esc(x)+'</li>').join("")+'</ul>':(i.texto?'<p>'+esc(i.texto)+'</p>':"")))+'</div>').join("");
 $("#msgs").append(d);$("#msgs").scrollTop=1e9}
async function briefing(){
 try{set("pensando","Preparando seu briefing...");
  const b=await(await fetch("/api/briefing")).json();set();
  mostrarBriefing(b);falar(b.fala)}catch(e){set()}}
setTimeout(briefing,2200);
/* ----- ações vindas do servidor (idioma, privacidade, ditado) ----- */
function aplicarUI(ui){if(!ui)return;
 if(ui.lang){window.__lang=ui.lang;if(recW)recW.lang=ui.lang==="en"?"en-US":"pt-BR"}
 if("privacidade" in ui){window.__mudo=ui.privacidade;document.body.classList.toggle("priv",ui.privacidade)}
 if(ui.voz==="listar"){bolha("Vozes ("+(window.__lang==="en"?"inglês":"português")+"): "+vozesLingua().map(v=>v.name).join(", ")+". Em uso: "+((escolherVoz()||{}).name||"padrão"),"j")}
 if(ui.voz==="trocar"){const ms=vozesMasc();if(ms.length<2)bolha("Só encontrei uma voz masculina neste navegador.","j");
  else{const L=window.__lang==="en"?"en":"pt",prox=ms[(ms.indexOf(escolherVoz())+1)%ms.length];try{localStorage.setItem("peterVoz_"+L,prox.name)}catch(e){}vozFixa[L]=prox.name;bolha("Nova voz: "+prox.name,"j")}}
 if("ditado" in ui){ditado=ui.ditado;$("#estado").textContent=ui.ditado?"✍️ Ditado ligado":"Ditado desligado"}}
fetch("/api/prefs").then(r=>r.json()).then(p=>aplicarUI({privacidade:p.privacidade,lang:p.ingles?"en":"pt"})).catch(()=>{});
/* ----- resposta em partes: o Peter começa a falar enquanto o modelo ainda escreve ----- */
function vozAtual(){return escolherVoz()}
function falarParte(txt){
 const s=txt.replace(/```[\s\S]*?```/g," O código está na tela. ").replace(/[*#`_>]/g,"").replace(/\bpeter\b/gi,"__NOME_FALA__").trim();
 if(!s||window.__mudo)return;
 const u=new SpeechSynthesisUtterance(s);u.lang=window.__lang==="en"?"en-US":"pt-BR";const v=vozAtual();if(v){u.voice=v;u.lang=v.lang}u.rate=VOZ_VEL;u.pitch=VOZ_TOM;
 u.onend=u.onerror=()=>{if(window.__streamFim&&!speechSynthesis.speaking&&!speechSynthesis.pending)set()};
 speechSynthesis.speak(u)}
async function chatStream(corpo){
 corpo.stream=true;
 const r0=await fetch("/api/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(corpo)});
 if(!(r0.headers.get("content-type")||"").includes("ndjson")){const r=await r0.json();aplicarUI(r.ui);return r}
 const rd=r0.body.getReader(),dec=new TextDecoder();
 let b="",texto="",el=null,falado=0,final=null;window.__streamFim=false;
 if(escuta)pausar();try{speechSynthesis.cancel()}catch(e){}
 const falarPendente=fim=>{
  const resto=texto.slice(falado);
  if((texto.match(/```/g)||[]).length%2)return;
  let corte=-1;
  if(fim)corte=resto.length;else{const ms=[...resto.matchAll(/[.!?…](?=\s)|\n/g)];if(ms.length)corte=ms[ms.length-1].index+1}
  if(corte>0&&resto.slice(0,corte).trim()){if(falado===0)_set("falando","Falando...");falarParte(resto.slice(0,corte));falado+=corte}};
 for(;;){const{done,value}=await rd.read();if(done)break;
  b+=dec.decode(value,{stream:true});let i;
  while((i=b.indexOf("\n"))>=0){const ln=b.slice(0,i);b=b.slice(i+1);if(!ln.trim())continue;
   const o=JSON.parse(ln);
   if(o.t){texto+=o.t;if(!el)el=bolha("","j");el.innerHTML=fmt(texto);$("#msgs").scrollTop=1e9;falarPendente(false)}
   if(o.fim)final=o}}
 window.__streamFim=true;
 if(final){if(!texto){texto=final.resposta;el=bolha(texto,"j")}
  falarPendente(true);
  if(el&&final.fontes&&final.fontes.length)el.innerHTML=fmt(texto)+final.fontes.map(f=>'<a href="'+f.url+'" target="_blank">🔗 '+esc(f.titulo)+"</a>").join("")}
 ultimaFala=texto;window.__jaMostrado=true;window.__conversa=true;
 if(!speechSynthesis.speaking&&!speechSynthesis.pending)set();
 return{resposta:texto,fontes:(final&&final.fontes)||[]}}
/* ----- avisos do servidor (lembretes, bateria, chuva, pausas...) e atalho global ----- */
const filaAvisos=[];
async function pollAvisos(){
 try{(await(await fetch("/api/avisos")).json()).forEach(x=>filaAvisos.push(x))}catch(e){}
 if(filaAvisos.length&&!speechSynthesis.speaking&&!coletando){const x=filaAvisos.shift();
  if(x.acao==="ouvir"){ouvir();return}
  if(x.texto){bolha("🔔 "+x.texto,"j");if(!window.__mudo){window.__conversa=false;falar(x.texto)}
   try{if(Notification.permission==="granted")new Notification("Peter",{body:window.__mudo?"Você tem um aviso.":x.texto})}catch(e){}}}}
setInterval(pollAvisos,3000);try{Notification.requestPermission()}catch(e){}
/* ----- sinal de vida (o servidor fecha tudo quando a janela some) e links no Chrome ----- */
const pingar=()=>fetch("/api/ping",{method:"POST"}).catch(()=>{});pingar();setInterval(pingar,4000);
window.addEventListener("pagehide",()=>{try{navigator.sendBeacon("/api/fechar")}catch(e){}});
document.addEventListener("click",e=>{const a=e.target.closest&&e.target.closest("a[href^='http']");
 if(a){e.preventDefault();fetch("/api/abrir",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({url:a.href})}).catch(()=>{})}});
/* ----- painéis do sistema e do projeto, ondas na esfera ----- */
(function(){
 const aside=document.querySelector("aside");
 const c1=document.createElement("div");c1.className="card";c1.innerHTML='<h2>Sistema</h2><div id="sis"></div>';aside.append(c1);
 const c2=document.createElement("div");c2.className="card";c2.style.display="none";c2.innerHTML='<h2>Projeto</h2><div id="proj"></div>';aside.append(c2);
 const barra=(n,v,u)=>'<div class="sb"><span>'+n+'</span><div class="bar"><i style="width:'+Math.min(100,v||0)+'%"></i></div><em>'+(v==null?"–":v+u)+'</em></div>';
 async function sis(){try{const e=await(await fetch("/api/sistema")).json();
  $("#sis").innerHTML=barra("CPU",e.cpu,"%")+barra("RAM",e.mem,"%")+barra("DISCO",e.disco,"%")+(e.bateria!=null?barra("BAT",e.bateria,"%"):"")+
   '<div class="sb2">Rede: '+(e.rede!=null?e.rede+" ms":"sem resposta")+" · livre: "+e.disco_livre+" GB</div>"}catch(x){}}
 async function proj(){try{const p=await(await fetch("/api/projeto")).json();c2.style.display=p.ativo?"":"none";if(!p.ativo)return;
  $("#proj").innerHTML='<div class="sb2"><b>'+esc(p.nome)+"</b> · "+esc(p.branch||"sem git")+'</div><div class="sb2">'+p.alterados.length+" alterado(s) · "+p.todos+" TODO</div>"+
   p.alterados.map(a=>'<div class="sb3">'+esc(a)+"</div>").join("")}catch(x){}}
 sis();proj();setInterval(sis,5000);setInterval(proj,30000);
 $("#orb").insertAdjacentHTML("beforeend",'<i class="w"></i><i class="w w2"></i>');
})();
function cenaClima(c){
 const gotas=k=>Array.from({length:k},(_,i)=>'<i class="gota" style="left:'+(14+i*11)+'px;animation-delay:-'+(i*0.17).toFixed(2)+'s"></i>').join("");
 const astro=c.noite?'<i class="lua"></i><i class="estrela" style="left:8px;top:10px"></i><i class="estrela" style="left:78px;top:18px;animation-delay:-1s"></i><i class="estrela" style="left:70px;top:6px;animation-delay:-.5s"></i>':'<i class="sol"></i>';
 switch(c.tipo){
  case"sol":return astro;
  case"parcial":return astro+'<i class="nuvem" style="left:26px;top:36px"></i>';
  case"nublado":return'<i class="nuvem" style="left:8px;top:20px"></i><i class="nuvem escura" style="left:30px;top:38px;animation-delay:-2s"></i>';
  case"chuva":return'<i class="nuvem escura" style="left:20px;top:14px"></i>'+gotas(7);
  case"trovoada":return'<i class="nuvem escura" style="left:20px;top:10px"></i><i class="raio"></i>'+gotas(4);
  case"neblina":return[10,26,42,58].map((t,i)=>'<i class="neb" style="top:'+t+'px;animation-delay:-'+i+'s"></i>').join("");
  default:return astro}}
function htmlClima(c){return'<div class="clima"><div class="cena">'+cenaClima(c)+'</div><div class="txt"><b>'+c.temp+'°</b><div>'+esc(c.desc)+" · "+esc(c.cidade)+
 '</div><div>máx '+c.max+"° · mín "+c.min+"° · chuva "+c.chuva+"%</div></div></div>"}
function htmlProd(p){const max=Math.max(1,...p.dias.map(d=>d.tarefas));
 return'<div class="grafico">'+p.dias.map((d,i)=>'<div class="col'+(i===6?" hoje":"")+'" title="'+d.data+': '+d.tarefas+' tarefa(s), '+d.habitos+' hábito(s), '+d.estudo+' estudo(s)"><em>'+d.tarefas+
  '</em><div class="barra"><i style="height:'+Math.round(d.tarefas/max*100)+'%"></i></div><span>'+d.rotulo+"</span></div>").join("")+"</div>"+
  '<div class="sb2">Hoje: '+p.hoje+" · semana: "+p.total+" tarefas</div><div class=\"sb2\">Hábitos: "+p.habitos+" · estudo: "+p.estudo+" (7 dias)</div>"}
(function(){
 const aside=document.querySelector("aside"),primeiro=aside.children[0];
 const cc=document.createElement("div");cc.className="card";cc.style.display="none";cc.innerHTML='<h2>Clima</h2><div id="clima"></div>';
 const cp=document.createElement("div");cp.className="card";cp.innerHTML='<h2>Produtividade</h2><div id="prod"></div>';
 primeiro.after(cc);cc.after(cp);
 async function clima(){try{const c=await(await fetch("/api/clima")).json();if(c.tipo){cc.style.display="";$("#clima").innerHTML=htmlClima(c)}}catch(x){}}
 async function prod(){try{$("#prod").innerHTML=htmlProd(await(await fetch("/api/produtividade")).json())}catch(x){}}
 const _c=carregar;carregar=async function(){await _c();prod()};
 clima();prod();setInterval(clima,600000);setInterval(prod,60000);
})();
carregar();
"""
ESCUTA_JS = (ESCUTA_JS.replace("__ATIVA__", "|".join(sorted(APELIDOS, key=len, reverse=True))).replace("__NOME__", NOME)
             .replace("__FONETICA__", json.dumps(FONETICA)).replace("__NOME_FALA__", NOME_FALA).replace("__ESPERA__", str(ESPERA_FALA_MS)).replace("__VOZ_M_EN__", json.dumps(VOZES_MASCULINAS_EN))
             .replace("__VOZ_M__", json.dumps(VOZES_MASCULINAS)).replace("__VOZ_F__", VOZES_FEMININAS)
             .replace("__VOZ_VEL__", str(VOZ_VELOCIDADE)).replace("__VOZ_TOM__", str(VOZ_TOM)))
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
aside{overflow-y:auto}
.clima{display:flex;align-items:center;gap:14px}.clima .txt b{font-size:30px;font-weight:300;color:var(--txt)}
.clima .txt div{font-size:12px;color:var(--mudo);margin-top:2px}
.cena{position:relative;width:96px;height:80px;flex:none;overflow:hidden}.cena i{display:block;position:absolute}
.sol{left:24px;top:12px;width:44px;height:44px;border-radius:50%;background:radial-gradient(circle,#fff6b0,#ffc83d);box-shadow:0 0 24px #ffc83d;animation:pulsar 3s ease-in-out infinite}
.sol::before{content:"";position:absolute;inset:-12px;border-radius:50%;border:3px dotted #ffc83d99;animation:gira 14s linear infinite}
.lua{left:30px;top:12px;width:36px;height:36px;border-radius:50%;box-shadow:inset -11px -4px 0 0 #dfe8ff;animation:pulsar 4s ease-in-out infinite}
.estrela{width:2px;height:2px;border-radius:50%;background:#fff;animation:piscar 2s infinite}
.nuvem{width:56px;height:20px;border-radius:20px;background:#cfd8e8;animation:deriva 6s ease-in-out infinite alternate}
.nuvem::before,.nuvem::after{content:"";position:absolute;background:inherit;border-radius:50%}
.nuvem::before{width:26px;height:26px;left:8px;top:-13px}.nuvem::after{width:20px;height:20px;left:28px;top:-9px}
.nuvem.escura{background:#8793ab}
.gota{top:36px;width:2px;height:10px;border-radius:2px;background:#7cc4ff;animation:cair .9s linear infinite}
.raio{left:38px;top:34px;width:18px;height:30px;background:#ffe45c;clip-path:polygon(50% 0,100% 0,60% 45%,95% 45%,20% 100%,40% 55%,5% 55%);animation:relampago 2.6s infinite}
.neb{left:6px;height:5px;width:78%;border-radius:3px;background:#c8d4e6aa;animation:deriva 5s ease-in-out infinite alternate}
@keyframes deriva{from{transform:translateX(-7px)}to{transform:translateX(9px)}}
@keyframes cair{from{transform:translateY(0);opacity:.9}to{transform:translateY(34px);opacity:0}}
@keyframes relampago{0%,84%,100%{opacity:0}86%,92%{opacity:1}89%{opacity:.25}}
@keyframes pulsar{50%{transform:scale(1.08)}}
@keyframes piscar{50%{opacity:.15}}
.grafico{display:flex;align-items:flex-end;gap:8px;height:92px;margin:2px 0 6px}
.grafico .col{flex:1;display:flex;flex-direction:column;align-items:center;gap:3px;height:100%;justify-content:flex-end}
.grafico .barra{width:100%;flex:1;display:flex;align-items:flex-end;background:#ffffff0d;border-radius:3px;overflow:hidden}
.grafico .barra i{display:block;width:100%;min-height:2px;background:linear-gradient(var(--rubro),var(--azulesc));border-radius:3px 3px 0 0;transition:height .6s}
.grafico .col.hoje .barra{outline:1px solid var(--rubro)}
.grafico em{font-style:normal;font-size:11px;color:var(--txt)}.grafico span{font-size:10px;color:var(--mudo);text-transform:uppercase;letter-spacing:.08em}
.sb{display:flex;align-items:center;gap:8px;margin:5px 0;font-size:11px;letter-spacing:.12em}
.sb span{width:46px;color:var(--mudo)}.sb em{width:46px;text-align:right;font-style:normal;color:var(--txt)}
.bar{flex:1;height:6px;background:#ffffff14;border-radius:3px;overflow:hidden}.bar i{display:block;height:100%;background:var(--rubro);transition:width .6s}
.sb2{font-size:12px;color:var(--mudo);margin:4px 0}.sb3{font:11px Consolas,monospace;color:var(--txt);opacity:.85}
.orb .w{position:absolute;inset:0;border-radius:50%;border:2px solid var(--ondac,#4d8dff);opacity:0;pointer-events:none}
.orb.ouvindo .w,.orb.falando .w{animation:onda2 1.6s ease-out infinite}.orb .w2{animation-delay:.8s}
.orb.ouvindo{--ondac:#00ff9d}.orb.falando{--ondac:#b388ff}
@keyframes onda2{0%{transform:scale(1);opacity:.7}100%{transform:scale(1.9);opacity:0}}
body.priv .t span,body.priv .m,body.priv .brief,body.priv #proj,body.priv #relogio span{filter:blur(7px)}
.nb{margin:8px 0;padding:9px 12px;border-left:3px solid var(--rubro);background:#ffffff09}
.nb a,.nb .nt{color:var(--azul);font-weight:600;text-decoration:none}.nb a:hover{text-decoration:underline}
.nb p{margin:4px 0 2px;font-size:14px}.nb small{color:var(--mudo);font-size:11px;letter-spacing:.06em}
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
def R(texto, fontes=None, ui=None):
    r = {"resposta": texto, "fontes": fontes or []}
    if ui:
        r["ui"] = ui
    return r


def achar_chrome():
    for base in (os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", ""), os.environ.get("LOCALAPPDATA", "")):
        if base and (c := Path(base) / "Google/Chrome/Application/chrome.exe").exists():
            return str(c)
    return None


def abrir_url(url):
    """Abre um link no Chrome (ou no navegador padrão, se o Chrome não estiver instalado)."""
    if chrome := achar_chrome():
        try:
            subprocess.Popen([chrome, url])
            return True
        except OSError:
            pass
    return webbrowser.open(url)


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


def ollama(msgs, system, tokens=350, ctx=4096, espera=300, temperatura=None):
    opcoes = {"num_ctx": ctx, "num_predict": tokens}
    if temperatura is not None:
        opcoes["temperature"] = temperatura
    corpo = json.dumps({"model": MODELO, "stream": False, "think": False, "keep_alive": "30m", "options": opcoes,
                        "messages": [{"role": "system", "content": system}] + msgs}).encode()
    req = urllib.request.Request(f"{OLLAMA}/api/chat", corpo, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=espera) as r:
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
    abrir_url(BUSCAS[site] + urllib.parse.quote(termo))
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
    abrir_url("https://accounts.spotify.com/authorize?" + urllib.parse.urlencode({
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


def protocolo_instalado(proto):
    """True se existe um aplicativo registrado para o protocolo (spotify:, discord:...). Evita a janela 'obter um app'."""
    try:
        import winreg
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, proto.rstrip(":")))
        return True
    except ImportError:
        return True
    except OSError:
        return False


def tocar_spotify(item, nome):
    """Abre o Spotify (se estiver fechado) e toca a playlist. Diz a verdade sobre o resultado."""
    if not protocolo_instalado("spotify:"):
        abrir_url(item["web"])
        return R("Não achei o aplicativo do Spotify instalado, então abri a playlist na web. É só clicar em play.")
    try:
        if not spotify_rodando():
            os.startfile("spotify:")
            for _ in range(24):
                time.sleep(0.5)
                if spotify_rodando():
                    break
            time.sleep(2)
    except OSError:
        abrir_url(item["web"])
        return R("Não achei o aplicativo do Spotify instalado, então abri a playlist na web. É só clicar em play.")
    resultado = spotify_api_tocar(item["uri"])
    if resultado and resultado[0]:
        return R(f"Tocando a playlist {nome} no Spotify.")
    try:
        os.startfile(item["uri"])
    except OSError:
        abrir_url(item["web"])
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


def hora_atual():
    return HORA_TESTE if HORA_TESTE is not None else datetime.now().hour


def periodo_do_dia(hora=None):
    hora = hora_atual() if hora is None else hora
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


def _resumo_curto(desc, titulo, limite=230):
    """Resumo de uma notícia a partir do trecho do próprio feed (sem inventar nada)."""
    t = re.sub(r"<[^>]+>", " ", html.unescape(desc or ""))
    t = re.sub(r"\s+", " ", html.unescape(t)).strip()
    t = re.sub(r"\s*(?:The post .*? appeared first on .*|O post .*? apareceu primeiro (?:em|no|na) .*)$", "", t, flags=re.I)
    t = re.sub(r"\s*(?:Leia mais|Saiba mais|Continue lendo|Read more)\b.*$", "", t, flags=re.I).strip()
    if len(t) < 25 or _sem_acento(t)[:40] == _sem_acento(titulo)[:40]:
        return ""
    if len(t) > limite:
        corte = t.rfind(". ", 0, limite)
        t = t[:corte + 1] if corte > 60 else t[:limite].rsplit(" ", 1)[0] + "…"
    return t


def noticias_itens(categoria, n=3):
    """Notícias do primeiro feed RSS que responder: título, link, resumo curto e fonte."""
    for url in FEEDS[categoria]:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 Peter"})
            with urllib.request.urlopen(req, timeout=8) as r:
                raiz = ET.fromstring(r.read())
            itens = []
            for i in raiz.iter("item"):
                titulo = html.unescape((i.findtext("title") or "").strip())
                if not titulo:
                    continue
                link = (i.findtext("link") or "").strip()
                link = link if link.startswith(("http://", "https://")) else ""
                itens.append({"titulo": titulo, "link": link, "resumo": _resumo_curto(i.findtext("description"), titulo),
                              "fonte": urllib.parse.urlparse(link).netloc.replace("www.", "")})
            if itens:
                return itens[:n]
        except Exception:
            continue
    return []


def manchetes(categoria, n=3):
    return [i["titulo"] for i in noticias_itens(categoria, n)]


def tarefas_pendentes_hoje():
    itens, _ = tarefas_do_dia()
    return [(f"{x['hora']} " if x.get("hora") else "") + x["texto"] for x in itens if not x["feita"]]


def montar_briefing(forcar=False):
    agora = datetime.now()
    p, hoje = periodo_do_dia(), f"{agora:%Y-%m-%d}"
    ja_deu = HORA_TESTE is None and BRIEF_ARQ.exists() and json.loads(BRIEF_ARQ.read_text("utf-8")).get("data") == hoje
    completo = forcar or (p == "manha" and not ja_deu)
    itens = [{"titulo": {"manha": "Bom dia", "tarde": "Boa tarde", "noite": "Boa noite"}[p],
              "texto": saudacao(p, hora_atual()), "fala": saudacao(p, hora_atual())}]
    if completo:
        with ThreadPoolExecutor(4) as ex:
            f_t, f_m, f_x = ex.submit(previsao), ex.submit(noticias_itens, "mundo"), ex.submit(noticias_itens, "tecnologia")
            f_v = ex.submit(radar_vagas)
            tempo, mundo, tech, vagas_novas = f_t.result(), f_m.result(), f_x.result(), f_v.result()
        itens.append({"titulo": "Previsão do tempo", "texto": tempo or "Não consegui a previsão do tempo agora.",
                      "fala": tempo or "Não consegui a previsão do tempo agora."})
        for chave, titulo, lista in (("No mundo", "Mundo", mundo), ("Em tecnologia", "Tecnologia", tech)):
            msg = f"Não consegui carregar as notícias de {titulo.lower()} agora."
            itens.append({"titulo": titulo, "noticias": lista, "texto": "" if lista else msg,
                          "fala": f"{chave}: " + "; ".join(x["titulo"] for x in lista) + "." if lista else msg})
        if mundo or tech:
            itens[-1]["fala"] += " Os resumos e os links estão na tela."
        if vagas_novas:
            itens.append({"titulo": "Vagas novas", "noticias": vagas_novas, "texto": "",
                          "fala": f"Encontrei {len(vagas_novas)} vagas novas para você. Os links estão na tela."})
        if HORA_TESTE is None:
            BRIEF_ARQ.write_text(json.dumps({"data": hoje}), "utf-8")
    if p == "noite" and not completo:
        itens.append({"titulo": "Fechamento do dia", "texto": fechamento(), "fala": fechamento()})
    pend = tarefas_pendentes_hoje()
    fala_t = (f"Você tem {len(pend)} tarefa{'s' if len(pend) != 1 else ''} pendente{'s' if len(pend) != 1 else ''} hoje: "
              + "; ".join(pend) + ".") if pend else "Você não tem tarefas pendentes hoje."
    itens.append({"titulo": "Tarefas de hoje", "lista": pend, "texto": "" if pend else fala_t, "fala": fala_t})
    nomes = {"manha": "manhã", "tarde": "tarde", "noite": "noite"}
    return {"titulo": f"Briefing da {nomes[p]} · {DIAS_SEMANA[agora.weekday()]}, {agora.day} de {MESES[agora.month - 1]}",
            "itens": itens, "fala": " ".join(i["fala"] for i in itens), "completo": completo}


def abrir_site(nome, url):
    ESTADO["site"] = (nome, url)
    if abrir_url(url):
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
    abrir_url("https://www.linkedin.com/jobs/search/?" + q)
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
 resumo do dia | previsão do tempo | notícias (resumo) | manchetes (lista completa) | pare (para de falar)
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
MEMÓRIA E PERSONALIDADE
 lembre que meu TCC é dia 12 | o que eu pedi para lembrar | esqueça 1 | seja mais direto / formal / bem-humorado
 modo inglês | sair do modo inglês | modo privacidade | definir senha falada <frase>
COMPUTADOR
 como está o computador | protocolo estudo | criar protocolo sexta: abrir youtube; toque música | listar protocolos
 captura de tela | bloquear o pc | brilho 50 | desligar o pc | cancelar desligamento | iniciar com o windows
 achar arquivo <nome> | abrir resultado 1 | organizar downloads | desfazer organização
 resuma / traduza / explique o que copiei | modo ditado | parar ditado (atalho global: Ctrl+Alt+P)
DESENVOLVIMENTO
 status do git | commits de hoje | criar branch X | sugerir mensagem de commit | fazer commit | revisar o último commit
 rodar projeto | explicar o erro | gerar readme | gerar testes para <arquivo> | fazer backup do projeto | ligar backup automático
 configurar github <token> | meus pull requests | minhas issues | notificações do github
DIA A DIA
 anote ideia: ... | diário: ... | minhas notas | o que anotei sobre X | gastei 30 no almoço | quanto gastei hoje
 bebi água | fiz uma pausa | me alonguei | sequência de água | lembre-me de beber água a cada 90 minutos
 lembre-me de ligar para o banco amanhã às 10h | hoje estudei Angular | me pergunte sobre o que estudei
 fechamento do dia | resumo da semana | adiar pendentes
CARREIRA E MONITORES
 simular entrevista de angular | encerrar entrevista | radar de vagas | monitorar site https://... | status dos sites
Você pode juntar comandos: "toque música e abra o vs code".
Para salvar mudanças em arquivos, responda: confirmar (ou cancelar)."""


# ------------------------------------------------------------------ roteador de comandos
def comandos_base(texto):
    t = re.sub(r"^\s*(?:" + "|".join(sorted(APELIDOS, key=len, reverse=True)) + r")\b[\s,.:;!?-]*", "", texto.strip(), flags=re.I)
    if not t:
        return R("Pois não?")
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
        tarefas[itens[n_ - 1]["id"]]["concluida"] = f"{datetime.now():%Y-%m-%d}"
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
            so_titulos = re.search(r"\b(?:manchetes|detalh\w+|lista)\b", hp)
            partes, links = [], []
            for cat, rotulo, quer in (("mundo", "No mundo", quer_mundo or not quer_tech),
                                      ("tecnologia", "Em tecnologia", quer_tech or not quer_mundo)):
                lista = noticias_itens(cat, 3) if quer else []
                if lista:
                    partes.append(f"{rotulo}:")
                for x in lista:
                    partes.append(f"{x['titulo']}." + ("" if so_titulos or not x["resumo"] else f" {x['resumo']}"))
                    if x["link"]:
                        links.append({"titulo": x["titulo"], "url": x["link"]})
            return R("\n".join(partes), links) if partes else R("Não consegui carregar as notícias agora. Confira a internet.")
        if re.match(r"^(?:bom dia|boa tarde|boa noite)\b", hp):
            return R(saudacao(periodo_do_dia(), hora_atual()))
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
        abrir_url(m.group(1))
        return R("Abri a vaga. Se tiver candidatura simplificada, é só clicar em Candidatar-se e anexar seu currículo.")
    if (m := re.search(r"abr(?:ir|a|e) (?:o |a )?(.+)", t, re.I)) and len(re.findall(r"\w+", t)) <= 6:
        alvo = m.group(1).lower()
        for nome in APENAS_SITE:     # WhatsApp, Netflix: o Windows mostra um "atalho" que só abre a loja; vai direto ao site
            if any(v in _sem_acento(alvo) for v in [nome] + ALIAS_SITES.get(nome, [])):
                return abrir_site(nome, SITES[nome])
        for nome, (proto, web) in PROTOCOLOS.items():
            if nome in alvo:
                if protocolo_instalado(proto):
                    try:
                        os.startfile(proto)
                        return R(f"Abrindo o {nome}.")
                    except OSError:
                        pass
                abrir_url(web)
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
        abrir_url(vaga["link"])
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
        tarefas = ler()
        tarefas.append({"texto": f"Dar retorno sobre a candidatura: {m.group(1)}", "feita": False,
                        "data": (datetime.now().date() + timedelta(days=7)).isoformat(), "hora": "",
                        "criada": datetime.now().isoformat(timespec="minutes")})
        gravar(tarefas)
        return R(f"Candidatura registrada: {m.group(1)}. Total: {len(c)}. Criei uma tarefa para cobrar retorno em 7 dias.")
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
            for v in [nome] + ALIAS_SITES.get(nome, []):
                verbo = rf"\b(?:abr(?:ir|a|e)|acess\w+|ir para|va para|me leve para|mostr\w+)\s+(?:(?:o|a|no|na|para|do|da|site|pagina)\s+)*{re.escape(v)}\b"
                if re.search(verbo, n) or (v in n and len(palavras) <= len(v.split()) + 1):
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


# ======================================================================
# EXTRAS (parte 1): preferências, memória, personalidade, streaming, frases compostas
# ======================================================================
PREFS_ARQ, MEMORIA, HISTORICO = PASTA / "prefs.json", PASTA / "memoria.json", PASTA / "historico.json"
INTERPRETAR_COM_IA = True      # entende frases livres de ação usando o modelo (com cuidado)
CONFIRMA = ("confirmar", "confirmo", "confirma", "sim", "salvar", "pode salvar", "pode")
PERSONALIDADES = {"formal": "Use um tom formal e educado.",
                  "bem-humorado": "Use um tom leve e bem-humorado, com no máximo uma piada curta.",
                  "direto": "Seja extremamente direto e objetivo, sem enfeites."}


def jl(nome, padrao):
    arq = PASTA / nome if isinstance(nome, str) else nome
    try:
        return json.loads(arq.read_text("utf-8")) if arq.exists() else padrao
    except ValueError:
        return padrao


def js(nome, dados):
    arq = PASTA / nome if isinstance(nome, str) else nome
    arq.write_text(json.dumps(dados, ensure_ascii=False, indent=2), "utf-8")


def prefs():
    return jl(PREFS_ARQ, {})


def salvar_pref(**kw):
    p = prefs()
    p.update(kw)
    js(PREFS_ARQ, p)


def sistema_extra():
    """Trechos extras do prompt: inglês, personalidade e memória de longo prazo."""
    p, partes = prefs(), []
    if p.get("ingles"):
        partes.append("MODO INGLÊS: converse em inglês simples (no máximo 3 frases). Se a usuária errar, corrija em "
                      "português, em uma linha começando com 'Correção:'.")
    if PERSONALIDADES.get(p.get("personalidade", "")):
        partes.append(PERSONALIDADES[p["personalidade"]])
    mem = jl(MEMORIA, [])[-20:]
    if mem:
        partes.append("Fatos que a usuária pediu para você lembrar: " + "; ".join(x["texto"] for x in mem) + ".")
    return " ".join(partes)


def preparar_chat(d):
    """Mensagens, prompt de sistema e fontes para o modelo (inclui histórico salvo e busca na web)."""
    msgs, fontes = d.get("mensagens", [])[-8:], []
    ultimo = msgs[-1]["content"] if msgs else ""
    if d.get("pesquisar") and msgs and DDGS:
        try:
            res = DDGS().text(ultimo, region="br-pt", max_results=5)
            fontes = [{"titulo": r["title"], "url": r["href"]} for r in res]
            ctx = "\n".join(f"- {r['title']}: {r['body']}" for r in res)
            msgs[-1] = {"role": "user", "content": ultimo + "\n\nResultados da web:\n" + ctx + "\n\nResuma de forma útil."}
        except Exception:
            fontes = []
    salvo = jl(HISTORICO, [])
    if len(msgs) <= 1 and salvo:                      # conversa nova: traz o final da conversa anterior
        msgs = salvo[-6:] + msgs
    return msgs, MODOS.get(d.get("modo"), MODOS["dev"]) + " " + sistema_extra(), fontes, ultimo


def salvar_historico(ultimo, resposta):
    if ultimo and resposta:
        js(HISTORICO, (jl(HISTORICO, []) + [{"role": "user", "content": ultimo},
                                            {"role": "assistant", "content": resposta}])[-12:])


def ollama_stream(msgs, system, tokens=400, ctx=4096):
    corpo = json.dumps({"model": MODELO, "stream": True, "think": False, "keep_alive": "30m",
                        "options": {"num_ctx": ctx, "num_predict": tokens},
                        "messages": [{"role": "system", "content": system}] + msgs}).encode()
    req = urllib.request.Request(f"{OLLAMA}/api/chat", corpo, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        for linha in r:
            if linha.strip():
                o = json.loads(linha)
                if o.get("message", {}).get("content"):
                    yield o["message"]["content"]
                if o.get("done"):
                    break


def limpar_nome(texto):
    return re.sub(r"^\s*(?:" + "|".join(sorted(APELIDOS, key=len, reverse=True)) + r")\b[\s,.:;!?-]*", "", texto.strip(), flags=re.I)


def confirmar_pendente(t):
    pend = ESTADO.get("pendente")
    if not pend:
        return None
    r = t.lower().strip(" .!")
    if r in ("cancelar", "cancela", "cancelo", "nao", "não"):
        ESTADO["pendente"] = None
        return R("Cancelado. Nada foi alterado.")
    senha = prefs().get("senha_hash")
    if pend.get("sensivel") and senha:
        if hashlib.sha256(_sem_acento(r).encode()).hexdigest() != senha:
            return R("Essa ação é sensível. Para confirmar, diga a sua senha falada, ou diga cancelar.") if r in CONFIRMA else None
    elif r not in CONFIRMA:
        return None
    ESTADO["pendente"] = None
    if pend.get("executar"):
        return pend["executar"]()
    p = pend["caminho"]
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        p.with_suffix(p.suffix + ".bak").write_text(p.read_text("utf-8", errors="replace"), "utf-8")
    p.write_text(pend["conteudo"], "utf-8")
    return R(f"Pronto! Arquivo salvo: {p.name}. Se existia, o original ficou em {p.name}.bak.")


def pedir_confirmacao(descricao, executar, sensivel=False):
    ESTADO["pendente"] = {"executar": executar, "sensivel": sensivel}
    aviso = " Diga a sua senha falada para confirmar, ou cancelar." if sensivel and prefs().get("senha_hash") else \
        " Diga confirmar ou cancelar."
    return R(descricao + aviso)


# ---- rotas extras (cada recurso novo registra um padrão e uma função)
ROTAS = []


def rota(padrao):
    def deco(fn):
        ROTAS.append((re.compile(padrao), fn))
        return fn
    return deco


def arg(m, t, i=1):
    """Trecho do grupo i no texto original (com acentos), quando o tamanho bate."""
    return t[m.start(i):m.end(i)] if len(m.string) == len(t) else m.group(i)


def comandos_extras(t):
    f = re.sub(r"(?<!\d),|,(?!\d)|[;!?]", " ", _sem_acento(t))      # mantém a vírgula decimal (12,50)
    for rx, fn in ROTAS:
        if m := rx.search(f):
            try:
                r = fn(m, t)
            except ValueError as e:                    # ex.: "defina um projeto primeiro", "configure o GitHub"
                return R(str(e))
            if r is not None:
                return r
    return None


def comandos_compostos(t):
    """'toque música e abra o vs code' vira dois comandos."""
    partes = [re.sub(r"^(?:e depois|depois|e|também|tambem)\s+", "", p.strip(" ."), flags=re.I)
              for p in re.split(r"\s*(?:,|;|\s+e\s+|\s+depois\s+|\s+também\s+)\s*", t, flags=re.I) if len(p.strip(" .")) > 2]
    if not 2 <= len(partes) <= 4:
        return None
    ok, nao = [], []
    for p in partes:
        r = comandos_extras(p) or comandos_base(p)
        (ok if r else nao).append(r["resposta"] if r else p)
    if not ok:
        return None
    return R(" ".join(ok) + (f" Não entendi: {'; '.join(nao)}." if nao else ""))


VERBO_ACAO = re.compile(r"^(?:por favor\s+)?(?:(?:voce\s+)?(?:pode|consegue)\s+)?(?:me\s+)?(?:abr\w+|toc\w+|toqu\w+|coloc\w+|"
                        r"coloqu\w+|lig\w+|mostr\w+|pesquis\w+|anot\w+|cri\w+|inici\w+|rod\w+|execut\w+|fech\w+|busc\w+|procur\w+)\b")
PROMPT_INTENCAO = ("Converta o pedido em uma lista JSON de no máximo 3 comandos do assistente, usando SOMENTE estes formatos: "
                   "\"abrir github\", \"abrir vs code\", \"abrir projeto\", \"toque música\", \"toque a playlist NOME\", "
                   "\"pausar música\", \"anote tarefa TEXTO amanhã às 15h\", \"vagas de ÁREA\", \"pesquise TEXTO no youtube\", "
                   "\"protocolo NOME\", \"status do git\", \"como está o computador\". Responda apenas o JSON, por exemplo "
                   "[\"toque música\", \"abrir vs code\"]. Se o pedido não for uma ação, responda [].")


def interpretar_com_ia(t):
    if not INTERPRETAR_COM_IA or len(t.split()) < 3 or not VERBO_ACAO.match(_sem_acento(t)):
        return None
    try:
        saida = ollama([{"role": "user", "content": t}], PROMPT_INTENCAO, tokens=120, ctx=2048, espera=30, temperatura=0)
        m = re.search(r"\[.*\]", saida, re.S)
        lista = json.loads(m.group(0)) if m else []
    except Exception:
        return None
    respostas = []
    for c in [str(x) for x in lista][:3]:
        if len(c) <= 90 and not re.search(r"desligar|reiniciar|apagar|excluir|formatar|senha|commit", c, re.I):
            if r := (comandos_extras(c) or comandos_base(c)):
                respostas.append(r["resposta"])
    return R("\n".join(respostas)) if respostas else None


NAO_COMPOR = re.compile(r"^\s*(?:criar protocolo|lembre|anote|anotar|registrar|salvar|definir|carta|editar|criar arquivo|gastei|"
                        r"estudei|hoje estudei|diario|nota|simular|conectar|configurar)\b")
COMPOSTO = re.compile(r"(?:,|;|\be\b|\bdepois\b|\btambem\b)\s+(?:me\s+)?(?:abr|abra|toqu|toc|coloc|colo|anot|pesquis|mostr|lig|inici|rod|cri|execut|fech|busc|procur|protocolo|modo)\w*")


def comandos(texto):
    t = limpar_nome(texto)
    if not t:
        return R("Pois não?")
    r = confirmar_pendente(t)
    folded = _sem_acento(t)
    if r is None and COMPOSTO.search(folded) and not NAO_COMPOR.match(folded):
        r = comandos_compostos(t)                       # "toque música e abra o github"
    if r is None:
        r = comandos_extras(t) or comandos_base(t)
    if r is None:
        r = comandos_compostos(t)
    if r is None and ESTADO.get("entrevista"):
        r = entrevista_resposta(t)
    if r is None:
        r = interpretar_com_ia(t)
    return r


def conversar(d):
    msgs, sistema, fontes, ultimo = preparar_chat(d)
    resposta = ollama(msgs, sistema)
    salvar_historico(ultimo, resposta)
    return R(resposta, fontes)


def responder_stream(h, d):
    """Resposta do modelo em partes (NDJSON), para a tela falar frase por frase enquanto o modelo escreve."""
    msgs = d.get("mensagens", [])
    try:
        r = comandos(msgs[-1]["content"]) if msgs else None
    except urllib.error.URLError:
        r = R("Não consegui falar com o Ollama. Verifique se ele está aberto.")
    except Exception as e:
        r = R(f"Não consegui concluir: {e}")
    if r is not None:
        return h.enviar(r)
    h.send_response(200)
    h.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
    h.send_header("Cache-Control", "no-cache")
    h.end_headers()
    h.close_connection = True

    def emitir(o):
        h.wfile.write((json.dumps(o, ensure_ascii=False) + "\n").encode())
        h.wfile.flush()
    total = ""
    try:
        msgs2, sistema, fontes, ultimo = preparar_chat(d)
        for pedaco in ollama_stream(msgs2, sistema):
            total += pedaco
            emitir({"t": pedaco})
        salvar_historico(ultimo, total)
        emitir({"fim": True, "resposta": total, "fontes": fontes})
    except urllib.error.HTTPError as e:
        emitir({"fim": True, "resposta": f"O modelo {MODELO} não está baixado. Rode: ollama pull {MODELO}" if e.code == 404
                else f"O Ollama respondeu com o erro {e.code}.", "fontes": []})
    except urllib.error.URLError:
        emitir({"fim": True, "resposta": "Não consegui falar com o Ollama. Verifique se ele está aberto.", "fontes": []})
    except Exception as e:
        emitir({"fim": True, "resposta": total or f"Não consegui concluir: {e}", "fontes": []})


@rota(r"\b(?:lembre|lembra|memorize|guarde)\b(?: que| de)?\s+(.+)")
def _lembrar(m, t):
    if re.match(r"-?\s*me\b", m.group(1)):          # "lembre-me de..." é lembrete, não memória
        return None
    mem = jl(MEMORIA, [])
    mem.append({"texto": arg(m, t).strip(" .:"), "data": f"{datetime.now():%Y-%m-%d}"})
    js(MEMORIA, mem)
    return R(f"Guardei: {arg(m, t).strip(' .:')}.")


@rota(r"\b(?:o que (?:eu )?pedi para (?:voce )?lembrar|minhas memorias|o que voce (?:lembra|sabe sobre mim)|o que voce guardou)\b")
def _listar_memorias(m, t):
    mem = jl(MEMORIA, [])
    if not mem:
        return R("Ainda não guardei nada. Diga, por exemplo: lembre que meu TCC é dia 12.")
    return R("Você me pediu para lembrar:\n" + "\n".join(f"{i}. {x['texto']}" for i, x in enumerate(mem, 1)))


@rota(r"\b(?:esqueca|esquecer|apague a memoria|apagar memoria)\s+(?:a\s+)?(?:memoria\s+)?(\d+|tudo)\b")
def _esquecer(m, t):
    mem = jl(MEMORIA, [])
    if m.group(1) == "tudo":
        js(MEMORIA, [])
        return R("Apaguei todas as memórias.")
    i = int(m.group(1))
    if not 1 <= i <= len(mem):
        return R("Não encontrei essa memória. Diga: o que eu pedi para lembrar.")
    removida = mem.pop(i - 1)
    js(MEMORIA, mem)
    return R(f"Esqueci: {removida['texto']}.")


@rota(r"\b(?:personalidade|seja|fale|modo|tom)\s+(?:mais\s+|de forma\s+|de jeito\s+)?(formal|bem humorad[oa]|bem-humorad[oa]|divertid[oa]|direto|objetivo|normal|padrao)\b")
def _personalidade(m, t):
    nome = {"bem humorado": "bem-humorado", "bem humorada": "bem-humorado", "divertido": "bem-humorado", "divertida": "bem-humorado",
            "objetivo": "direto", "normal": "", "padrao": ""}.get(m.group(1), m.group(1))
    salvar_pref(personalidade=nome)
    return R(f"Certo, agora vou ser {nome}." if nome else "Voltei ao jeito normal.")


@rota(r"\b(?:modo ingles|vamos praticar ingles|praticar ingles|speak english)\b")
def _ingles_on(m, t):
    if re.search(r"\b(?:sair|parar|voltar|desligar)\b", m.string):
        return None
    salvar_pref(ingles=True)
    return R("Great! Let's practice English. How was your day?", ui={"lang": "en"})


@rota(r"\b(?:sair do modo ingles|parar (?:de )?praticar ingles|voltar (?:para|pro) portugues|modo portugues)\b")
def _ingles_off(m, t):
    salvar_pref(ingles=False)
    return R("Certo, voltamos ao português.", ui={"lang": "pt"})


# ======================================================================
# EXTRAS (parte 2): avisos, computador, protocolos, arquivos, área de transferência, ditado
# ======================================================================
AVISOS, _lock_avisos = [], threading.Lock()


def avisar(texto, tipo="info", acao=None):
    with _lock_avisos:
        AVISOS.append({"texto": texto, "tipo": tipo, "acao": acao})


def pegar_avisos():
    with _lock_avisos:
        itens = AVISOS[:]
        AVISOS.clear()
    return itens


def ps(cmd, timeout=25):
    return subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def cpu_percent():
    try:
        import ctypes

        class FT(ctypes.Structure):
            _fields_ = [("lo", ctypes.c_uint32), ("hi", ctypes.c_uint32)]

        def tempos():
            a, b, c = FT(), FT(), FT()
            ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(a), ctypes.byref(b), ctypes.byref(c))
            v = lambda x: (x.hi << 32) | x.lo
            return v(a), v(b) + v(c)
        i1, t1 = tempos()
        time.sleep(0.4)
        i2, t2 = tempos()
        return round(100 * (1 - (i2 - i1) / (t2 - t1))) if t2 > t1 else 0
    except Exception:
        return None


def memoria_pc():
    try:
        import ctypes

        class MS(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_uint32), ("dwMemoryLoad", ctypes.c_uint32), ("total", ctypes.c_uint64),
                        ("livre", ctypes.c_uint64), ("p1", ctypes.c_uint64), ("p2", ctypes.c_uint64),
                        ("p3", ctypes.c_uint64), ("p4", ctypes.c_uint64), ("p5", ctypes.c_uint64)]
        ms = MS()
        ms.dwLength = ctypes.sizeof(MS)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))
        return ms.dwMemoryLoad, ms.total / 2 ** 30, ms.livre / 2 ** 30
    except Exception:
        return None


def bateria():
    """(percentual, carregando) ou None se o PC não tem bateria."""
    try:
        import ctypes

        class SPS(ctypes.Structure):
            _fields_ = [("ac", ctypes.c_ubyte), ("flag", ctypes.c_ubyte), ("pct", ctypes.c_ubyte), ("sf", ctypes.c_ubyte),
                        ("t1", ctypes.c_uint32), ("t2", ctypes.c_uint32)]
        st = SPS()
        ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(st))
        return None if st.pct == 255 or st.flag == 128 else (st.pct, st.ac == 1)
    except Exception:
        return None


def latencia_rede():
    try:
        t0 = time.time()
        socket.create_connection(("1.1.1.1", 53), timeout=2).close()
        return round((time.time() - t0) * 1000)
    except OSError:
        return None


def estado_sistema():
    mem, bat, disco = memoria_pc(), bateria(), shutil.disk_usage(Path.home())
    return {"cpu": cpu_percent(), "mem": mem[0] if mem else None, "mem_total": round(mem[1], 1) if mem else None,
            "disco": round(100 * disco.used / disco.total), "disco_livre": round(disco.free / 2 ** 30),
            "bateria": bat[0] if bat else None, "carregando": bat[1] if bat else None, "rede": latencia_rede()}


@rota(r"\b(?:como esta (?:o )?(?:computador|pc|maquina)|diagnostico (?:do )?(?:pc|computador)|status (?:do )?(?:pc|computador)|saude do (?:pc|computador))\b")
def _diagnostico(m, t):
    e = estado_sistema()
    partes = []
    if e["cpu"] is not None:
        partes.append(f"processador em {e['cpu']}%")
    if e["mem"] is not None:
        partes.append(f"memória em {e['mem']}% de {e['mem_total']} GB")
    partes.append(f"disco com {e['disco_livre']} GB livres")
    if e["bateria"] is not None:
        partes.append(f"bateria em {e['bateria']}%" + (", carregando" if e["carregando"] else ", na bateria"))
    partes.append(f"internet com {e['rede']} milissegundos" if e["rede"] is not None else "sem resposta da internet")
    return R("Seu computador está assim: " + ", ".join(partes) + ".")


# ---- protocolos (rotinas por voz)
PROTOCOLOS_PADRAO = {"estudo": ["abrir vs code", "toque música"], "trabalho": ["abrir vs code", "abrir github", "abrir linkedin"]}


def protocolos():
    p = jl("protocolos.json", None)
    if p is None:
        p = dict(PROTOCOLOS_PADRAO)
        js("protocolos.json", p)
    return p


@rota(r"\bcriar protocolo\s+([a-z0-9][a-z0-9 ]*?)\s*[:=]\s*(.+)")
def _criar_protocolo(m, t):
    passos = [x.strip(" .") for x in re.split(r"[;,]", arg(m, t, 2)) if x.strip(" .")]
    if not passos:
        return R("Diga os passos assim: criar protocolo estudo: abrir vs code; toque música")
    p = protocolos()
    p[m.group(1).strip()] = passos
    js("protocolos.json", p)
    return R(f"Protocolo {m.group(1).strip()} salvo com {len(passos)} passos. Diga: protocolo {m.group(1).strip()}.")


@rota(r"\b(?:listar|meus|quais)\s+protocolos\b")
def _listar_protocolos(m, t):
    return R("Seus protocolos:\n" + "\n".join(f"{n}: " + "; ".join(p) for n, p in protocolos().items()))


@rota(r"\b(?:apagar|remover|excluir)\s+protocolo\s+([a-z0-9 ]+)")
def _apagar_protocolo(m, t):
    p = protocolos()
    if p.pop(m.group(1).strip(), None) is None:
        return R("Não encontrei esse protocolo.")
    js("protocolos.json", p)
    return R("Protocolo apagado.")


@rota(r"^\s*(?:por favor\s+)?(?:ativar\s+|iniciar\s+|executar\s+|rodar\s+)?(?:protocolo|modo)\s+([a-z0-9][a-z0-9 ]*?)\s*[.]?\s*$")
def _rodar_protocolo(m, t):
    p = protocolos()
    nome = m.group(1).strip()
    if nome not in p:
        return R(f"Não tenho o protocolo {nome}. Protocolos: {', '.join(p)}.") if m.group(0).strip().startswith(("protocolo", "executar", "rodar", "iniciar", "ativar")) else None
    respostas = []
    for passo in p[nome]:
        r = comandos_extras(passo) or comandos_base(passo)
        respostas.append(r["resposta"] if r else f"(não entendi o passo: {passo})")
    return R(f"Protocolo {nome}: " + " ".join(respostas))


# ---- ações do sistema
@rota(r"\b(?:tire|tirar|faca|fazer|capturar)\s+(?:uma\s+)?(?:captura de tela|print|screenshot)\b|\bcaptura de tela\b|\bprint da tela\b")
def _captura(m, t):
    pasta = Path.home() / "Pictures" / "Peter"
    pasta.mkdir(parents=True, exist_ok=True)
    arq = pasta / f"tela_{datetime.now():%Y%m%d_%H%M%S}.png"
    ps("Add-Type -AssemblyName System.Windows.Forms,System.Drawing;$b=[System.Windows.Forms.SystemInformation]::VirtualScreen;"
       "$bmp=New-Object System.Drawing.Bitmap $b.Width,$b.Height;$g=[System.Drawing.Graphics]::FromImage($bmp);"
       f"$g.CopyFromScreen($b.Location,[System.Drawing.Point]::Empty,$b.Size);$bmp.Save('{arq}');$g.Dispose();$bmp.Dispose()")
    return R(f"Captura salva em {arq}." if arq.exists() else "Não consegui capturar a tela.")


@rota(r"\b(?:bloquear|travar)\s+(?:o\s+)?(?:pc|computador|tela)\b")
def _bloquear(m, t):
    try:
        subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"])
        return R("Bloqueando o computador.")
    except OSError:
        return R("Não consegui bloquear a tela.")


@rota(r"\bbrilho\b.*?\b(\d{1,3})\b")
def _brilho(m, t):
    n = max(0, min(100, int(m.group(1))))
    r = ps(f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{n})")
    return R(f"Brilho em {n}%." if r.returncode == 0 else "Não consegui mudar o brilho (só funciona em notebooks e telas compatíveis).")


def _desligamento(modo):
    def executar():
        subprocess.Popen(["shutdown", "/s" if modo == "desligar" else "/r", "/t", "30"])
        return R(f"{'Desligando' if modo == 'desligar' else 'Reiniciando'} em 30 segundos. Diga: cancelar desligamento, para abortar.")
    return executar


@rota(r"\b(desligar|desligue|reiniciar|reinicie)\s+(?:o\s+)?(?:pc|computador|maquina)\b")
def _desligar(m, t):
    modo = "desligar" if m.group(1).startswith("deslig") else "reiniciar"
    return pedir_confirmacao(f"Vou {modo} o computador (30 segundos de aviso).", _desligamento(modo), sensivel=True)


@rota(r"\bcancelar\s+(?:o\s+)?(?:desligamento|reinicio|reinicializacao)\b")
def _cancelar_desligamento(m, t):
    subprocess.run(["shutdown", "/a"], capture_output=True)
    return R("Cancelei o desligamento, se havia algum agendado.")


@rota(r"\b(?:trocar|mudar|outra)\s+(?:de\s+|a\s+)?voz\b")
def _trocar_voz(m, t):
    return R("Troquei de voz. Esta é a minha nova voz.", ui={"voz": "trocar"})


@rota(r"\b(?:listar|quais|mostrar)\s+(?:as\s+)?vozes\b")
def _listar_vozes(m, t):
    return R("Estas são as vozes que o navegador tem.", ui={"voz": "listar"})


@rota(r"\b(?:ligar|ativar|iniciar|comecar)\s+(?:o\s+)?(?:modo\s+)?ditado\b|\bmodo ditado\b")
def _ditado_on(m, t):
    return R("Modo ditado ligado. Clique no programa onde quer escrever e fale. Diga: parar ditado, para encerrar.", ui={"ditado": True})


@rota(r"\b(?:parar|desligar|encerrar|fim d[oe])\s+(?:o\s+)?(?:modo\s+)?ditado\b")
def _ditado_off(m, t):
    return R("Modo ditado desligado.", ui={"ditado": False})


def colar_texto(texto):
    """Cola o texto no programa em foco (área de transferência + Ctrl+V)."""
    if not copiar(texto + " "):
        return False
    try:
        import ctypes
        u = ctypes.windll.user32
        for cod, tipo in ((0x11, 0), (0x56, 0), (0x56, 2), (0x11, 2)):
            u.keybd_event(cod, 0, tipo, 0)
        return True
    except Exception:
        return False


def atalho_global():
    """Ctrl+Alt+P em qualquer janela: manda a tela começar a ouvir."""
    try:
        import ctypes
        import ctypes.wintypes as w
        u = ctypes.windll.user32
        if not u.RegisterHotKey(None, 1, 0x0001 | 0x0002, 0x50):
            return
        msg = w.MSG()
        while u.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            if msg.message == 0x0312:
                avisar("", acao="ouvir")
    except Exception:
        pass


# ---- área de transferência
def ler_clipboard():
    try:
        return (ps("[Console]::OutputEncoding=[Text.Encoding]::UTF8; Get-Clipboard -Raw").stdout or "").strip()
    except Exception:
        return ""


@rota(r"\b(resum\w+|traduz\w+|explic\w+|corrij\w+)\s+(?:o\s+(?:texto\s+)?)?que\s+(?:eu\s+)?copiei\b(?:\s+(?:para|pra|em)\s+(ingles|portugues))?")
def _clipboard(m, t):
    texto = ler_clipboard()[:4000]
    if not texto:
        return R("A área de transferência está vazia. Copie um texto e peça de novo.")
    verbo, alvo = m.group(1), m.group(2)
    if verbo.startswith("resum"):
        sistema = "Resuma o texto em português do Brasil, em até 3 frases curtas."
    elif verbo.startswith("traduz"):
        sistema = f"Traduza o texto para {'português do Brasil' if alvo == 'portugues' else 'inglês'}. Responda só com a tradução."
    elif verbo.startswith("corrij"):
        sistema = "Corrija a gramática e a ortografia do texto, mantendo o idioma. Responda só com o texto corrigido."
    else:
        sistema = "Explique o texto em português do Brasil, de forma simples, em até 4 frases."
    return R(ollama([{"role": "user", "content": texto}], sistema, tokens=500, ctx=6144))


# ---- arquivos por voz
CATEGORIAS = {"Imagens": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"},
              "Documentos": {".pdf", ".doc", ".docx", ".txt", ".xls", ".xlsx", ".ppt", ".pptx", ".csv", ".odt"},
              "Instaladores": {".exe", ".msi"}, "Compactados": {".zip", ".rar", ".7z", ".tar", ".gz"},
              "Videos": {".mp4", ".mkv", ".avi", ".mov"}, "Audios": {".mp3", ".wav", ".flac", ".m4a"},
              "Codigo": {".py", ".js", ".ts", ".java", ".cs", ".html", ".css", ".json", ".sql"}}


def achar_arquivos(termo, limite=15):
    termo, achados = _sem_acento(termo).strip(), []
    pastas = [Path.home() / n for n in ("Downloads", "Documents", "Documentos", "Desktop", "Área de Trabalho")]
    if projeto():
        pastas.append(projeto())
    for raiz in (p for p in pastas if p.is_dir()):
        for dp, dn, fn in os.walk(raiz):
            dn[:] = [d for d in dn if d not in IGNORAR and not d.startswith(".")]
            if dp[len(str(raiz)):].count(os.sep) >= 3:
                dn[:] = []
            achados += [Path(dp) / f for f in fn if termo in _sem_acento(f)]
    achados.sort(key=lambda a: a.stat().st_mtime, reverse=True)
    return achados[:limite]


@rota(r"\b(?:achar|encontrar|procurar|buscar|localizar)\s+(?:o\s+|um\s+)?arquivo\s+(.+)")
def _achar_arquivo(m, t):
    achados = achar_arquivos(m.group(1).strip(" ."))
    ESTADO["achados"] = achados
    if not achados:
        return R("Não encontrei nenhum arquivo com esse nome em Downloads, Documentos, Área de Trabalho ou no projeto.")
    return R(f"Encontrei {len(achados)} arquivo(s). Diga: abrir resultado 1.\n" + bloco("\n".join(f"{i}. {a}" for i, a in enumerate(achados, 1))))


@rota(r"\babrir\s+(?:o\s+)?resultado\s+(\d+)")
def _abrir_resultado(m, t):
    achados = ESTADO.get("achados") or []
    i = int(m.group(1))
    if not 1 <= i <= len(achados):
        return R("Não tenho esse resultado. Procure primeiro: achar arquivo <nome>.")
    os.startfile(achados[i - 1])
    return R(f"Abrindo {achados[i - 1].name}.")


@rota(r"\borganiz\w+\s+(?:a\s+)?(?:pasta\s+)?(?:de\s+)?downloads\b")
def _organizar_downloads(m, t):
    pasta = Path.home() / "Downloads"
    plano = []
    if pasta.is_dir():
        for f in pasta.iterdir():
            if f.is_file() and not f.name.startswith("."):
                cat = next((c for c, exts in CATEGORIAS.items() if f.suffix.lower() in exts), "Outros")
                plano.append((f, pasta / cat / f.name))
    if not plano:
        return R("A pasta Downloads já está organizada (não há arquivos soltos).")
    contagem = {}
    for _, dest in plano:
        contagem[dest.parent.name] = contagem.get(dest.parent.name, 0) + 1

    def executar():
        feitos = []
        for origem_, dest in plano:
            dest.parent.mkdir(exist_ok=True)
            final, n = dest, 1
            while final.exists():
                final, n = dest.with_name(f"{dest.stem} ({n}){dest.suffix}"), n + 1
            shutil.move(str(origem_), str(final))
            feitos.append([str(final), str(origem_)])
        js("organizacao.json", feitos)
        return R(f"Organizei {len(feitos)} arquivos. Se quiser voltar atrás, diga: desfazer organização.")
    return pedir_confirmacao(f"Vou mover {len(plano)} arquivos de Downloads para pastas por tipo ("
                             + ", ".join(f"{k}: {v}" for k, v in contagem.items()) + ").", executar)


@rota(r"\bdesfazer\s+(?:a\s+)?organizacao\b")
def _desfazer_organizacao(m, t):
    feitos = jl("organizacao.json", [])
    voltou = 0
    for atual, antigo in feitos:
        if Path(atual).exists() and not Path(antigo).exists():
            shutil.move(atual, antigo)
            voltou += 1
    js("organizacao.json", [])
    return R(f"Devolvi {voltou} arquivos para onde estavam.")


# ---- iniciar com o Windows
def _atalho_inicio():
    return Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs/Startup/Peter.lnk"


@rota(r"\bnao (?:iniciar|abrir) (?:junto )?com o windows\b|\b(?:parar|desativar) (?:de )?(?:iniciar|abrir) (?:junto )?com o windows\b")
def _inicio_off(m, t):
    _atalho_inicio().unlink(missing_ok=True)
    return R("Pronto, o Peter não abre mais junto com o Windows.")


@rota(r"\b(?:iniciar|abrir|comecar) (?:junto )?com o windows\b|\bativar inicio (?:automatico|com o windows)\b")
def _inicio_on(m, t):
    exe = Path(sys.executable)
    alvo = exe.with_name("pythonw.exe") if exe.with_name("pythonw.exe").exists() else exe
    script = Path(sys.argv[0]).resolve()
    ps(f"$s=(New-Object -COM WScript.Shell).CreateShortcut('{_atalho_inicio()}');$s.TargetPath='{alvo}';"
       f"$s.Arguments='\"{script}\"';$s.WorkingDirectory='{script.parent}';$s.Save()")
    return R("Pronto, o Peter vai abrir junto com o Windows." if _atalho_inicio().exists() else "Não consegui criar o atalho de inicialização.")


# ======================================================================
# EXTRAS (parte 3): desenvolvimento (Git, GitHub, rodar projeto, README, testes, backup)
# ======================================================================
GH_ARQ = PASTA / "github.json"


def git(*args, timeout=25):
    raiz = projeto()
    if not raiz:
        raise ValueError("Defina um projeto primeiro: usar projeto D:\\codigos\\meu-app")
    r = subprocess.run(["git", *args], cwd=raiz, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return (r.stdout + r.stderr).strip()


@rota(r"\b(?:status do git|git status|situacao do git|status do repositorio)\b")
def _git_status(m, t):
    return R("Estado do Git:\n" + bloco(git("status", "-sb")))


@rota(r"\bcriar (?:uma )?branch\s+([a-z0-9._/-]+)")
def _git_branch(m, t):
    return R(git("switch", "-c", arg(m, t)) or "Branch criada.")


@rota(r"\bcommits? de hoje\b|\bo que (?:eu )?fiz hoje no (?:git|projeto)\b")
def _git_hoje(m, t):
    out = git("log", "--since=midnight", "--pretty=format:%h %s")
    return R("Commits de hoje:\n" + bloco(out) if out else "Nenhum commit hoje neste projeto.")


@rota(r"\b(?:sugerir|sugira|gerar|gere|escrever|escreva)\s+(?:uma\s+)?mensagem de commit\b")
def _git_msg(m, t):
    dif = git("diff", "HEAD", "--stat") + "\n" + git("diff", "HEAD")[:5000]
    if not dif.strip():
        return R("Não há mudanças para commitar.")
    msg = ollama([{"role": "user", "content": dif}], "Escreva UMA linha de mensagem de commit em inglês (conventional commits, "
                 "até 70 caracteres). Responda só a mensagem.", tokens=60, ctx=6144).strip().splitlines()[0].strip("`\" ")
    ESTADO["msg_commit"] = msg
    return R(f"Sugestão de mensagem: {msg}\nDiga: fazer commit (ou: fazer commit: outra mensagem).")


@rota(r"\bfazer commit(?:\s*[:-]\s*(.+))?\s*$")
def _git_commit(m, t):
    msg = (arg(m, t).strip() if m.group(1) else None) or ESTADO.get("msg_commit")
    if not msg:
        return R("Diga a mensagem: fazer commit: ajusta tela de login. Ou peça antes: sugerir mensagem de commit.")

    def executar():
        git("add", "-A")
        return R("Commit feito.\n" + bloco(git("commit", "-m", msg)))
    return pedir_confirmacao(f"Vou adicionar todas as mudanças e fazer commit com a mensagem: {msg}.", executar, sensivel=True)


@rota(r"\brevis\w+\s+(?:o\s+)?(?:ultimo\s+)?commit\b")
def _git_revisar(m, t):
    dif = git("show", "HEAD", "--stat", "--patch")[:7000]
    return R(ollama([{"role": "user", "content": dif}], "Você é um revisor de código. Em português do Brasil, aponte em até 5 "
                    "pontos curtos possíveis bugs, riscos e melhorias neste commit.", tokens=450, ctx=6144))


def comando_projeto():
    raiz = projeto()
    if (raiz / "package.json").exists():
        sc = json.loads((raiz / "package.json").read_text("utf-8", errors="replace")).get("scripts", {})
        return "npm start" if "start" in sc else "npm run dev" if "dev" in sc else None
    if list(raiz.glob("*.csproj")) or list(raiz.glob("*.sln")):
        return "dotnet run"
    return next((f"python {n}" for n in ("main.py", "app.py") if (raiz / n).exists()), None)


@rota(r"\b(?:rodar|executar|rode|execute|iniciar)\s+(?:o\s+)?projeto\b")
def _rodar_projeto(m, t):
    if not projeto():
        return R("Defina um projeto primeiro: usar projeto D:\\codigos\\meu-app")
    cmd = comando_projeto()
    if not cmd:
        return R("Não reconheci como rodar este projeto (procurei package.json, .csproj, main.py e app.py).")

    def executar():
        proc = subprocess.Popen(cmd, shell=True, cwd=projeto(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                encoding="utf-8", errors="replace")
        try:
            saida, _ = proc.communicate(timeout=30)
            fim = f"terminou com código {proc.returncode}"
        except subprocess.TimeoutExpired:
            try:
                subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
            except OSError:
                proc.kill()
            saida, _ = proc.communicate()
            fim = "ainda estava rodando após 30 segundos (parei o processo)"
        ESTADO["saida_proj"] = saida
        return R(f"`{cmd}` {fim}. Últimas linhas:\n" + bloco("\n".join(saida.splitlines()[-40:])) + "\nSe houve erro, diga: explicar o erro.")
    return pedir_confirmacao(f"Vou rodar `{cmd}` na pasta do projeto (por até 30 segundos).", executar)


@rota(r"\bexplic\w+\s+(?:o\s+)?(?:erro|problema|saida)\b")
def _explicar_erro(m, t):
    saida = ESTADO.get("saida_proj")
    if not saida:
        return R("Ainda não rodei nada. Diga: rodar projeto.")
    return R(ollama([{"role": "user", "content": saida[-3500:]}], "Explique em português do Brasil, em até 5 frases curtas, "
                    "o erro desta saída de terminal e como corrigir.", tokens=400, ctx=6144))


@rota(r"\b(?:gerar|gere|criar|crie|escrever|escreva)\s+(?:um\s+)?readme\b")
def _readme(m, t):
    raiz = projeto()
    if not raiz:
        return R("Defina um projeto primeiro: usar projeto D:\\codigos\\meu-app")
    todos = arquivos(raiz)
    resumo = "Estrutura:\n" + "\n".join(str(a.relative_to(raiz)) for a in todos[:60]) + "\n\nTrechos:\n"
    for a in sorted(todos, key=lambda a: (a.name.lower() not in PRIORIDADE, a.stat().st_size))[:5]:
        resumo += f"\n### {a.relative_to(raiz)}\n{a.read_text('utf-8', errors='replace')[:1000]}\n"
    texto = so_codigo(ollama([{"role": "user", "content": resumo}], "Escreva um README.md em português do Brasil para este projeto: "
                             "título, descrição, tecnologias, como instalar e rodar. Use só o que o código mostra. Responda só com o Markdown.",
                             tokens=1200, ctx=6144))
    ESTADO["pendente"] = {"caminho": raiz / "README.md", "conteudo": texto}
    return R("Preparei um README. Diga confirmar para salvar (se já existir, o antigo vira .bak) ou cancelar.\n" + bloco(texto))


@rota(r"\b(?:gerar|gere|criar|crie)\s+testes?\s+(?:para|do|de)\s+(?:o\s+)?(?:arquivo\s+)?(\S+)")
def _testes(m, t):
    p = caminho(arg(m, t))
    if not p.is_file():
        return R("Não encontrei esse arquivo no projeto.")
    destino = {".py": p.with_name(f"test_{p.name}"), ".js": p.with_suffix(".test.js"), ".ts": p.with_suffix(".spec.ts")}.get(p.suffix)
    if not destino:
        return R("Por enquanto gero testes para arquivos .py, .js e .ts.")
    texto = so_codigo(ollama([{"role": "user", "content": p.read_text("utf-8", errors="replace")[:7000]}],
                             f"Escreva testes unitários para este arquivo ({p.name}). Responda só com o código do arquivo de testes.",
                             tokens=1500, ctx=8192))
    ESTADO["pendente"] = {"caminho": destino, "conteudo": texto}
    return R(f"Preparei {destino.name}. Diga confirmar para salvar ou cancelar.\n" + bloco(texto))


def backup_projeto():
    raiz = projeto()
    if not raiz:
        return None
    pasta = PASTA / "backups"
    pasta.mkdir(exist_ok=True)
    destino = pasta / f"{raiz.name}_{datetime.now():%Y%m%d_%H%M}.zip"
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        for dp, dn, fn in os.walk(raiz):
            dn[:] = [d for d in dn if d not in IGNORAR]
            for f in fn:
                z.write(Path(dp) / f, (Path(dp) / f).relative_to(raiz.parent))
    for antigo in sorted(pasta.glob(f"{raiz.name}_*.zip"))[:-10]:
        antigo.unlink()
    return destino


@rota(r"\b(?:fazer|faca|criar)\s+(?:um\s+)?backup(?:\s+do\s+projeto)?\b")
def _backup(m, t):
    arq = backup_projeto()
    if not arq:
        return R("Defina um projeto primeiro: usar projeto D:\\codigos\\meu-app")
    return R(f"Backup criado: {arq} ({round(arq.stat().st_size / 2 ** 20, 1)} MB). Guardo os 10 mais recentes.")


@rota(r"\b(ligar|ativar|desligar|desativar)\s+(?:o\s+)?backup automatico\b")
def _backup_auto(m, t):
    ligar = m.group(1) in ("ligar", "ativar")
    salvar_pref(backup_auto=ligar)
    return R("Backup automático ligado: faço um por dia, depois das 20 horas." if ligar else "Backup automático desligado.")


def info_projeto():
    raiz = projeto()
    if not raiz:
        return {"ativo": False}
    if time.time() - ESTADO.get("proj_cache_t", 0) < 20 and ESTADO.get("proj_cache"):
        return ESTADO["proj_cache"]
    info = {"ativo": True, "nome": raiz.name, "branch": "", "alterados": [], "todos": 0}
    try:
        info["branch"] = git("rev-parse", "--abbrev-ref", "HEAD")
        info["alterados"] = [x for x in git("status", "--porcelain").splitlines()][:8]
    except Exception:
        pass
    for a in arquivos(raiz, 200):
        try:
            info["todos"] += len(re.findall(r"\b(?:TODO|FIXME)\b", a.read_text("utf-8", errors="ignore")[:20000]))
        except OSError:
            pass
    ESTADO["proj_cache"], ESTADO["proj_cache_t"] = info, time.time()
    return info


# ---- GitHub com token
def gh(caminho_api, token=None):
    tok = token or jl(GH_ARQ, {}).get("token")
    if not tok:
        raise ValueError("Configure o GitHub antes: configurar github SEU_TOKEN")
    return _http("https://api.github.com" + caminho_api, cab={"Authorization": "Bearer " + tok, "User-Agent": "Peter",
                                                              "Accept": "application/vnd.github+json"})


@rota(r"\bconfigurar github\s+(\S{20,})")
def _gh_configurar(m, t):
    token = arg(m, t)
    st, d = gh("/user", token)
    if st != 200:
        return R(f"O GitHub recusou o token (erro {st}). Crie um em github.com/settings/tokens com permissões repo e notifications.")
    js(GH_ARQ, {"token": token, "login": d.get("login")})
    return R(f"GitHub conectado como {d.get('login')}. O token fica salvo só neste computador, na pasta .jarvis.")


def _busca_github(q, vazio, rotulo):
    st, d = gh("/search/issues?per_page=8&q=" + urllib.parse.quote(q))
    if st != 200:
        return R(f"O GitHub respondeu com o erro {st}.")
    itens = d.get("items", [])
    if not itens:
        return R(vazio)
    linhas = [f"{x['title']} ({x['repository_url'].split('/repos/')[-1]})" for x in itens]
    return R(f"Você tem {d.get('total_count', len(itens))} {rotulo} abertos. " + "; ".join(linhas[:5]) + ".",
             [{"titulo": x["title"], "url": x["html_url"]} for x in itens])


@rota(r"\b(?:meus pull requests|pull requests abertos|meus prs)\b")
def _gh_prs(m, t):
    return _busca_github("is:open is:pr author:@me archived:false", "Você não tem pull requests abertos.", "pull requests")


@rota(r"\b(?:minhas issues|issues abertas)\b")
def _gh_issues(m, t):
    return _busca_github("is:open is:issue assignee:@me archived:false", "Você não tem issues abertas para você.", "issues")


@rota(r"\bnotificacoes do github\b")
def _gh_notif(m, t):
    st, d = gh("/notifications?per_page=8")
    if st != 200 or not isinstance(d, list):
        return R(f"O GitHub respondeu com o erro {st}.")
    if not d:
        return R("Nenhuma notificação nova no GitHub.")
    return R(f"{len(d)} notificações: " + "; ".join(f"{x['subject']['title']} ({x['repository']['full_name']})" for x in d[:5]) + ".",
             [{"titulo": x["subject"]["title"], "url": "https://github.com/" + x["repository"]["full_name"]} for x in d])


# ======================================================================
# EXTRAS (parte 4): dia a dia, estudo, carreira, monitores, fechamento, privacidade
# ======================================================================
NOTAS, GASTOS, HABITOS, ESTUDO, MONITORES = (PASTA / n for n in ("notas.json", "gastos.json", "habitos.json", "estudo.json", "monitores.json"))


def hoje_iso(dias=0):
    return (datetime.now().date() + timedelta(days=dias)).isoformat()


def brl(v):
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ---- notas e diário
@rota(r"\b(?:anote|anotar|salve|salvar|registre|registrar)\s+(?:uma\s+)?(nota|ideia)\s*(?:de|sobre)?\s*[:.]?\s+(.+)")
def _nota(m, t):
    notas = jl(NOTAS, [])
    notas.append({"texto": arg(m, t, 2).strip(" ."), "tipo": m.group(1), "quando": f"{datetime.now():%Y-%m-%d %H:%M}"})
    js(NOTAS, notas)
    return R("Anotei." if m.group(1) == "nota" else "Ideia guardada.")


@rota(r"^\s*diario\s*[:.]\s*(.+)")
def _diario(m, t):
    notas = jl(NOTAS, [])
    notas.append({"texto": arg(m, t).strip(" ."), "tipo": "diario", "quando": f"{datetime.now():%Y-%m-%d %H:%M}"})
    js(NOTAS, notas)
    return R("Registrei no seu diário.")


@rota(r"\b(?:minhas notas|ultimas notas|ler (?:as )?notas)\b")
def _ver_notas(m, t):
    notas = jl(NOTAS, [])[-8:]
    return R("Suas últimas notas:\n" + "\n".join(f"{n['quando'][:10]} - {n['texto']}" for n in notas) if notas else "Você ainda não tem notas.")


@rota(r"\bo que (?:eu )?anotei sobre\s+(.+)")
def _buscar_notas(m, t):
    termo = m.group(1).strip(" .?")
    achadas = [n for n in jl(NOTAS, []) if termo in _sem_acento(n["texto"])]
    return R(f"Achei {len(achadas)} nota(s) sobre {termo}:\n" + "\n".join(f"{n['quando'][:10]} - {n['texto']}" for n in achadas[-6:])
             if achadas else f"Não achei nada sobre {termo} nas suas notas.")


# ---- gastos
@rota(r"\bgastei\s+(?:r\$\s*)?(\d+(?:[.,]\d{1,2})?)\s*(?:reais?)?\s*(?:no|na|em|com|de|para|pra)?\s*(.*)")
def _gastei(m, t):
    valor = float(m.group(1).replace(",", "."))
    desc = arg(m, t, 2).strip(" .") or "sem descrição"
    g = jl(GASTOS, [])
    g.append({"valor": valor, "desc": desc, "data": hoje_iso()})
    js(GASTOS, g)
    mes = sum(x["valor"] for x in g if x["data"][:7] == hoje_iso()[:7])
    return R(f"Registrei {brl(valor)} em {desc}. Neste mês você já gastou {brl(mes)}.")


@rota(r"\b(?:quanto gastei|gastos d[oe]s?|resumo (?:de|dos) gastos)\s*(hoje|ontem|(?:nesta|esta|essa) semana|(?:neste|este|esse|no) mes|do mes)?")
def _gastos(m, t):
    p = m.group(1) or "do mes"
    g = jl(GASTOS, [])
    if p == "hoje":
        sel, rotulo = [x for x in g if x["data"] == hoje_iso()], "hoje"
    elif p == "ontem":
        sel, rotulo = [x for x in g if x["data"] == hoje_iso(-1)], "ontem"
    elif "semana" in p:
        sel, rotulo = [x for x in g if x["data"] >= hoje_iso(-6)], "nos últimos 7 dias"
    else:
        sel, rotulo = [x for x in g if x["data"][:7] == hoje_iso()[:7]], "neste mês"
    if not sel:
        return R(f"Você não registrou gastos {rotulo}.")
    return R(f"Você gastou {brl(sum(x['valor'] for x in sel))} {rotulo}.\n" +
             "\n".join(f"{x['data'][8:]}/{x['data'][5:7]} - {brl(x['valor'])} - {x['desc']}" for x in sel[-8:]))


# ---- hábitos
HABITOS_NOMES = {"agua": "água", "pausa": "pausa", "alongamento": "alongamento"}


def registrar_habito(h):
    dados = jl(HABITOS, {"checkins": [], "lembretes": {}})
    dados["checkins"].append({"h": h, "d": hoje_iso(), "hora": f"{datetime.now():%H:%M}"})
    js(HABITOS, dados)
    if h == "pausa":
        ESTADO["ultima_pausa"] = time.time()
    return R(f"Registrado: {HABITOS_NOMES[h]}. Sequência de {sequencia(h)} dia(s).")


def sequencia(h):
    dias = {c["d"] for c in jl(HABITOS, {"checkins": []})["checkins"] if c["h"] == h}
    n, d = 0, 0
    while hoje_iso(-d) in dias or (d == 0 and hoje_iso(-1) in dias):
        if hoje_iso(-d) in dias:
            n += 1
        d += 1
    return n


@rota(r"\b(?:bebi|tomei)\s+(?:um\s+)?(?:copo\s+(?:de\s+|d\s*)?)?agua\b")
def _h_agua(m, t):
    return registrar_habito("agua")


@rota(r"\b(?:fiz|tirei)\s+(?:uma\s+)?pausa\b|\bdescansei\b")
def _h_pausa(m, t):
    return registrar_habito("pausa")


@rota(r"\bme alonguei\b|\bfiz (?:o\s+)?alongamento\b")
def _h_along(m, t):
    return registrar_habito("alongamento")


@rota(r"\bsequencia (?:de|da|do)\s+(agua|pausas?|alongamento)\b")
def _h_seq(m, t):
    h = "pausa" if m.group(1).startswith("pausa") else m.group(1)
    return R(f"Sua sequência de {HABITOS_NOMES[h]} é de {sequencia(h)} dia(s).")


@rota(r"\blembre[- ]me\s+(?:de\s+)?(beber agua|fazer pausas?|alongar)(?:\s+a cada\s+(\d+)\s+(minutos?|horas?))?")
def _h_lembrete(m, t):
    h = {"beber agua": "agua", "alongar": "alongamento"}.get(m.group(1), "pausa")
    cada = int(m.group(2) or 120) * (60 if m.group(3) and m.group(3).startswith("hora") else 1)
    dados = jl(HABITOS, {"checkins": [], "lembretes": {}})
    dados["lembretes"][h] = {"cada": cada, "ultimo": time.time()}
    js(HABITOS, dados)
    return R(f"Combinado: aviso de {HABITOS_NOMES[h]} a cada {cada} minutos, entre 7h e 22h.")


@rota(r"\b(?:desativar|parar|cancelar)\s+(?:o\s+)?lembrete de (agua|pausa|alongamento)\b")
def _h_lembrete_off(m, t):
    dados = jl(HABITOS, {"checkins": [], "lembretes": {}})
    dados["lembretes"].pop(m.group(1), None)
    js(HABITOS, dados)
    return R("Lembrete desativado.")


@rota(r"\blembre[- ]me\s+(?:de\s+)?(.+)")
def _lembrete_tarefa(m, t):
    texto_t, dia, hora = interpretar_tarefa(arg(m, t))
    tarefas = ler()
    tarefas.append({"texto": texto_t, "feita": False, "data": dia, "hora": hora, "criada": datetime.now().isoformat(timespec="minutes")})
    gravar(tarefas)
    return R(f"Combinado, vou te lembrar para {quando(dia, hora)}: {texto_t}." + ("" if hora else " Sem horário, ela só aparece na lista do dia."))


# ---- estudo
@rota(r"\b(?:hoje\s+)?estudei\s+(.+)")
def _estudei(m, t):
    tema = arg(m, t).strip(" .")
    est = jl(ESTUDO, [])
    est.append({"tema": tema, "data": hoje_iso()})
    js(ESTUDO, est)
    tarefas = ler()
    for dias in (1, 3, 7):
        tarefas.append({"texto": f"Revisar: {tema}", "feita": False, "data": hoje_iso(dias), "hora": "",
                        "criada": datetime.now().isoformat(timespec="minutes")})
    gravar(tarefas)
    return R(f"Anotei que você estudou {tema}. Agendei revisões para amanhã, daqui a 3 dias e daqui a 7 dias.")


@rota(r"\b(?:me pergunte|faca perguntas|me teste|me faca um quiz)\s+(?:sobre\s+)?(?:o que (?:eu )?estudei|meus estudos)\b")
def _quiz_estudo(m, t):
    temas = [e["tema"] for e in jl(ESTUDO, [])[-5:]]
    if not temas:
        return R("Ainda não registrei o que você estudou. Diga: hoje estudei Angular signals.")
    return R(ollama([{"role": "user", "content": "Temas: " + "; ".join(temas)}],
                    "Crie 3 perguntas curtas, em português do Brasil, para testar o conhecimento sobre os temas. Só as perguntas, numeradas.",
                    tokens=250))


# ---- carreira: simulador de entrevista e radar de vagas
def _sistema_entrevista(tema):
    return (f"Você é um entrevistador técnico de {tema}. Faça UMA pergunta por vez, em português do Brasil. Quando a candidata "
            "responder, dê um feedback de 1 ou 2 frases (ponto forte e o que melhorar) e faça a próxima pergunta.")


@rota(r"\bsimular entrevista(?:\s+(?:de|sobre|para)\s+(.+))?")
def _entrevista(m, t):
    tema = arg(m, t).strip(" .") if m.group(1) else "desenvolvimento full stack júnior"
    ESTADO["entrevista"] = {"tema": tema, "hist": []}
    pergunta = ollama([{"role": "user", "content": "Comece a entrevista."}], _sistema_entrevista(tema), tokens=150)
    ESTADO["entrevista"]["hist"] = [{"role": "user", "content": "Comece a entrevista."}, {"role": "assistant", "content": pergunta}]
    return R(f"Entrevista de {tema} iniciada. Responda normalmente; diga: encerrar entrevista, para sair.\n{pergunta}")


@rota(r"\b(?:encerrar|terminar|parar|sair d[aeo])\s+(?:a\s+)?entrevista\b")
def _entrevista_fim(m, t):
    if not ESTADO.get("entrevista"):
        return None
    ESTADO["entrevista"] = None
    return R("Entrevista encerrada. Bom treino!")


def entrevista_resposta(t):
    e = ESTADO["entrevista"]
    e["hist"].append({"role": "user", "content": t})
    resp = ollama(e["hist"][-10:], _sistema_entrevista(e["tema"]), tokens=250)
    e["hist"].append({"role": "assistant", "content": resp})
    return R(resp)


def radar_vagas(n=6):
    """Vagas novas (ainda não vistas) pela busca na web. Só avisa; nunca se candidata."""
    if not DDGS:
        return []
    try:
        res = DDGS().text(f"site:linkedin.com/jobs {cargo_padrao()} júnior", region="br-pt", max_results=12)
    except Exception:
        return []
    vistos = set(jl("vagas_vistas.json", []))
    novos = [r for r in res if r["href"] not in vistos][:n]
    js("vagas_vistas.json", sorted(vistos | {r["href"] for r in novos})[-300:])
    return [{"titulo": r["title"], "link": r["href"], "resumo": (r.get("body") or "")[:200],
             "fonte": urllib.parse.urlparse(r["href"]).netloc.replace("www.", "")} for r in novos]


@rota(r"\bradar de vagas\b|\bvagas novas\b")
def _radar(m, t):
    if not DDGS:
        return R("O radar precisa do pacote ddgs: pip install ddgs.")
    novos = radar_vagas()
    if not novos:
        return R("Não encontrei vagas novas agora.")
    return R(f"Encontrei {len(novos)} vagas novas. Abra e candidate-se você mesma.\n" + "\n".join(x["titulo"] for x in novos),
             [{"titulo": x["titulo"], "url": x["link"]} for x in novos])


# ---- monitores de site
def site_no_ar(url):
    try:
        urllib.request.urlopen(urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0 Peter"}), timeout=8)
        return True
    except urllib.error.HTTPError as e:
        return e.code < 500
    except Exception:
        return False


@rota(r"\bmonitorar (?:o\s+)?site\s+(https?://\S+)")
def _monitorar(m, t):
    mon = jl(MONITORES, {})
    mon[arg(m, t)] = {"ok": site_no_ar(arg(m, t))}
    js(MONITORES, mon)
    return R(f"Vou vigiar {arg(m, t)} e avisar se cair ou voltar.")


@rota(r"\bstatus dos sites\b|\b(?:o\s+)?site\s+(https?://\S+)\s+esta no ar\b")
def _status_sites(m, t):
    urls = [arg(m, t)] if m.group(1) else list(jl(MONITORES, {}))
    if not urls:
        return R("Nenhum site monitorado. Diga: monitorar site https://...")
    return R(" ".join(f"{u}: {'no ar' if site_no_ar(u) else 'FORA DO AR'}." for u in urls))


# ---- fechamento do dia, semana e adiamento
def fechamento():
    t = ler()
    feitas = [x for x in t if x.get("concluida") == hoje_iso()]
    pend = [x for x in t if x.get("data") == hoje_iso() and not x["feita"]]
    amanha = [x for x in t if x.get("data") == hoje_iso(1) and not x["feita"]]
    partes = [f"Hoje você concluiu {len(feitas)} tarefa{'s' if len(feitas) != 1 else ''}" + (": " + "; ".join(x["texto"] for x in feitas) if feitas else "") + "."]
    if pend:
        partes.append(f"Ficaram pendentes: {'; '.join(x['texto'] for x in pend)}. Diga: adiar pendentes, para passar tudo para amanhã.")
    partes.append(f"Para amanhã você já tem {len(amanha)} tarefa{'s' if len(amanha) != 1 else ''}.")
    return " ".join(partes)


@rota(r"\b(?:fechamento do dia|resumo da noite|como foi (?:o )?meu dia)\b")
def _fechamento(m, t):
    return R(fechamento())


@rota(r"\bresumo da semana\b")
def _resumo_semana(m, t):
    desde = hoje_iso(-6)
    feitas = [x for x in ler() if (x.get("concluida") or "") >= desde]
    gastos = sum(x["valor"] for x in jl(GASTOS, []) if x["data"] >= desde)
    hab = [c for c in jl(HABITOS, {"checkins": []})["checkins"] if c["d"] >= desde]
    est = [e for e in jl(ESTUDO, []) if e["data"] >= desde]
    return R(f"Nos últimos 7 dias: {len(feitas)} tarefas concluídas, {len(est)} sessões de estudo, {len(hab)} registros de hábitos"
             f" e {brl(gastos)} em gastos.")


@rota(r"\badiar (?:as\s+)?(?:tarefas\s+)?pendentes?\b")
def _adiar(m, t):
    tarefas, n = ler(), 0
    for x in tarefas:
        if x.get("data") == hoje_iso() and not x["feita"]:
            x["data"] = hoje_iso(1)
            n += 1
    gravar(tarefas)
    return R(f"Passei {n} tarefa(s) pendente(s) para amanhã.")


# ---- privacidade e senha falada
@rota(r"\bmodo privacidade\s*(ligar|ligado|ativar|desligar|desativar)?|\b(ligar|ativar|desligar|desativar)\s+(?:o\s+)?modo privacidade\b")
def _privacidade(m, t):
    acao = m.group(1) or m.group(2) or "ligar"
    on = acao in ("ligar", "ligado", "ativar")
    salvar_pref(privacidade=on)
    return R("Modo privacidade ligado: escondo seus dados na tela e não leio nada em voz alta." if on else "Modo privacidade desligado.",
             ui={"privacidade": on})


@rota(r"\bdefinir senha falada\s*[:=]?\s+(.+)")
def _senha(m, t):
    salvar_pref(senha_hash=hashlib.sha256(_sem_acento(m.group(1).strip(" .")).encode()).hexdigest())
    return R("Senha falada definida. Ela será pedida para ações sensíveis (desligar, reiniciar, commit). Dica: apague essa mensagem do histórico.")


@rota(r"\bremover senha falada\b")
def _senha_off(m, t):
    salvar_pref(senha_hash=None)
    return R("Senha falada removida.")


# ======================================================================
# EXTRAS (parte 5): alertas proativos (lembretes, bateria, chuva, pausa, hábitos, monitores, backup)
# ======================================================================
INICIO = time.time()


def chuva_proxima():
    st, d = _http("https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode({
        "latitude": CIDADE["lat"], "longitude": CIDADE["lon"], "timezone": "auto", "forecast_hours": 3,
        "hourly": "precipitation_probability"}))
    probs = d.get("hourly", {}).get("precipitation_probability", []) if st == 200 and isinstance(d, dict) else []
    return max([p or 0 for p in probs[:3]] or [0])


def a_cada(chave, minutos):
    """True a cada `minutos` (para checagens mais lentas dentro do agendador)."""
    if time.time() - ESTADO.setdefault("ult", {}).get(chave, 0) >= minutos * 60:
        ESTADO["ult"][chave] = time.time()
        return True
    return False


def verificar_alertas():
    agora = datetime.now()
    av = ESTADO.setdefault("avisados", set())
    for x in tarefas_do_dia()[0]:
        if x["feita"] or not x.get("hora"):
            continue
        faltam = (datetime.combine(agora.date(), datetime.strptime(x["hora"], "%H:%M").time()) - agora).total_seconds() / 60
        for chave, ok, msg in (("10", 9 <= faltam <= 10.5, f"Daqui a 10 minutos: {x['texto']}."),
                               ("0", -1 <= faltam <= 0.5, f"Hora da tarefa: {x['texto']}.")):
            if ok and (hoje_iso(), x["id"], chave) not in av:
                av.add((hoje_iso(), x["id"], chave))
                avisar(msg, "tarefa")
    if 6 <= agora.hour < 23:
        if (b := bateria()) is not None:
            if b[0] <= 20 and not b[1] and not ESTADO.get("bat_av"):
                avisar(f"A bateria está em {b[0]}%. Conecte o carregador.", "alerta")
                ESTADO["bat_av"] = True
            elif b[1]:
                ESTADO["bat_av"] = False
        if time.time() - ESTADO.get("ultima_pausa", INICIO) >= 7200:
            ESTADO["ultima_pausa"] = time.time()
            avisar("Você está há 2 horas sem pausa. Que tal levantar, beber água e alongar um pouco?", "alerta")
        if a_cada("chuva", 30) and chuva_proxima() >= 60 and time.time() - ESTADO.get("chuva_av", 0) > 3 * 3600:
            ESTADO["chuva_av"] = time.time()
            avisar(f"Pode chover em {CIDADE['nome']} nas próximas horas. Leve o guarda-chuva.", "alerta")
        dados = jl(HABITOS, {"checkins": [], "lembretes": {}})
        for h, cfg in dados["lembretes"].items():
            if 7 <= agora.hour < 22 and time.time() - cfg["ultimo"] >= cfg["cada"] * 60:
                cfg["ultimo"] = time.time()
                js(HABITOS, dados)
                avisar({"agua": "Hora de beber água!", "pausa": "Hora de uma pausa!", "alongamento": "Hora de alongar!"}[h], "habito")
    if a_cada("monitores", 5):
        mon = jl(MONITORES, {})
        for url, est in mon.items():
            ok = site_no_ar(url)
            if ok != est["ok"]:
                est["ok"] = ok
                avisar(f"O site {url} {'voltou ao ar' if ok else 'saiu do ar'}.", "alerta")
        js(MONITORES, mon)
    if agora.hour >= 20 and prefs().get("backup_auto") and projeto() and jl("backup_estado.json", "") != hoje_iso():
        js("backup_estado.json", hoje_iso())
        if backup_projeto():
            avisar("Fiz o backup diário do seu projeto.", "info")


def agendador():
    while True:
        try:
            verificar_alertas()
        except Exception as e:
            print("(agendador)", e)
        time.sleep(30)


# ======================================================================
# EXTRAS (parte 6): clima animado e gráfico de produtividade
# ======================================================================
def tipo_clima(codigo):
    return ("sol" if codigo in (0, 1) else "parcial" if codigo == 2 else "nublado" if codigo == 3 else
            "neblina" if codigo in (45, 48) else "trovoada" if codigo >= 95 else "chuva")


def clima_atual():
    """Clima de agora para a tela (cache de 10 minutos). None se falhar."""
    if ESTADO.get("clima") and time.time() - ESTADO.get("clima_t", 0) < 600:
        return ESTADO["clima"]
    try:
        st, d = _http("https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode({
            "latitude": CIDADE["lat"], "longitude": CIDADE["lon"], "timezone": "auto", "forecast_days": 1,
            "current": "temperature_2m,weather_code,is_day",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max"}))
        if st != 200 or not isinstance(d, dict):
            return ESTADO.get("clima")
        c, dia = d["current"], d["daily"]
        info = {"cidade": CIDADE["nome"], "temp": round(c["temperature_2m"]), "desc": CODIGOS_TEMPO.get(c["weather_code"], "tempo variável"),
                "tipo": tipo_clima(c["weather_code"]), "noite": not c.get("is_day", 1), "max": round(dia["temperature_2m_max"][0]),
                "min": round(dia["temperature_2m_min"][0]), "chuva": dia["precipitation_probability_max"][0] or 0}
        ESTADO["clima"], ESTADO["clima_t"] = info, time.time()
        return info
    except Exception:
        return ESTADO.get("clima")


def produtividade():
    """Tarefas concluídas, hábitos e estudo dos últimos 7 dias."""
    t, hab, est = ler(), jl(HABITOS, {"checkins": []})["checkins"], jl(ESTUDO, [])
    nomes = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
    dias = []
    for i in range(6, -1, -1):
        iso = hoje_iso(-i)
        dias.append({"data": iso, "rotulo": nomes[date.fromisoformat(iso).weekday()],
                     "tarefas": sum(1 for x in t if x.get("concluida") == iso),
                     "habitos": sum(1 for c in hab if c["d"] == iso), "estudo": sum(1 for e in est if e["data"] == iso)})
    return {"dias": dias, "hoje": dias[-1]["tarefas"], "total": sum(d["tarefas"] for d in dias),
            "habitos": sum(d["habitos"] for d in dias), "estudo": sum(d["estudo"] for d in dias)}


# ======================================================================
# EXTRAS (parte 7): concluir tarefas por nome
# ======================================================================
def achar_tarefas(alvo):
    """Tarefas pendentes que combinam com o número (da lista de hoje) ou com o texto dito. [(indice, tarefa)]"""
    alvo = alvo.strip(" .")
    hoje_itens, _ = tarefas_do_dia()
    if alvo.isdigit() or alvo in NUMEROS:
        n = int(alvo) if alvo.isdigit() else NUMEROS[alvo]
        return [(hoje_itens[n - 1]["id"], hoje_itens[n - 1])] if 1 <= n <= len(hoje_itens) else []
    palavras = [w for w in alvo.split() if w not in ("a", "o", "as", "os", "de", "da", "do", "tarefa", "de", "que")]
    if not palavras:
        return []
    casa = lambda x: all(w in _sem_acento(x["texto"]) for w in palavras)
    achadas = [(x["id"], x) for x in hoje_itens if not x["feita"] and casa(x)]
    return achadas or [(i, x) for i, x in enumerate(ler()) if not x.get("feita") and casa(x)]


CONCLUIDA = r"(?:concluida|feita|finalizada|completa|pronta|resolvida|ok)"


@rota(r"\b(marque|marcar|marca|conclua|concluir|conclui|finalize|finalizar|finalizei|complete|completar|completei|terminei|termine|terminar)\s+(?:a\s+|o\s+)?(tarefa\s+)?(.+?)(?:\s+como\s+" + CONCLUIDA + r")?\s*[.!]?\s*$")
def _concluir_por_nome(m, t):
    primeira_pessoa = m.group(1) in ("terminei", "finalizei", "completei", "conclui")
    if not (m.group(2) or primeira_pessoa or re.search(r"\bcomo\s+" + CONCLUIDA + r"\b", m.string)):
        return None                                   # "concluir o curso" sem a palavra tarefa: não é comando
    alvo = m.group(3).strip()
    achadas = achar_tarefas(alvo)
    if not achadas:
        return R(f"Não encontrei nenhuma tarefa pendente com \"{alvo}\". Diga: minhas tarefas, para ver a lista.")
    if len(achadas) > 1:
        return R("Achei mais de uma tarefa: " + "; ".join(f"{x['texto']} ({quando(x['data'], x.get('hora', ''))})" for _, x in achadas[:5]) +
                 ". Diga o nome completo ou: concluir tarefa <número>.")
    i, x = achadas[0]
    tarefas = ler()
    tarefas[i]["feita"] = True
    tarefas[i]["concluida"] = hoje_iso()
    gravar(tarefas)
    return R(f"Tarefa concluída: {x['texto']}. Parabéns!")


@rota(r"\b(?:desmarque|desmarcar|reabra|reabrir)\s+(?:a\s+)?(?:tarefa\s+)?(.+?)\s*[.!]?\s*$")
def _reabrir_tarefa(m, t):
    palavras = [w for w in m.group(1).split() if w not in ("a", "o", "de", "da", "do", "tarefa")]
    tarefas = ler()
    for i, x in enumerate(tarefas):
        if x.get("feita") and palavras and all(w in _sem_acento(x["texto"]) for w in palavras):
            x["feita"], x["concluida"] = False, None
            gravar(tarefas)
            return R(f"Reabri a tarefa: {x['texto']}.")
    return R("Não encontrei uma tarefa concluída com esse nome.")


# ======================================================================
# EXTRAS (parte 8): encerrar tudo junto (janela, Ollama e servidor)
# ======================================================================
JANELA = {"ping": 0.0, "fechar_em": None, "proc": None}


def matar_janela():
    """Fecha o Edge do Peter (o processo que abrimos e qualquer processo que use o perfil do Peter)."""
    try:
        ps("Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*" + str(PASTA / "perfil").replace("'", "''") +
           "*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }", timeout=15)
    except Exception:
        pass
    proc = JANELA.get("proc")
    if proc and proc.poll() is None:
        try:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True, timeout=10)
        except Exception:
            proc.kill()


def fechar_ollama():
    for nome in ("ollama app.exe", "ollama.exe", "ollama_llama_server.exe"):
        try:
            subprocess.run(["taskkill", "/F", "/T", "/IM", nome], capture_output=True, timeout=10)
        except Exception:
            pass


def fechar_tudo(motivo=""):
    if ESTADO.get("fechando"):
        return
    ESTADO["fechando"] = True
    print(f"Encerrando o Peter ({motivo})...")
    if FECHAR_JANELA:
        matar_janela()
    if FECHAR_OLLAMA:
        fechar_ollama()
    os._exit(0)


def vigia_janela():
    """Fecha tudo quando a janela do Peter some: aviso ao fechar (6 s de tolerância para recarregar) ou 2 minutos sem sinal."""
    ult_loop = time.time()
    while True:
        time.sleep(2)
        agora = time.time()
        if agora - ult_loop > 15:                    # o computador dormiu: recomeça a contagem
            JANELA["ping"] = agora
        ult_loop = agora
        if JANELA["fechar_em"] and agora >= JANELA["fechar_em"]:
            fechar_tudo("janela fechada")
        elif JANELA["ping"] and agora - JANELA["ping"] > 120:
            fechar_tudo("sem sinal da janela")


@rota(r"\b(?:encerrar|fechar|desligar|finalizar)\s+(?:o\s+)?(?:peter|tudo|assistente)\b|^\s*encerrar\s*$")
def _encerrar(m, t):
    threading.Timer(4.5, fechar_tudo, ["comando de voz"]).start()
    return R(f"Até logo, {USUARIO}! Estou fechando tudo.")


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
        if rota.path == "/api/avisos":
            return self.enviar(pegar_avisos())
        if rota.path == "/api/clima":
            return self.enviar(clima_atual() or {})
        if rota.path == "/api/produtividade":
            return self.enviar(produtividade())
        if rota.path == "/api/projeto":
            return self.enviar(info_projeto())
        if rota.path == "/api/sistema":
            return self.enviar(estado_sistema())
        if rota.path == "/api/prefs":
            p = prefs()
            return self.enviar({"privacidade": bool(p.get("privacidade")), "ingles": bool(p.get("ingles"))})
        if self.path == "/api/tarefas":
            itens, outras = tarefas_do_dia()
            return self.enviar({"hoje": itens, "outras": outras})
        self.enviar(HTML, "text/html")

    def do_POST(self):
        dados = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        if self.path == "/api/chat":
            return responder_stream(self, dados) if dados.get("stream") else self.enviar(responder(dados))
        if self.path == "/api/ping":
            JANELA["ping"], JANELA["fechar_em"] = time.time(), None
            return self.enviar({"ok": True})
        if self.path == "/api/fechar":
            JANELA["fechar_em"] = time.time() + 6
            return self.enviar({"ok": True})
        if self.path == "/api/abrir":
            url = str(dados.get("url", ""))
            return self.enviar({"ok": url.startswith(("http://", "https://")) and abrir_url(url)})
        if self.path == "/api/ditar":
            return self.enviar({"ok": colar_texto(dados.get("texto", ""))})
        t = ler()
        if self.path == "/api/tarefas":
            texto_t, dia, hora = interpretar_tarefa(dados["texto"])
            t.append({"texto": texto_t, "feita": False, "data": dia, "hora": hora,
                      "criada": datetime.now().isoformat(timespec="minutes")})
        elif m := re.fullmatch(r"/api/tarefas/(\d+)/alternar", self.path):
            if int(m.group(1)) < len(t):
                x = t[int(m.group(1))]
                x["feita"] = not x["feita"]
                x["concluida"] = f"{datetime.now():%Y-%m-%d}" if x["feita"] else None
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
            JANELA["proc"] = subprocess.Popen([str(exe), f"--app={url}", "--autoplay-policy=no-user-gesture-required",
                                               f"--user-data-dir={PASTA / 'perfil'}", "--no-first-run",
                                               "--no-default-browser-check", "--disable-background-mode"])
            return
    webbrowser.open(url)


if __name__ == "__main__":
    print(f"JARVIS v2 rodando em http://localhost:{PORTA}  (Ctrl+C para sair)")
    if HORA_TESTE is not None:
        print(f"*** MODO TESTE: fingindo que são {HORA_TESTE}h para o briefing e as saudações ***")
    threading.Thread(target=garantir_ollama, daemon=True).start()
    threading.Thread(target=apps_iniciar, daemon=True).start()
    threading.Thread(target=agendador, daemon=True).start()
    threading.Thread(target=vigia_janela, daemon=True).start()
    if sys.platform == "win32":
        threading.Thread(target=atalho_global, daemon=True).start()
    threading.Timer(1.2, abrir_janela).start()
    try:
        ThreadingHTTPServer(("127.0.0.1", PORTA), Handler).serve_forever()
    except KeyboardInterrupt:
        fechar_tudo("Ctrl+C")