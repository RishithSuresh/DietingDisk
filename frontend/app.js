const API = '';
const PAGE_SIZE = 100;
let fileOffset = 0, folderOffset = 0, issueOffset = 0, activeScanId = null, pollHandle = null, toastHandle = null;
const $ = (id) => document.getElementById(id);
const fmt = (n) => { if (n === null || n === undefined || !Number.isFinite(Number(n))) return '—'; n = Number(n); if (n < 0) return '—'; const units=['B','KB','MB','GB','TB','PB']; let i=0; while(n>=1024&&i<units.length-1){n/=1024;i++;} return `${n.toLocaleString(undefined,{maximumFractionDigits:i?2:0})} ${units[i]}`; };
const intFmt = (n) => Number(n||0).toLocaleString();
const dateFmt = (s) => { if(!s)return '—'; try{return new Date(s).toLocaleString();}catch{return s;} };
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function showToast(message){$('toast').textContent=message;$('toast').classList.remove('hidden');clearTimeout(toastHandle);toastHandle=setTimeout(()=>$('toast').classList.add('hidden'),4500);}
async function api(path, options={}){const r=await fetch(API+path,{headers:{'Content-Type':'application/json'},...options});let data;try{data=await r.json();}catch{data={};}if(!r.ok)throw new Error(data.detail||`Request failed (${r.status})`);return data;}
function go(view){document.querySelectorAll('.view').forEach(x=>x.classList.add('hidden'));$('view-'+view).classList.remove('hidden');document.querySelectorAll('.nav-item').forEach(x=>x.classList.toggle('active',x.dataset.view===view));const meta={overview:['Storage overview','Understand where your disk space is going.'],analytics:['Storage analytics','Explore file types, largest folders and where space is concentrated.'],classifier:['Smart classification','Understand likely file purpose, explanations and confidence.'],treemap:['Interactive storage map','Explore nested folders and large files visually.'],files:['File inventory','Search, sort and review individual files.'],folders:['Largest folders','Find storage-heavy directories.'],issues:['Scan issues & exclusions','See inaccessible and intentionally skipped locations.']}[view];$('page-title').textContent=meta[0];$('page-subtitle').textContent=meta[1];if(view==='files')loadFiles();if(view==='folders')loadFolders();if(view==='issues')loadIssues();if(view==='analytics')loadAnalytics();if(view==='classifier')loadClassifier();if(view==='treemap')loadTreemap(treePath);}

