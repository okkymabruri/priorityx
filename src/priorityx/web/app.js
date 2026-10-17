(async function(){
'use strict';
const $=id=>document.getElementById(id),families=['matrix','timeline','paths'];
const Q={Q1:'#d62728',Q2:'#ff7f0e',Q3:'#2ca02c',Q4:'#1f77b4'},EC={1:'#d62728',2:'#ff7f0e',3:'#ffdd57',4:'#2ca02c'},NAMES={1:'Crisis',2:'Investigate',3:'Monitor',4:'Low'};
const SERVICE=document.documentElement.dataset.service==='true',ctx=document.createElement('canvas').getContext('2d');
let boot=JSON.parse($('workspace-data').textContent),prepared=boot.prepared,bundle=boot.bundle;
let state={},revision=0,queue=Promise.resolve(),restoring=false,ready=false,printing=false,opening=false,storageWarning=false,report={},tableKeys={};
const clone=value=>JSON.parse(JSON.stringify(value)),esc=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const storageKey=()=> 'priorityx.view.'+prepared.bundle_id+'.'+(document.documentElement.dataset.artifact||'workspace');
const baseSettings=()=>{const opening=prepared.datasets.find(d=>d.cadence==='quarterly')||prepared.datasets[0];return {schema_version:1,bundle_id:prepared.bundle_id,entity_type:opening?.entity_type||'',cadence:opening?.cadence||'quarterly',member:'',panel_height:422,min_panel_width:380,timeline_scale:1,layout_mode:'auto',static_width:null,static_height:null,dpi:150,views:{}}};

function data(){return prepared.datasets.find(d=>d.entity_type===state.entity_type&&d.cadence===state.cadence)}
function view(){const d=data();if(!d)return {};return state.views[d.key]??=( {ranges:{},timeline:{left:0,top:0},row_left:0,focus:'matrix',data_tab:'matrix',paths_scope:'shown',disclosures:{},tables:{}})}
function checkSettings(value){
 if(!value||value.schema_version!==1)throw Error('Unsupported settings version. Choose a version 1 settings file.');
 if(value.bundle_id!==prepared.bundle_id)throw Error('These settings belong to different saved results. Open the matching result bundle first.');
 const defaults=baseSettings(),keys=new Set(Object.keys(defaults));
 for(const k of Object.keys(value))if(!keys.has(k))throw Error('Unknown settings field: '+k);
 const v={...defaults,...clone(value)};
 for(const [key,limit] of Object.entries(prepared.settings_schema)){
  const x=v[key];if(x===null&&limit.nullable)continue;
  if(typeof x!=='number'||!Number.isFinite(x)||x<limit.min||x>limit.max||(limit.integer&&!Number.isInteger(x)))throw Error('Invalid '+key+' setting.');
 }
 if(!['auto','manual'].includes(v.layout_mode))throw Error('Invalid layout mode.');
 if(v.layout_mode==='manual'&&(!v.static_width||!v.static_height))throw Error('Manual print size needs both width and height.');
 if(new TextEncoder().encode(JSON.stringify(v.views)).length>500000)throw Error('Saved interaction state exceeds 500 KB.');
 if(!v.views||typeof v.views!=='object'||Array.isArray(v.views))throw Error('Invalid saved view state.');
 const d=prepared.datasets.find(d=>d.entity_type===v.entity_type&&d.cadence===v.cadence);
 if(prepared.datasets.length&&!d)throw Error('The selected type and cadence are unavailable in these results.');
 if(typeof v.entity_type!=='string'||!['monthly','quarterly'].includes(v.cadence))throw Error('Invalid type or cadence.');
 if(typeof v.member!=='string')throw Error('Invalid selected entity.');
 if(d&&v.member&&!allMembers(d).includes(v.member))throw Error('The saved entity is unavailable in this view.');
 for(const [k,item] of Object.entries(v.views)){
  if(!prepared.datasets.some(d=>d.key===k)||!item||typeof item!=='object'||Array.isArray(item))throw Error('Invalid dataset view state.');
  v.views[k]={ranges:{},timeline:{left:0,top:0},row_left:0,focus:'matrix',data_tab:'matrix',paths_scope:'shown',disclosures:{},tables:{},...item};
  for(const name of ['ranges','timeline','disclosures','tables'])if(!v.views[k][name]||typeof v.views[k][name]!=='object'||Array.isArray(v.views[k][name]))throw Error('Invalid saved '+name+'.');
  const vitem=v.views[k],allowed=new Set(['ranges','timeline','row_left','focus','disclosures','tables','data_tab','paths_scope']);
  if(Object.keys(item).some(name=>!allowed.has(name)))throw Error('Unknown saved interaction field.');
  const position=x=>{if(typeof x!=='number'||!Number.isFinite(x)||x<0||x>100000000)throw Error('Invalid saved reading position.')};
  for(const [family,range] of Object.entries(vitem.ranges)){
   if(!['matrix','paths'].includes(family)||!range||typeof range!=='object'||Object.keys(range).sort().join(',')!=='x,y')throw Error('Chart ranges need x and y bounds.');
   for(const axis of ['x','y'])if(!Array.isArray(range[axis])||range[axis].length!==2||!range[axis].every(Number.isFinite)||range[axis][0]>=range[axis][1])throw Error('Invalid chart range.');
  }
  for(const [name,x] of Object.entries(vitem.timeline)){if(name==='row'){if(typeof x!=='string')throw Error('Invalid row anchor.')}else if(['left','top','row_offset'].includes(name))position(x);else throw Error('Unknown timeline position.')}
  position(vitem.row_left);
  if(!families.includes(vitem.focus))throw Error('Invalid chart focus.');
  if(!families.includes(vitem.data_tab))throw Error('Invalid data tab.');
  if(!['shown','all'].includes(vitem.paths_scope))throw Error('Invalid trajectory table scope.');
  for(const [id,x] of Object.entries(vitem.disclosures))if(!['data-panel','details','matrix-data','timeline-data','paths-data','layout-settings','import-panel'].includes(id)||typeof x!=='boolean')throw Error('Invalid disclosure state.');
  for(const [name,x] of Object.entries(vitem.tables)){if(!families.includes(name))throw Error('Invalid table name.');position(x)}
  const legacy= families.find(name=>vitem.disclosures[name+'-data']);
  if(!Object.hasOwn(item,'data_tab')&&legacy)vitem.data_tab=legacy;
  vitem.disclosures={'data-panel':vitem.disclosures['data-panel']??!!legacy,details:vitem.disclosures.details??false};
 }
 return v;
}
function strictParse(text){
 const value=JSON.parse(text),stack=[];
 for(let i=0;i<text.length;i++){
  const c=text[i];if(c==='{'){stack.push(new Set());continue}if(c==='['){stack.push(null);continue}if(c==='}'||c===']'){stack.pop();continue}
  if(c!=='"')continue;const start=i;for(i++;i<text.length;i++){if(text[i]==='\\'){i++;continue}if(text[i]==='"')break}
  let next=i+1;while(/\s/.test(text[next]||'')&&next<text.length)next++;
  if(text[next]===':'&&stack.at(-1)){const key=JSON.parse(text.slice(start,i+1)),keys=stack.at(-1);if(keys.has(key))throw Error('Duplicate JSON field: '+key);keys.add(key)}
 }
 return value;
}
function allMembers(d){return [...new Set([...d.matrix.map(p=>p.entity),...d.rows,...Object.keys(d.paths)])].sort()}
function capture(){
 if(restoring||!data()||renderedIdentity!==prepared.bundle_id+'|'+data().key)return;
 const v=view();
 for(const family of ['matrix','paths']){const p=$('pl-'+family+'-inner');if(p._fullLayout?.xaxis&&p._fullLayout?.yaxis)v.ranges[family]={x:[...p._fullLayout.xaxis.range],y:[...p._fullLayout.yaxis.range]}}
 const t=$('pl-timeline');v.timeline={left:t.scrollLeft,top:t.scrollTop};
 const g=window.priorityxWorkspace?.lastGeometry;
 if(g?.rows.length){const row=g.rows.find(r=>r.end>t.scrollTop)||g.rows.at(-1);v.timeline.row=row.entity;v.timeline.row_offset=Math.max(0,t.scrollTop-row.start)}
 v.row_left=$('chart-scroll').scrollLeft;
 for(const id of ['data-panel','details'])v.disclosures[id]=$(id).open;
 if($('data-panel').open)v.tables[v.data_tab]=$(v.data_tab+'-table-scroll').scrollTop;
}
function persist(){if(!data())return;try{localStorage.setItem(storageKey(),JSON.stringify(state))}catch{storageWarning=true}}
function remember(){if(!restoring){capture();persist()}}
function announce(text,busy=false){$('render-status').textContent=text;$('render-status').className='render-status'+(busy?'':' ready')}
function errorMessage(error,retry=false){$('error').textContent=error?.message||String(error);$('feedback').hidden=false;$('retry').hidden=!retry}
function clearError(){$('feedback').hidden=true;$('error').textContent='';$('retry').hidden=true}
function windowData(d){const q=d.cadence==='quarterly',last=Number(d.asOf.slice(q?6:5)),year=d.asOf.slice(0,4),periods=Array.from({length:last},(_,i)=>year+(q?'-Q'+(i+1):'-'+String(i+1).padStart(2,'0'))),events=d.events.filter(e=>e.period>=periods[0]&&e.period<=d.asOf);return {periods,events,hidden:d.events.length-events.length}}
function textWidth(value,size=12){ctx.font=size+'px Arial';return ctx.measureText(String(value)).width}
function wrap(value,width){
 const lines=[];let line='';for(const token of String(value).split(/\s+/)){
  if(textWidth(token)>width){if(line){lines.push(line);line=''}for(const glyph of Array.from(token)){if(line&&textWidth(line+glyph)>width){lines.push(line);line=''}line+=glyph}}
  else if(line&&textWidth(line+' '+token)>width){lines.push(line);line=token}else line+=(line?' ':'')+token;
 }if(line)lines.push(line);return lines.length?lines:[''];
}

function geometry(d,w){
 const width=$('pl-timeline').clientWidth,left=Math.min(180,Math.max(96,width*.34)),right=12,labels=d.rows.map(n=>wrap(n,left-16));
 const prefix=e=>12+textWidth(e.source+'→'),suffix=e=>e.suffix?12+textWidth(e.suffix):8;
 const first=Math.max(26,...w.events.map(prefix))+4,last=Math.max(12,...w.events.map(suffix))+4,space=width-left-right;
 const step=w.periods.length>1?(space-first-last)/(w.periods.length-1):space;
 const x=period=>w.periods.length>1?first+w.periods.indexOf(period)*step:space/2;
 const positions=new Map(),rows=[];let total=0;
 for(let i=0;i<d.rows.length;i++){
  const entity=d.rows[i],ends=[],events=w.events.filter(e=>e.entity===entity).sort((a,b)=>a.period.localeCompare(b.period));
  for(const e of events){const start=x(e.period)-prefix(e);let lane=ends.findIndex(end=>end+8<=start);if(lane<0)lane=ends.length;ends[lane]=x(e.period)+suffix(e);positions.set(e,lane)}
  const lanes=Math.max(1,ends.length),height=Math.max(38,labels[i].length*14+16,lanes*26+12),start=total;
  for(const e of events)positions.set(e,start+(height-lanes*26)/2+(positions.get(e)+.5)*26);
  total+=height;rows.push({entity,start,end:total,center:start+height/2});
 }
 const shortMonths=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
 const tickLabels=w.periods.map(p=>textWidth(p)+8<=step?p:d.cadence==='quarterly'?p.slice(5):shortMonths[Number(p.slice(5))-1]);
 const tickLanes=Math.max(1,Math.ceil((Math.max(...tickLabels.map(p=>textWidth(p)))+6)/step)),axisHeight=32+(tickLanes-1)*22;
 return {left,right,top:8,bottom:8,width,height:Math.max(80,total+16),labels,rows,positions,x,step,axisHeight,tickLabels,tickLanes,
  xRange:w.periods.length>1?[-first/step,w.periods.length-1+last/step]:[-.5,.5],contentHeight:Math.max(64,total)};
}
function axisExtent(rows){const range=values=>{const low=Math.min(0,...values),high=Math.max(0,...values),pad=Math.max(high-low,1)*.08;return [low-pad,high+pad]};return {x:range(rows.map(p=>p.x)),y:range(rows.map(p=>p.y))}}
function fillOptions(select,options,value){select.replaceChildren(...options.map(([value,label])=>new Option(label,value)));select.value=value}
function controls(){
 const d=data(),types=[];for(const item of prepared.datasets)if(!types.some(([type])=>type===item.entity_type))types.push([item.entity_type,item.typeLabel]);
 fillOptions($('type'),types,state.entity_type);fillOptions($('cadence'),prepared.datasets.filter(v=>v.entity_type===state.entity_type).map(v=>[v.cadence,v.cadence==='quarterly'?'Quarterly':'Monthly']),state.cadence);
 fillOptions($('member'),[['',d.trajectorySelection?.mode==='trend_change'?'Automatic group':'Saved group'],...allMembers(d).map(s=>[s,s])],state.member);
}
function updateContent(d,w){
 $('snapshot').textContent='Through '+d.asOf;$('clear').hidden=!state.member;
 $('matrix-meta').textContent=d.availability.matrix?d.matrix.length+' fitted entities':'No saved matrix';
 $('timeline-meta').textContent=d.availability.timeline?'YTD · '+w.periods[0]+' – '+d.asOf+' · '+w.events.length+' events':'No saved transitions';
 const automatic=d.trajectorySelection?.mode==='trend_change';
 $('paths-meta').textContent=d.availability.paths?(state.member?'1 selected entity':d.defaultPaths.length+(automatic?' largest trend changes':' saved selections'))+' · '+d.pathWindow+'-period window':'No saved movement';
 $('selection-info').textContent=automatic?'Default trajectories show up to three entities with the largest total absolute trend changes in this window, including the change into its first visible period when earlier history exists. Ties use entity identifiers.':'Default trajectories follow the ordered selection stored with these results.';
 $('source-info').textContent=d.typeLabel+' · '+state.cadence+' · '+d.source_id+' · '+d.coverage_start+' – '+d.asOf;
 $('source-hash').textContent='Bundle SHA-256: '+prepared.bundle_id;
 $('library-info').textContent='Plotly.js '+Plotly.version+' · SVG charts';
 $('history-note').textContent=w.hidden+' earlier timeline events are outside YTD. Full saved history remains in the result bundle and HTML export.';
 const e=w.events.find(e=>e.entity===state.member)||w.events[0];$('read-event').replaceChildren();
 if(e){for(const [text,marker] of [[e.source+'→',false],[e.destination,true],[e.suffix,false]]){const s=document.createElement('span');s.textContent=text;if(marker){s.className='event-marker';s.style.background=EC[e.class];s.style.color=e.class===1?'#fff':'#18291f'}$('read-event').append(s)}$('read-event-context').textContent=e.entity+' · '+e.period+' · '+NAMES[e.class]}else $('read-event-context').textContent='No events in this YTD window.';
 const messages={matrix:!d.availability.matrix?'No matrix table was supplied.':state.member&&!d.matrix.some(p=>p.entity===state.member)?'No fitted matrix point for this entity.':'',timeline:!d.availability.timeline?'No transition table was supplied.':state.member&&!w.events.some(e=>e.entity===state.member)?'No YTD events for this entity.':'',paths:!d.availability.paths?'No movement table was supplied.':state.member&&!pathRows(d)[state.member]?.length?'No saved trajectory in this window.':''};
 messages.timeline=[messages.timeline,...(d.warnings||[])].filter(Boolean).join(' ');
 for(const name of families)$ (name+'-message').textContent=messages[name];
 $('matrix-count').textContent=d.matrix.length;
 $('timeline-count').textContent=w.events.length;
 const paths=pathRows(d),names=view().paths_scope==='all'?Object.keys(paths):shownNames(d);
 $('paths-count').textContent=names.reduce((n,name)=>n+(paths[name]||[]).length,0);updatePathKey(d);
}
function buildTable(name){
 const d=data();if(!d)return;const id=d.key+'|'+prepared.bundle_id+(name==='paths'?'|'+state.member+'|'+view().paths_scope:'');if(tableKeys[name]===id){for(const b of $(name+'-table').querySelectorAll('button'))b.setAttribute('aria-pressed',String(b.dataset.entity===state.member));return}
 const rows=name==='matrix'?d.matrix.map(p=>[p.entity,p.x,p.y,p.quadrant,p.count]):name==='timeline'?windowData(d).events.map(e=>[e.entity,e.period,e.source+'→'+e.destination+e.suffix,NAMES[e.class]]):Object.entries(pathRows(d)).filter(([entity])=>view().paths_scope==='all'||shownNames(d).includes(entity)).flatMap(([entity,ps])=>ps.map(p=>[entity,p.period,p.x,p.y,p.quadrant]));
 const body=$(name+'-table'),focused=body.contains(document.activeElement)?document.activeElement.dataset.row:null,frag=document.createDocumentFragment();
 for(const values of rows){const tr=document.createElement('tr');values.forEach((value,i)=>{const td=document.createElement('td');if(i===0){const b=document.createElement('button');b.textContent=value;b.dataset.entity=value;b.dataset.row=JSON.stringify(values.slice(0,2));b.setAttribute('aria-pressed',String(value===state.member));b.onclick=()=>select(value);td.append(b)}else td.textContent=String(value);tr.append(td)});frag.append(tr)}body.replaceChildren(frag);tableKeys[name]=id;
 if(focused)([...body.querySelectorAll('button')].find(b=>b.dataset.row===focused)||$('tab-'+name)).focus({preventScroll:true});
}
function syncDataPanel(){
 const v=view(),name=v.data_tab||'matrix';$('pathsScope').value=v.paths_scope||'shown';
 for(const family of families){const active=family===name;$('tab-'+family).setAttribute('aria-selected',String(active));$('tab-'+family).tabIndex=active?0:-1;$(family+'-data').hidden=!active}
 if($('data-panel').open){buildTable(name);$(name+'-table-scroll').scrollTop=v.tables[name]||0}
}
function selectDataTab(name,{focus=false}={}){capture();view().data_tab=name;syncDataPanel();if(focus)$('tab-'+name).focus({preventScroll:true});remember()}
function openData(name){capture();view().data_tab=name;$('data-panel').open=true;syncDataPanel();$('tab-'+name).focus({preventScroll:true});$('data-panel').scrollIntoView({block:'start'});remember()}
function focusChart(name){const v=view();v.focus=name;const row=$('chart-scroll'),panel=$('panel-'+name);row.scrollLeft+=panel.getBoundingClientRect().left-row.getBoundingClientRect().left;for(const b of document.querySelectorAll('[data-focus]'))b.setAttribute('aria-pressed',String(b.dataset.focus===name));remember()}
function syncLayoutForm(){if(layoutDirty)return;for(const [id,key] of [['panelWidth','min_panel_width'],['panelHeight','panel_height'],['layoutMode','layout_mode'],['staticWidth','static_width'],['staticHeight','static_height'],['printDpi','dpi']])$(id).value=state[key]??'';for(const id of ['staticWidth','staticHeight'])$(id).disabled=state.layout_mode!=='manual'}
function setAvailable(){
 window.WORKSPACE_READY=ready;
 const has=prepared.datasets.length>0;$('empty').hidden=has;$('toolbar').hidden=!has;$('chart-scroll').hidden=!has;
 $('data-panel').hidden=!has;$('details').hidden=!has;$('export-menu').hidden=!has;$('pending-layout').hidden=!layoutDirty;
 for(const id of ['saveHtml','saveMatrix','saveSettings','loadSettings','saveReport','saveBundle','layoutLink','savePng','saveSvg'])$(id).disabled=!has||!ready||(layoutDirty&&!['loadSettings','layoutLink'].includes(id))||((id==='savePng'||id==='saveSvg')&&(!SERVICE||printing));
 $('emptyImport').disabled=!SERVICE;$('showImport').disabled=!SERVICE;$('empty').querySelector('p').textContent=SERVICE?'Choose a result bundle or import saved CSV files to inspect your charts.':'Start the local app to open saved results. This offline file contains no datasets.';
 $('openResults').disabled=!SERVICE||opening;$('emptyOpen').disabled=!SERVICE||opening;for(const el of $('import-form').elements)el.disabled=!SERVICE||opening;
 $('service-note').textContent=SERVICE?'Print exports use the local Python renderer and the same saved values.':'Open the local app to import results or generate print images. Chart controls, settings and HTML/SVG exports work offline.';
 if(!has)document.querySelector('.navigation').hidden=true;
}

let renderedIdentity='',resetSequence=0,layoutDirty=false;
function baseLayout(d,family,width,height,ranges){const extent=ranges||axisExtent([]);return {width,height,margin:{l:52,r:24,t:28,b:44},font:{family:'Arial',size:12,color:'#34483b'},paper_bgcolor:'#fff',plot_bgcolor:'#fff',showlegend:false,hovermode:'closest',uirevision:d.key+'-'+family+'-'+resetSequence,xaxis:{range:extent.x,zeroline:true,zerolinecolor:'#92a599',gridcolor:'#e6ede8',title:{text:'Level'},tickfont:{size:11}},yaxis:{range:extent.y,zeroline:true,zerolinecolor:'#92a599',gridcolor:'#e6ede8',title:{text:'Trend'},tickfont:{size:11}}}}
function intersects(a,b){return a.x<b.x+b.w&&a.x+a.w>b.x&&a.y<b.y+b.h&&a.y+a.h>b.y}
function labelAnnotations(rows,bounds,width,height,margin,allPoints=[]){
 const boxes=[],annotations=[],rangeX=bounds.x[1]-bounds.x[0],rangeY=bounds.y[1]-bounds.y[0],pw=width-margin.l-margin.r,ph=height-margin.t-margin.b;
 const pixel=p=>({x:margin.l+(p.x-bounds.x[0])/rangeX*pw,y:margin.t+(bounds.y[1]-p.y)/rangeY*ph});
 const points=allPoints.map(pixel).map(p=>({x:p.x-5,y:p.y-5,w:10,h:10}));
 for(const p of rows){
  if(p.x<bounds.x[0]||p.x>bounds.x[1]||p.y<bounds.y[0]||p.y>bounds.y[1])continue;
  const at=pixel(p),lines=wrap(p.label,Math.min(220,pw-12)),w=Math.max(...lines.map(s=>textWidth(s)))+6,h=lines.length*14+6,candidates=[];
  for(const radius of [12,26,44,68,96]){
   for(const [dx,dy] of [[radius,-h-radius],[-w-radius,-h-radius],[radius,radius],[-w-radius,radius],[-w/2,-h-radius],[-w/2,radius]]){
    const x=Math.max(margin.l+3,Math.min(width-margin.r-w-3,at.x+dx)),y=Math.max(margin.t+3,Math.min(height-margin.b-h-3,at.y+dy)),box={x,y,w,h};
    const score=boxes.filter(b=>intersects(b,box)).length*100000+points.filter(b=>intersects(b,box)).length*120+Math.hypot(x+w/2-at.x,y+h/2-at.y);
    candidates.push({box,score});
   }
  }
  const selected=candidates.sort((a,b)=>a.score-b.score)[0].box;boxes.push(selected);
  const dx=selected.x-at.x,dy=selected.y-at.y,arrow=Math.hypot(dx+w/2,dy+h/2)>24;
  annotations.push({x:p.x,y:p.y,text:lines.map(esc).join('<br>'),font:{size:12,color:p.color||'#26382c'},xanchor:'left',yanchor:'top',align:'left',showarrow:arrow,arrowhead:0,arrowwidth:.7,arrowcolor:'#718176',...(arrow?{ax:dx,ay:dy}:{xshift:dx,yshift:-dy})});
 }
 return annotations;
}
async function plot(name,traces,layout){
 const node=$('pl-'+name+'-inner');await Plotly.react(node,traces,layout,{responsive:false,displaylogo:false,scrollZoom:false,displayModeBar:false});
 node.removeAllListeners('plotly_click');node.on('plotly_click',event=>{const entity=event.points[0]?.customdata?.entity;if(entity)select(entity)});
 node.removeAllListeners('plotly_relayout');node.on('plotly_relayout',()=>{if(!restoring&&ready){capture();persist()}});
}

function shownNames(d){return (state.member?[state.member]:d.defaultPaths).filter(n=>pathRows(d)[n]?.length)}
function pathIndex(d,name){const index=d.defaultPaths.indexOf(name);return Math.max(0,index)}
function pathId(d,name){let n=pathIndex(d,name)+1,id='';while(n){n--;id=String.fromCharCode(65+n%26)+id;n=Math.floor(n/26)}return id}
function pathDash(d,name){return ['solid','dash','dot'][pathIndex(d,name)%3]}
function updatePathKey(d){
 const key=$('path-key'),focused=key.contains(document.activeElement)?document.activeElement.dataset.entity:null;key.replaceChildren();
 for(const name of shownNames(d)){
  const button=document.createElement('button');button.type='button';button.className='path-entry';button.dataset.entity=name;
  button.setAttribute('aria-pressed',String(state.member===name));button.onclick=()=>select(state.member===name?'':name);
  const mark=document.createElement('span');mark.className='path-swatch';mark.style.setProperty('--path-color',Q[pathRows(d)[name][0].quadrant]);mark.dataset.dash=pathDash(d,name);mark.textContent=pathId(d,name);mark.setAttribute('aria-hidden','true');
  const label=document.createElement('span');label.textContent=name;button.append(mark,label);key.append(button);
 }
 if(focused)[...key.querySelectorAll('button')].find(b=>b.dataset.entity===focused)?.focus({preventScroll:true});
}

function pathRows(d){const periods=new Set(d.pathPeriods||[]);return Object.fromEntries(Object.entries(d.paths).map(([n,ps])=>[n,periods.size?ps.filter(p=>periods.has(p.period)):ps]))}
async function render(d,w,g,requested){
 const height=state.panel_height-2,v=view(),matrixWidth=$('pl-matrix').clientWidth-2,matrixRange=v.ranges.matrix||axisExtent(d.matrix),ml=baseLayout(d,'matrix',matrixWidth,height,matrixRange),selected=d.matrix.find(p=>p.entity===state.member);
 if(selected&&(selected.x<matrixRange.x[0]||selected.x>matrixRange.x[1]||selected.y<matrixRange.y[0]||selected.y>matrixRange.y[1]))$('matrix-message').textContent='Selected entity is outside this zoom. Reset view to locate it.';
 ml.annotations=labelAnnotations(selected?[{...selected,label:selected.entity}]:[],matrixRange,matrixWidth,height,ml.margin,d.matrix);
 await plot('matrix',[{type:'scatter',mode:'markers',x:d.matrix.map(p=>p.x),y:d.matrix.map(p=>p.y),customdata:d.matrix.map(p=>({...p,label:esc(p.entity)})),marker:{size:d.matrix.map(p=>p.entity===state.member?13:8),color:d.matrix.map(p=>Q[p.quadrant]),opacity:d.matrix.map(p=>state.member&&state.member!==p.entity?.25:1),line:{color:'#fff',width:1}},hovertemplate:'%{customdata.label}<br>%{customdata.quadrant} · %{customdata.count} records<br>Level %{x:.6g} · Trend %{y:.6g}<extra></extra>'}],ml);
 if(requested!==revision)return;
 const axis=$('timeline-axis');axis.style.width=g.width+'px';axis.style.height=g.axisHeight+'px';axis.replaceChildren();w.periods.forEach((period,i)=>{const span=document.createElement('span');span.className='period-tick';span.textContent=g.tickLabels[i];span.dataset.period=period;span.title=period;span.setAttribute('aria-label',period);span.style.left=(g.left+g.x(period))+'px';span.style.top=(6+i%g.tickLanes*22)+'px';axis.append(span)});
 const events=w.events,annotations=events.flatMap(e=>{const a={x:w.periods.indexOf(e.period),y:g.positions.get(e),xref:'x',yref:'y',showarrow:false,yanchor:'middle',opacity:state.member&&state.member!==e.entity?.22:1,font:{family:'Arial',size:12,color:'#26382c'},captureevents:false};return [{...a,text:e.source+'→',xshift:-12,xanchor:'right'},{...a,text:e.suffix,xshift:12,xanchor:'left'}]});
 await plot('timeline',[{type:'scatter',mode:'markers+text',x:events.map(e=>w.periods.indexOf(e.period)),y:events.map(e=>g.positions.get(e)),text:events.map(e=>e.destination),textposition:'middle center',textfont:{family:'Arial',size:12,color:events.map(e=>e.class===1?'#fff':'#18291f')},customdata:events.map(e=>({...e,label:esc(e.entity),event:e.source+'→'+e.destination+e.suffix,className:NAMES[e.class]})),marker:{size:16,color:events.map(e=>EC[e.class]),opacity:events.map(e=>state.member&&state.member!==e.entity?.22:1),line:{color:events.map(e=>state.member===e.entity?'#152b1c':'#fff'),width:1}},hovertemplate:'%{customdata.label}<br>%{customdata.period} · %{customdata.event}<br>%{customdata.className}<extra></extra>'}],{...baseLayout(d,'timeline',g.width,g.height),margin:{l:g.left,r:g.right,t:g.top,b:g.bottom},xaxis:{range:g.xRange,tickmode:'array',tickvals:w.periods.map((_,i)=>i),showticklabels:false,gridcolor:'#e6ede8',zeroline:false,fixedrange:true},yaxis:{range:[g.contentHeight,0],tickmode:'array',tickvals:g.rows.map(r=>r.center),ticktext:g.labels.map(lines=>lines.map(esc).join('<br>')),tickfont:{size:12},showgrid:false,zeroline:false,fixedrange:true},shapes:g.rows.slice(0,-1).map(r=>({type:'line',xref:'paper',x0:0,x1:1,y0:r.end,y1:r.end,line:{color:'#e6ede8',width:1},layer:'below'})),annotations});
 if(requested!==revision)return;
 const paths=pathRows(d),names=state.member?[state.member]:d.defaultPaths,ps=names.flatMap(n=>paths[n]||[]),width=$('pl-paths').clientWidth-2,range=v.ranges.paths||axisExtent(ps.length?ps:d.matrix),pl=baseLayout(d,'paths',width,height,range);
 pl.annotations=labelAnnotations(names.filter(n=>paths[n]?.length).map(n=>({...paths[n].at(-1),label:pathId(d,n),color:'#26382c'})),range,width,height,pl.margin,ps);
 await plot('paths',names.filter(n=>paths[n]?.length).map(n=>{const points=paths[n];return {type:'scatter',mode:'lines+markers',name:n,x:points.map(p=>p.x),y:points.map(p=>p.y),customdata:points.map(p=>({...p,entity:n,label:esc(n)})),line:{color:Q[points[0].quadrant],width:2,dash:pathDash(d,n)},marker:{size:6},hovertemplate:'%{customdata.label}<br>%{customdata.period}<br>Level %{x:.6g} · Trend %{y:.6g}<extra></extra>'}}),pl);
}
function measureLayout(d,w,g){
 const warnings=[...(d.warnings||[])],issues={matrix:0,timeline:0,paths:0};
 for(const name of ['matrix','paths']){
  const node=$('pl-'+name+'-inner'),bounds=node.getBoundingClientRect(),boxes=[...node.querySelectorAll('.annotation-text-g')].map(n=>n.getBoundingClientRect());
  for(let i=0;i<boxes.length;i++){const b=boxes[i];if(b.left<bounds.left-.5||b.right>bounds.right+.5||b.top<bounds.top-.5||b.bottom>bounds.bottom+.5||boxes.slice(0,i).some(a=>a.left<b.right&&a.right>b.left&&a.top<b.bottom&&a.bottom>b.top))issues[name]++}
 }
 const node=$('pl-timeline-inner'),bounds=node.getBoundingClientRect(),points=[...node.querySelectorAll('.scatterlayer .point')],labels=[...node.querySelectorAll('.annotation')],groups=w.events.map((e,i)=>{const rs=[points[i],labels[i*2],...(e.suffix?[labels[i*2+1]]:[])].filter(Boolean).map(e=>e.getBoundingClientRect());return {x:Math.min(...rs.map(b=>b.left)),y:Math.min(...rs.map(b=>b.top)),w:Math.max(...rs.map(b=>b.right))-Math.min(...rs.map(b=>b.left)),h:Math.max(...rs.map(b=>b.bottom))-Math.min(...rs.map(b=>b.top))}});
 for(let i=0;i<groups.length;i++){const b=groups[i];if(b.x<bounds.left+g.left||b.x+b.w>bounds.right||b.y<bounds.top||b.y+b.h>bounds.bottom||groups.slice(0,i).some(a=>intersects(a,b)))issues.timeline++}
 for(const [elements,frame] of [[node.querySelectorAll('.ytick text'),bounds],[$('timeline-axis').querySelectorAll('.period-tick'),$('timeline-axis').getBoundingClientRect()]]){
  const boxes=[...elements].map(e=>e.getBoundingClientRect());
  for(let i=0;i<boxes.length;i++){const b=boxes[i];if(b.left<frame.left-.5||b.right>frame.right+.5||b.top<frame.top-.5||b.bottom>frame.bottom+.5||boxes.slice(0,i).some(a=>a.left<b.right&&a.right>b.left&&a.top<b.bottom&&a.bottom>b.top))issues.timeline++}
 }
 for(const name of families)if(issues[name]){const message=issues[name]+' label conflict'+(issues[name]===1?'':'s')+' remain. Increase space in Layout before exporting.';warnings.push(name+': '+message);$(name+'-message').textContent=[$(name+'-message').textContent,message].filter(Boolean).join(' ')}
 const unresolved=Object.values(issues).reduce((a,b)=>a+b,0);
 report={schema_version:1,bundle_id:prepared.bundle_id,dataset_key:d.key,renderer:'plotly.js',renderer_version:Plotly.version,dimensions:{width:$('pl-matrix').getBoundingClientRect().width,height:state.panel_height,timeline_width:g.width,timeline_height:g.height},resolved_settings:clone(state),warnings,unresolved,status:unresolved?'unresolved':'ready'};
 $('layout-report').textContent=unresolved?'Some labels need more space. The layout report identifies affected charts.':'Checked label bounds and label-group overlaps at the current display size.';
 return report;
}
function draw({reveal=false,preserve=true}={}){
 if(!prepared.datasets.length){ready=false;setAvailable();announce('No saved results loaded.');return Promise.resolve()}
 if(preserve&&renderedIdentity===prepared.bundle_id+'|'+data()?.key)capture();
 const requested=++revision;ready=false;window.WORKSPACE_READY=false;setAvailable();$('chart-scroll').setAttribute('aria-busy','true');announce('Updating charts…',true);
 const run=async()=>{if(requested!==revision)return;restoring=true;clearError();
 try{
  const d=data(),w=windowData(d),v=view();controls();updateContent(d,w);const g=geometry(d,w);$('pl-timeline-inner').style.width=g.width+'px';$('pl-timeline-inner').style.height=g.height+'px';
  await render(d,w,g,requested);if(requested!==revision)return;
  renderedIdentity=prepared.bundle_id+'|'+d.key;
  const box=$('pl-timeline'),anchor=g.rows.find(r=>r.entity===v.timeline.row);box.scrollLeft=0;box.scrollTop=anchor?anchor.start+Math.min(v.timeline.row_offset||0,anchor.end-anchor.start-1):v.timeline.top||0;
  if(reveal&&state.member){const row=g.rows.find(r=>r.entity===state.member);if(row)box.scrollTop=Math.max(0,g.axisHeight+g.top+row.center-box.clientHeight/2)}
  $('chart-scroll').scrollLeft=v.row_left||0;
  for(const id of ['data-panel','details'])$(id).open=!!v.disclosures[id];
  syncDataPanel();
  for(const b of document.querySelectorAll('[data-focus]'))b.setAttribute('aria-pressed',String(b.dataset.focus===(v.focus||'matrix')));
  document.querySelector('.navigation').hidden=$('chart-scroll').scrollWidth<=$('chart-scroll').clientWidth+1;
  measureLayout(d,w,g);ready=true;window.WORKSPACE_READY=true;window.WORKSPACE_VIEW={type:state.entity_type,cadence:state.cadence,member:state.member,events:w.events.length};
  window.priorityxWorkspace.lastGeometry=g;
  announce(d.typeLabel+', '+state.cadence+', '+w.events.length+' YTD events'+(state.member?', selected '+state.member:''));if(layoutDirty)stale();
 }catch(error){window.WORKSPACE_READY=false;ready=false;errorMessage(error,true);announce('Charts could not update. Your saved results and settings are retained.',true)}
 finally{restoring=false;$('chart-scroll').setAttribute('aria-busy','false');setAvailable();if(ready){capture();persist()}}
 };queue=queue.then(run,run);return queue;
}
function select(member){capture();const changed=state.member!==member;state.member=member;if(changed)delete view().ranges.paths;return draw({reveal:true,preserve:false})}
function stale(){layoutDirty=true;$('layout-status').textContent='Settings changed. Apply layout to update charts and downloads.';setAvailable()}
function download(content,type,name){const u=URL.createObjectURL(content instanceof Blob?content:new Blob([content],{type})),a=document.createElement('a');a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),1000)}
async function api(path,payload){const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),40000);try{const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),signal:controller.signal});if(!r.ok){let body;try{body=await r.json()}catch{body={error:'The local app could not complete this request.'}}throw Error(body.error||body.message||'The local app rejected this request.')}return r}catch(e){if(e.name==='AbortError')throw Error('The local app took too long. Retry with a smaller view.');if(e instanceof TypeError)throw Error('The local app is unavailable. Restart it and retry; the current charts and settings are retained.');throw e}finally{clearTimeout(timer)}}
function install(newBoot,initial=null,restore=true){
 boot=newBoot;prepared=boot.prepared;bundle=boot.bundle;let value=initial||baseSettings();if(restore)try{const saved=localStorage.getItem(storageKey());if(saved)value=JSON.parse(saved)}catch{storageWarning=true}
 try{state=checkSettings(value)}catch(error){state=baseSettings();errorMessage(error)}
 tableKeys={};renderedIdentity='';layoutDirty=false;for(const f of families)$(f+'-table').replaceChildren();
 $('layout-status').textContent='';$('settings-status').textContent='';
 document.querySelector('main').style.setProperty('--panel-min',state.min_panel_width+'px');document.querySelector('main').style.setProperty('--chart-height',state.panel_height+'px');syncLayoutForm();for(const [id,key] of [['panelWidth','min_panel_width'],['panelHeight','panel_height'],['staticWidth','static_width'],['staticHeight','static_height'],['printDpi','dpi']]){const limit=prepared.settings_schema[key];$(id).min=limit.min;$(id).max=limit.max;$(id).step=limit.integer?'1':'any'}window.priorityxWorkspace.state=state;window.priorityxWorkspace.source=bundle;window.priorityxWorkspace.prepared=prepared;
 return draw();
}

