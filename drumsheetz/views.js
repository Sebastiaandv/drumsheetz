/* Drumsheetz Studio — weergaven in de zijbalk (GitLab, forScore, Setlists, Status), de setlist-bouwer en het opstarten. */
"use strict";

/* ================================================================== forScore */
const FS = { data:null };
const FS_TODO = s => ["niet","gewijzigd","wacht"].includes(s.status);
async function loadFs(){
  try{ FS.data = await api("/api/forscore/catalog"); }catch(err){ FS.data=null; }
  drawTree(); drawFsView(); drawSetlists(); fsBadge();
}
function fsInfo(path){ return FS.data ? (FS.data.songs.find(s=>s.path===path) || FS.data.setlists.find(s=>s.path===path)) : null; }
function fsDot(path){
  const s=fsInfo(path); if(!s) return "";
  const cls={niet:"nieuw", gewijzigd:"pdf", wacht:"pdf"}[s.status] || s.status;
  if(s.items){
    const tip={niet:"setlist nog niet in forScore", actueel:`in forScore als '${s.fs_title||s.title}'`,
      gewijzigd:`veranderd: wordt '${s.title} V${(s.version||0)+1}' in forScore`, wacht:"nog niet (opnieuw) in forScore"}[s.status]||"";
    return `<span class="dot ${cls}" title="${esc(tip)}"></span>`;
  }
  let tip = {niet:`nog niet in forScore · wordt V${s.next}`, actueel:`in forScore als '${s.name}'`,
    gewijzigd:`gewijzigd: wordt V${s.next} in forScore (een nieuw stuk naast de oude, er wordt niets overschreven)`,
    wacht:`V${s.version} staat nog niet in forScore`, fout:"bevat een fout"}[s.status] || "";
  if((s.old_in_forscore||[]).length) tip += ` · oude versie(s) nog in forScore: ${s.old_in_forscore.map(x=>x.replace(/\.pdf$/,"")).join(", ")}`;
  let out = s.version ? `<span class="vb${s.status==="gewijzigd"?" ch":""}" title="${s.status==="gewijzigd"?"gewijzigd sinds V"+s.version:"versie "+s.version}">V${s.version}${s.status==="gewijzigd"?"*":""}</span>` : "";
  if((s.label_todo||[]).length) out += `<span class="warnmark" title="Labels in forScore (${esc((s.labels_have||[]).join(", ")||"geen")}) wijken af van de map (${esc((s.labels_want||[]).join(", ")||"geen")}): pas het label in forScore aan">⚑</span>`;
  if((s.dups||[]).length) out += `<span class="warnmark" title="staat ${s.dups.length}× in forScore: ${esc(s.dups.join(", "))}">⚠</span>`;
  return out + `<span class="dot ${cls}" title="${esc(tip)}"></span>`;
}
function fsTodoCount(){ const d=FS.data; return d ? d.songs.filter(FS_TODO).length + d.setlists.filter(s=>s.status!=="actueel").length : 0; }
function fsBadge(){
  const d=FS.data, n=fsTodoCount();
  $("#bdFs").textContent = n ? String(n) : ""; $("#bdFs").className = "badge";
  $("#sbFsT").textContent = !d ? "forScore ?" : (!d.library_ok ? "forScore niet gelezen" : (n ? `forScore: ${n} te doen` : "forScore ✓"));
  $("#sbFs").title = !d ? "forScore" : (d.library_ok ? `forScore: ${d.fs_counts.scores} stukken, ${d.fs_counts.setlists} setlists` : "forScore-bibliotheek niet gelezen: "+(d.notes||[]).join("; "));
}
const FS_TXT = s => ({niet:`nog niet in forScore → V${s.next}`, gewijzigd:`gewijzigd → wordt V${s.next}`, wacht:`V${s.version} nog niet in forScore`,
  actueel: s.name ? `in forScore: ${s.name.replace(/\.pdf$/,"")}` : "in forScore", fout: s.error || "bevat een fout"}[s.status] || s.status);