let treePath = '';
function renderBars(rows, labelKey, countKey='bytes') {
  const total = rows.reduce((n, r) => n + Number(r[countKey] || 0), 0) || 1;
  return rows.map(r => { const value = Number(r[countKey] || 0); const pct = Math.max(1, value / total * 100); return `<div class="category-row"><span class="category-name" title="${esc(r[labelKey])}">${esc(r[labelKey])}</span><span class="category-size">${fmt(value)} · ${intFmt(r.file_count || 0)}</span><div class="category-track"><div class="category-fill" style="width:${Math.min(100,pct)}%"></div></div></div>`; }).join('');
}
async function loadAnalytics(){
  try {
    const d = await api(`/api/analytics${activeScanId?`?scan_id=${activeScanId}`:''}`);
    if(!d.scan){$('analytics-type-count').textContent='—';$('analytics-largest-folder').textContent='No scan';$('extension-breakdown').innerHTML='<div class="muted">Run a scan first.</div>';return;}
    const totalBytes = Number(d.scan.bytes_scanned||0);
    $('analytics-type-count').textContent=intFmt(d.extension_count ?? d.extensions.length);
    $('analytics-total-size').textContent=fmt(totalBytes);
    const largest=d.largest_folders[0];
    $('analytics-largest-folder').textContent=largest?(largest.name||largest.path):'—';
    $('analytics-largest-folder').title=largest?largest.path:'';
    $('analytics-largest-folder-size').textContent=largest?`${fmt(largest.total_bytes)} · ${largest.path}`:'No folder data';
    const review=d.classifications.filter(c=>String(c.classification).startsWith('REVIEW'));
    $('analytics-review-count').textContent=intFmt(review.reduce((n,c)=>n+Number(c.file_count||0),0));
    const extTotal=d.extensions.reduce((n,x)=>n+Number(x.bytes||0),0)||1;
    $('extension-breakdown').innerHTML=d.extensions.length?d.extensions.map(c=>`<div class="category-row"><span class="category-name">${esc(c.extension)}</span><span class="category-size">${fmt(c.bytes)} · ${intFmt(c.file_count)} files</span><div class="category-track"><div class="category-fill" style="width:${Math.max(1,Number(c.bytes||0)/extTotal*100)}%"></div></div></div>`).join(''):'<div class="muted">No extension data.</div>';
    $('analytics-largest-folders').innerHTML=d.largest_folders.slice(0,10).map(f=>`<button class="compact-row compact-button" data-tree-path="${esc(f.path)}"><span class="file-symbol">▰</span><span class="compact-file"><strong>${esc(f.name||f.path)}</strong><small title="${esc(f.path)}">${esc(f.path)}</small></span><span class="compact-size">${fmt(f.total_bytes)}</span></button>`).join('')||'<div class="muted">No folders found.</div>';
    $('analytics-largest-folders').querySelectorAll('[data-tree-path]').forEach(b=>b.addEventListener('click',()=>{treePath=b.dataset.treePath;go('treemap');}));
  } catch(e){showToast('Could not load storage analytics: '+e.message);}
}
async function loadClassifier(){
  try{
    const d=await api(`/api/analytics${activeScanId?`?scan_id=${activeScanId}`:''}`);
    const categories=d.classifications||[];
    $('classifier-categories').innerHTML=categories.length?categories.map(c=>`<div class="classification-row"><div class="classification-row-head"><strong>${esc(c.classification)}</strong><span>${fmt(c.bytes)} · ${intFmt(c.file_count)} files</span></div><p>${esc(classificationExplanation(c.classification))}</p></div>`).join(''):'<div class="muted">No classification data available.</div>';
    const review=await api(`/api/files?limit=100&sort=size&order=desc&${activeScanId?`scan_id=${activeScanId}&`:''}`);
    const candidates=review.files.filter(f=>String(f.classification).startsWith('REVIEW')).slice(0,10);
    $('classifier-review-files').innerHTML=candidates.map(f=>`<div class="compact-row"><span class="file-symbol">?</span><span class="compact-file"><strong title="${esc(f.path)}">${esc(f.name)}</strong><small title="${esc(f.path)}">${esc(f.reason||f.path)}</small></span><span class="compact-size">${fmt(f.size_bytes)}</span></div>`).join('')||'<div class="muted">No review-labelled files among the largest 100. Use File inventory to filter all categories.</div>';
  }catch(e){showToast('Could not load classification data: '+e.message);}
}
function classificationExplanation(label){
 const key=String(label).toUpperCase();
 if(key.includes('SYSTEM'))return 'System or application-managed location. Preserve; use official maintenance tools.';
 if(key.includes('DATA / MODEL'))return 'Likely dataset, model, checkpoint or serialized data. Verify purpose and backup.';
 if(key.includes('GAME / APPLICATION'))return 'Likely required game/application assets. Do not delete individual assets manually.';
 if(key.includes('APPLICATION DATA'))return 'Database or app state may be important. Confirm ownership and backups.';
 if(key.includes('CACHE'))return 'May be rebuildable, but can be active dependencies or build outputs.';
 if(key.includes('TEMPORARY'))return 'Possible temporary data; check age and whether an app is using it.';
 if(key.includes('ARCHIVE'))return 'Archive, installer, backup or log; verify before any cleanup.';
 if(key.includes('MEDIA'))return 'Likely personal media; protect unless verified as duplicate.';
 if(key.includes('DOCUMENT'))return 'Likely user document or tabular data; preserve.';
 if(key.includes('SOURCE'))return 'Likely code or project/user data; preserve.';
 return 'Purpose uncertain. Manual investigation required; not a deletion recommendation.';
}
async function refreshClassifications(){
 const button=$('refresh-classification');button.disabled=true;button.textContent='Refreshing…';
 try{const d=await api(`/api/classification/refresh${activeScanId?`?scan_id=${activeScanId}`:''}`,{method:'POST'});showToast(`Updated labels for ${intFmt(d.updated_files)} file records. No drive files were changed.`);await loadSummary();await loadClassifier();await loadAnalytics();}
 catch(e){showToast('Classification refresh failed: '+e.message);}
 finally{button.disabled=false;button.textContent='Refresh classifications';}
}
function treemapColor(item){const s=String(item.classification||'');if(item.type==='folder')return '#d7eadb';if(s.startsWith('PROTECT')||s.startsWith('PROTECTED'))return '#8fc49c';if(s.startsWith('REVIEW'))return '#efd8a6';return '#b8cbd8';}
function treemapLayout(items){
 const positive=items.map(item=>({...item,_weight:Math.max(1,Number(item.size_bytes)||0)}));
 const out=[];
 function divide(list,x,y,w,h){
  if(!list.length)return;
  if(list.length===1){out.push({...list[0],x,y,w,h});return;}
  const total=list.reduce((n,item)=>n+item._weight,0)||list.length;
  let accumulated=0,split=1,best=Infinity;
  for(let i=1;i<list.length;i++){
   accumulated+=list[i-1]._weight;
   const difference=Math.abs(total/2-accumulated);
   if(difference<best){best=difference;split=i;}
  }
  const first=list.slice(0,split),second=list.slice(split);
  const firstWeight=first.reduce((n,item)=>n+item._weight,0)||1;
  const ratio=Math.min(.98,Math.max(.02,firstWeight/total));
  if(w>=h){const cut=w*ratio;divide(first,x,y,cut,h);divide(second,x+cut,y,w-cut,h);}
  else{const cut=h*ratio;divide(first,x,y,w,cut);divide(second,x,y+cut,w,h-cut);}
 }
 divide(positive,0,0,100,100);
 return out;
}
async function loadTreemap(path=''){
 try{
  const query=new URLSearchParams();if(activeScanId)query.set('scan_id',activeScanId);if(path)query.set('path',path);query.set('limit','120');
  const d=await api('/api/treemap?'+query.toString());treePath=d.path||'';
  const parts=treePath.split('\\').filter(Boolean);$('treemap-breadcrumb').innerHTML=parts.map((part,i)=>`<button class="breadcrumb-button" data-depth="${i}">${esc(part)}</button>`).join('<span class="breadcrumb-sep">›</span>');
  $('treemap-breadcrumb').querySelectorAll('[data-depth]').forEach(b=>b.addEventListener('click',()=>{const upto=parts.slice(0,Number(b.dataset.depth)+1);let p=upto[0]||'';if(p.endsWith(':'))p+='\\';else p+='\\';treePath=p;loadTreemap(treePath);}));
  $('treemap-up').disabled=!parts.length||parts.length<=1;
  $('treemap-summary').textContent=`${intFmt(d.items.length)} direct items shown · folder size includes descendants · colors indicate item type/category`;
  const canvas=$('treemap-canvas');
  if(!d.items.length){canvas.innerHTML='<div class="empty-card">No direct items were found here. This can happen for an inaccessible or empty folder.</div>';return;}
  const items=treemapLayout(d.items);canvas.innerHTML=items.map(item=>`<button class="treemap-tile ${item.type==='folder'?'tile-folder':'tile-file'}" style="left:${item.x}%;top:${item.y}%;width:${item.w}%;height:${item.h}%;background:${treemapColor(item)}" data-type="${item.type}" data-path="${esc(item.path)}" title="${esc(item.path)} · ${fmt(item.size_bytes)}"><span>${item.type==='folder'?'▰':'▤'} ${esc(item.name||item.path)}</span><small>${fmt(item.size_bytes)}</small></button>`).join('');
  canvas.querySelectorAll('.treemap-tile').forEach(button=>button.addEventListener('click',()=>{const item=d.items.find(x=>x.path===button.dataset.path);if(!item)return;if(item.type==='folder'){treePath=item.path;loadTreemap(treePath);}else{$('treemap-detail').innerHTML=`<strong>${esc(item.name||item.path)}</strong><span>${fmt(item.size_bytes)} · ${esc(item.classification||'Unclassified')}</span><small>${esc(item.path)}</small><p>${esc(item.reason||'No explanation recorded.')}</p>`;}}));
  $('treemap-detail').textContent='Select a rectangle to view its details.';
  if(d.truncated)showToast('Showing the largest direct items in this folder to keep the map responsive.');
 }catch(e){$('treemap-canvas').innerHTML=`<div class="empty-card">Could not load storage map: ${esc(e.message)}</div>`;}
}