async function exportHtml(){
 if(!ready||layoutDirty)throw Error('Apply layout and wait for charts to finish before exporting.');
 capture();persist();$('export-status').textContent='Preparing HTML…';
 try{
  const doc=document.documentElement.cloneNode(true);doc.dataset.service='false';doc.dataset.artifact=globalThis.crypto?.randomUUID?.()||String(Date.now());
  for(const name of families){doc.querySelector('#pl-'+name+'-inner').replaceChildren();doc.querySelector('#'+name+'-table').replaceChildren()}
  doc.querySelector('#initial').textContent=JSON.stringify(state).replace(/</g,'\\u003c');
  doc.querySelector('#workspace-data').textContent=JSON.stringify(boot).replace(/</g,'\\u003c');
  for(const node of doc.querySelectorAll('[data-runtime],#js-plotly-tester,.plotly-notifier,script[src]'))node.remove();
  for(const node of doc.querySelectorAll('dialog[open],.action-menu[open],.export-menu[open]'))node.removeAttribute('open');
  for(const id of ['error','export-status','print-status','layout-status','settings-status'])doc.querySelector('#'+id).textContent='';
  doc.querySelector('#feedback').hidden=true;doc.querySelector('#render-status').textContent='Opening saved results…';
  download('<!doctype html>'+doc.outerHTML,'text/html','priorityx-workspace.html');$('export-status').textContent='HTML saved with this view and full saved history.';
 }catch(error){errorMessage(error);$('export-status').textContent='HTML was not saved.'}
}
async function exportStatic(format){
 if(!SERVICE||!ready||layoutDirty)return;
 capture();const savedState=clone(state),savedBundle=clone(bundle),family=$('printFamily').value,requested=revision,identity=prepared.bundle_id;printing=true;
 $('savePng').disabled=true;$('saveSvg').disabled=true;$('print-status').textContent='Preparing print layout…';
 try{const r=await api('/api/static',{bundle:savedBundle,settings:savedState,family,format}),blob=await r.blob(),raw=r.headers.get('X-PriorityX-Layout'),layout=raw?JSON.parse(raw):null;
  if(requested!==revision||identity!==prepared.bundle_id){$('print-status').textContent='The view changed while rendering. Export the current view again.';return}
  if(layout)window.priorityxWorkspace.lastStaticReport=layout;download(blob,blob.type,'priorityx-'+family+'.'+format);
  $('print-status').textContent=layout?.unresolved?'Image saved; '+layout.unresolved+' unresolved label conflicts. Adjust print size before sharing.':'Print image saved.';
 }catch(error){$('print-status').textContent=error.message}finally{printing=false;setAvailable()}
}
async function openResults(file){
 if(!file)return;if(file.size>64*1024*1024)throw Error('Result bundle exceeds the 64 MiB limit.');
 if(opening)throw Error('Wait for the current result bundle to open.');const prior=ready;opening=true;ready=false;setAvailable();announce('Validating saved results…',true);
 try{const r=await api('/api/prepare',{bundle_json:await file.text(),activate:true});capture();await install(await r.json(),null,true)}
 catch(error){ready=prior;errorMessage(error);announce('Results were not replaced. Choose a valid bundle and retry.',true);setAvailable()}finally{opening=false;setAvailable()}
}
async function importCsv(event){
 event.preventDefault();if(opening)return;opening=true;setAvailable();clearError();$('import-status').textContent='Validating CSV files…';
 try{
  const files={};for(const [role,id] of [['matrix','csvMatrix'],['movement','csvMovement'],['transitions','csvTransitions']]){const f=$(id).files[0];if(f){if(f.size>32*1024*1024)throw Error('CSV file exceeds the 32 MiB limit.');files[role]={name:f.name,text:await f.text()}}}
  if(!Object.keys(files).length)throw Error('Choose at least one saved result CSV.');
  const payload={entity_type:$('importType').value,type_label:$('importLabel').value||null,cadence:$('importCadence').value,source_id:$('importSource').value,coverage_start:$('importStart').value,as_of:$('importAsOf').value,files};
  const r=await api('/api/import',payload),incoming=await r.json(),added=incoming.bundle.datasets[0],existing=bundle.datasets.findIndex(d=>d.entity_type===added.entity_type&&d.cadence===added.cadence);
  if(existing>=0&&!$('importReplace').checked)throw Error('This type and cadence are already loaded. Select Replace to continue.');
  const merged=clone(bundle);if(existing>=0)merged.datasets[existing]=added;else merged.datasets.push(added);
  const activated=await api('/api/prepare',{bundle:merged,activate:true});const next=await activated.json();await install(next,{...baseSettings(),bundle_id:next.prepared.bundle_id,entity_type:added.entity_type,cadence:added.cadence,member:'',views:{}},false);$('import-status').textContent='Results imported.';$('import-panel').close();announce('Results imported. '+$('render-status').textContent);remember();
 }catch(error){$('import-status').textContent=error.message;errorMessage(error)}finally{opening=false;setAvailable()}
}
const dialogOpeners=new Map();
function closeMenus(){for(const id of ['results-menu','export-menu'])$(id).open=false}
function showDialog(id,focusId){const active=document.activeElement,menu=active?.closest('.action-menu,.export-menu');dialogOpeners.set(id,menu?menu.querySelector('summary'):active);closeMenus();if(!$(id).open)$(id).showModal();$(focusId).focus()}
function showLayout(){syncLayoutForm();showDialog('layout-settings','layoutMode')}
function showImport(){showDialog('import-panel','importType')}
for(const button of document.querySelectorAll('[data-close]'))button.onclick=()=>$(button.dataset.close).close();
for(const id of ['layout-settings','import-panel'])$(id).addEventListener('close',()=>dialogOpeners.get(id)?.focus({preventScroll:true}));
$('openResults').onclick=()=>{closeMenus();$('results-menu').querySelector('summary').focus();$('resultsFile').click()};$('emptyOpen').onclick=$('openResults').onclick;
$('resultsFile').onchange=()=>{const file=$('resultsFile').files[0];$('resultsFile').value='';openResults(file).catch(error=>errorMessage(error))};
$('showImport').onclick=showImport;$('emptyImport').onclick=showImport;$('import-form').onsubmit=importCsv;
$('type').onchange=()=>{capture();state.entity_type=$('type').value;const available=prepared.datasets.filter(d=>d.entity_type===state.entity_type);state.cadence=available.some(d=>d.cadence===state.cadence)?state.cadence:available.some(d=>d.cadence==='quarterly')?'quarterly':available[0].cadence;state.member='';state.timeline_scale=1;const v=view();v.ranges={};v.timeline={left:0,top:0};v.row_left=0;v.focus='matrix';syncLayoutForm();draw()};
$('cadence').onchange=()=>{capture();const member=state.member;state.cadence=$('cadence').value;state.member=allMembers(data()).includes(member)?member:'';delete view().ranges.paths;draw({preserve:false})};
$('pathsScope').onchange=()=>{capture();view().paths_scope=$('pathsScope').value;view().tables.paths=0;delete tableKeys.paths;updateContent(data(),windowData(data()));syncDataPanel();remember()};
$('member').onchange=()=>select($('member').value);$('clear').onclick=()=>select('');
$('reset').onclick=()=>{const v=view();v.ranges={};v.timeline={left:0,top:0};v.row_left=0;v.focus='matrix';state.timeline_scale=1;resetSequence++;renderedIdentity='';syncLayoutForm();draw()};
 $('retry').onclick=()=>draw();