function drawFsView(){
  const body=$("#fsBody"), d=FS.data; if(!body) return;
  const n=fsTodoCount();
  $("#fsAll").disabled = !d || !n; $("#fsAll").textContent = "Alles naar forScore" + (n?` (${n})`:"");
  if(!d){ body.innerHTML='<div class="empty">forScore-overzicht laden…</div>'; return; }
  const q=$("#fsSearch").value.toLowerCase().trim(), onlyTodo=$("#fsTodo").checked;
  let h = d.library_ok ? "" : `<div class="notice">De forScore-bibliotheek op deze Mac kan niet gelezen worden (${esc((d.notes||[]).join("; "))}). Nummers die nog nooit verstuurd zijn worden overgeslagen, zodat er niets dubbel komt. Zie Status.</div>`;
  const groups={};
  for(const s of d.songs){
    const attention = FS_TODO(s) || (s.label_todo||[]).length || (s.dups||[]).length || s.status==="fout";
    if(onlyTodo && !attention) continue;
    if(q && !(s.title+" "+(s.artist||"")+" "+s.path).toLowerCase().includes(q)) continue;
    const parts=s.path.split("/"); const folder = parts.length>2 ? parts[1] : "";
    (groups[folder]=groups[folder]||[]).push(s);
  }
  const keys=Object.keys(groups).sort((a,b)=>(a==="")-(b==="") || a.localeCompare(b,"nl"));
  for(const k of keys){
    h += `<div class="grp">${k ? "▤ "+esc(k)+' <span class="chip">label</span>' : "Zonder map"}<span class="n">${groups[k].length}</span></div>`;
    for(const s of groups[k]){
      const warn = ((s.label_todo||[]).length?`<span class="warnmark" title="labels in forScore wijken af van de map">⚑</span>`:"")+((s.dups||[]).length?`<span class="warnmark" title="dubbel in forScore">⚠</span>`:"")
        + (s.path.split("/").length>3?` <span class="chip fout" title="forScore kent geen mappen in mappen">map te diep</span>`:"");
      h += `<div class="li${state&&s.path===state.path?" active":""}" data-open="${esc(s.path)}"><span class="dot ${s.status}"></span>
        <div class="m"><div class="t">${esc(s.title)} ${s.version?`<span class="vb">V${s.version}</span>`:""}${warn}</div><div class="s">${esc(s.artist||"")}${s.artist?" · ":""}${esc(FS_TXT(s))}</div></div>
        <span class="acts"><button class="ib" data-fs="${esc(s.path)}" title="${FS_TODO(s)?"naar forScore":"staat er al actueel in"}" ${FS_TODO(s)?"":"disabled"}><svg class="i s"><use href="#i-send"/></svg></button></span></div>`;
    }
  }
  const sls=d.setlists.filter(s=>(!onlyTodo || s.status!=="actueel") && (!q || s.title.toLowerCase().includes(q)));
  if(sls.length){
    h += `<div class="grp">☰ Setlists<span class="n">${sls.length}</span></div>`;
    for(const s of sls){
      const txt={niet:"nog niet in forScore", actueel:`in forScore: ${s.fs_title||s.title}`, gewijzigd:`veranderd → wordt ${s.title} V${(s.version||0)+1}`, wacht:"nog niet (opnieuw) in forScore"}[s.status]||s.status;
      h += `<div class="li" data-open="${esc(s.path)}"><span class="dot ${s.status}"></span><div class="m"><div class="t">${esc(s.title)}</div><div class="s">${esc(txt)}</div></div>
        <span class="acts"><button class="ib" data-fsset="${esc(s.name)}" ${s.status==="actueel"?"disabled":""} title="setlist naar forScore"><svg class="i s"><use href="#i-send"/></svg></button></span></div>`;
    }
  }
  if(!keys.length && !sls.length) h += `<div class="empty${onlyTodo&&!q?" ok":""}">${onlyTodo && !q ? "✓ forScore is bijgewerkt." : "Niets gevonden."}</div>`;
  body.innerHTML = h;
}
$("#fsTodo").addEventListener("change", drawFsView);
$("#fsSearch").addEventListener("input", drawFsView);
$("#fsRefresh").onclick = loadFs;
$("#fsBody").addEventListener("click", e=>{
  const b=e.target.closest("button"); if(b){ e.stopPropagation();
    if(b.dataset.fs) return fsSend({paths:[b.dataset.fs]});
    if(b.dataset.fsset) return fsSend({setlists:[b.dataset.fsset]}); return; }
  const r=e.target.closest("[data-open]"); if(r) openFile(r.dataset.open, {preview:true});
});
$("#fsMore").onclick = e=>{ e.stopPropagation(); menuAt(e.currentTarget, [
  ["Alles naar forScore", fsSyncAll, "", fsTodoCount()>0], ["Extra labels ophalen uit forScore…", fsPullLabels], ["Zelftest…", fsSelfTest]]); };
$("#fsAll").onclick = fsSyncAll;
async function fsSend(body){
  await saveAll();
  busy(true,"Naar forScore sturen (één voor één, met controle)…");
  try{ const j=await api("/api/forscore", body); log(j.log); toast(j.ok?"Naar forScore gestuurd":"Klaar, met meldingen (zie Uitvoer)"); }
  catch(err){ toast(err.message); } finally{ busy(false); loadFs(); refreshSongView(); loadGit(); }
}
async function fsSyncAll(){
  await saveAll();
  const d=FS.data;
  if(d){
    const nw=d.songs.filter(s=>s.status==="niet").length, ch=d.songs.filter(s=>["gewijzigd","wacht"].includes(s.status)).length, sl=d.setlists.filter(s=>s.status!=="actueel").length;
    if(nw+ch+sl===0 && !confirm("Alles lijkt al bijgewerkt. Toch controleren en synchroniseren?")) return;
    if(nw+ch+sl>0 && !confirm(`forScore bijwerken?\n\n• ${nw} nieuw nummer(s) (als V1)\n• ${ch} nieuwe versie(s): komen als nieuw stuk naast de oude\n• ${sl} setlist(s)\n\nStukken die al in forScore staan worden nooit aangeraakt.`)) return;
  }
  busy(true,"forScore bijwerken (één voor één, met controle)…");
  try{ const j=await api("/api/forscore",{}); log(j.log); toast(/Zelf doen in forScore/.test(j.log) ? "Klaar: een paar dingen moet je zelf in forScore doen (zie Uitvoer)" : "forScore is bijgewerkt"); }
  catch(err){ toast(err.message); } finally{ busy(false); loadFs(); refreshSongView(); loadGit(); }
}
async function fsSelfTest(){
  if(!confirm("Zelftest: er worden 2 teststukken en 1 testsetlist ('Drumsheetz zelftest') naar forScore gestuurd en gecontroleerd. Daarna kun je ze in forScore weggooien. Doorgaan?")) return;
  busy(true,"Zelftest met forScore (± 2 minuten)…");
  try{ const j=await api("/api/forscore/selftest",{}); log(j.log); toast("Zelftest klaar: rapport in Uitvoer"); }catch(err){ toast(err.message); } finally{ busy(false); loadFs(); }
}
async function fsPullLabels(){
  await saveAll(); busy(true,"Labels uit forScore lezen…");
  try{
    const j=await api("/api/forscore/labels",{}); log(j.log);
    if(/→/.test(j.log) && confirm("De extra labels hierboven (zie Uitvoer) overnemen in de nummers?")){
      const k=await api("/api/forscore/labels",{apply:true}); log(k.log); toast("Labels overgenomen");
      for(const t of TABS) if(!dirty(t)) await reloadFromDisk(t);
    } else if(!/→/.test(j.log)) toast("Niets over te nemen");
  }catch(err){ toast(err.message); } finally{ busy(false); loadFs(); }
}

