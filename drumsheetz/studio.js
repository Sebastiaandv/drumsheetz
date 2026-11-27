/* Drumsheetz Studio — kern: tabbladen, editor, controleren, voorbeeld, paneel, statusbalk, palet, verkenner,
   overzicht, eigenschappen, versies, invoegen en help. De zijbalk-weergaven GitLab, forScore, Setlists, Status
   en de setlist-bouwer staan in views.js. */
"use strict";
const $ = (s, el=document) => el.querySelector(s);
const $$ = (s, el=document) => [...el.querySelectorAll(s)];
const ed = $("#editor"), hl = $("#hl"), gut = $("#gutter");
const esc = s => String(s ?? "").replace(/[&<>"']/g, c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const isMac = /Mac|iPhone|iPad/.test(navigator.platform);
const MOD = isMac ? "⌘" : "Ctrl+";
const store = {
  get(k, d){ try{ const v = localStorage.getItem("ds-"+k); return v===null ? d : JSON.parse(v); }catch(e){ return d; } },
  set(k, v){ try{ localStorage.setItem("ds-"+k, JSON.stringify(v)); }catch(e){} }
};

/* ------------------------------------------------------------ api en meldingen */
async function api(url, body){
  const opt = body===undefined ? {} : {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)};
  const r = await fetch(url, opt);
  let j; try{ j = await r.json(); }catch(e){ throw new Error(r.status+" "+r.statusText); }
  if(!r.ok) throw new Error(j.error || r.statusText);
  return j;
}
function toast(msg){ const t=$("#toast"); t.textContent=msg; t.classList.add("show"); clearTimeout(t._h); t._h=setTimeout(()=>t.classList.remove("show"), Math.max(2400, 45*String(msg).length)); }
function busy(on, msg){ $("#busyMsg").textContent = msg||"Bezig…"; $("#busy").classList.toggle("show", !!on); }
function log(text, show=true){ $("#logOut").textContent = text || "(geen uitvoer)"; if(show){ showPanel(true); panelTab("log"); } }
function fmtDur(s){ if(s==null || isNaN(s)) return "?"; s=Math.round(s); return s>=3600 ? `${Math.floor(s/3600)}:${String(Math.floor(s%3600/60)).padStart(2,"0")}:${String(s%60).padStart(2,"0")}` : `${Math.floor(s/60)}:${String(s%60).padStart(2,"0")}`; }
function fmtTime(t){ return new Date(t*1000).toLocaleString("nl-NL",{day:"2-digit",month:"2-digit",year:"numeric",hour:"2-digit",minute:"2-digit"}); }
function ago(t){ if(!t) return ""; const d=Math.round(Date.now()/1000-t); if(d<90) return "zojuist"; if(d<3600) return Math.round(d/60)+" min geleden";
  if(d<86400) return Math.round(d/3600)+" uur geleden"; return new Date(t*1000).toLocaleDateString("nl-NL"); }
const urlOf = p => "/"+p.split("/").map(encodeURIComponent).join("/");
const parentOf = p => p.includes("/") ? p.slice(0, p.lastIndexOf("/")) : "";
const baseOf = p => p.slice(p.lastIndexOf("/")+1);
const nameOf = p => baseOf(p).replace(/\.(drum|txt)$/,"");

/* ------------------------------------------------------------ tabbladen (open bestanden) */
const TABS = [];
let state = null;                      // het actieve tabblad
let H = {stack:[], i:-1, t:0, force:false};
function newModel(path, kind, content){
  return {path, kind, content, saved:content, hist:{stack:[{v:content,s:0,e:0}], i:0, t:0, force:false},
          sel:[0,0], scroll:[0,0], errLine:null, lastCheck:null, pdf:null, preview:false,
          view: kind==="setlist" ? store.get("setlistView","builder") : "text"};
}
function dirty(m=state){ if(!m) return false; return (m===state ? ed.value : m.content) !== m.saved; }
function stash(){ if(!state) return; state.content=ed.value; state.sel=[ed.selectionStart, ed.selectionEnd]; state.scroll=[ed.scrollTop, ed.scrollLeft]; }
function persistTabs(){ store.set("tabs", TABS.filter(t=>!t.preview || t===state).map(t=>t.path)); store.set("active", state ? state.path : null); }
function activate(m, opts={}){
  if(state===m && !opts.force){ return; }
  stash();
  state = m; H = m ? m.hist : {stack:[],i:-1,t:0,force:false};
  if(m){
    ed.value = m.content; ed.setSelectionRange(m.sel[0], m.sel[1]);
    ed.scrollTop = m.scroll[0]; ed.scrollLeft = m.scroll[1];
  } else ed.value = "";
  closeFind(false);
  $("#welcome").style.display = m ? "none" : "grid";
  render(); drawTabs(); updateUI(); cursorPos(); drawTree(); drawOutline();
  showPdfOf(m);
  if(m){ if(m.lastCheck) applyCheck(m.lastCheck); else setProblems([]); check(); }
  else { setProblems([]); $("#tabOut").innerHTML='<span class="hint">Hier verschijnt het nummer als drumtab terwijl je typt.</span>'; $("#sbInfo").textContent=""; }
  refreshSongView();
  if(typeof builderSync==="function") builderSync();
  persistTabs();
  if(m && !opts.nofocus && !isBuilder()) setTimeout(()=>ed.focus(), 0);
}
const OPENING = new Map();         // bestanden die nu worden opgehaald (dubbelklik = niet twee keer openen)
async function openFile(path, opts={}){
  const pinned = !!opts.pinned;
  if(OPENING.has(path)){ await OPENING.get(path).catch(()=>{}); }
  let m = TABS.find(t=>t.path===path);
  if(!m){
    let j;
    const req = api("/api/file?path="+encodeURIComponent(path));
    OPENING.set(path, req);
    try{ j = await req; }
    catch(err){ toast(err.message); return null; }
    finally{ OPENING.delete(path); }
    m = TABS.find(t=>t.path===path);
    if(m){ if(pinned) m.preview=false; activate(m, {force:true, nofocus:opts.nofocus}); if(opts.line) gotoLine(opts.line); return m; }
    m = newModel(j.path, j.kind, j.content);
    m.preview = !pinned;
    const reuse = !pinned ? TABS.findIndex(t=>t.preview && !dirty(t)) : -1;
    if(reuse>=0) TABS.splice(reuse, 1, m);
    else { const at = state ? TABS.indexOf(state)+1 : TABS.length; TABS.splice(at, 0, m); }
  } else if(pinned) m.preview = false;
  activate(m, {force:true, nofocus:opts.nofocus});
  if(opts.line) gotoLine(opts.line);
  try{ const rec = store.get("recent", []).filter(p=>p!==path); rec.unshift(path); store.set("recent", rec.slice(0, 30)); }catch(e){}
  return m;
}
function pin(m){ if(m && m.preview){ m.preview=false; drawTabs(); persistTabs(); } }
function ask(dlg){ return new Promise(res=>{ const d=$(dlg); const f=d.querySelector("form"); f.reset?.(); d.showModal();
  d.addEventListener("close", ()=>res(d.returnValue==="ok" ? Object.fromEntries(new FormData(f)) : (d.returnValue||null)), {once:true}); }); }
async function closeTab(m){
  if(!m) return true;
  if(dirty(m)){
    if(m!==state) activate(m);
    $("#closeTitle").textContent = `Wijzigingen in '${baseOf(m.path)}' opslaan?`;
    const r = await ask("#dlgClose");
    if(r==="save"){ if(!(await saveModel(m))) return false; }
    else if(r!=="discard") return false;
  }
  const i = TABS.indexOf(m); TABS.splice(i, 1);
  if(state===m){ state=null; activate(TABS[i] || TABS[i-1] || null, {force:true}); }
  else { drawTabs(); persistTabs(); }
  return true;
}
async function closeOthers(m){ for(const t of [...TABS]) if(t!==m && !(await closeTab(t))) return; }
function drawTabs(){
  $("#tabs").innerHTML = TABS.map((t,i)=>{
    const ic = t.kind==="setlist" ? "☰" : t.path.endsWith(".drum") ? "♩" : t.path.endsWith(".md") ? "?" : "⚙";
    return `<div class="etab${t===state?" on":""}${t.preview?" preview":""}${dirty(t)?" dirty":""}" data-i="${i}" draggable="true" title="${esc(t.path)}">
      <span class="ic">${ic}</span><span class="nm">${esc(nameOf(t.path))}</span><span class="x" data-close="${i}" title="Sluiten (${isMac?"⌥":"Alt+"}W)"><span>✕</span></span></div>`;
  }).join("");
  const on = $("#tabs .etab.on"); if(on) on.scrollIntoView({block:"nearest", inline:"nearest"});
}
$("#tabs").addEventListener("click", e=>{
  const x = e.target.closest("[data-close]"); if(x){ e.stopPropagation(); closeTab(TABS[+x.dataset.close]); return; }
  const t = e.target.closest(".etab"); if(t) activate(TABS[+t.dataset.i]);
});
$("#tabs").addEventListener("auxclick", e=>{ const t=e.target.closest(".etab"); if(t && e.button===1){ e.preventDefault(); closeTab(TABS[+t.dataset.i]); } });
$("#tabs").addEventListener("dblclick", e=>{ const t=e.target.closest(".etab"); if(t) pin(TABS[+t.dataset.i]); });
$("#tabs").addEventListener("contextmenu", e=>{ const t=e.target.closest(".etab"); if(!t) return; e.preventDefault(); const m=TABS[+t.dataset.i];
  showMenu(e.clientX, e.clientY, [
    ["Sluiten", ()=>closeTab(m), (isMac?"⌥":"Alt+")+"W"], ["Andere sluiten", ()=>closeOthers(m)], ["Alles sluiten", ()=>closeOthers(null)], "-",
    ["Vastzetten", ()=>pin(m), "", !m.preview], ["Toon in verkenner", ()=>revealInTree(m.path)], ["Pad kopiëren", ()=>navigator.clipboard?.writeText(m.path)]]); });
let dragTab = null;
$("#tabs").addEventListener("dragstart", e=>{ const t=e.target.closest(".etab"); if(t){ dragTab=+t.dataset.i; e.dataTransfer.effectAllowed="move"; e.dataTransfer.setData("text/x-ds-tab", t.dataset.i); } });
$("#tabs").addEventListener("dragover", e=>{ if(dragTab===null) return; const t=e.target.closest(".etab"); if(!t) return; e.preventDefault(); $$(".etab.drag-over").forEach(x=>x.classList.remove("drag-over")); t.classList.add("drag-over"); });
$("#tabs").addEventListener("drop", e=>{ const t=e.target.closest(".etab"); if(t===null || dragTab===null) return; e.preventDefault();
  const to=+t.dataset.i; const [m]=TABS.splice(dragTab,1); TABS.splice(to,0,m); dragTab=null; drawTabs(); persistTabs(); });
$("#tabs").addEventListener("dragend", ()=>{ dragTab=null; $$(".etab.drag-over").forEach(x=>x.classList.remove("drag-over")); });
function nextTab(d){ if(!TABS.length) return; const i=(TABS.indexOf(state)+d+TABS.length)%TABS.length; activate(TABS[i]); }

/* ------------------------------------------------------------ syntax-kleuring */
const OPTS = new Set(("crash china splash crash2 stack fill fills ppp pp p mp mf f ff fff sfz sf fp sfp rfz cresc dim decresc < > "+
  "rit rall accel a-tempo tempo-primo halftime doubletime fermata uitgeschreven herhaal volta segno coda fine naar-coda ds "+
  "ds-al-coda ds-al-fine dc dc-al-coda dc-al-fine nieuweregel nieuwepagina doorlopen einde klein groot normaal heelklein "+
  "heelgroot tacet rust tijd vrij maten maat halftime doubletime half-time double-time").split(" "));
function splitComment(line){
  let q=false;
  for(let i=0;i<line.length;i++){ const c=line[i]; if(c==='"') q=!q; else if(c==="#"&&!q) return [line.slice(0,i), line.slice(i)]; }
  return [line,""];
}
function hlGrid(s){
  return s.replace(/[^\s]/g, c=>{
    if(c==="x") return '<span class="k-hit">x</span>';
    if("X^FDZTOBK".includes(c)) return '<span class="k-acc">'+esc(c)+'</span>';
    if(c==="g") return '<span class="k-ghost">g</span>';
    if("-._".includes(c)) return '<span class="k-rest">'+c+'</span>';
    if(c==="|") return '<span class="k-bar">|</span>';
    if(!"fdrzthoc@bk+".includes(c)) return '<span class="k-bad" title="dit teken bestaat niet in een raster">'+esc(c)+'</span>';
    return '<span class="k-mod">'+esc(c)+'</span>';
  });
}
function hlRowValue(v){
  if(/[0-9*!]/.test(v.replace(/\|\|/g,""))){
    return v.split(/(\s+)/).map(t=>{
      if(/^\s+$/.test(t)||!t) return t;
      const m=t.match(/^(!?)([^:]*)(:?)(.*)$/);
      return (m[1]?'<span class="k-acc">!</span>':"")+'<span class="k-num">'+esc(m[2])+'</span>'+(m[3]?'<span class="k-rest">:</span>'+hlGrid(m[4]):"");
    }).join("");
  }
  return hlGrid(v);
}
function hlPhase(s){
  let out="", first=true;
  const toks = s.match(/("[^"]*"?|\{[^}]*\}?|\s+|[^\s"{]+)/g)||[];
  for(const t of toks){
    if(/^\s+$/.test(t)){ out+=t; continue; }
    if(t[0]==='"') out+='<span class="k-str">'+esc(t)+'</span>';
    else if(t[0]==="{") out+='<span class="k-name">'+esc(t)+'</span>';
    else if(first && /^\d+x?$/i.test(t)) out+='<span class="k-num">'+esc(t)+'</span>';
    else if(OPTS.has(t.toLowerCase()) || /=/.test(t) || /^\d+x$/i.test(t)) out+='<span class="k-opt">'+esc(t)+'</span>';
    else out+='<span class="k-name">'+esc(t)+'</span>';
    first=false;
  }
  return out;
}
function hlLine(line, inPattern){
  const [code, com] = splitComment(line);
  let h, m;
  if((m=code.match(/^(\s*)\[([^\]]*)\](.*)$/))) h = esc(m[1])+'<span class="k-sec">['+esc(m[2])+']</span>'+hlPhase(m[3]);
  else if((m=code.match(/^(groove|fill|patroon|pattern|ritme)(\s+)([^\s=:]+)(.*)$/i)))
    h = '<span class="k-kw">'+m[1]+'</span>'+m[2]+(USED.used.has(m[3]) ? '<span class="k-name">'+esc(m[3])+'</span>'
      : '<span class="k-unused" title="wordt nergens in de opbouw gebruikt">'+esc(m[3])+'</span>')+esc(m[4]);
  else if((m=code.match(/^(instrument|kit)(\s+)(.*)$/i))) h='<span class="k-kw">'+m[1]+'</span>'+m[2]+esc(m[3]);
  else if(inPattern && (m=code.match(/^(\s*)([A-Za-z][\w\-]*)(\s*:\s*)(.*)$/))){
    const isOpt = /^(info|maten|maat|basis|bars|meter|base|uitleg|doc)$/i.test(m[2]);
    h = esc(m[1])+'<span class="'+(isOpt?"k-key":"k-inst")+'">'+esc(m[2])+'</span>'+esc(m[3])+(isOpt?esc(m[4]):hlRowValue(m[4]));
  }
  else if((m=code.match(/^([A-Za-z][\w\-]*)(\s*:)(.*)$/))) h='<span class="k-key">'+esc(m[1])+'</span>'+esc(m[2])+'<span class="k-str">'+esc(m[3])+'</span>';
  else if(/^\s*\d/.test(code)) h = hlPhase(code);
  else if(/^\s+\S/.test(code) && !inPattern) h = hlPhase(code);
  else h = esc(code);
  return h + (com?'<span class="k-com">'+esc(com)+'</span>':"");
}
function usedPatterns(lines){
  const defs={}, used=new Set(); let inPattern=false, cur=null;
  const OPT=/^(crash|china|splash|crash2|stack|fill|fills|tacet|rust|tijd|vrij|maten|maat)$/i;
  for(const raw of lines){
    const code=splitComment(raw)[0];
    let m=code.match(/^(groove|fill|patroon|pattern|ritme)\s+([^\s=:]+)(?:\s*=\s*([^\s:]+))?/i);
    if(m){ inPattern=true; cur=m[2]; defs[cur]=new Set(m[3]?[m[3]]:[]); continue; }
    if(inPattern && (/^\s/.test(code) || /^[A-Za-z][\w\-]*\s*:/.test(code) || !code.trim())){
      const b=code.match(/^\s*(basis|base)\s*:\s*(\S+)/i); if(b&&cur) defs[cur].add(b[2]); continue; }
    inPattern=false;
    const ph=code.match(/^\s*(?:\[[^\]]*\]\s*)?\d+x?\s+(?:maten?\s+)?([^\s"{]+)/i);
    if(ph && !OPT.test(ph[1])) used.add(ph[1]);
    for(const f of code.matchAll(/\bfills?\s*[=: ]\s*([^\s"]+)/gi)) f[1].split(",").forEach(x=>x&&used.add(x));
    for(const b of code.matchAll(/(?:basis|base)\s*:\s*([^;}\s]+)/gi)) used.add(b[1]);
  }
  let grow=true; while(grow){ grow=false; for(const n of [...used]) for(const b of (defs[n]||[])) if(!used.has(b)){ used.add(b); grow=true; } }
  return {used, defs};
}
let USED={used:new Set(),defs:{}};
let KITSET=new Set(["BD","SD","HH","RD","CR","T1","T2","T3","FT"]);
let curLine = 1;
function render(){
  const lines = ed.value.split("\n");
  USED = usedPatterns(lines);
  let inPattern=false, html="", g="";
  const plain = !state || ["text","settings"].includes(state.kind) || /\.(py|md)$/.test(state.path);
  lines.forEach((ln,i)=>{
    const code = splitComment(ln)[0];
    if(/^(groove|fill|patroon|pattern|ritme)\s/i.test(code)) inPattern = true;
    else if(code.trim() && !/^\s/.test(code)){
      const km = code.match(/^([A-Za-z][\w\-]*)\s*:/);
      if(!km || !(KITSET.has(km[1].toUpperCase()) || /^(maten|maat|basis|base|info|uitleg|doc|bars|meter|st|stick|sticking|plak|hand|handen)$/i.test(km[1]))) inPattern = false;
    }
    const err = state && state.errLine===i+1;
    const body = plain ? esc(ln) : hlLine(ln, inPattern && !/^(groove|fill|patroon|pattern|ritme)\s/i.test(code));
    html += '<span class="l'+(err?" err":"")+(i+1===curLine?" curl":"")+'">'+(body||"​")+'</span>';
    g += '<div class="'+(err?"err":"")+(i+1===curLine?" cur":"")+'">'+(i+1)+'</div>';
  });
  hl.innerHTML = html; gut.innerHTML = g; renderFind(); syncScroll();
}
function syncScroll(){
  hl.style.transform = `translate(${-ed.scrollLeft}px,${-ed.scrollTop}px)`;
  $("#findhl").style.transform = hl.style.transform;
  gut.scrollTop = ed.scrollTop;
}

/* ------------------------------------------------------------ ongedaan maken (eigen geschiedenis per tabblad) */
function histRecord(force){
  if(!state) return;
  const snap={v:ed.value,s:ed.selectionStart,e:ed.selectionEnd};
  if(H.i>=0 && H.stack[H.i].v===snap.v) return;
  const now=Date.now();
  if(!force && !H.force && H.i>0 && now-H.t<700){ H.stack[H.i]=snap; }
  else { H.stack=H.stack.slice(0,H.i+1); H.stack.push(snap); H.i++; if(H.stack.length>500){ H.stack.shift(); H.i--; } }
  H.t=now; H.force=false;
}
function histApply(d){
  if(!state) return;
  histRecord(true);
  const j=H.i+d; if(j<0||j>=H.stack.length){ toast(d<0?"Niets meer om ongedaan te maken":"Niets meer om opnieuw te doen"); return; }
  H.i=j; const s=H.stack[j];
  ed.value=s.v; if(!isBuilder()){ ed.focus(); } ed.setSelectionRange(s.s,s.e);
  afterChange(); H.t=0;
}
/* alles wat moet gebeuren na een wijziging van de tekst (typen, invoegen, bouwer, eigenschappen, ongedaan maken) */
function afterChange(){
  if(!state) return;
  state.content = ed.value;
  if(state.preview){ state.preview=false; }
  render(); updateUI(); scheduleCheck(); cursorPos();
  clearTimeout(afterChange._t); afterChange._t=setTimeout(()=>{ refreshDoc(); drawOutline(); }, 350);
  if(typeof builderChanged==="function") builderChanged();
}
function setContent(text){
  if(!state) return;
  histRecord(true); H.force=true;
  const sel=ed.selectionStart; ed.value=text; ed.setSelectionRange(Math.min(sel,text.length), Math.min(sel,text.length));
  histRecord(true);
  afterChange();
}

/* ------------------------------------------------------------ editor gedrag */
function updateUI(){
  const k = state ? state.kind : null, can = k==="song"||k==="setlist"||k==="library";
  $("#aBuild").disabled = !can;
  $("#aBuild").title = k==="setlist" ? "Maak setlist: PDF's, boek, voorblad (⌘↵)" : k==="library" ? "Maak catalogus (⌘↵)" : "Maak PDF (⌘↵)";
  $("#aView").style.display = k==="setlist" ? "" : "none";
  $("#aView").title = isBuilder() ? "Toon als tekst" : "Toon de setlist-bouwer";
  $("#aView").classList.toggle("on", !isBuilder() && k==="setlist");
  $("#aPreview").classList.toggle("on", $("#area").classList.contains("withpreview"));
  $("#aPreview").disabled = !state;
  $$(".etab").forEach((el,i)=>{ const t=TABS[i]; if(t) el.classList.toggle("dirty", dirty(t)); });
  document.title = (state ? (dirty()?"● ":"")+nameOf(state.path)+" — " : "") + "Drumsheetz Studio";
  drawCrumbs();
}
ed.addEventListener("scroll", syncScroll);
ed.addEventListener("input", ()=>{ histRecord(); afterChange(); });
ed.addEventListener("keyup", cursorPos); ed.addEventListener("click", cursorPos);
ed.addEventListener("focus", ()=>{ if(state && state.preview && dirty()) pin(state); });
function cursorPos(){
  const before = ed.value.slice(0, ed.selectionStart).split("\n");
  const line = before.length;
  $("#sbPos").textContent = `r ${line}, k ${before[before.length-1].length+1}`;
  if(line!==curLine){ curLine=line; render(); drawCrumbs(); markOutline(); }
}
ed.addEventListener("keydown", e=>{
  if(e.key==="Tab" && !e.metaKey && !e.ctrlKey){
    e.preventDefault();
    const a=ed.selectionStart, b=ed.selectionEnd;
    if(a!==b && ed.value.slice(a,b).includes("\n")){            // meerdere regels inspringen / terug
      const start=ed.value.lastIndexOf("\n", a-1)+1, block=ed.value.slice(start,b);
      const nb = e.shiftKey ? block.replace(/^ {1,2}/gm,"") : block.replace(/^/gm,"  ");
      histRecord(true); ed.setRangeText(nb, start, b, "select"); histRecord(true); afterChange();
    } else if(e.shiftKey){
      const start=ed.value.lastIndexOf("\n", a-1)+1;
      if(ed.value.slice(start,start+2)==="  "){ histRecord(true); ed.setRangeText("", start, start+2, "end"); afterChange(); }
    } else insertText("  ");
  }
  else if(e.key==="Enter" && !e.metaKey && !e.ctrlKey){
    const before = ed.value.slice(0, ed.selectionStart); const line = before.split("\n").pop();
    let ind = (line.match(/^\s*/)||[""])[0];
    if(/^(groove|fill|patroon)\s.*:\s*$/i.test(line) || /^\[[^\]]*\]\s*$/.test(line)) ind = "  ";
    e.preventDefault(); insertText("\n"+ind);
  }
});
function insertText(t, selectInside){
  if(!state){ toast("Open eerst een bestand"); return; }
  if(isBuilder()){ toast("Schakel naar de tekst (⟨/⟩) om tekst in te voegen"); return; }
  ed.focus();
  const a=ed.selectionStart, b=ed.selectionEnd;
  histRecord(true); H.force=true;
  ed.setRangeText(t, a, b, "end");
  if(selectInside){ const i=t.indexOf(selectInside); if(i>=0) ed.setSelectionRange(a+i, a+i+selectInside.length); }
  histRecord(true); afterChange();
}
function insertWord(w){ const a=ed.selectionStart, prev=ed.value[a-1]; insertText((prev && !/\s/.test(prev) ? " " : "")+w+" "); }
function gotoLine(n){
  if(isBuilder()) setSetlistView("text");
  const lines = ed.value.split("\n"); let pos=0;
  n = Math.max(1, Math.min(n, lines.length));
  for(let i=0;i<n-1;i++) pos+=lines[i].length+1;
  ed.focus(); ed.setSelectionRange(pos, pos+(lines[n-1]||"").length);
  ed.scrollTop = Math.max(0,(n-6)*20); syncScroll(); cursorPos();
}
window.addEventListener("beforeunload", e=>{ stash(); if(TABS.some(t=>dirty(t))){ e.preventDefault(); e.returnValue=""; } });

/* ------------------------------------------------------------ opslaan, controleren, maken */
async function saveModel(m=state){
  if(!m) return false;
  if(m===state) stash();
  try{ await api("/api/save",{path:m.path, content:m.content}); m.saved=m.content; pin(m); updateUI(); drawTabs(); toast("Opgeslagen");
    refreshSongView(); if(typeof onSaved==="function") onSaved(m); return true; }
  catch(err){ toast("Opslaan mislukt: "+err.message); return false; }
}
const save = ()=>saveModel(state);
async function saveAll(){ for(const t of TABS) if(dirty(t)) await saveModel(t); }
let checkTimer=null;
function scheduleCheck(){ clearTimeout(checkTimer); checkTimer=setTimeout(check, 450); }
async function check(){
  const m = state;
  if(!m || !["song","setlist","library"].includes(m.kind)){
    $("#sbInfo").textContent=""; $("#tabOut").innerHTML='<span class="hint">Geen controle voor dit bestand.</span>'; setProblems([]); return;
  }
  const content = ed.value;
  let j; try{ j = await api("/api/check",{path:m.path, content}); }catch(err){ return; }
  if(m!==state) { m.lastCheck=j; return; }
  m.lastCheck = j; applyCheck(j);
}
function applyCheck(j){
  const m = state; if(!m) return;
  const prev = m.errLine; m.errLine = j.ok ? null : j.line;
  if(prev!==m.errLine) render();
  const probs = [];
  if(!j.ok) probs.push({lvl:"err", msg:j.error, line:j.line});
  (j.warnings||[]).forEach(w=>probs.push({lvl:"warn", msg:w}));
  setProblems(probs);
  if(j.ok) $("#tabOut").textContent = j.tab || "";
  $("#sbInfo").textContent = j.info || "";
  if(j.kind==="song" && j.pdf && !m.pdf){ m.pdf = "uitvoer/pdf/"+j.id+".pdf"; showPdfOf(m); }
}
function setProblems(list){
  const b=$("#probBadge"); b.textContent=list.length; b.className = "badge" + (list.length? (list.some(p=>p.lvl==="err")?"":" warn") : " zero");
  $("#p-prob").innerHTML = list.length ? list.map(p=>
    `<div class="problem ${p.lvl}" ${p.line?`data-line="${p.line}"`:""}><span class="lvl">${p.lvl==="err"?"✗":"!"}</span>`+
    `<span>${esc(p.msg)}${p.line?` <span class="hint">[regel ${p.line}]</span>`:""}</span></div>`).join("") : '<div class="okmsg">Geen problemen gevonden.</div>';
  const e=list.filter(p=>p.lvl==="err").length, w=list.length-e;
  $("#sbProbT").innerHTML = !state ? "" : (e||w) ? `${e?`<span class="e">✗ ${e}</span>`:""} ${w?`<span class="w">! ${w}</span>`:""}` : '<span class="g">✓</span>';
}
$("#p-prob").addEventListener("click", e=>{ const p=e.target.closest(".problem"); if(p&&p.dataset.line) gotoLine(+p.dataset.line); });
async function build(){
  if(!state || $("#aBuild").disabled) return;
  const m = state; stash();
  busy(true, m.kind==="setlist" ? "Setlist maken (nummers, boek, voorblad)…" : "MuseScore maakt de PDF…");
  try{
    const j = await api("/api/build",{path:m.path, content:m.content});
    m.saved = m.content; pin(m); updateUI(); drawTabs();
    log(j.log||"", !j.pdf || !j.ok);
    if(j.pdf){ m.pdf=j.pdf; showPreview(true); showPdfOf(m, true); toast(j.ok?"PDF gemaakt":"Klaar, met meldingen (zie Uitvoer)"); }
    else toast(j.ok?"Klaar":"Mislukt, zie Uitvoer");
    check(); refreshSongView(); if(typeof onSaved==="function") onSaved(m);
  }catch(err){ log(err.message); toast("Mislukt: "+err.message); }
  finally{ busy(false); }
}
async function midi(){
  if(!state || state.kind!=="song") return;
  const v = await ask("#dlgMidi"); if(!v || typeof v!=="object") return;
  if(dirty()) await save();
  busy(true,"MIDI maken…");
  try{ const j=await api("/api/midi",{path:state.path, tempo:v.tempo, countin:v.countin, click:!!v.click});
    log(j.log, !j.ok); if(j.ok){ const a=document.createElement("a"); a.href=urlOf(j.midi); a.download=""; a.click(); toast("MIDI gemaakt"); } else toast("Mislukt (zie Uitvoer)"); }
  catch(err){ toast(err.message); } finally{ busy(false); }
}
async function archiveSong(path){
  path = path || (state && state.path);
  if(!path || !path.startsWith("nummers/")) return;
  if(!confirm(`'${baseOf(path)}' (en de PDF's) naar archief/ verplaatsen?`)) return;
  const open = TABS.find(t=>t.path===path);
  if(open && dirty(open) && !(await saveModel(open))) return;
  const j = await api("/api/archive",{path}); log(j.log, !j.ok); toast(j.ok?"Gearchiveerd":"Mislukt");
  if(j.ok){ if(open){ if(open===state) stash(); open.saved=open.content; await closeTab(open); } loadTree(); }
}

/* ------------------------------------------------------------ voorbeeld (PDF naast de editor) */
function showPreview(on){
  const a=$("#area"); a.classList.toggle("withpreview", on===undefined ? !a.classList.contains("withpreview") : on);
  store.set("preview", a.classList.contains("withpreview")); updateUI(); showPdfOf(state);
}
function showPdfOf(m, reload){
  const f=$("#pdfFrame"), has = m && m.pdf;
  $("#pvTitle").textContent = m ? (m.kind==="setlist" ? "Voorbeeld" : "PDF · "+nameOf(m.path)) : "Voorbeeld";
  if(!$("#area").classList.contains("withpreview")) return;
  if(has){
    const src = urlOf(m.pdf);
    if(reload || !f.dataset.src || f.dataset.src!==src){ f.src = src+"?t="+Date.now(); f.dataset.src = src; }
    f.style.display="block"; $("#pvEmpty").style.display="none";
  } else { f.style.display="none"; f.removeAttribute("src"); delete f.dataset.src; $("#pvEmpty").style.display="grid";
    $("#pvEmpty").innerHTML = !m ? "Open een nummer." : (["song","setlist","library"].includes(m.kind) ? "Nog geen PDF van dit bestand.<br>Klik op ▶ (of "+MOD+"↵) om hem te maken." : "Geen voorbeeld voor dit bestand."); }
}
$("#pvClose").onclick = ()=>showPreview(false);
$("#pvBuild").onclick = build;
$("#pvOpen").onclick = ()=>{ if(state && state.pdf) window.open(urlOf(state.pdf)+"?t="+Date.now(), "_blank"); };

/* ------------------------------------------------------------ paneel onderin */
function showPanel(on){ const w=$("#work"); w.classList.toggle("nopanel", on===undefined ? !w.classList.contains("nopanel") : !on); store.set("panel", !w.classList.contains("nopanel")); }
function panelTab(p){ $$(".ptab").forEach(x=>x.classList.toggle("on", x.dataset.p===p)); $$(".pbody").forEach(x=>x.classList.toggle("on", x.id==="p-"+p)); store.set("ptab", p); }
$("#ptabs").addEventListener("click", e=>{ const t=e.target.closest(".ptab"); if(t) panelTab(t.dataset.p); });
$("#panelClose").onclick = ()=>showPanel(false);

/* ------------------------------------------------------------ zijbalk en weergaven */
let VIEW = null;
const VIEW_HOOKS = {};             // views.js zet hier per weergave een functie die bij het tonen wordt aangeroepen
function setView(v, toggle){
  const app=$("#app");
  if(toggle && VIEW===v && !app.classList.contains("noside")){ app.classList.add("noside"); store.set("side", false); return; }
  VIEW=v; app.classList.remove("noside"); store.set("side", true); store.set("view", v);
  $$(".act[data-view]").forEach(a=>a.classList.toggle("on", a.dataset.view===v));
  $$(".view").forEach(x=>x.classList.toggle("on", x.id==="v-"+v));
  if(VIEW_HOOKS[v]) VIEW_HOOKS[v]();
}
function toggleSide(){ const app=$("#app"); app.classList.toggle("noside"); store.set("side", !app.classList.contains("noside")); }
$("#activity").addEventListener("click", e=>{ const a=e.target.closest(".act[data-view]"); if(a) setView(a.dataset.view, true); });
$("#side").addEventListener("click", e=>{
  const b=e.target.closest("[data-cmd]"); if(b){ e.stopPropagation(); runCmd(b.dataset.cmd); return; }
  const h=e.target.closest(".sec-h"); if(h && !e.target.closest("button,input")){
    const s=h.parentElement; s.classList.toggle("closed"); h.querySelector(".tw").textContent = s.classList.contains("closed")?"▸":"▾";
    const st=store.get("secs",{}); if(s.id){ st[s.id]=s.classList.contains("closed"); store.set("secs",st); } }
});
function isSongView(){ return VIEW==="song" && !$("#app").classList.contains("noside"); }

/* ------------------------------------------------------------ verslepen van de randen */
function dragResize(handle, onMove){
  handle.addEventListener("mousedown", e=>{
    e.preventDefault(); handle.classList.add("drag"); $("#pdfFrame").style.pointerEvents="none";
    const move = ev=>onMove(ev);
    const up = ()=>{ document.removeEventListener("mousemove",move); document.removeEventListener("mouseup",up); handle.classList.remove("drag"); $("#pdfFrame").style.pointerEvents=""; saveLayout(); };
    document.addEventListener("mousemove",move); document.addEventListener("mouseup",up);
  });
}
const root = document.documentElement;
dragResize($("#sideSplit"), ev=>{ root.style.setProperty("--side-w", Math.min(560, Math.max(180, ev.clientX-48))+"px"); });
dragResize($("#previewSplit"), ev=>{ const r=$("#area").getBoundingClientRect(); root.style.setProperty("--preview-w", Math.min(r.width-260, Math.max(240, r.right-ev.clientX))+"px"); });
dragResize($("#panelSplit"), ev=>{ const r=$("#work").getBoundingClientRect(); root.style.setProperty("--panel-h", Math.min(r.height-160, Math.max(80, r.bottom-ev.clientY))+"px"); });
function saveLayout(){ store.set("layout", {side:root.style.getPropertyValue("--side-w"), preview:root.style.getPropertyValue("--preview-w"), panel:root.style.getPropertyValue("--panel-h")}); }
function loadLayout(){
  const l=store.get("layout",{}); if(l.side) root.style.setProperty("--side-w", l.side); if(l.preview) root.style.setProperty("--preview-w", l.preview); if(l.panel) root.style.setProperty("--panel-h", l.panel);
  const secs=store.get("secs",{}); for(const [id,closed] of Object.entries(secs)){ const s=document.getElementById(id); if(s){ s.classList.toggle("closed", closed); const tw=s.querySelector(".tw"); if(tw) tw.textContent=closed?"▸":"▾"; } }
  if(!store.get("panel", true)) showPanel(false);
  panelTab(store.get("ptab","prob"));
  if(store.get("preview", false)) $("#area").classList.add("withpreview");
  setTheme(store.get("theme","auto"), true);
}
function setTheme(t, quiet){ store.set("theme", t); if(t==="auto") root.removeAttribute("data-theme"); else root.setAttribute("data-theme", t);
  if(!quiet) toast("Thema: "+({auto:"automatisch (zoals je systeem)", light:"licht", dark:"donker"}[t])); }

/* ------------------------------------------------------------ menu's */
function showMenu(x, y, items){
  const m=$("#menu");
  m.innerHTML = items.map((it,i)=> it==="-" ? '<div class="ms"></div>' :
    `<div class="mi${it[3]===false?" dis":""}" data-i="${i}"><span>${esc(it[0])}</span>${it[2]?`<span class="k">${esc(it[2])}</span>`:""}</div>`).join("");
  m.classList.add("show");
  const r=m.getBoundingClientRect();
  m.style.left = Math.min(x, innerWidth-r.width-6)+"px"; m.style.top = Math.min(y, innerHeight-r.height-6)+"px";
  m.onclick = e=>{ const el=e.target.closest(".mi"); if(!el) return; hideMenu(); items[+el.dataset.i][1](); };
}
function hideMenu(){ $("#menu").classList.remove("show"); }
document.addEventListener("mousedown", e=>{ if(!e.target.closest("#menu")) hideMenu(); if(!e.target.closest("#qp")) closeQP(); });
function menuAt(btn, items){ const r=btn.getBoundingClientRect(); showMenu(r.left, r.bottom+2, items); }
$("#aMore").onclick = e=>{ e.stopPropagation(); const k=state&&state.kind;
  menuAt(e.currentTarget, [
    ["Opslaan", save, MOD+"S", !!state], ["Alles opslaan", saveAll, "", TABS.some(t=>dirty(t))], "-",
    ["Controleer", ()=>{ check(); showPanel(true); panelTab("prob"); }, "", !!state],
    ["MIDI-oefenbestand…", midi, "", k==="song"],
    ["Naar forScore (dit nummer)", ()=>runCmd("fsThis"), "", k==="song"||k==="setlist"],
    ["Nieuwe versie…", ()=>{ setView("song"); }, "", k==="song"], "-",
    ["Archiveer nummer", ()=>archiveSong(), "", k==="song" && !!state && state.path.startsWith("nummers/")],
    ["Setlist hernoemen…", ()=>renameSetlist(state.path), "", k==="setlist"],
    ["Setlist verwijderen (naar archief)", ()=>deleteSetlist(state.path), "", k==="setlist"],
    ["Toon in verkenner", ()=>state && revealInTree(state.path), "", !!state],
    ["PDF in nieuw tabblad", ()=>$("#pvOpen").click(), "", !!(state && state.pdf)]]); };
$("#aBuild").onclick = build;
$("#aPreview").onclick = ()=>showPreview();
$("#aView").onclick = ()=>setSetlistView(isBuilder() ? "text" : "builder");
$("#actSettings").onclick = e=>{ e.stopPropagation(); const r=e.currentTarget.getBoundingClientRect();
  showMenu(r.right+4, r.top-150, [
    ["Opdrachtenpalet…", ()=>openQP(">"), MOD+"⇧P"], ["Instellingen (instellingen.txt)", ()=>openFile("instellingen.txt",{pinned:true})],
    ["Eigen bibliotheek (bibliotheek.drum)", ()=>openFile("bibliotheek.drum",{pinned:true})], "-",
    ["Thema: automatisch", ()=>setTheme("auto")], ["Thema: licht", ()=>setTheme("light")], ["Thema: donker", ()=>setTheme("dark")], "-",
    ["Sneltoetsen", showKeys]]); };
function isBuilder(){ return !!state && state.kind==="setlist" && state.view==="builder"; }
function setSetlistView(v){ if(!state || state.kind!=="setlist") return; state.view=v; store.set("setlistView", v); updateUI(); if(typeof builderSync==="function") builderSync(); if(v==="text") setTimeout(()=>ed.focus(),0); }

/* ------------------------------------------------------------ kruimelpad, overzicht, statusbalk */
function outlineItems(){
  if(!state) return [];
  const out=[], lines=ed.value.split("\n");
  lines.forEach((ln,i)=>{
    const c=splitComment(ln)[0]; let m;
    if(state.kind==="setlist"){
      if((m=c.match(/^\s*\[(.*)\]/))) out.push({kind:"set", name:m[1], line:i+1});
    } else if((m=c.match(/^\s*\[([^\]]*)\]/))) out.push({kind:"sec", name:m[1], line:i+1});
    else if((m=c.match(/^(groove|fill|patroon|pattern|ritme)\s+([^\s=:]+)/i))) out.push({kind:m[1].toLowerCase()==="fill"?"fill":"groove", name:m[2], line:i+1, unused:!USED.used.has(m[2])});
  });
  return out;
}
function currentSymbol(){ let cur=null; for(const it of outlineItems()) if(it.line<=curLine) cur=it; return cur; }
function drawCrumbs(){
  const c=$("#crumbs");
  if(!state){ c.innerHTML=""; return; }
  const parts=state.path.split("/");
  let h=parts.map((p,i)=>`<span class="c" data-reveal="${esc(parts.slice(0,i+1).join("/"))}">${esc(i===parts.length-1?p:p)}</span>`).join('<span class="sep">›</span>');
  const sym=currentSymbol();
  if(sym && !isBuilder()) h+=`<span class="sep">›</span><span class="c sym" data-sym="1">${sym.kind==="sec"||sym.kind==="set"?"["+esc(sym.name)+"]":esc(sym.name)}</span>`;
  c.innerHTML=h;
}
$("#crumbs").addEventListener("click", e=>{
  const s=e.target.closest("[data-sym]"); if(s){ openQP("@"); return; }
  const r=e.target.closest("[data-reveal]"); if(r) revealInTree(r.dataset.reveal);
});
function drawOutline(){
  const box=$("#outline"); if(!box) return;
  const items=outlineItems();
  if(!state){ box.innerHTML='<div class="empty">Open een bestand.</div>'; return; }
  if(!items.length){ box.innerHTML='<div class="empty">Geen secties of patronen.</div>'; return; }
  const ic={sec:"▭", set:"☰", groove:"♬", fill:"✦"};
  box.innerHTML = items.map(it=>`<div class="li" data-line="${it.line}" title="regel ${it.line}"><span class="hint" style="width:14px;text-align:center">${ic[it.kind]}</span>
    <div class="m"><div class="t"${it.unused?' style="text-decoration:line-through;color:var(--muted)"':""}>${it.kind==="sec"||it.kind==="set"?"["+esc(it.name)+"]":esc(it.name)}</div></div><span class="hint" style="font-size:11px">${it.line}</span></div>`).join("");
  markOutline();
}
function markOutline(){ const sym=currentSymbol(); $$("#outline .li").forEach(x=>x.classList.toggle("active", !!sym && +x.dataset.line===sym.line)); }
$("#outline").addEventListener("click", e=>{ const r=e.target.closest(".li"); if(r) gotoLine(+r.dataset.line); });
$("#sbPos").onclick = ()=>openQP(":");
$("#sbProb").onclick = ()=>{ showPanel(true); panelTab("prob"); };
$("#sbVer").onclick = ()=>setView("song");

/* ------------------------------------------------------------ verkenner (bestandsboom) */
let treeData=[];
async function loadTree(){ try{ treeData = (await api("/api/tree")).tree; drawTree(); }catch(e){ $("#tree").innerHTML='<div class="empty">'+esc(e.message)+'</div>'; } }
const openDirs = new Set(store.get("openDirs", ["nummers","setlists"]));
const MANAGED = ["nummers","setlists","voorbeelden"];
function dirDepth(path){ return path.split("/").length - 1; }
function canNewDir(path){ const top=path.split("/")[0]; return path==="nummers" || top==="voorbeelden"; }
function tooDeep(path){ const top=path.split("/")[0]; return (top==="nummers" && dirDepth(path)>1) || (top==="setlists" && dirDepth(path)>0); }
function allFiles(nodes=treeData, out=[]){ for(const n of nodes){ if(n.dir) allFiles(n.children||[], out); else out.push(n.path); } return out; }
function drawTree(){
  const draw = (nodes, depth)=>nodes.map(n=>{
    const pad = `style="padding-left:${6+depth*12}px"`;
    if(n.dir){
      const open = openDirs.has(n.path), managed = MANAGED.includes(n.path.split("/")[0]), deep = tooDeep(n.path);
      const tip = deep ? "te diep: forScore kent geen mappen in mappen (map = label). Sleep de nummers naar een map direct onder 'nummers'." : (n.parked?"geparkeerd: wordt niet meegenomen bij 'alles maken'":"");
      return `<div class="node${n.parked?" parked":""}${deep?" deep":""}" ${pad} data-dir="${esc(n.path)}" ${managed&&!n.root?'draggable="true"':""} ${managed&&!deep?'data-drop="1"':""} title="${esc(tip)}"><span class="tw">${open?"▾":"▸"}</span><span class="nm">${esc(n.name)}</span>${deep?'<span class="warnmark">⚠</span>':""}</div>`+
        `<div class="kids${open?"":" closed"}">${draw(n.children||[], depth+1)}</div>`;
    }
    const ic = n.name.endsWith(".drum")?"♩":n.name.endsWith(".txt")?(n.path.startsWith("setlists")?"☰":"⚙"):n.name.endsWith(".md")?"?":"⌘";
    const managed = MANAGED.includes(n.path.split("/")[0]);
    const open = TABS.find(t=>t.path===n.path);
    return `<div class="node${state&&n.path===state.path?" active":""}" ${pad} data-file="${esc(n.path)}" ${managed?'draggable="true"':""}><span class="tw"></span><span class="ic">${ic}</span><span class="nm">${esc(n.name.replace(/\.(drum|txt)$/,""))}${open&&dirty(open)?' <span style="color:var(--accent)">●</span>':""}</span><span class="meta">${typeof fsDot==="function"?fsDot(n.path):""}</span></div>`;
  }).join("");
  $("#tree").innerHTML = draw(treeData, 0) || '<div class="empty">Geen bestanden.</div>';
  store.set("openDirs", [...openDirs]);
}
function revealInTree(path){
  const parts=path.split("/"); for(let i=1;i<=parts.length;i++) openDirs.add(parts.slice(0,i).join("/"));
  setView("explorer"); drawTree();
  const n=$$("#tree .node").find(x=>(x.dataset.file||x.dataset.dir)===path); if(n){ n.scrollIntoView({block:"center"}); n.classList.add("focus"); setTimeout(()=>n.classList.remove("focus"),1200); }
}
$("#tree").addEventListener("click", e=>{
  const n = e.target.closest(".node"); if(!n || e.target.closest("input")) return;
  if(n.dataset.dir){ openDirs.has(n.dataset.dir)?openDirs.delete(n.dataset.dir):openDirs.add(n.dataset.dir); drawTree(); }
  else openFile(n.dataset.file, {preview:true});
});
$("#tree").addEventListener("dblclick", e=>{ const n=e.target.closest(".node[data-file]"); if(n){ e.preventDefault(); openFile(n.dataset.file, {pinned:true}); } });
$("#tree").addEventListener("contextmenu", e=>{
  const n=e.target.closest(".node"); if(!n) return; e.preventDefault();
  const path=n.dataset.dir||n.dataset.file, isDir=!!n.dataset.dir, top=path.split("/")[0], managed=MANAGED.includes(top);
  const items = isDir ? [
    ["Nieuw nummer hier…", ()=>newSong(path), "", top!=="setlists" && managed],
    ["Nieuwe map…", ()=>newFolder(path), "", canNewDir(path)],
    ["Alle nummers hierin maken", ()=>buildFolder(path), "", top!=="setlists"], "-",
    ["Hernoemen", ()=>startRename(n), "F2", managed && !MANAGED.includes(path)],
    ["Lege map weghalen", ()=>delDir(path), "", managed && !MANAGED.includes(path)],
  ] : [
    ["Openen", ()=>openFile(path, {pinned:true})],
    ["Openen in voorbeeld", async ()=>{ await openFile(path,{pinned:true}); showPreview(true); }, "", /\.drum$/.test(path)], "-",
    ["Naar forScore", ()=>fsSend(path.startsWith("setlists/") ? {setlists:[nameOf(path)]} : {paths:[path]}), "", top==="nummers"||top==="setlists"],
    ["Hernoemen", ()=>startRename(n), "F2", managed],
    ["Archiveren", ()=>archiveSong(path), "", top==="nummers"],
    ["Verwijderen (naar archief)", ()=>deleteSetlist(path), "", top==="setlists"], "-",
    ["Pad kopiëren", ()=>navigator.clipboard?.writeText(path)],
  ];
  showMenu(e.clientX, e.clientY, items);
});
document.addEventListener("keydown", e=>{
  if(e.key==="F2" && state && document.activeElement!==ed){ const n=$$("#tree .node[data-file]").find(x=>x.dataset.file===state.path); if(n && n.getAttribute("draggable")==="true"){ e.preventDefault(); startRename(n); } }
});
async function newFolder(parent="nummers"){
  if(!canNewDir(parent)){ toast("Mappen in mappen kan niet: in forScore is een map een label."); return; }
  const name=prompt("Naam van de nieuwe map:"); if(!name) return;
  try{ const j=await api("/api/mkdir",{path:parent+"/"+name.trim()}); openDirs.add(parent); openDirs.add(j.path); await loadTree(); }catch(err){ toast(err.message); }
}
async function delDir(path){ try{ await api("/api/deldir",{path}); toast("Map weggehaald"); await loadTree(); }catch(err){ toast(err.message); } }
async function buildFolder(path){ await saveAll(); busy(true,`Alle nummers in '${baseOf(path)}' maken…`);
  try{ const j=await api("/api/build-folder",{path}); log(j.log); toast(j.ok?"Klaar":"Klaar, met meldingen (zie Uitvoer)"); }catch(err){ toast(err.message); } finally{ busy(false); } }
function startRename(node){
  const nm=node.querySelector(".nm"); if(!nm || node.querySelector("input")) return;
  const path=node.dataset.dir||node.dataset.file, isFile=!!node.dataset.file;
  const old = isFile ? baseOf(path).replace(/\.(drum|txt|py)$/,"") : baseOf(path);
  const inp=document.createElement("input"); inp.value=old; inp.className="rename";
  nm.replaceWith(inp); inp.focus(); inp.select(); node.setAttribute("draggable","false");
  let done=false;
  const finish = async ok=>{
    if(done) return; done=true;
    const name=inp.value.trim();
    if(!ok || !name || name===old){ drawTree(); return; }
    const ext = isFile ? (baseOf(path).match(/\.(drum|txt|py)$/)||[""])[0] : "";
    await doMove(path, (parentOf(path)?parentOf(path)+"/":"")+name+ext);
  };
  inp.addEventListener("keydown", e=>{ e.stopPropagation(); if(e.key==="Enter") finish(true); if(e.key==="Escape") finish(false); });
  inp.addEventListener("blur", ()=>finish(true));
}
async function doMove(from, to){
  try{
    for(const t of TABS) if((t.path===from || t.path.startsWith(from+"/")) && dirty(t)) await saveModel(t);
    const j=await api("/api/move",{from, to});
    for(const t of TABS){ if(t.path===from) t.path=j.path; else if(t.path.startsWith(from+"/")) t.path=j.path+t.path.slice(from.length); }
    if(openDirs.has(from)) openDirs.add(j.path);
    openDirs.add(parentOf(j.path));
    drawTabs(); updateUI(); persistTabs(); await loadTree(); if(typeof loadFs==="function") loadFs();
    if(typeof builderSync==="function" && isBuilder()){ BL.path=null; builderSync(); }
    toast("Verplaatst naar "+j.path);
  }catch(err){ toast(err.message); drawTree(); }
}
$("#tree").addEventListener("dragstart", e=>{ const n=e.target.closest('.node[draggable="true"]'); if(!n) return;
  e.dataTransfer.setData("text/x-ds-move", n.dataset.dir||n.dataset.file); e.dataTransfer.effectAllowed="move"; });
$("#tree").addEventListener("dragover", e=>{
  if(!e.dataTransfer.types.includes("text/x-ds-move")) return;
  const t=e.target.closest(".node[data-drop]"); if(!t) return;
  e.preventDefault(); $$("#tree .drop-ok").forEach(x=>x.classList.remove("drop-ok")); t.classList.add("drop-ok"); });
$("#tree").addEventListener("dragleave", e=>{ const t=e.target.closest(".node[data-drop]"); if(t) t.classList.remove("drop-ok"); });
$("#tree").addEventListener("drop", e=>{
  const t=e.target.closest(".node[data-drop]"); if(!t) return; e.preventDefault(); t.classList.remove("drop-ok");
  const from=e.dataTransfer.getData("text/x-ds-move"), dir=t.dataset.dir;
  if(!from || parentOf(from)===dir || from===dir) return;
  if(from.split("/")[0]!==dir.split("/")[0]){ toast("Verplaatsen kan alleen binnen dezelfde hoofdmap"); return; }
  const isDir = !!$$("#tree .node[data-dir]").find(x=>x.dataset.dir===from);
  if(isDir && dir.split("/")[0]!=="voorbeelden" && dir!=="nummers"){ toast("Mappen in mappen kan niet: in forScore is een map een label, en labels kunnen niet in elkaar."); return; }
  openDirs.add(dir); doMove(from, dir+"/"+baseOf(from));
});

/* ------------------------------------------------------------ setlists hernoemen en verwijderen */
async function renameSetlist(path){
  const old = nameOf(path);
  let name = prompt("Nieuwe bestandsnaam voor de setlist (zonder .txt):", old); if(name===null) return;
  name = name.trim().replace(/\.txt$/i,"").replace(/[\\/:*?"<>|]+/g,"-").trim();
  if(!name || name===old) return;
  await doMove(path, "setlists/"+name+".txt");
  drawSetlists && drawSetlists();
}
async function deleteSetlist(path){
  if(!confirm(`Setlist '${nameOf(path)}' verwijderen?\n\nHij gaat naar archief/setlists/ (daar kun je hem altijd terughalen). De setlist in forScore blijft staan.`)) return;
  try{
    const j = await api("/api/delete-setlist", {path});
    const m = TABS.find(t=>t.path===path);
    if(m){ if(m===state) stash(); m.saved = m.content; await closeTab(m); }
    toast("Verwijderd: staat nu in "+j.archived);
    await loadTree(); if(typeof loadFs==="function") loadFs();
  }catch(err){ toast(err.message); }
}

/* ------------------------------------------------------------ nieuw nummer / setlist */
async function newSong(folder){
  folder = typeof folder==="string" ? folder : "";
  $("#dlgSong h3").textContent = folder && folder!=="nummers" ? `Nieuw nummer in '${folder.replace(/^nummers\//,"")}'` : "Nieuw nummer";
  const v = await ask("#dlgSong"); if(!v || typeof v!=="object") return;
  if(folder) v.folder = folder;
  try{ const j=await api("/api/new-song", v); if(!j.ok){ log(j.log); toast("Bestaat al of mislukt (zie Uitvoer)"); }
    await loadTree(); if(j.ok) openFile(j.path, {pinned:true}); }catch(err){ toast(err.message); }
}
async function newSetlist(){
  const v = await ask("#dlgSet"); if(!v || typeof v!=="object") return;
  try{ const j=await api("/api/new-setlist", v); await loadTree(); if(j.ok){ const m=await openFile(j.path, {pinned:true}); if(m){ m.view="builder"; setSetlistView("builder"); } } else { log(j.log); toast("Mislukt (zie Uitvoer)"); } }
  catch(err){ toast(err.message); }
}

/* ------------------------------------------------------------ zoeken en vervangen in het bestand */
const F = { matches:[], cur:-1 };
function findRegex(){ const q=$("#fFind").value; if(!q) return null; return new RegExp(q.replace(/[.*+?^${}()|[\]\\]/g,"\\$&"), $("#fCase").checked?"g":"gi"); }
function computeFind(){
  F.matches=[]; const re=findRegex();
  if(re && $("#findbar").classList.contains("show")){ let m; while((m=re.exec(ed.value))){ F.matches.push([m.index, m.index+m[0].length]); if(m[0].length===0) re.lastIndex++; } }
  if(F.cur>=F.matches.length) F.cur=F.matches.length-1;
  $("#fCount").textContent = $("#fFind").value ? (F.matches.length ? `${F.cur+1>0?F.cur+1:0}/${F.matches.length}` : "geen") : "";
}
function renderFind(){
  const layer=$("#findhl");
  if(!$("#findbar").classList.contains("show") || !$("#fFind").value){ layer.innerHTML=""; return; }
  computeFind();
  const v=ed.value; let out="", last=0;
  F.matches.forEach(([a,b],n)=>{ out+=esc(v.slice(last,a))+`<mark${n===F.cur?' class="cur"':""}>`+esc(v.slice(a,b))+"</mark>"; last=b; });
  out+=esc(v.slice(last));
  layer.innerHTML = out.split("\n").map(l=>'<span class="l">'+(l||"​")+"</span>").join("");
}
function gotoMatch(d){
  computeFind(); if(!F.matches.length){ renderFind(); return; }
  const pos=ed.selectionEnd;
  if(d>0){ F.cur = F.matches.findIndex(m=>m[0]>=pos - (F.cur>=0&&F.matches[F.cur]&&F.matches[F.cur][1]===pos?0:1)); if(F.cur<0) F.cur=0; }
  else { const s=ed.selectionStart; let i=-1; F.matches.forEach((m,n)=>{ if(m[0]<s) i=n; }); F.cur = i<0 ? F.matches.length-1 : i; }
  const [a,b]=F.matches[F.cur]; ed.setSelectionRange(a,b);
  const line=ed.value.slice(0,a).split("\n").length;
  if(line*20 < ed.scrollTop+20 || line*20 > ed.scrollTop+ed.clientHeight-40) ed.scrollTop=Math.max(0,(line-6)*20);
  syncScroll(); renderFind(); cursorPos();
}
function openFind(){
  if(!state) return; if(isBuilder()) setSetlistView("text");
  const fb=$("#findbar"); fb.classList.add("show");
  const sel=ed.value.slice(ed.selectionStart, ed.selectionEnd);
  if(sel && !sel.includes("\n")) $("#fFind").value=sel;
  $("#fFind").focus(); $("#fFind").select(); F.cur=-1; renderFind();
}
function closeFind(focus=true){ $("#findbar").classList.remove("show"); renderFind(); if(focus && state) ed.focus(); }
$("#fFind").addEventListener("input", ()=>{ F.cur=-1; renderFind(); });
$("#fCase").addEventListener("change", ()=>{ F.cur=-1; renderFind(); });
$("#fFind").addEventListener("keydown", e=>{ if(e.key==="Enter"){ e.preventDefault(); gotoMatch(e.shiftKey?-1:1); $("#fFind").focus(); } if(e.key==="Escape") closeFind(); });
$("#fRepl").addEventListener("keydown", e=>{ if(e.key==="Escape") closeFind(); });
$("#fNext").onclick=()=>gotoMatch(1); $("#fPrev").onclick=()=>gotoMatch(-1); $("#fClose").onclick=()=>closeFind();
$("#fRep1").onclick=()=>{
  computeFind(); const [a,b]=F.matches[F.cur]||[];
  if(a===undefined || ed.selectionStart!==a || ed.selectionEnd!==b){ gotoMatch(1); return; }
  ed.focus(); ed.setSelectionRange(a,b); insertText($("#fRepl").value); gotoMatch(1);
};
$("#fRepAll").onclick=()=>{
  const re=findRegex(); if(!re) return; const n=(ed.value.match(re)||[]).length; if(!n) return;
  setContent(ed.value.replace(re, ()=>$("#fRepl").value)); toast(`${n}× vervangen`);
};

/* ------------------------------------------------------------ zoeken in alle bestanden (zijbalk) */
let gsTimer=null;
function gsRegex(q){ return new RegExp(q.replace(/[.*+?^${}()|[\]\\]/g,"\\$&"), $("#gsCase").checked?"g":"gi"); }
async function globalSearch(){
  const q=$("#gsFind").value.trim(), box=$("#gsResults");
  if(q.length<2){ box.innerHTML='<div class="empty">Typ minstens 2 tekens.</div>'; return; }
  let j; try{ j=await api("/api/search?q="+encodeURIComponent(q)+($("#gsCase").checked?"&case=1":"")); }catch(err){ box.innerHTML='<div class="empty">'+esc(err.message)+'</div>'; return; }
  if(q!==$("#gsFind").value.trim()) return;
  if(!j.results.length){ box.innerHTML=`<div class="empty">Niets gevonden voor "${esc(q)}".</div>`; return; }
  const re=gsRegex(q), by={};
  for(const r of j.results) (by[r.path]=by[r.path]||[]).push(r);
  box.innerHTML = `<div class="grp">${j.results.length}${j.more?"+":""} resultaten in ${Object.keys(by).length} bestanden</div>` +
    Object.entries(by).map(([p,rs])=>`<div class="sfile" data-p="${esc(p)}"><span class="hint">${p.endsWith(".drum")?"♩":p.startsWith("setlists")?"☰":"⚙"}</span>${esc(nameOf(p))}<span class="hint" style="font-weight:400;font-size:11px">${esc(parentOf(p))}</span><span class="n">${rs.length}</span></div>`+
      rs.map(r=>`<div class="sres" data-p="${esc(r.path)}" data-l="${r.line}" title="regel ${r.line}">${esc(r.text.trim()).replace(re, m=>"<b>"+m+"</b>")}</div>`).join("")).join("") +
    (j.more?'<div class="empty">Meer dan 300 resultaten; zoek specifieker.</div>':"");
}
$("#gsFind").addEventListener("input", ()=>{ clearTimeout(gsTimer); gsTimer=setTimeout(globalSearch, 250); });
$("#gsCase").addEventListener("change", globalSearch);
$("#gsResults").addEventListener("click", async e=>{
  const r=e.target.closest(".sres,.sfile"); if(!r) return;
  await openFile(r.dataset.p, {pinned:true});
  if(r.dataset.l){ gotoLine(+r.dataset.l); $("#fFind").value=$("#gsFind").value; $("#fCase").checked=$("#gsCase").checked; }
});
$("#gsReplOpen").onclick=()=>{
  const q=$("#gsFind").value; if(!q || !state){ toast("Open eerst een bestand en typ wat je zoekt"); return; }
  if(isBuilder()) setSetlistView("text");
  const re=gsRegex(q), n=(ed.value.match(re)||[]).length; if(!n){ toast("Niet gevonden in het open bestand"); return; }
  setContent(ed.value.replace(re, ()=>$("#gsRepl").value)); toast(`${n}× vervangen in ${nameOf(state.path)} (nog niet opgeslagen)`);
};

/* ------------------------------------------------------------ Nummer: eigenschappen */
let PROPS=null, ALIAS={};
async function initProps(){ try{ const j=await api("/api/props"); PROPS=j.fields; ALIAS=j.aliases; drawDoc(); }catch(e){} }
function headerEnd(lines){
  for(let i=0;i<lines.length;i++){ const c=splitComment(lines[i])[0];
    if(/^(groove|fill|patroon|pattern|ritme|instrument|kit)\s/i.test(c) || /^\s*\[/.test(c) || /^\s*\d/.test(c)) return i; }
  return lines.length;
}
function readHeader(){
  const lines=ed.value.split("\n"), end=headerEnd(lines), vals={}, where={};
  for(let i=0;i<end;i++){ const m=splitComment(lines[i])[0].match(/^([A-Za-z][\w\-]*)\s*:\s*(.*?)\s*$/);
    if(m && ALIAS[m[1].toLowerCase()]){ const id=ALIAS[m[1].toLowerCase()]; vals[id]=m[2]; where[id]=i; } }
  return {lines,end,vals,where};
}
function setHeader(field, value){
  const h=readHeader(); const lines=h.lines; value=String(value??"").trim();
  const keepEmpty = ["credit","subtitle"].includes(field.id) && field.default;
  if(h.where[field.id]!==undefined){
    const i=h.where[field.id], com=splitComment(lines[i])[1];
    if(!value && !keepEmpty) lines.splice(i,1); else lines[i]=`${field.key}: ${value}`+(com?"   "+com:"");
  } else if(value || keepEmpty){
    let at=-1; for(const i of Object.values(h.where)) at=Math.max(at,i);
    if(at<0){ at=0; while(at<h.end && /^\s*#/.test(lines[at])) at++; at--; }
    lines.splice(at+1,0,`${field.key}: ${value}`);
  }
  setContent(lines.join("\n"));
}
function drawDoc(){
  const box=$("#docForm"); if(!PROPS) return;
  if(!state || !state.path.endsWith(".drum") || state.kind!=="song"){
    box.innerHTML='<div class="empty">Open een nummer (.drum) om de eigenschappen te zien. Instellingen voor álle nummers staan in <a href="#" data-open="instellingen.txt">instellingen.txt</a>.</div>'; return;
  }
  const {vals}=readHeader(); let html='<p class="doc-note">De kop van dit nummer. Leeg = standaard uit <a href="#" data-open="instellingen.txt">instellingen.txt</a>.</p>', group="";
  PROPS.forEach((f,n)=>{
    if(f.group!==group){ group=f.group; html+=`<div class="pgroup">${esc(group)}</div>`; }
    const v=vals[f.id], has=v!==undefined, ph = f.default ? `standaard: ${f.default}` : "";
    let input;
    if(f.type==="select") input=`<select data-n="${n}" class="${has?"has":""}">`+f.options.map(o=>`<option value="${esc(o)}" ${(v||"")===o?"selected":""}>${o?esc(o):(f.default?"standaard ("+esc(f.default)+")":"standaard")}</option>`).join("")+`</select>`;
    else input=`<input data-n="${n}" type="${f.type==="number"?"number":"text"}" value="${has?esc(v):""}" placeholder="${esc(ph)}" class="${has?"has":""}">`;
    html+=`<div class="prop"><label><span>${esc(f.label)} <code style="font-size:10px">${esc(f.key)}</code></span></label>${input}<div class="help">${esc(f.help)}</div></div>`;
  });
  box.innerHTML=html;
  box.querySelectorAll("[data-n]").forEach(el=>{
    const f=PROPS[+el.dataset.n];
    const apply=()=>{ setHeader(f, el.value); el.classList.toggle("has", !!el.value); };
    if(el.tagName==="SELECT") el.onchange=apply; else { el.oninput=()=>{ clearTimeout(el._t); el._t=setTimeout(apply,350); }; el.onchange=apply; }
  });
}
$("#docForm").addEventListener("click", e=>{ const a=e.target.closest("[data-open]"); if(a){ e.preventDefault(); openFile(a.dataset.open,{pinned:true}); } });
function refreshDoc(){
  if(!isSongView() || !PROPS) return;
  if(document.activeElement && document.activeElement.closest && document.activeElement.closest("#docForm")) return;
  drawDoc();
}
function refreshSongView(){
  $("#songViewTitle").textContent = state && state.kind==="song" ? "Nummer · "+nameOf(state.path) : "Nummer";
  if(isSongView()){ drawDoc(); drawVersions(); }
  updateVersionBadge();
}

/* ------------------------------------------------------------ Nummer: versies */
const VER = { data:null };
async function updateVersionBadge(){
  const sb=$("#sbVer");
  if(!state || state.kind!=="song" || !/\.drum$/.test(state.path)){ sb.textContent=""; sb.style.display="none"; return; }
  sb.style.display="";
  const m=state;
  try{ const j=await api("/api/versions",{path:m.path}); if(m!==state) return; VER.data=j;
    sb.textContent = j.latest ? `V${j.latest}${j.changed?"*":""}` : "geen versie";
    sb.title = j.latest ? (j.changed ? `Gewijzigd sinds V${j.latest}: wordt V${j.next}` : `Gelijk aan V${j.latest}`) : "Nog geen versie (ontstaat bij forScore of Nieuwe versie)";
  }catch(e){ sb.textContent=""; }
}
async function drawVersions(){
  const box=$("#verBox");
  if(!state || state.kind!=="song" || !/\.drum$/.test(state.path)){ box.innerHTML='<div class="empty">Open een nummer (.drum) om de versies te zien.</div>'; return; }
  const m=state;
  let j; try{ j=await api("/api/versions",{path:m.path}); }catch(err){ box.innerHTML='<div class="empty">'+esc(err.message)+'</div>'; return; }
  if(m!==state) return;
  VER.data=j;
  let h="";
  if(dirty()) h+='<div class="notice">Niet-opgeslagen wijzigingen tellen pas mee na opslaan.</div>';
  if(!j.versions.length) h+='<div class="ver-now">Nog geen versies. De eerste (V1) ontstaat bij <b>forScore</b> of met <b>Nieuwe versie</b>.</div>';
  else if(j.changed) h+=`<div class="ver-now changed">Gewijzigd sinds V${j.latest}: wordt <b>V${j.next}</b><br><span class="hint">${esc(j.pending)}</span></div>`;
  else h+=`<div class="ver-now">Gelijk aan <b>V${j.latest}</b>.</div>`;
  h+=`<div class="ver-new"><input class="field" id="verNote" placeholder="Notitie, bv. 'nieuwe intro'"><button class="btn" id="verMake" ${j.changed?"":"disabled"} title="Leg de huidige versie vast (met PDF)">Nieuwe versie</button></div>`;
  (j.problems||[]).forEach(p=>{ h+=`<div class="ver-prob">✗ ${esc(p)}</div>`; });
  for(const v of j.versions){
    const fs = v.forscore ? `forScore: ${esc(v.forscore.replace(/\.pdf$/,""))}${v.adopted?" (stond er al)":""}${v.reused?` (= V${v.reused})`:""}` : "nog niet in forScore";
    h+=`<div class="ver${v.current?" cur":""}" data-n="${v.n}">
      <div class="ver-h"><b>V${v.n}</b><span class="hint">${fmtTime(v.time)}</span>${v.current?'<span class="tag">= nu</span>':""}</div>
      <div class="ver-note" title="Klik om de notitie te veranderen">${v.note?esc(v.note):'<span class="hint">+ notitie</span>'}</div>
      ${v.changes?`<div class="hint" style="font-size:12px">${esc(v.changes)}</div>`:""}
      <div class="hint" style="font-size:12px">${fs}</div>
      <div class="ver-act"><button data-a="diff" ${v.current?"disabled":""}>Verschil met nu</button>${v.has_pdf?'<button data-a="pdf">PDF</button>':""}<button data-a="restore" ${v.current?"disabled":""}>Terugzetten</button></div>
    </div>`;
  }
  if(j.backups.length) h+=`<details><summary class="hint" style="margin:4px 12px;cursor:pointer">Reservekopieën (${j.backups.length})</summary>`+j.backups.map(b=>
      `<div class="ver-bk" data-file="${esc(b.file)}"><span>${fmtTime(b.time)} · ${esc(b.why)}</span><span class="ver-act" style="margin:0"><button data-a="bk">Terugzetten</button></span></div>`).join("")+"</details>";
  box.innerHTML=h;
}
async function reloadFromDisk(m){
  const j=await api("/api/file?path="+encodeURIComponent(m.path));
  if(m===state){ setContent(j.content); }
  m.content=j.content; m.saved=j.content; updateUI(); drawTabs();
}
function showDiff(title, sum, lines){
  $("#diffTitle").textContent=title; $("#diffSum").textContent=sum;
  $("#diffOut").innerHTML = lines.length ? lines.map(([k,t])=>k==="@"?`<span class="hunk">${esc(t)}</span>`:
    (k===" "?` ${esc(t)}\n`:`<span class="${k==="+"?"add":"del"}">${k}${esc(t)}</span>`)).join("") : "Geen verschil.";
  $("#dlgDiff").showModal();
}
$("#verBox").addEventListener("click", async e=>{
  const j=VER.data; if(!j || !state) return;
  if(e.target.id==="verMake"){
    if(dirty()) await save();
    busy(true,"Nieuwe versie maken (met PDF)…");
    try{ const r=await api("/api/versions/create",{path:state.path, note:$("#verNote").value.trim()}); log(r.log, false); toast(`V${r.version.n} vastgelegd`); }
    catch(err){ toast(err.message); } finally{ busy(false); refreshSongView(); if(typeof loadFs==="function") loadFs(); }
    return;
  }
  const card=e.target.closest(".ver"), btn=e.target.closest("button[data-a]");
  if(card && e.target.closest(".ver-note")){
    const v=j.versions.find(x=>x.n==card.dataset.n);
    const note=prompt(`Notitie bij V${v.n}:`, v.note||""); if(note===null) return;
    try{ await api("/api/versions/note",{path:state.path, n:v.n, note}); drawVersions(); }catch(err){ toast(err.message); }
    return;
  }
  if(!btn) return;
  if(btn.dataset.a==="bk"){
    const file=btn.closest(".ver-bk").dataset.file;
    if(dirty()) await save();
    if(!confirm("Deze reservekopie terugzetten? Wat er nu staat wordt eerst ook als reservekopie bewaard.")) return;
    try{ const r=await api("/api/versions/restore-backup",{path:state.path, file}); toast(r.log||"Teruggezet"); await reloadFromDisk(state); refreshSongView(); }catch(err){ toast(err.message); }
    return;
  }
  const n=+card.dataset.n, v=j.versions.find(x=>x.n===n);
  if(btn.dataset.a==="pdf"){ window.open("/versies/"+j.id.split("/").map(encodeURIComponent).join("/")+"/"+encodeURIComponent(v.pdf), "_blank"); return; }
  if(btn.dataset.a==="diff"){
    if(dirty()) await save();
    try{ const d=await api("/api/versions/diff",{path:state.path, a:n, b:"werk"}); showDiff(`V${n} → nu`, d.summary, d.lines); }catch(err){ toast(err.message); }
    return;
  }
  if(btn.dataset.a==="restore"){
    if(dirty()) await save();
    if(!confirm(`V${n} terugzetten in het nummer?\n\nWat er nu staat wordt eerst als reservekopie bewaard. Bij de volgende keer forScore wordt dit een nieuwe versie; staat V${n} nog in forScore, dan wordt die gewoon weer gebruikt.`)) return;
    try{ const r=await api("/api/versions/restore",{path:state.path, n}); toast(r.log||"Teruggezet"); await reloadFromDisk(state); refreshSongView(); if(typeof loadFs==="function") loadFs(); }catch(err){ toast(err.message); }
  }
});

/* ------------------------------------------------------------ Invoegen */
const SNIPS = [
  ["groove", "groove naam:\n  HH: *8\n  SD: 2 4\n  BD: 1 3\n", "naam"],
  ["fill", "fill naam:\n  SD: 4 4e 4& 4a\n", "naam"],
  ["variant", "groove nieuw = basis:\n  HH: -\n  RD: *8\n", "nieuw"],
  ["2 maten", "groove naam:\n  maten: 2\n  HH: *8\n  SD: 2 4 || 2 4 4&\n  BD: 1 3 || 1 2& 3\n", "naam"],
  ["sectie", "[Naam] 8 rock\n", "Naam"],
  ["sectie+regels", "[Naam]\n  8 rock mf\n  7 rock\n  1 rock fill sd4\n", "Naam"],
  ["herhaling", "[Naam] herhaal 2\n  8 rock\n", "Naam"],
  ["volta's", "[Naam]\n  6 rock\n  2 rock volta 1 fill sd4\n  2 rock volta 2 fill tomfull\n", "Naam"],
  ["segno/coda", "[Couplet] segno\n  8 rock\n[Brug] 8 halftime ds-al-coda\n[Coda] coda\n  4 rock\n  1 hit fermata\n", "Couplet"],
  ["inline maat", "1 {SD: *16 4:X; BD: 1}\n", "SD: *16 4:X; BD: 1"],
  ["sticking", "  ST: RLRLRLRLRLRLRLRL\n", "RLRLRLRLRLRLRLRL"],
  ["slot", "[Outro]\n  4 rock crash\n  1 hit fermata\n", "Outro"],
];
const OPTCHIPS = ["crash","fill ","\"tekst\"","mf","p","f","ff","cresc","dim","p<f","f>p","tempo=","rit","fermata","maat=","herhaal 2",
  "volta 1","volta 2","segno","coda","ds-al-coda","naar-coda","uitgeschreven","nieuweregel","klein","groot","tacet","tijd","halftime","doubletime"];
const COUNTS = [["*4","kwarten"],["*8","8sten"],["*16","16den"],["*8t","triolen"],["*&","de &-en"],["1 3",""],["2 4",""],
  ["1e",""],["1&",""],["1a",""],["1t",""],["1l",""],["3-4*16",""],["!3&","weghalen"],[":X","accent"],[":g","ghost"],[":o","open"]];
function chip(label, small){ return `<span class="cchip">${esc(label)}${small?`<small>${esc(small)}</small>`:""}</span>`; }
async function initTools(){
  $("#snips").innerHTML = SNIPS.map(s=>chip(s[0])).join("");
  $$("#snips .cchip").forEach((c,i)=>c.onclick=()=>{ const s=SNIPS[i]; const a=ed.selectionStart; const atLineStart = a===0 || ed.value[a-1]==="\n"; insertText((atLineStart?"":"\n")+s[1], s[2]); });
  $("#opts").innerHTML = OPTCHIPS.map(o=>chip(o)).join("");
  $$("#opts .cchip").forEach((c,i)=>c.onclick=()=>{ const o=OPTCHIPS[i];
    if(o==="\"tekst\"") { insertWord('"tekst"'); const p=ed.selectionStart-7; ed.setSelectionRange(p,p+5); }
    else if(o.endsWith("=")||o.endsWith(" ")) { const a=ed.selectionStart, prev=ed.value[a-1]; insertText((prev&&!/\s/.test(prev)?" ":"")+o); }
    else insertWord(o); });
  $("#counts").innerHTML = COUNTS.map(c=>chip(c[0], c[1])).join("");
  $$("#counts .cchip").forEach((c,i)=>c.onclick=()=>{ const t=COUNTS[i][0]; if(t[0]===":") insertText(t); else insertWord(t); });
  try{
    const k = await api("/api/kit");
    KITSET = new Set(k.instruments.flatMap(i=>[i.code, ...i.aliases])); render();
    $("#insts").innerHTML = k.instruments.map(i=>`<span class="cchip" title="${esc(i.name)} · ${i.pos} · ${esc(i.head)}${i.aliases.length?" · ook: "+esc(i.aliases.join(", ")):""}">${i.code}<small>${esc(i.name.split(" (")[0].split(" /")[0])}</small></span>`).join("")+
      `<span class="cchip" title="sticking-rij">ST<small>sticking</small></span>`;
    $$("#insts .cchip").forEach(c=>c.onclick=()=>{ const code=c.firstChild.textContent; const a=ed.selectionStart, lineStart = a===0||ed.value[a-1]==="\n"; insertText((lineStart?"  ":"\n  ")+code+": "); });
    $("#mods").innerHTML = k.mods.map(m=>`<div class="modrow" title="klik om in te voegen"><code>${esc(m.ch)}</code><span>${esc(m.desc)}</span></div>`).join("")+
      `<div class="modrow"><code>-</code><span>rust (ook . of _)</span></div><div class="modrow"><code>|</code><span>stukken binnen de maat</span></div><div class="modrow"><code>||</code><span>volgende maat</span></div>`;
    $$("#mods .modrow").forEach(r=>r.onclick=()=>insertText(r.querySelector("code").textContent));
  }catch(e){}
}
let LIB=[];
async function initLib(){ try{ LIB=(await api("/api/library")).items; drawLib(); }catch(e){} }
function drawLib(){
  const q=$("#libSearch").value.toLowerCase().trim();
  const items = LIB.filter(i=>!q || (i.name+" "+i.doc+" "+i.meter+" "+i.kind).toLowerCase().includes(q));
  $("#libList").innerHTML = items.map(i=>`<div class="lib-item" data-n="${LIB.indexOf(i)}">
    <div class="lib-head"><b>${esc(i.name)}</b><span class="tag">${i.kind} · ${esc(i.meter)}</span><span class="doc">${esc(i.doc)}</span></div>
    <div class="lib-body"><div class="hint" style="font-size:12px">${esc(i.doc)}${i.src&&i.src!=="ingebouwd"?" · "+esc(i.src):""}</div>
    <pre>${esc(i.grid)}</pre><button class="btn small" data-a="ins">Naam invoegen</button></div></div>`).join("") || '<div class="empty">Niets gevonden.</div>';
}
$("#libSearch").addEventListener("input", drawLib);
$("#libList").addEventListener("click", e=>{
  const it=e.target.closest(".lib-item"); if(!it) return;
  if(e.target.dataset.a==="ins"){ insertWord(LIB[+it.dataset.n].name); return; }
  if(e.target.closest(".lib-head")) it.classList.toggle("open");
});

/* ------------------------------------------------------------ Help */
let HELP=[];
function mdInline(s){
  return esc(s).replace(/`([^`]+)`/g,"<code>$1</code>").replace(/\*\*([^*]+)\*\*/g,"<b>$1</b>")
    .replace(/(^|[^*])\*([^*]+)\*/g,"$1<i>$2</i>").replace(/\[([^\]]+)\]\(([^)]+)\)/g,(m,t,u)=>u.startsWith("#")?`<a href="#" data-sec="${esc(u.slice(1))}">${t}</a>`:`<a href="${u}" target="_blank">${t}</a>`);
}
function md(text){
  const lines=text.split("\n"); let out="", i=0;
  while(i<lines.length){
    const l=lines[i];
    if(l.startsWith("```")){ let code=[]; i++; while(i<lines.length && !lines[i].startsWith("```")) code.push(lines[i++]); i++; out+=`<pre><code>${esc(code.join("\n"))}</code></pre>`; continue; }
    if(/^\|/.test(l)){ const rows=[]; while(i<lines.length && /^\|/.test(lines[i])) rows.push(lines[i++]);
      const cells=r=>r.replace(/^\||\|$/g,"").split(/(?<!\\)\|/).map(c=>c.trim().replace(/\\\|/g,"|"));
      out+="<table>"+rows.filter((r,k)=>!(k===1&&/^[\s|:-]+$/.test(r))).map((r,k)=>"<tr>"+cells(r).map(c=>k===0?`<th>${mdInline(c)}</th>`:`<td>${mdInline(c)}</td>`).join("")+"</tr>").join("")+"</table>"; continue; }
    if(/^#{2,4}\s/.test(l)){ out+=`<h4>${mdInline(l.replace(/^#+\s/,""))}</h4>`; i++; continue; }
    if(/^>\s?/.test(l)){ let q=[]; while(i<lines.length && /^>/.test(lines[i])) q.push(lines[i++].replace(/^>\s?/,"")); out+=`<blockquote>${mdInline(q.join(" "))}</blockquote>`; continue; }
    if(/^\s*[-*]\s/.test(l) || /^\s*\d+\.\s/.test(l)){ const ol=/^\s*\d+\./.test(l); let it=[];
      while(i<lines.length && (/^\s*[-*]\s/.test(lines[i])||/^\s*\d+\.\s/.test(lines[i])||/^\s{2,}\S/.test(lines[i]))){
        if(/^\s{2,}\S/.test(lines[i]) && !/^\s*([-*]|\d+\.)\s/.test(lines[i])) it[it.length-1]+=" "+lines[i].trim(); else it.push(lines[i].replace(/^\s*([-*]|\d+\.)\s/,"")); i++; }
      out+=(ol?"<ol>":"<ul>")+it.map(x=>`<li>${mdInline(x)}</li>`).join("")+(ol?"</ol>":"</ul>"); continue; }
    if(/^---+$/.test(l)||!l.trim()){ i++; continue; }
    let p=[]; while(i<lines.length && lines[i].trim() && !/^(```|\||#|>|\s*[-*]\s|\s*\d+\.\s)/.test(lines[i])) p.push(lines[i++]);
    out+=`<p>${mdInline(p.join(" "))}</p>`;
  }
  return out;
}
async function initHelp(){ try{ HELP=(await api("/api/help")).sections; drawHelp(); }catch(e){} }
function drawHelp(){
  const q=$("#helpSearch").value.toLowerCase().trim();
  let list = HELP.map((s,n)=>({s,n,score: !q?0: (s.title.toLowerCase().includes(q)?10:0) + (s.body.toLowerCase().split(q).length-1)}));
  if(q) list = list.filter(x=>x.score>0).sort((a,b)=>b.score-a.score);
  const hiq = t => q ? esc(t).replace(new RegExp(q.replace(/[.*+?^${}()|[\]\\]/g,"\\$&"),"gi"), m=>`<mark>${m}</mark>`) : esc(t);
  $("#helpList").innerHTML = list.slice(0,80).map(({s,n})=>{
    let snip=""; if(q){ const b=s.body, k=b.toLowerCase().indexOf(q); if(k>=0) snip=b.slice(Math.max(0,k-50), k+90).replace(/\s+/g," "); }
    else snip=s.body.replace(/[`*|#>]/g,"").replace(/\s+/g," ").slice(0,110);
    return `<div class="help-res" data-n="${n}" style="${s.level>2&&!q?"padding-left:24px":""}"><div class="t">${hiq(s.title)}</div><div class="s">${hiq(snip)}</div></div>`;
  }).join("") || '<div class="empty">Niets gevonden. Probeer een ander woord.</div>';
}
function showHelp(n){
  const s=HELP[n]; if(!s) return;
  $("#helpList").innerHTML = `<span class="back">← terug</span><div class="md"><h3>${mdInline(s.title)}</h3>${md(s.body)}</div>`;
  $("#helpList").scrollTop=0;
}
function slugify(t){ return t.toLowerCase().replace(/[^\w\s-]/g,"").trim().replace(/\s/g,"-"); }
$("#helpSearch").addEventListener("input", drawHelp);
$("#helpList").addEventListener("click", e=>{
  if(e.target.classList.contains("back")){ drawHelp(); return; }
  const a=e.target.closest("a[data-sec]"); if(a){ e.preventDefault(); const n=HELP.findIndex(s=>slugify(s.title)===a.dataset.sec); if(n>=0) showHelp(n); return; }
  const r=e.target.closest(".help-res"); if(r) showHelp(+r.dataset.n);
});

/* ------------------------------------------------------------ opdrachten, palet en snel openen */
const CMDS = [
  ["quickOpen","Bestand openen…",MOD+"P",()=>openQP("")],
  ["palette","Opdrachtenpalet…",MOD+"⇧P",()=>openQP(">")],
  ["newSong","Nieuw nummer…","",()=>newSong()],
  ["newSetlist","Nieuwe setlist…","",()=>newSetlist()],
  ["newFolder","Nieuwe map in nummers…","",()=>newFolder("nummers")],
  ["save","Opslaan",MOD+"S",()=>save()],
  ["saveAll","Alles opslaan","",()=>saveAll()],
  ["build","Maak PDF / setlist",MOD+"↵",()=>build()],
  ["buildAll","Alle gewijzigde nummers maken","",async ()=>{ await saveAll(); busy(true,"Alle gewijzigde nummers maken…");
    try{ const j=await api("/api/build-all",{}); log(j.log); toast(j.ok?"Alles gemaakt":"Klaar, met fouten (zie Uitvoer)"); }catch(err){ toast(err.message); } finally{ busy(false); } }],
  ["preview","Voorbeeld naast de editor aan/uit",MOD+"⇧V",()=>showPreview()],
  ["panel","Paneel onderin aan/uit",MOD+"J",()=>showPanel()],
  ["sidebar","Zijbalk aan/uit",MOD+"B",()=>toggleSide()],
  ["find","Zoeken in dit bestand",MOD+"F",()=>openFind()],
  ["searchAll","Zoeken in alle bestanden",MOD+"⇧F",()=>{ setView("search"); $("#gsFind").focus(); $("#gsFind").select(); }],
  ["gotoLine","Ga naar regel…",(isMac?"⌃":"Ctrl+")+"G",()=>openQP(":")],
  ["gotoSymbol","Ga naar sectie of patroon…",MOD+"⇧O",()=>openQP("@")],
  ["closeTab","Tabblad sluiten",(isMac?"⌥":"Alt+")+"W",()=>closeTab(state)],
  ["closeAll","Alle tabbladen sluiten","",()=>closeOthers(null)],
  ["nextTab","Volgend tabblad",MOD+(isMac?"⌥→":"Alt+→"),()=>nextTab(1)],
  ["prevTab","Vorig tabblad",MOD+(isMac?"⌥←":"Alt+←"),()=>nextTab(-1)],
  ["check","Controleer",""  ,()=>{ check(); showPanel(true); panelTab("prob"); }],
  ["midi","MIDI-oefenbestand…","",()=>midi()],
  ["archive","Archiveer dit nummer","",()=>archiveSong()],
  ["renameSetlist","Setlist hernoemen…","",()=>state && state.kind==="setlist" && renameSetlist(state.path)],
  ["deleteSetlist","Setlist verwijderen (naar archief)","",()=>state && state.kind==="setlist" && deleteSetlist(state.path)],
  ["reveal","Toon in verkenner","",()=>state && revealInTree(state.path)],
  ["setlistText","Setlist: als tekst","",()=>setSetlistView("text")],
  ["setlistBuilder","Setlist: bouwer","",()=>setSetlistView("builder")],
  ["fsThis","forScore: dit nummer of deze setlist versturen","",()=>{ if(!state) return; fsSend(state.kind==="setlist" ? {setlists:[nameOf(state.path)]} : {paths:[state.path]}); }],
  ["fsAll","forScore: alles bijwerken","",()=>typeof fsSyncAll==="function" && fsSyncAll()],
  ["fsSelftest","forScore: zelftest","",()=>typeof fsSelfTest==="function" && fsSelfTest()],
  ["fsLabels","forScore: extra labels ophalen","",()=>typeof fsPullLabels==="function" && fsPullLabels()],
  ["gitAll","GitLab: alles vastleggen en versturen","",()=>typeof gitSendAll==="function" && gitSendAll()],
  ["gitPull","GitLab: ophalen","",()=>$("#gitPull").click()],
  ["gitRemote","GitLab: adres instellen…","",()=>$("#gitRemote").click()],
  ["newVersion","Nieuwe versie van dit nummer…","",()=>setView("song")],
  ["settings","Instellingen openen (instellingen.txt)","",()=>openFile("instellingen.txt",{pinned:true})],
  ["library","Eigen bibliotheek openen (bibliotheek.drum)","",()=>openFile("bibliotheek.drum",{pinned:true})],
  ["themeAuto","Thema: automatisch","",()=>setTheme("auto")],
  ["themeLight","Thema: licht","",()=>setTheme("light")],
  ["themeDark","Thema: donker","",()=>setTheme("dark")],
  ["keys","Sneltoetsen tonen","",()=>showKeys()],
  ["refresh","Vernieuwen","",()=>{ loadTree(); if(typeof refreshAll==="function") refreshAll(); }],
  ["collapse","Alle mappen inklappen","",()=>{ openDirs.clear(); drawTree(); }],
  ["vExplorer","Weergave: Verkenner",MOD+"⇧E",()=>setView("explorer")],
  ["vGit","Weergave: GitLab",MOD+"⇧G",()=>setView("git")],
  ["vFs","Weergave: forScore","",()=>setView("forscore")],
  ["vSetlists","Weergave: Setlists","",()=>setView("setlists")],
  ["vSong","Weergave: Nummer (eigenschappen en versies)","",()=>setView("song")],
  ["vInsert","Weergave: Invoegen","",()=>setView("insert")],
  ["vHelp","Weergave: Handleiding","",()=>setView("help")],
  ["vStatus","Weergave: Status","",()=>setView("status")],
];
function runCmd(id){ const c=CMDS.find(x=>x[0]===id); if(c) c[3](); }
function showKeys(){
  log("Sneltoetsen\n\n"+CMDS.filter(c=>c[2]).map(c=>c[2].padEnd(10)+"  "+c[1]).join("\n")+"\n\nIn de editor: Tab / ⇧Tab inspringen, ook voor meerdere regels.");
}
/* palet */
const QP = { items:[], sel:0, mode:"" };
function fuzzy(q, s){
  if(!q) return {score:1, html:esc(s)};
  const ql=q.toLowerCase(), sl=s.toLowerCase(); let i=0, score=0, last=-2, html="";
  const sub = sl.indexOf(ql);
  if(sub>=0) return {score:100-sub+(sub===0?50:0), html:esc(s.slice(0,sub))+"<b>"+esc(s.slice(sub,sub+q.length))+"</b>"+esc(s.slice(sub+q.length))};
  for(let k=0;k<s.length;k++){
    if(i<ql.length && sl[k]===ql[i]){ score += (k===last+1?3:1); last=k; i++; html+="<b>"+esc(s[k])+"</b>"; } else html+=esc(s[k]);
  }
  return i===ql.length ? {score, html} : null;
}
function openQP(prefix){
  hideMenu(); const q=$("#qp"); q.classList.add("show"); const inp=$("#qpIn"); inp.value=prefix||""; inp.focus(); QP.sel=0; drawQP();
}
function closeQP(){ $("#qp").classList.remove("show"); }
function drawQP(){
  const v=$("#qpIn").value; let items=[], hint="";
  if(v.startsWith(">")){
    const q=v.slice(1).trim();
    items = CMDS.filter(c=>!["palette"].includes(c[0])).map(c=>{ const f=fuzzy(q,c[1]); return f && {html:f.html, score:f.score, desc:"", key:c[2], run:c[3]}; }).filter(Boolean);
    hint = "Opdracht kiezen · ↵ uitvoeren · Esc sluiten";
  } else if(v.startsWith("@")){
    const q=v.slice(1).trim();
    items = outlineItems().map(it=>{ const label=(it.kind==="sec"||it.kind==="set")?"["+it.name+"]":it.name; const f=fuzzy(q,label);
      return f && {html:f.html, score:f.score+(1000-it.line)/1000, desc:"regel "+it.line, run:()=>gotoLine(it.line)}; }).filter(Boolean);
    if(!q) items.sort((a,b)=>+a.desc.slice(6)-+b.desc.slice(6));
    hint = state ? "Ga naar een sectie of patroon in "+nameOf(state.path) : "Open eerst een bestand";
  } else if(v.startsWith(":")){
    const n=parseInt(v.slice(1)); const total=ed.value.split("\n").length;
    items = state && n ? [{html:`Ga naar regel ${n}`, desc:`van ${total}`, run:()=>gotoLine(n)}] : [];
    hint = state ? `Typ een regelnummer (1–${total})` : "Open eerst een bestand";
  } else {
    const q=v.trim(), recent=store.get("recent",[]);
    items = allFiles().map(p=>{ const f=fuzzy(q, nameOf(p)) || (q && fuzzy(q,p)); if(!f) return null;
      const r=recent.indexOf(p); return {html: fuzzy(q,nameOf(p)) ? f.html : esc(nameOf(p)), score:f.score + (r>=0 ? (q?5:100)-r : 0), desc:parentOf(p), run:()=>openFile(p,{pinned:true})}; }).filter(Boolean);
    hint = "Typ een naam · > opdrachten · @ secties · : regel";
  }
  if(!v.startsWith("@") || v.slice(1).trim()) items.sort((a,b)=>b.score-a.score);
  QP.items=items.slice(0,60); QP.sel=Math.min(QP.sel, Math.max(0,QP.items.length-1));
  $("#qpList").innerHTML = QP.items.map((it,i)=>`<div class="qi${i===QP.sel?" on":""}" data-i="${i}"><span class="l">${it.html}</span><span class="d">${esc(it.desc||"")}</span>${it.key?`<kbd class="k">${esc(it.key)}</kbd>`:""}</div>`).join("") || '<div class="empty">Niets gevonden.</div>';
  $("#qpHint").textContent = hint;
  const on=$("#qpList .qi.on"); if(on) on.scrollIntoView({block:"nearest"});
}
$("#qpIn").addEventListener("input", ()=>{ QP.sel=0; drawQP(); });
$("#qpIn").addEventListener("keydown", e=>{
  if(e.key==="ArrowDown"){ e.preventDefault(); QP.sel=Math.min(QP.items.length-1, QP.sel+1); drawQP(); }
  else if(e.key==="ArrowUp"){ e.preventDefault(); QP.sel=Math.max(0, QP.sel-1); drawQP(); }
  else if(e.key==="Enter"){ e.preventDefault(); const it=QP.items[QP.sel]; closeQP(); if(it) it.run(); }
  else if(e.key==="Escape"){ e.preventDefault(); closeQP(); if(state && !isBuilder()) ed.focus(); }
});
$("#qpList").addEventListener("click", e=>{ const r=e.target.closest(".qi"); if(!r) return; const it=QP.items[+r.dataset.i]; closeQP(); if(it) it.run(); });

/* ------------------------------------------------------------ sneltoetsen */
document.addEventListener("keydown", e=>{
  const mod = e.metaKey||e.ctrlKey, k=e.key.toLowerCase();
  const inField = document.activeElement && document.activeElement!==ed && /^(INPUT|SELECT|TEXTAREA)$/.test(document.activeElement.tagName);
  if(e.key==="Escape"){ hideMenu(); if($("#qp").classList.contains("show")){ closeQP(); return; } if($("#findbar").classList.contains("show")){ closeFind(); return; } }
  if(e.key==="F1" || (mod && e.shiftKey && k==="p")){ e.preventDefault(); openQP(">"); return; }
  if(mod && !e.shiftKey && k==="p"){ e.preventDefault(); openQP(""); return; }
  if(mod && k==="s"){ e.preventDefault(); if(e.altKey) saveAll(); else save(); return; }
  if(mod && e.key==="Enter"){ e.preventDefault(); build(); return; }
  if(mod && !e.shiftKey && k==="b"){ e.preventDefault(); toggleSide(); return; }
  if(mod && !e.shiftKey && k==="j"){ e.preventDefault(); showPanel(); return; }
  if(mod && e.shiftKey && k==="f"){ e.preventDefault(); runCmd("searchAll"); return; }
  if(mod && e.shiftKey && k==="e"){ e.preventDefault(); setView("explorer"); return; }
  if(mod && e.shiftKey && k==="g"){ e.preventDefault(); setView("git"); return; }
  if(mod && e.shiftKey && k==="o"){ e.preventDefault(); openQP("@"); return; }
  if(mod && e.shiftKey && k==="v"){ e.preventDefault(); showPreview(); return; }
  if(e.ctrlKey && !e.metaKey && k==="g"){ e.preventDefault(); openQP(":"); return; }
  if(e.altKey && !mod && (k==="w" || e.code==="KeyW")){ e.preventDefault(); closeTab(state); return; }
  if(mod && e.altKey && (e.key==="ArrowRight" || e.key==="ArrowLeft")){ e.preventDefault(); nextTab(e.key==="ArrowRight"?1:-1); return; }
  if(mod && !e.shiftKey && k==="f" && state){ e.preventDefault(); openFind(); return; }
  if(mod && !inField && state && (k==="z" || k==="y")){ e.preventDefault(); histApply(k==="z" && !e.shiftKey ? -1 : 1); return; }
});

/* ------------------------------------------------------------ welkom */
function drawWelcome(){
  const rec = store.get("recent",[]).filter(p=>allFiles().includes(p)).slice(0,8);
  $("#welcome").innerHTML = `<div class="w"><h1>Drumsheetz Studio</h1><div class="sub">Drum sheets uitschrijven, versies, forScore en GitLab.</div>
    <div class="cols"><div><h4>Begin</h4><a data-cmd="newSong">＋ Nieuw nummer…</a><a data-cmd="newSetlist">＋ Nieuwe setlist…</a><a data-cmd="quickOpen">Bestand openen… <kbd>${MOD}P</kbd></a><a data-cmd="vHelp">Handleiding</a></div>
    <div><h4>Recent</h4>${rec.map(p=>`<a data-open="${esc(p)}" title="${esc(p)}">${esc(nameOf(p))} <span class="hint">${esc(parentOf(p))}</span></a>`).join("")||'<span class="hint">Nog niets geopend.</span>'}</div></div>
    <div class="keys"><kbd>${MOD}P</kbd><span>bestand openen</span><kbd>${MOD}⇧P</kbd><span>alle opdrachten</span><kbd>${MOD}S</kbd><span>opslaan</span>
      <kbd>${MOD}↵</kbd><span>PDF maken</span><kbd>${MOD}⇧V</kbd><span>voorbeeld ernaast</span><kbd>${MOD}B</kbd><span>zijbalk</span><kbd>${MOD}J</kbd><span>paneel onderin</span></div></div>`;
}
$("#welcome").addEventListener("click", e=>{ const c=e.target.closest("[data-cmd]"); if(c){ runCmd(c.dataset.cmd); return; } const o=e.target.closest("[data-open]"); if(o) openFile(o.dataset.open,{pinned:true}); });