for(const b of document.querySelectorAll('[data-focus]'))b.onclick=()=>focusChart(b.dataset.focus);
for(const a of document.querySelectorAll('[data-data]'))a.onclick=e=>{e.preventDefault();openData(a.dataset.data)};
$('data-summary').addEventListener('click',capture);
for(const id of ['data-panel','details'])$(id).addEventListener('toggle',()=>{if(restoring||!data())return;if(id==='data-panel')syncDataPanel();remember()});
for(const b of document.querySelectorAll('[data-tab]')){
 b.onclick=()=>selectDataTab(b.dataset.tab);
 b.onkeydown=event=>{let next;const index=families.indexOf(b.dataset.tab);if(event.key==='ArrowRight')next=(index+1)%families.length;if(event.key==='ArrowLeft')next=(index+families.length-1)%families.length;if(event.key==='Home')next=0;if(event.key==='End')next=families.length-1;if(next!==undefined){event.preventDefault();selectDataTab(families[next],{focus:true})}};
}
for(const name of families)$(name+'-table-scroll').addEventListener('scroll',remember,{passive:true});
for(const id of ['chart-scroll','pl-timeline'])$(id).addEventListener('scroll',remember,{passive:true});
$('layoutLink').onclick=showLayout;$('reviewLayout').onclick=showLayout;
$('layout-form').addEventListener('input',()=>{stale();for(const id of ['staticWidth','staticHeight'])$(id).disabled=$('layoutMode').value!=='manual'});
 $('layout-form').onsubmit=event=>{event.preventDefault();try{capture();const proposed={...state,min_panel_width:Number($('panelWidth').value),panel_height:Number($('panelHeight').value),layout_mode:$('layoutMode').value,static_width:$('layoutMode').value==='manual'?Number($('staticWidth').value):null,static_height:$('layoutMode').value==='manual'?Number($('staticHeight').value):null,dpi:Number($('printDpi').value)};state=checkSettings(proposed);window.priorityxWorkspace.state=state;document.querySelector('main').style.setProperty('--panel-min',state.min_panel_width+'px');document.querySelector('main').style.setProperty('--chart-height',state.panel_height+'px');layoutDirty=false;$('layout-status').textContent='Layout applied.';draw()}catch(error){$('layout-status').textContent=error.message}};