/* ================================================================== GitLab */
const G = { data:null, sel:new Set() };
const GSTATE = {nieuw:"nieuw", gewijzigd:"gewijzigd", verwijderd:"verwijderd", verplaatst:"verplaatst", versies:"versies"};
const GMARK = {nieuw:"+", gewijzigd:"~", verwijderd:"−", verplaatst:"→"};
async function loadGit(fetchRemote){
  try{ G.data = await api("/api/git/status" + (fetchRemote ? "?fetch=1" : "")); }
  catch(err){ G.data = {enabled:false, reason:err.message, items:[]}; }
  for(const k of [...G.sel]) if(!(G.data.items||[]).some(i=>i.key===k)) G.sel.delete(k);
  drawGit(); gitBadge();
}
function gitBadge(){
  const d=G.data; if(!d) return;
  const n=(d.items||[]).length;
  $("#bdGit").textContent = n ? String(n) : (d.ahead ? "↑" : "");
  $("#sbGitT").textContent = !d.enabled ? "geen git" : `${d.branch||"main"}${n?` · ${n} gewijzigd`:""}${d.ahead?` ↑${d.ahead}`:""}${d.behind?` ↓${d.behind}`:""}`;
  $("#sbGit").title = !d.enabled ? d.reason : (d.remote ? "GitLab: "+d.remote : "GitLab nog niet ingesteld (alleen lokaal vastleggen)");
}
function drawGit(){
  const body=$("#gitBody"), d=G.data; if(!body || !d) return;
  const msgEl=$("#gitMsg"), keepMsg = msgEl ? msgEl.value : "";
  if(!d.enabled){
    body.innerHTML = `<div class="notice">${esc(d.reason)}</div>` + (d.can_init ? `<div class="side-tools"><button class="btn primary wide" id="gitInit">Maak er een git-repo van</button></div>` : "");
    return;
  }
  const items=d.items||[], nsel=G.sel.size;
  let h = `<div class="side-tools">
    <input class="field" id="gitMsg" placeholder="Omschrijving (leeg = automatisch)">
    <button class="btn primary wide" id="gitAll" ${items.length||d.ahead?"":"disabled"}>${items.length ? `✓ Alles naar GitLab (${items.length})` : (d.ahead ? `↑ ${d.ahead} versturen naar GitLab` : "✓ Alles staat in GitLab")}</button>
    ${nsel?`<button class="btn wide" id="gitSel">Geselecteerde naar GitLab (${nsel})</button>`:""}
    <div class="hint" style="font-size:12px">${d.remote ? "GitLab: <span class='mono'>"+esc(d.remote)+"</span>" : "Nog geen GitLab-adres: alles wordt alleen hier vastgelegd (🔗 om het in te stellen)."}
      ${d.behind?`<br><b>${d.behind} nieuw in GitLab</b> — ophalen met ↓`:""}${d.fetch_error?`<br><span style="color:var(--err)">GitLab niet bereikbaar</span>`:""}
      ${d.last?`<br>Laatste: ${esc(d.last.subject)} (${ago(d.last.time)})`:""}</div>
  </div>`;
  if(!items.length){ h += `<div class="empty ok">✓ Geen wijzigingen.</div>`; body.innerHTML=h; if($("#gitMsg")) $("#gitMsg").value=keepMsg; return; }
  for(const [kind,label] of [["song","Nummers"],["setlist","Setlists"],["other","Overig"]]){
    const list=items.filter(i=>i.kind===kind); if(!list.length) continue;
    h += `<div class="grp"><input type="checkbox" data-selgroup="${kind}" ${list.every(i=>G.sel.has(i.key))?"checked":""} title="alles in deze groep selecteren"> ${label}<span class="n">${list.length}</span></div>`;
    for(const it of list){
      const main = it.main || (it.paths[0]||{}).path;
      const mainP = it.paths.find(p=>p.path===main) || {};
      const sub = it.moved_from ? `verplaatst van ${it.moved_from}` : it.paths.map(p=>(GMARK[p.state]||"·")+" "+p.path.replace(/^(nummers|setlists|versies)\//,"")).join(", ");
      const deep = kind==="song" && it.name.split("/").length>2 ? ' <span class="chip fout">map te diep</span>' : "";
      h += `<div class="li" data-key="${esc(it.key)}" data-main="${esc(main||"")}" data-base="${esc(mainP.base||"")}" title="${esc(it.paths.map(p=>p.state+": "+p.path).join("\n"))}">
        <input type="checkbox" data-sel="${esc(it.key)}" ${G.sel.has(it.key)?"checked":""}>
        <div class="m"><div class="t">${esc(it.title||it.name)} <span class="chip ${it.state}">${GSTATE[it.state]||it.state}</span>${deep}</div><div class="s">${esc(sub)}</div></div>
        <span class="acts">${main && /\.(drum|txt|py|md)$/.test(main)?`<button class="ib" data-diff="1" title="Bekijk wat er veranderd is"><svg class="i s"><use href="#i-split"/></svg></button>`:""}
          <button class="ib" data-send="${esc(it.key)}" title="Alleen dit naar GitLab"><svg class="i s"><use href="#i-send"/></svg></button></span></div>`;
    }
  }
  body.innerHTML = h;
  if($("#gitMsg")) $("#gitMsg").value = keepMsg;
}
async function gitAct(msg, fn){
  busy(true, msg);
  try{ const j=await fn(); if(j && j.log!==undefined) log(j.log, !j.ok); if(j && j.ok!==false) toast("Klaar"); return j; }
  catch(err){ log("✗ "+err.message); toast(err.message); }
  finally{ busy(false); await loadGit(false); if(typeof loadHealth==="function" && VIEW==="status") loadHealth(); }
}
async function gitSendAll(){
  await saveAll(); await loadGit(false);
  const d=G.data; if(!d || !d.enabled){ setView("git"); return; }
  const n=(d.items||[]).length;
  if(!n && !d.ahead){ toast("Alles staat al in GitLab"); return; }
  if(n && !confirm(`Alle ${n} wijziging(en) vastleggen${d.remote?" en naar GitLab sturen":""}?`)) return;
  return gitAct("Naar GitLab…", ()=>api("/api/git/send", {all:true, message:($("#gitMsg")||{}).value||""}));
}
$("#gitBody").addEventListener("change", e=>{
  const c=e.target;
  if(c.dataset.sel){ c.checked ? G.sel.add(c.dataset.sel) : G.sel.delete(c.dataset.sel); drawGit(); }
  if(c.dataset.selgroup){ (G.data.items||[]).filter(i=>i.kind===c.dataset.selgroup).forEach(i=>c.checked?G.sel.add(i.key):G.sel.delete(i.key)); drawGit(); }
});
$("#gitBody").addEventListener("click", async e=>{
  const t=e.target; const msg=()=>($("#gitMsg")?$("#gitMsg").value.trim():"");
  if(t.closest("input")) return;
  if(t.id==="gitInit") return gitAct("Git-repo maken…", ()=>api("/api/git/init", {}));
  if(t.id==="gitAll") return gitSendAll();
  if(t.id==="gitSel"){ await saveAll(); return gitAct("Naar GitLab…", async ()=>{ const j=await api("/api/git/send", {keys:[...G.sel], message:msg()}); G.sel.clear(); return j; }); }
  const row=t.closest(".li"); if(!row) return;
  const b=t.closest("button");
  if(b && b.dataset.send){ await saveAll(); return gitAct("Naar GitLab…", ()=>api("/api/git/send", {keys:[b.dataset.send], message:msg()})); }
  if(b && b.dataset.diff || (!b && row.dataset.main)){
    const path=row.dataset.main, base=row.dataset.base||null;
    if(!b && allFiles().includes(path)){ openFile(path, {preview:true}); return; }
    try{ const d=await api("/api/git/diff", {path, base}); showDiff(base?`${base} → ${path}`:path, "Ten opzichte van de laatste vastlegging: "+d.summary, d.lines); }catch(err){ toast(err.message); }
  }
});
$("#gitRefresh").onclick = ()=>{ busy(true,"GitLab bekijken…"); loadGit(true).finally(()=>busy(false)); };
$("#gitPull").onclick = ()=>{ if(!G.data || !G.data.remote){ toast("Stel eerst het GitLab-adres in (🔗)"); return; }
  gitAct("Ophalen uit GitLab…", ()=>api("/api/git/pull", {})).then(async ()=>{ for(const t of TABS) if(!dirty(t)) await reloadFromDisk(t).catch(()=>{}); loadTree(); }); };
$("#gitRemote").onclick = ()=>{
  if(G.data && !G.data.enabled){ setView("git"); toast(G.data.reason); return; }
  const url = prompt("Adres van de GitLab-repo voor je muziek (bv. git@gitlab.thuis:sebastiaan/drumsheetz-muziek.git of https://…).\nLeeg = weghalen.", (G.data&&G.data.remote)||"");
  if(url===null) return;
  gitAct("GitLab-adres instellen…", ()=>api("/api/git/remote", {url}));
};
$("#sbGit").onclick = ()=>setView("git");
$("#sbFs").onclick = ()=>setView("forscore");

/* ================================================================== Status */
const HEALTH = { data:null, timer:null };
async function loadHealth(){
  const body=$("#stBody");
  if(!HEALTH.data) body.innerHTML='<div class="empty">Controleren…</div>';
  try{ HEALTH.data = await api("/api/health"); }catch(err){ body.innerHTML=`<div class="notice err">${esc(err.message)}</div>`; return; }
  drawHealth();
}
function drawHealth(){
  const d=HEALTH.data, body=$("#stBody"); if(!d) return;
  const order=["ok","info","warn","err"], bad=d.checks.filter(c=>c.state==="err").length, warn=d.checks.filter(c=>c.state==="warn").length;
  const title={ok:"Alles werkt", info:"Alles werkt", warn:"Werkt, maar let op", err:"Er werkt iets niet"}[d.overall];
  let h=`<div class="statbanner ${d.overall}"><span class="dot ${d.overall==="info"?"ok":d.overall}"></span>${title}<span class="hint" style="margin-left:auto;font-weight:400;font-size:11px">${new Date(d.time*1000).toLocaleTimeString("nl-NL")}</span></div>`;
  const groups=[]; for(const c of d.checks){ let g=groups.find(x=>x.name===c.group); if(!g){ g={name:c.group, items:[]}; groups.push(g); } g.items.push(c); }
  for(const g of groups){
    const worst=order[Math.max(...g.items.map(c=>order.indexOf(c.state)))];
    h += `<div class="grp"><span class="dot ${worst==="info"?"ok":worst}"></span> ${esc(g.name)}</div>` + g.items.map(c=>
      `<div class="statrow"><span class="dot ${c.state}"></span><div class="m"><div class="nm">${esc(c.name)}</div><div class="d">${esc(c.detail)}</div>${c.hint?`<div class="tip">${esc(c.hint)}</div>`:""}</div></div>`).join("");
  }
  body.innerHTML=h;
  const b=$("#bdStatus"); b.textContent = bad ? String(bad) : (warn ? "!" : ""); b.className = "badge " + (bad ? "err" : "warn");
}
$("#stRefresh").onclick = loadHealth;

/* ================================================================== Setlists (lijst) */
function drawSetlists(){
  const body=$("#slBody"); if(!body) return;
  const node=(treeData||[]).find(n=>n.path==="setlists"); const files=node ? node.children.filter(c=>!c.dir) : [];
  if(!files.length){ body.innerHTML='<div class="empty">Nog geen setlists. Maak er een met ＋ hierboven.</div>'; return; }
  body.innerHTML = files.map(f=>{
    const s = FS.data ? FS.data.setlists.find(x=>x.path===f.path) : null;
    const n = s ? s.items.filter(i=>i.kind!=="break").length : null;
    return `<div class="li${state&&f.path===state.path?" active":""}" data-open="${esc(f.path)}"><span class="hint" style="width:14px">☰</span>
      <div class="m"><div class="t">${esc(s ? s.title : nameOf(f.path))}</div><div class="s">${n!==null?n+" nummers · ":""}${esc(baseOf(f.path))}</div></div>
      <span class="acts"><button class="ib" data-rename="${esc(f.path)}" title="Bestandsnaam wijzigen"><svg class="i s"><use href="#i-code"/></svg></button>
        <button class="ib" data-del="${esc(f.path)}" title="Verwijderen (naar archief)"><svg class="i s"><use href="#i-close"/></svg></button></span>${fsDot(f.path)}</div>`;
  }).join("");
}
$("#slBody").addEventListener("click", e=>{
  const b=e.target.closest("button"); if(b){ e.stopPropagation(); if(b.dataset.rename) renameSetlist(b.dataset.rename); if(b.dataset.del) deleteSetlist(b.dataset.del); return; }
  const r=e.target.closest("[data-open]"); if(r) openFile(r.dataset.open, {pinned:true}).then(m=>{ if(m){ setSetlistView("builder"); } }); });

/* ================================================================== setlist-bouwer */
const BL = { songs:null, info:null, infoFor:null, items:[], header:[], trailing:[], timer:null, drag:null, q:"" };
const META_FIELDS = [["titel","Titel",/^(titel|title|naam)$/i],["datum","Datum",/^(datum|date)$/i],["plaats","Plaats",/^(plaats|locatie|venue)$/i],["notitie","Notitie",/^(notitie|notes)$/i]];
async function loadSongs(force){ if(BL.songs && !force) return; try{ BL.songs=(await api("/api/songs")).songs; }catch(e){ BL.songs=[]; } }
function builderSync(){
  const on=isBuilder(); $("#builder").classList.toggle("on", on);
  if(!on) return;
  loadSongs().then(()=>{ if(isBuilder()) refreshBuilderInfo(true); });
  drawBuilder();
}
function builderChanged(){ if(!isBuilder()) return; clearTimeout(BL.timer); BL.timer=setTimeout(()=>refreshBuilderInfo(), 200); }
async function refreshBuilderInfo(now){
  if(!isBuilder()) return;
  const m=state, content=ed.value;
  if(!now && BL.infoFor===content && BL.path===m.path) return;
  try{ const j=await api("/api/setlist-info", {path:m.path, content}); if(m!==state || content!==ed.value) return;
    BL.info=j; BL.infoFor=content; BL.path=m.path; buildModel(content, j); drawBuilder(); }catch(err){ toast(err.message); }
}
function buildModel(text, info){
  const lines=text.split("\n"), byLine={};
  for(const e of info.entries) byLine[e.line]=e;
  const first = info.entries.length ? Math.min(...info.entries.map(e=>e.line)) : lines.length+1;
  BL.header = lines.slice(0, first-1);
  BL.items=[]; let pre=[];
  for(let i=first-1;i<lines.length;i++){
    const ln=lines[i], e=byLine[i+1];
    if(e){ BL.items.push({raw:ln, pre, info:e}); pre=[]; }
    else if(/^\s*#/.test(ln)) pre.push(ln);
    else if(!ln.trim()) continue;
    else { BL.items.push({raw:ln, pre, info:{kind:"song", title:ln.trim(), error:"?"}}); pre=[]; }
  }
  BL.trailing = pre;
}
function serialize(){
  const out=BL.header.slice(); while(out.length && !out[out.length-1].trim()) out.pop();
  if(out.length) out.push("");
  BL.items.forEach((it,i)=>{ if(it.info.kind==="break" && i>0 && out.length && out[out.length-1]!=="") out.push(""); out.push(...it.pre, it.raw); });
  out.push(...BL.trailing);
  return out.join("\n").replace(/\n*$/,"")+"\n";
}
function commit(){ const t=serialize(); BL.infoFor=null; setContent(t); drawBuilder(); }
function metaValue(rx){ for(const ln of BL.header){ const m=splitComment(ln)[0].match(/^\s*([\w\-]+)\s*:\s*(.*?)\s*$/); if(m && rx.test(m[1])) return m[2]; } return ""; }
function setMeta(key, rx, value){
  let done=false;
  BL.header = BL.header.map(ln=>{ if(done) return ln; const m=splitComment(ln)[0].match(/^\s*([\w\-]+)\s*:/); if(m && rx.test(m[1])){ done=true; return value ? `${key}: ${value}` : null; } return ln; }).filter(x=>x!==null);
  if(!done && value){ let at=0; while(at<BL.header.length && /^\s*#/.test(BL.header[at])) at++;
    let last=at-1; BL.header.forEach((ln,i)=>{ if(/^\s*[\w\-]+\s*:/.test(splitComment(ln)[0])) last=i; });
    BL.header.splice(last+1, 0, `${key}: ${value}`); }
  commit();
}
function lineFor(song){ return song.id; }
function setNote(it, note){
  const [code, com] = splitComment(it.raw);
  const i = code.indexOf("|");
  const left = (i>=0 ? code.slice(0,i) : code).trimEnd();
  it.raw = (note ? left.padEnd(Math.max(26, left.length+1))+"| "+note : left) + (com ? "   "+com.trim() : "");
  it.info.note = note; commit();
}
function drawBuilder(){
  const box=$("#builder"); if(!isBuilder()) return;
  if(BL.path!==state.path || !BL.info){ box.innerHTML='<div class="b-main"><div class="empty">Setlist laden…</div></div>'; return; }
  const meta = Object.fromEntries(META_FIELDS.map(([k,l,rx])=>[k, metaValue(rx)]));
  let n=0, tot=0, unknown=0, h="";
  const songs = BL.items.filter(it=>it.info.kind!=="break");
  for(const it of songs){ if(it.info.duration) tot+=it.info.duration; else unknown++; }
  // subtotalen per set
  const sub=[]; let cur=null;
  BL.items.forEach((it,i)=>{ if(it.info.kind==="break"){ cur={i, d:0, n:0, u:0}; sub[i]=cur; } else if(cur){ cur.n++; if(it.info.duration) cur.d+=it.info.duration; else cur.u++; } });
  const rows = BL.items.map((it,i)=>{
    const e=it.info;
    if(e.kind==="break"){ const s=sub[i];
      return `<div class="b-row brk" draggable="true" data-i="${i}"><span class="h" title="slepen">⋮⋮</span><span></span>
        <div class="tt"><span class="t" data-rename="${i}" title="dubbelklik om te hernoemen">${esc(e.display||e.title||"Pauze")}</span></div><span></span><span></span>
        <span class="num">${s.n?fmtDur(s.d)+(s.u?"+":""):""}</span>
        <span class="ra"><button class="ib" data-rm="${i}" title="Weghalen"><svg class="i s"><use href="#i-close"/></svg></button></span></div>`; }
    n++;
    const missing = e.error && e.kind!=="pdf";
    return `<div class="b-row${missing?" missing":""}" draggable="true" data-i="${i}"><span class="h" title="slepen">⋮⋮</span><span class="nr">${n}</span>
      <div class="tt"><div class="t">${esc(e.title||e.ref)}${e.artist?` <span class="a">– ${esc(e.artist)}</span>`:""}${e.kind==="pdf"?' <span class="chip">PDF</span>':""}</div>
        ${missing?`<div class="err">${esc(e.error==="?"?"onbekende regel":"niet gevonden: "+(e.ref||e.title))}</div>`:""}
        <div class="note" data-note="${i}" title="klik voor een notitie">${e.note?esc(e.note):'<span style="opacity:.6">+ notitie</span>'}</div></div>
      <span class="num">${e.bpm?esc(e.bpm)+" bpm":""}</span><span class="num">${esc(e.meter||"")}</span><span class="num">${e.duration?fmtDur(e.duration):"?"}</span>
      <span class="ra">${e.path&&e.path.startsWith("nummers/")?`<button class="ib" data-openi="${i}" title="Nummer openen"><svg class="i s"><use href="#i-external"/></svg></button>`:""}
        <button class="ib" data-rm="${i}" title="Uit de setlist halen"><svg class="i s"><use href="#i-close"/></svg></button></span></div>`;
  }).join("");
  const inSet = {}; for(const it of songs) if(it.info.path) inSet[it.info.path]=(inSet[it.info.path]||0)+1;
  const q=BL.q.toLowerCase();
  const picks=(BL.songs||[]).filter(s=>!q || (s.title+" "+s.artist+" "+s.folder+" "+s.id).toLowerCase().includes(q))
    .sort((a,b)=>a.title.localeCompare(b.title,"nl"));
  h = `<div class="b-main">
    <div class="b-head">
      <label class="full">Titel<input class="title" data-meta="titel" value="${esc(meta.titel)}" placeholder="${esc(nameOf(state.path))}"></label>
      <label>Datum<input data-meta="datum" value="${esc(meta.datum)}" placeholder="bv. 12 juni 2026"></label>
      <label>Plaats<input data-meta="plaats" value="${esc(meta.plaats)}" placeholder="bv. De Boerderij"></label>
      <label class="full">Notitie<input data-meta="notitie" value="${esc(meta.notitie)}" placeholder="bv. In-ears mee!"></label>
      <div class="full b-file">Bestand: <span class="mono">${esc(state.path)}</span>
        <button class="btn small" id="blRename" title="Bestandsnaam wijzigen">Hernoemen…</button>
        <button class="btn small" id="blDelete" title="Naar archief/setlists/ verplaatsen">Verwijderen</button></div>
    </div>
    <div class="b-sum"><span><b>${n}</b> nummers</span><span>speelduur <b>${fmtDur(tot)}${unknown?"+":""}</b></span>
      <span class="sp"></span>
      <button class="btn small" id="blBreak">＋ Set / pauze</button>
      <button class="btn small" id="blFs" title="Setlist (met de nummers) naar forScore">→ forScore</button>
      <button class="btn small primary" id="blBuild" title="PDF's, boek, voorblad en podiumlijst maken">▶ Maak setlist</button></div>
    <div class="b-list" id="blList">${rows || '<div class="b-empty">Sleep nummers hierheen, of klik op ＋ bij een nummer rechts.</div>'}</div>
    <div class="hint" style="margin-top:8px;font-size:12px">Sleep om de volgorde te veranderen · dubbelklik op een set om te hernoemen · ${MOD}Z maakt ongedaan · ${MOD}S slaat op · ⟨/⟩ rechtsboven toont de tekst</div>
  </div>
  <div class="b-pick"><div class="side-h"><span class="t">Nummers toevoegen</span>
      <button class="ib" id="blReload" title="Lijst vernieuwen"><svg class="i s"><use href="#i-refresh"/></svg></button></div>
    <div class="tools"><input class="field" id="blSearch" placeholder="Zoek op titel, artiest of map…" value="${esc(BL.q)}">
      <button class="btn small" id="blLoose" title="Een nummer dat (nog) niet in Drumsheetz staat: komt als plaatshouder in forScore">＋ Los nummer (plaatshouder)</button></div>
    <div class="list">${picks.map(s=>`<div class="b-song" draggable="true" data-path="${esc(s.path)}" title="${esc(s.path)}">
      <div class="m"><div class="t">${esc(s.title)}</div><div class="s">${esc(s.artist||"")}${s.folder?" · ▤ "+esc(s.folder):""} · ${s.bpm?esc(s.bpm)+" bpm · ":""}${s.duration?fmtDur(s.duration):"?"}</div></div>
      ${inSet[s.path]?`<span class="in" title="staat al in de setlist">✓${inSet[s.path]>1?inSet[s.path]+"×":""}</span>`:""}
      <button class="ib" data-add="${esc(s.path)}" title="Achteraan toevoegen"><svg class="i s"><use href="#i-insert"/></svg></button></div>`).join("") || '<div class="empty">Geen nummers gevonden.</div>'}</div></div>`;
  const focus = document.activeElement && box.contains(document.activeElement) ? document.activeElement : null;
  const fKey = focus ? (focus.dataset.meta || (focus.id==="blSearch"?"search":null)) : null, fPos = focus ? focus.selectionStart : 0;
  box.innerHTML = h;
  if(fKey){ const el = fKey==="search" ? $("#blSearch") : $(`#builder [data-meta="${fKey}"]`); if(el){ el.focus(); try{ el.setSelectionRange(fPos,fPos); }catch(e){} } }
}
function songItem(s){ return {raw:lineFor(s), pre:[], info:{kind:"song", title:s.title, artist:s.artist, bpm:s.bpm, meter:s.meter, duration:s.duration, path:s.path, note:"", ref:s.id}}; }
$("#builder").addEventListener("input", e=>{
  const t=e.target;
  if(t.id==="blSearch"){ BL.q=t.value; const pos=t.selectionStart; drawBuilder(); const s=$("#blSearch"); s.focus(); s.setSelectionRange(pos,pos); return; }
  if(t.dataset.meta){ clearTimeout(t._t); t._t=setTimeout(()=>{ const f=META_FIELDS.find(x=>x[0]===t.dataset.meta); setMeta(f[0], f[2], t.value.trim()); }, 400); }
});
$("#builder").addEventListener("click", async e=>{
  const t=e.target.closest("button,[data-note]"); if(!t) return;
  if(t.id==="blBuild") return build();
  if(t.id==="blRename"){ if(dirty()) await save(); return renameSetlist(state.path); }
  if(t.id==="blDelete") return deleteSetlist(state.path);
  if(t.id==="blFs") return fsSend({setlists:[nameOf(state.path)]});
  if(t.id==="blReload"){ await loadSongs(true); drawBuilder(); return; }
  if(t.id==="blBreak"){ const name=prompt("Naam van de set of pauze:", BL.items.some(i=>i.info.kind==="break") ? "Pauze" : "Set 1"); if(!name) return;
    BL.items.push({raw:`[${name.trim()}]`, pre:[], info:{kind:"break", display:name.trim(), title:name.trim()}}); commit(); return; }
  if(t.id==="blLoose"){ const name=prompt("Titel van het nummer (bv. 'Queen - Somebody To Love'):"); if(!name) return;
    BL.items.push({raw:name.trim(), pre:[], info:{kind:"song", title:name.trim(), error:"niet gevonden"}}); commit(); return; }
  if(t.dataset.add){ const s=BL.songs.find(x=>x.path===t.dataset.add); if(s){ BL.items.push(songItem(s)); commit(); toast(`'${s.title}' toegevoegd`); } return; }
  if(t.dataset.rm!==undefined){ BL.items.splice(+t.dataset.rm,1); commit(); return; }
  if(t.dataset.openi!==undefined){ const it=BL.items[+t.dataset.openi]; if(it.info.path) openFile(it.info.path, {pinned:true}); return; }
  if(t.dataset.note!==undefined){ const it=BL.items[+t.dataset.note]; const note=prompt(`Notitie bij '${it.info.title}':`, it.info.note||""); if(note===null) return; setNote(it, note.trim()); }
});
$("#builder").addEventListener("dblclick", e=>{ const r=e.target.closest("[data-rename]"); if(!r) return; const it=BL.items[+r.dataset.rename];
  const name=prompt("Nieuwe naam:", it.info.display||""); if(!name) return; it.raw=`[${name.trim()}]`; it.info.display=name.trim(); commit(); });
$("#builder").addEventListener("dragstart", e=>{
  const r=e.target.closest(".b-row"); const s=e.target.closest(".b-song");
  if(r){ BL.drag={row:+r.dataset.i}; r.classList.add("dragging"); e.dataTransfer.effectAllowed="move"; e.dataTransfer.setData("text/plain", "row"); }
  else if(s){ BL.drag={song:s.dataset.path}; e.dataTransfer.effectAllowed="copy"; e.dataTransfer.setData("text/plain", "song"); }
});
function clearDrop(){ $$("#builder .drop-before,#builder .drop-after").forEach(x=>x.classList.remove("drop-before","drop-after")); const l=$("#blList"); if(l) l.classList.remove("drop-end"); }
$("#builder").addEventListener("dragover", e=>{
  if(!BL.drag) return; const list=e.target.closest("#blList"); if(!list) return; e.preventDefault(); clearDrop();
  const r=e.target.closest(".b-row");
  if(r){ const box=r.getBoundingClientRect(); r.classList.add(e.clientY < box.top+box.height/2 ? "drop-before" : "drop-after"); }
  else list.classList.add("drop-end");
});
$("#builder").addEventListener("dragleave", e=>{ if(!e.relatedTarget || !$("#builder").contains(e.relatedTarget)) clearDrop(); });
$("#builder").addEventListener("drop", e=>{
  if(!BL.drag) return; const list=e.target.closest("#blList"); if(!list){ BL.drag=null; return; } e.preventDefault();
  const r=e.target.closest(".b-row"); let at=BL.items.length;
  if(r){ const box=r.getBoundingClientRect(); at=+r.dataset.i + (e.clientY < box.top+box.height/2 ? 0 : 1); }
  clearDrop();
  if(BL.drag.row!==undefined){ const from=BL.drag.row; if(at>from) at--; if(at!==from){ const [it]=BL.items.splice(from,1); BL.items.splice(at,0,it); commit(); } }
  else if(BL.drag.song){ const s=BL.songs.find(x=>x.path===BL.drag.song); if(s){ BL.items.splice(at,0,songItem(s)); commit(); } }
  BL.drag=null;
});
$("#builder").addEventListener("dragend", ()=>{ BL.drag=null; clearDrop(); $$("#builder .dragging").forEach(x=>x.classList.remove("dragging")); });

/* ================================================================== koppelingen en opstarten */
VIEW_HOOKS.explorer = ()=>drawOutline();
VIEW_HOOKS.git = ()=>loadGit(false);
VIEW_HOOKS.forscore = ()=>{ drawFsView(); if(!FS.data) loadFs(); };
VIEW_HOOKS.setlists = ()=>drawSetlists();
VIEW_HOOKS.song = ()=>{ drawDoc(); drawVersions(); };
VIEW_HOOKS.status = ()=>loadHealth();
VIEW_HOOKS.search = ()=>setTimeout(()=>$("#gsFind").focus(), 0);
function onSaved(m){ BL.songs=null; loadFs(); loadGit(false); if(m.kind==="setlist" && isBuilder()) refreshBuilderInfo(true); }
function refreshAll(){ loadFs(); loadGit(true); if(VIEW==="status") loadHealth(); }
const _drawTree = drawTree;
drawTree = function(){ _drawTree(); if(VIEW==="setlists") drawSetlists(); };

(async function init(){
  loadLayout();
  const path = location.pathname;
  const startView = path==="/sync" ? "git" : path==="/status" ? "status" : store.get("view","explorer");
  if(path!=="/") history.replaceState(null, "", "/");
  setView(startView);
  if(!store.get("side", true) && path==="/") $("#app").classList.add("noside");
  await loadTree();
  drawWelcome();
  initTools(); initLib(); initHelp(); initProps();
  try{ const s=await api("/api/status");
    $("#sbMs").innerHTML = s.musescore ? "MuseScore ✓" : '<span class="e">MuseScore ontbreekt</span>';
    $("#sbMs").title = s.musescore || "MuseScore niet gevonden: alleen MusicXML. Zie Status.";
    $("#sbMs").onclick = ()=>setView("status");
  }catch(e){}
  const files = allFiles();
  const tabs = store.get("tabs", []).filter(p=>files.includes(p));
  for(const p of tabs) await openFile(p, {pinned:true, nofocus:true});
  const active = store.get("active", null);
  if(active && TABS.find(t=>t.path===active)) activate(TABS.find(t=>t.path===active), {force:true});
  if(!TABS.length) activate(null, {force:true});
  loadFs(); loadGit(false);
  api("/api/health").then(d=>{ HEALTH.data=d; drawHealth(); }).catch(()=>{});
  setInterval(()=>{ if(document.visibilityState==="visible"){ loadGit(false); } }, 60000);
  setInterval(()=>{ if(document.visibilityState==="visible" && VIEW==="status") loadHealth(); }, 60000);
  window.addEventListener("focus", ()=>{ loadGit(false); });
})();