document.querySelectorAll('.nav-item').forEach(b=>b.addEventListener('click',()=>go(b.dataset.view)));
document.querySelectorAll('[data-go]').forEach(b=>b.addEventListener('click',()=>go(b.dataset.go)));
async function loadDrives(){try{const data=await api('/api/drives');$('drive-grid').innerHTML=data.drives.length?data.drives.map(d=>`<div class="drive-card"><div class="drive-top"><div class="drive-symbol">▰</div><div><div class="drive-title">${esc(d.mountpoint)} <span style="font-weight:400;color:#849087">${esc(d.filesystem||'')}</span></div><div class="drive-subtitle">${esc(d.device||'Drive')}</div></div><div class="drive-percent">${Number(d.percent||0).toFixed(0)}%</div></div><div class="drive-track"><div class="drive-fill" style="width:${Math.min(100,Math.max(0,Number(d.percent||0)))}%"></div></div><div class="drive-stats"><span>${fmt(d.free_bytes)} free of ${fmt(d.total_bytes)}</span><span>${fmt(d.used_bytes)} used</span></div></div>`).join(''):'<div class="empty-card">No mounted drives found.</div>';}catch(e){$('drive-grid').innerHTML=`<div class="empty-card">Could not read drive statistics: ${esc(e.message)}</div>`;}}
function selectedRoots(){return [...document.querySelectorAll('.drive-option input:checked')].map(x=>x.value);}
async function startScan(){const roots=selectedRoots();if(!roots.length){showToast('Select at least one drive.');return;}if(!confirm(`Start a read-only inventory of ${roots.join(' and ')}? This may take a long time. No scanned files will be changed.`))return;try{const d=await api('/api/scan/start',{method:'POST',body:JSON.stringify({roots})});activeScanId=d.scan_id;$('progress-card').classList.remove('hidden');$('scan-btn').disabled=true;$('cancel-btn').disabled=false;$('scan-badge').textContent='Scanning…';showToast('Scan started. You can keep browsing while it runs.');if(pollHandle)clearInterval(pollHandle);pollHandle=setInterval(pollStatus,1000);await pollStatus();}catch(e){showToast(e.message);}}
async function cancelScan(){try{await api('/api/scan/cancel',{method:'POST'});$('cancel-btn').disabled=true;showToast('Cancellation requested. Waiting for the scanner to stop safely…');}catch(e){showToast(e.message);}}
async function pollStatus(){try{const s=await api('/api/scan/status');if(s.scan_id)activeScanId=s.scan_id;$('progress-title').textContent=s.status==='running'?'Scanning accessible files…':s.status==='cancelled'?'Scan cancelled':s.status==='failed'?'Scan failed':'Scan status';$('progress-status').textContent=s.status;$('progress-counts').textContent=`${intFmt(s.files_scanned)} files · ${intFmt(s.folders_scanned)} folders · ${intFmt(s.errors_count)} access issues · ${intFmt(s.exclusions_count)} exclusions`;$('progress-size').textContent=`${fmt(s.bytes_scanned)} inventoried`;$('current-path').textContent=s.current_path||s.message||'';$('progress-bar').style.width=s.status==='running'?'100%':s.status==='completed'?'100%':'0%';$('progress-bar').style.opacity=s.status==='running'?'.75':'1';if(s.status!=='running'){$('scan-btn').disabled=false;$('cancel-btn').disabled=true;if(pollHandle){clearInterval(pollHandle);pollHandle=null;}await loadSummary();await loadFiles();await loadFolders();await loadIssues();$('export-btn').disabled=!s.scan_id;$('scan-badge').textContent=s.status==='completed'?'Inventory ready':s.status==='cancelled'?'Partial inventory':s.status==='failed'?'Scan failed':'No scan yet';$('scan-badge').classList.toggle('done',s.status==='completed');if(s.status==='completed')showToast('Scan complete. Review access issues and exclusions before relying on the totals.');}}catch(e){console.error(e);}}
async function loadSummary(){try{const d=await api(activeScanId?`/api/summary?scan_id=${activeScanId}`:'/api/summary');if(!d.scan){$('metric-files').textContent='—';$('metric-folders').textContent='—';$('metric-size').textContent='—';$('metric-issues').textContent='—';return;}const s=d.scan;$('metric-files').textContent=intFmt(s.files_scanned);$('metric-folders').textContent=intFmt(s.folders_scanned);$('metric-size').textContent=fmt(s.bytes_scanned);$('metric-issues').textContent=intFmt(s.errors_count);$('largest-files').innerHTML=d.largest_files.length?d.largest_files.map(f=>`<div class="compact-row"><div class="file-symbol">▤</div><div class="compact-file"><strong title="${esc(f.path)}">${esc(f.name)}</strong><small title="${esc(f.path)}">${esc(f.path)}</small></div><span class="compact-size">${fmt(f.size_bytes)}</span></div>`).join(''):'<div class="muted">No files in this scan.</div>';$('categories').innerHTML=d.categories.length?d.categories.map(c=>{const total=d.categories.reduce((n,x)=>n+Number(x.bytes||0),0)||1;const pct=Math.max(1,Number(c.bytes||0)/total*100);return `<div class="category-row"><span class="category-name">${esc(c.classification)}</span><span class="category-size">${fmt(c.bytes)} · ${intFmt(c.file_count)}</span><div class="category-track"><div class="category-fill" style="width:${pct}%"></div></div></div>`}).join(''):'<div class="muted">No categories available.</div>';activeScanId=s.id;}catch(e){console.error(e);}}
function classClass(c){if(c.startsWith('PROTECTED')||c.startsWith('PROTECT'))return 'protect';if(c.startsWith('REVIEW'))return 'review';if(c.startsWith('DO NOT'))return 'system';return '';}
async function loadFiles(){const q=encodeURIComponent($('file-search').value.trim());const cls=encodeURIComponent($('file-class-filter').value);const sort=$('file-sort').value;try{const d=await api(`/api/files?limit=${PAGE_SIZE}&offset=${fileOffset}&search=${q}&classification=${cls}&sort=${sort}&order=desc${activeScanId?`&scan_id=${activeScanId}`:''}`);$('files-count').textContent=`${intFmt(d.total)} results · showing ${d.files.length?fileOffset+1:0}–${Math.min(fileOffset+d.files.length,d.total)}`;$('files-prev').disabled=fileOffset===0;$('files-next').disabled=fileOffset+PAGE_SIZE>=d.total;$('files-body').innerHTML=d.files.length?d.files.map(f=>`<tr><td class="path-cell"><strong title="${esc(f.path)}">${esc(f.name)}</strong><small title="${esc(f.path)}">${esc(f.path)}</small></td><td class="size-cell">${fmt(f.size_bytes)}</td><td><span class="class-pill ${classClass(f.classification)}">${esc(f.classification)}</span></td><td>${esc(dateFmt(f.modified_at))}</td></tr>`).join(''):'<tr><td colspan="4" class="empty-cell">No matching files. Run a scan or adjust your filters.</td></tr>';const classes=[...new Set(d.files.map(f=>f.classification))];const select=$('file-class-filter');const current=select.value;const known=new Set([...select.options].map(o=>o.value));classes.forEach(c=>{if(!known.has(c)){const o=document.createElement('option');o.value=c;o.textContent=c;select.appendChild(o);}});if(current)select.value=current;}catch(e){showToast(e.message);}}
async function loadFolders(){try{const d=await api(`/api/folders?limit=${PAGE_SIZE}&offset=${folderOffset}${activeScanId?`&scan_id=${activeScanId}`:''}`);$('folders-count').textContent=`${intFmt(d.total)} folders · showing ${d.folders.length?folderOffset+1:0}–${Math.min(folderOffset+d.folders.length,d.total)}`;$('folders-prev').disabled=folderOffset===0;$('folders-next').disabled=folderOffset+PAGE_SIZE>=d.total;$('folders-body').innerHTML=d.folders.length?d.folders.map(f=>`<tr><td class="path-cell"><strong title="${esc(f.path)}">${esc(f.name||f.path)}</strong><small title="${esc(f.path)}">${esc(f.path)}</small></td><td class="size-cell">${fmt(f.total_bytes)}</td><td>${intFmt(f.file_count)}</td><td>${esc(f.parent_path||'—')}</td></tr>`).join(''):'<tr><td colspan="4" class="empty-cell">No folders found. Run a scan first.</td></tr>';}catch(e){showToast(e.message);}}
async function loadIssues(){try{const type=encodeURIComponent($('issue-filter').value);const d=await api(`/api/issues?limit=${PAGE_SIZE}&offset=${issueOffset}&issue_type=${type}${activeScanId?`&scan_id=${activeScanId}`:''}`);$('issues-count').textContent=`${intFmt(d.total)} issues · showing ${d.issues.length?issueOffset+1:0}–${Math.min(issueOffset+d.issues.length,d.total)}`;$('issues-prev').disabled=issueOffset===0;$('issues-next').disabled=issueOffset+PAGE_SIZE>=d.total;$('issues-body').innerHTML=d.issues.length?d.issues.map(i=>`<tr><td><span class="issue-type ${esc(i.issue_type)}">${esc(i.issue_type.replace('_',' '))}</span></td><td class="path-cell"><strong title="${esc(i.path)}">${esc(i.path)}</strong></td><td>${esc(i.message)}</td></tr>`).join(''):'<tr><td colspan="3" class="empty-cell">No issues found for this filter.</td></tr>';}catch(e){showToast(e.message);}}
$('refresh-classification').addEventListener('click',refreshClassifications);$('treemap-up').addEventListener('click',()=>{const parts=treePath.split('\\').filter(Boolean);if(parts.length>1){parts.pop();treePath=parts.join('\\')+'\\';loadTreemap(treePath);}else{treePath='';loadTreemap('');}});$('scan-btn').addEventListener('click',startScan);$('cancel-btn').addEventListener('click',cancelScan);$('refresh-drives').addEventListener('click',loadDrives);$('refresh-folders').addEventListener('click',loadFolders);$('export-btn').addEventListener('click',()=>{const url=activeScanId?`/api/export/csv?scan_id=${activeScanId}`:'/api/export/csv';window.location.href=url;});$('file-search').addEventListener('input',()=>{fileOffset=0;clearTimeout(window.searchDelay);window.searchDelay=setTimeout(loadFiles,250);});$('file-class-filter').addEventListener('change',()=>{fileOffset=0;loadFiles();});$('file-sort').addEventListener('change',()=>{fileOffset=0;loadFiles();});$('issue-filter').addEventListener('change',()=>{issueOffset=0;loadIssues();});$('files-prev').addEventListener('click',()=>{fileOffset=Math.max(0,fileOffset-PAGE_SIZE);loadFiles();});$('files-next').addEventListener('click',()=>{fileOffset+=PAGE_SIZE;loadFiles();});$('folders-prev').addEventListener('click',()=>{folderOffset=Math.max(0,folderOffset-PAGE_SIZE);loadFolders();});$('folders-next').addEventListener('click',()=>{folderOffset+=PAGE_SIZE;loadFolders();});$('issues-prev').addEventListener('click',()=>{issueOffset=Math.max(0,issueOffset-PAGE_SIZE);loadIssues();});$('issues-next').addEventListener('click',()=>{issueOffset+=PAGE_SIZE;loadIssues();});
(async()=>{try{await api('/api/health');await Promise.all([loadDrives(),loadSummary()]);const s=await api('/api/scan/status');if(s.status==='running'){$('progress-card').classList.remove('hidden');$('scan-btn').disabled=true;$('cancel-btn').disabled=false;pollHandle=setInterval(pollStatus,1000);}else if(s.scan_id){activeScanId=s.scan_id;$('export-btn').disabled=false;$('scan-badge').textContent=s.status==='completed'?'Inventory ready':s.status;$('scan-badge').classList.toggle('done',s.status==='completed');await loadSummary();}}catch(e){showToast('Could not connect to the local DietingDisk API: '+e.message);}})();