$('resetSettings').onclick=()=>{state=baseSettings();window.priorityxWorkspace.state=state;renderedIdentity='';resetSequence++;layoutDirty=false;document.querySelector('main').style.setProperty('--panel-min',state.min_panel_width+'px');document.querySelector('main').style.setProperty('--chart-height',state.panel_height+'px');$('layout-status').textContent='Default settings restored.';syncLayoutForm();draw()};
$('saveSettings').onclick=()=>{capture();download(JSON.stringify(state,null,2),'application/json','priorityx-view-settings.json');$('settings-status').textContent='Settings saved.'};
$('loadSettings').onclick=()=> $('settingsFile').click();
$('settingsFile').onchange=async()=>{const file=$('settingsFile').files[0];$('settingsFile').value='';if(!file)return;try{if(file.size>2*1024*1024)throw Error('Settings file exceeds the 2 MiB limit.');const loaded=checkSettings(strictParse(await file.text()));capture();state=loaded;window.priorityxWorkspace.state=state;renderedIdentity='';layoutDirty=false;document.querySelector('main').style.setProperty('--panel-min',state.min_panel_width+'px');document.querySelector('main').style.setProperty('--chart-height',state.panel_height+'px');$('layout-status').textContent='';syncLayoutForm();await draw();$('settings-status').textContent='Settings restored.'}catch(error){$('settings-status').textContent=error.message}};
$('saveHtml').onclick=()=>exportHtml().catch(error=>errorMessage(error));
$('saveMatrix').onclick=async()=>{if(!ready||layoutDirty)return;try{const requested=revision,identity=prepared.bundle_id;const image=await Plotly.toImage($('pl-matrix-inner'),{format:'svg'}),text=image.includes(';base64,')?new TextDecoder().decode(Uint8Array.from(atob(image.split(',')[1]),c=>c.charCodeAt(0))):decodeURIComponent(image.slice(image.indexOf(',')+1));if(requested!==revision||identity!==prepared.bundle_id){$('export-status').textContent='The view changed. Export the current matrix again.';return}capture();const metadata=esc(JSON.stringify({...report,resolved_settings:state})),tag=text.match(/<svg\b[^>]*>/);const enriched=tag?text.replace(tag[0],tag[0]+'<metadata id="priorityx-provenance">'+metadata+'</metadata>'):text;download(enriched,'image/svg+xml','priorityx-matrix.svg');$('export-status').textContent='Matrix SVG saved.'}catch(error){$('export-status').textContent=error.message}};
$('saveBundle').onclick=()=>download(JSON.stringify(bundle,null,2),'application/json','priorityx-results.json');
$('saveReport').onclick=()=>{capture();report.resolved_settings=clone(state);download(JSON.stringify(report,null,2),'application/json','priorityx-layout-report.json')};
$('savePng').onclick=()=>exportStatic('png');$('saveSvg').onclick=()=>exportStatic('svg');
for(const id of ['results-menu','export-menu'])$(id).addEventListener('toggle',()=>{if($(id).open)for(const other of ['results-menu','export-menu'])if(other!==id)$(other).open=false});
document.addEventListener('keydown',e=>{if(e.key==='Escape')for(const id of ['results-menu','export-menu'])if($(id).open){$(id).open=false;$(id).querySelector('summary').focus()}});
document.addEventListener('click',e=>{for(const id of ['results-menu','export-menu'])if(!$(id).contains(e.target))$(id).open=false});
window.addEventListener('pagehide',remember);
let resizeTimer;window.addEventListener('resize',()=>{remember();clearTimeout(resizeTimer);resizeTimer=setTimeout(()=>draw(),150)});
window.priorityxWorkspace={get state(){return state},set state(value){state=value},get source(){return bundle},set source(value){bundle=value},get prepared(){return prepared},set prepared(value){prepared=value},data,draw,select,windowData,geometry,focusChart,exportHtml,openResults,install,capture,checkSettings,get report(){return report},get ready(){return ready},get service(){return SERVICE}};
const initial=JSON.parse($('initial').textContent);await install(boot,initial,true);
if(storageWarning)errorMessage('Browser storage is unavailable. Save settings before closing to keep this view.');
})().catch(error=>{const p=document.getElementById('error');p.textContent='Workspace could not open: '+error.message;document.getElementById('feedback').hidden=false;document.getElementById('render-status').textContent='Choose valid saved results and retry.';console.error(error)});
