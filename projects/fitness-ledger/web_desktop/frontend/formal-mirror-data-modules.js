const bridge=window.__fitnessLedgerFormalMirrorBridge;
if(!bridge){console.error('[Data Module Mirror] Web bridge unavailable');}
else{
const $=(selector,root=document)=>root.querySelector(selector);
const $$=(selector,root=document)=>[...root.querySelectorAll(selector)];
const esc=value=>String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const state={catalog:null,activePreview:null,entryRaw:'',formContext:null,catalogRequestSerial:0,catalogAppliedSerial:0,bodyShelfBusy:false};
const post=(path,payload)=>bridge.postApi(path,payload);
const get=path=>bridge.api(path);
const categoryLabel=id=>state.catalog?.categories?.find(item=>item.category_id===id)?.label||id||'未分类';
const moduleById=id=>state.catalog?.modules?.find(item=>item.module_id===id);
const placementLabel=value=>state.catalog?.placement_choices?.find(item=>item.value===value)?.label||'页面摘要';
const formatValue=(value,unit='')=>`${value??'暂无'}${value!==undefined&&value!==null&&value!==''&&unit?' '+unit:''}`;

async function loadCatalog(){const serial=++state.catalogRequestSerial;const next=await get('/api/data-modules/product-catalog');if(serial>=state.catalogAppliedSerial){state.catalog=next;state.catalogAppliedSerial=serial}return state.catalog}
function friendlyError(error){
  const payload=error?.payload||{};
  const code=payload.code||'';
  const details=payload.details||{};
  if(code==='MODULE_ALIAS_CONFLICT'||code==='MODULE_LABEL_CONFLICT')return `“${details.conflict_alias||details.alias||'这个表达'}”已经用于记录项“${details.conflict_with_label||details.conflict_with||'已有记录项'}”。请换一个表达，或编辑已有记录项。`;
  if(code==='CATEGORY_LABEL_REQUIRED')return '请填写类别名称。';
  if(code==='MODULE_CATEGORY_REQUIRED')return '请选择记录项所属类别。';
  if(code==='MODULE_NOT_RECORDABLE'||code==='CATEGORY_NOT_RECORDABLE')return '这个记录项目前已停用，不能新增记录；历史记录仍然保留。';
  if(code==='MODULE_VALUE_MISSING')return '这条记录里没有找到数值，请把数值写在记录项名称后面。';
  if(code==='MODULE_PREVIEW_INVALID')return '当前数值没有通过校验，请检查单位或数值范围。';
  if(code==='MODULE_PREVIEW_STALE'||code==='DEFINITION_PREVIEW_STALE')return '页面内容已经变化，请重新预览后再确认。';
  return error?.message||'本地候选服务暂时无法完成这一步。';
}
function closeOverlay(){bridge.root.innerHTML='';state.formContext=null}
function openShellModal(title,body,actions=''){
  bridge.root.innerHTML=`<div class="overlay" data-close><section class="modal light dm-modal" data-dm-stop><button class="close" data-close aria-label="关闭">×</button><span class="eyebrow">DATA MODULES / LOCAL MIRROR</span><h2>${esc(title)}</h2>${body}${actions?`<div class="modal-actions">${actions}</div>`:''}</section></div>`;
}

function formMarkup({mode='create',module=null,candidate=null}={}){
  const values=module||candidate||{};
  const activeCategories=(state.catalog?.categories||[]).filter(item=>item.status==='active');
  const selectedCategory=values.category_id||candidate?.suggested_category_id||'body';
  const placement=module?.placement||'summary';
  const aliases=(values.aliases||candidate?.aliases||[]).join('，');
  const caps=module?.capabilities||{};
  return `<form id="dm-definition-form" data-mode="${mode}" data-module-id="${esc(module?.module_id||'')}" data-source-raw="${esc(candidate?.raw||'')}">
    <p class="dm-form-intro">普通记录项只需要一个名称。类别、单位和展示位置可以稍后在 Tools 中调整。</p>
    <div class="dm-form-grid">
      <label><span>记录项名称</span><input name="label" required value="${esc(values.label||'')}" placeholder="例如：晨间脉搏"></label>
      <label><span>类别</span><select name="category_id" required>${activeCategories.map(item=>`<option value="${esc(item.category_id)}" ${selectedCategory===item.category_id?'selected':''}>${esc(item.label)}</option>`).join('')}<option value="__new__">＋ 新建类别</option></select></label>
      <label class="dm-new-category-field" hidden><span>新类别名称</span><input name="new_category_label" placeholder="例如：恢复状态"></label>
      <label><span>单位 <small>可选</small></span><input name="actual_unit" value="${esc(values.actual_unit||candidate?.unit||'')}" placeholder="例如：bpm、cm"></label>
      <label class="is-wide"><span>常用表达 <small>可选，用逗号分开</small></span><textarea name="aliases" rows="2" placeholder="例如：晨间脉搏，早晨心率">${esc(aliases)}</textarea></label>
      <label><span>放在哪里 <small>可选</small></span><select name="placement">${(state.catalog?.placement_choices||[]).map(item=>`<option value="${esc(item.value)}" ${placement===item.value?'selected':''}>${esc(item.label)}</option>`).join('')}</select></label>
    </div>
    <details class="dm-advanced"><summary>高级设置（普通记录无需修改）</summary><div class="dm-advanced-grid"><label><input type="checkbox" name="analysis_visible" ${caps.analysis_visible?'checked':''}>允许分析读取</label><label><input type="checkbox" name="cloud_syncable" ${caps.cloud_syncable?'checked':''}>允许加入 Cloud dry-run</label><label><input type="checkbox" name="mini_program_visible" ${caps.mini_program_visible?'checked':''}>允许 Mini renderer 读取</label></div><p>默认关闭下游能力；开启只影响候选镜像能力契约，不会联网或发布。</p></details>
    <p class="dm-form-error" data-dm-form-error hidden></p>
  </form>`;
}
function openModuleForm(options={}){
  if(!state.catalog){loadCatalog().then(()=>openModuleForm(options));return}
  state.formContext=options;
  const mode=options.mode||'create';
  const title=mode==='edit'?'编辑记录项':'建立新的记录项';
  const action=mode==='edit'?'保存修改':'创建并继续';
  openShellModal(title,formMarkup(options),`<button class="btn" data-close>取消</button><button class="btn btn-primary" type="button" data-dm-submit-definition>${action} <span>→</span></button>`);
  const form=$('#dm-definition-form');
  form?.querySelector('[name="category_id"]')?.addEventListener('change',event=>{const field=$('.dm-new-category-field',form);if(field)field.hidden=event.target.value!=='__new__'});
  if(form?.querySelector('[name="category_id"]')?.value==='__new__')$('.dm-new-category-field',form).hidden=false;
}
function readForm(form){
  const data=Object.fromEntries(new FormData(form).entries());
  data.aliases=String(data.aliases||'').split(/[,，\n]/).map(item=>item.trim()).filter(Boolean);
  data.capabilities={recordable:true,queryable:true,history_enabled:true,exportable:true,analysis_visible:form.elements.analysis_visible?.checked===true,cloud_syncable:form.elements.cloud_syncable?.checked===true,mini_program_visible:form.elements.mini_program_visible?.checked===true};
  return data;
}
async function saveDefinition(){
  const form=$('#dm-definition-form');
  if(!form)return;
  const button=$('[data-dm-submit-definition]');
  const errorBox=$('[data-dm-form-error]');
  const showError=message=>{if(errorBox){errorBox.hidden=false;errorBox.textContent=message}};
  const values=readForm(form);
  if(!values.label.trim()){showError('请填写记录项名称。');return}
  button.disabled=true;button.textContent='正在准备…';
  try{
    let categoryId=values.category_id;
    if(categoryId==='__new__'){
      if(!String(values.new_category_label||'').trim()){showError('请填写新类别名称。');button.disabled=false;button.textContent='创建并继续 →';return}
      const categoryPreview=await post('/api/data-modules/product-definition-preview',{kind:'category',action:'create',values:{label:String(values.new_category_label).trim()}});
      await post('/api/data-modules/definition-save',{preview:categoryPreview,confirmed:true});
      await loadCatalog();
      categoryId=state.catalog.categories.find(item=>item.label===String(values.new_category_label).trim())?.category_id;
      if(!categoryId)throw Error('新类别已保存，但页面没有找到它。');
    }
    values.category_id=categoryId;
    const request={kind:'module',action:form.dataset.mode==='edit'?'update':'create',module_id:form.dataset.moduleId||undefined,values};
    if(request.action==='update')request.changes=values;
    button.textContent='正在预览…';
    const preview=await post('/api/data-modules/product-definition-preview',request);
    button.textContent='正在保存…';
    await post('/api/data-modules/definition-save',{preview,confirmed:true});
    const sourceRaw=form.dataset.sourceRaw||'';
    closeOverlay();
    await loadCatalog();
    bridge.showToast(`“${values.label}”已加入${categoryLabel(categoryId)}。`);
    if(form.dataset.mode!=='edit'&&sourceRaw){state.entryRaw=sourceRaw;await openRecordPreview(sourceRaw)}
    else if(bridge.currentRoute().view==='tools')renderManagementPage();
  }catch(error){showError(friendlyError(error));button.disabled=false;button.textContent=form.dataset.mode==='edit'?'保存修改':'创建并继续'}
}
function openCategoryForm(){
  openShellModal('新建类别','<form id="dm-category-form"><p class="dm-form-intro">类别只是帮助你整理记录项。系统会自动生成内部标识和顺序。</p><label><span>类别名称</span><input name="label" required placeholder="例如：恢复状态"></label><p class="dm-form-error" data-dm-category-error hidden></p></form>','<button class="btn" data-close>取消</button><button class="btn btn-primary" data-dm-submit-category>保存类别 <span>→</span></button>');
}
async function saveCategory(){
  const form=$('#dm-category-form'),button=$('[data-dm-submit-category]'),errorBox=$('[data-dm-category-error]');
  const label=form?.elements.label?.value.trim();if(!label){errorBox.hidden=false;errorBox.textContent='请填写类别名称。';return}
  button.disabled=true;try{const preview=await post('/api/data-modules/product-definition-preview',{kind:'category',action:'create',values:{label}});await post('/api/data-modules/definition-save',{preview,confirmed:true});closeOverlay();await loadCatalog();bridge.showToast(`类别“${label}”已建立。`);renderManagementPage()}catch(error){errorBox.hidden=false;errorBox.textContent=friendlyError(error);button.disabled=false}}

async function openRecordPreview(raw,knownPreview=null){
  state.entryRaw=raw;bridge.root.innerHTML='<div class="overlay"><section class="modal light dm-modal"><div class="loading-page" style="height:180px"><i></i><p>正在准备当前记录…</p></div></section></div>';
  try{const preview=knownPreview||await post('/api/data-modules/preview',{raw});state.activePreview=preview;const candidates=preview.candidates||[];openShellModal('当前记录预览',`<p class="dm-form-intro">确认后才会写入匿名候选沙盒；返回修改不会产生记录。</p><div class="dm-preview-list">${candidates.map(item=>{const mod=moduleById(item.module_id)||{};return `<article class="dm-preview-row"><div><span class="eyebrow">${esc(categoryLabel(mod.category_id))}</span><h3>${esc(mod.label||item.matched_alias)}</h3></div><strong>${esc(formatValue(item.value,mod.display_unit||mod.actual_unit||item.unit_hint))}</strong><small>${esc(item.date||'')}</small></article>`}).join('')}</div><p class="dm-preview-raw">原始输入：${esc(raw)}</p>`,'<button class="btn" data-close>返回编辑</button><button class="btn btn-primary" data-dm-confirm-record>确认并保存 <span>→</span></button>')}catch(error){openShellModal('这条记录还不能保存',`<p class="dm-form-error">${esc(friendlyError(error))}</p>`,'<button class="btn btn-primary" data-close>知道了</button>')}}
async function confirmRecord(){
  if(!state.activePreview)return;const button=$('[data-dm-confirm-record]');button.disabled=true;button.textContent='正在保存…';
  try{const result=await post('/api/data-modules/save',{preview:state.activePreview,confirmed:true});state.activePreview=null;await bridge.refreshWebState();openShellModal('已保存到记录历史',`<div class="dm-success"><span class="dm-success-mark">✓</span><h3>这是一个正式的 Module Record</h3><p>它已经进入本地候选档案，可以在 Body、History 和 Normal Export 中查看。</p><div class="dm-save-receipt"><span>保存状态</span><strong>${esc(result.status||'CREATED')}</strong></div></div>`,'<button class="btn" data-dm-go-history>查看历史</button><button class="btn btn-primary" data-dm-go-body>打开 Body <span>→</span></button>')}catch(error){button.disabled=false;button.textContent='确认并保存 →';bridge.showToast(friendlyError(error))}}

async function showHistory(moduleId){
  try{const payload=await get(`/api/data-modules/history?module_id=${encodeURIComponent(moduleId)}`),module=moduleById(moduleId)||payload.module||{};bridge.modal(`${module.label||moduleId} · 历史`,`<div class="dm-history-list">${(payload.history||[]).map(item=>`<div class="dm-history-row"><strong>${esc(item.date)}</strong><span>${esc(formatValue(item.display_value??item.value,module.display_unit||module.actual_unit))}</span></div>`).join('')||'<p class="empty-copy">还没有保存过记录。</p>'}</div><p class="quiet-note">停用只会阻止新记录，历史不会消失。</p>`,{light:true,actions:'<button class="btn btn-primary" data-close>关闭</button>'})}catch(error){bridge.showToast(friendlyError(error))}}

function downstreamPanel(){return `<section class="admin-panel dm-downstream"><header class="admin-panel-header"><div><span class="admin-kicker">DOWNSTREAM / SAFE BY DEFAULT</span><h2>配套能力</h2></div><span class="admin-status-badge">LOCAL ONLY</span></header><div class="dm-downstream-grid"><div><strong>Normal Export</strong><small>已接入本地导出</small></div><div><strong>Analysis</strong><small>新模块默认关闭</small></div><div><strong>Cloud dry-run</strong><small>只生成检查结果，不联网</small></div><div><strong>Mini renderer</strong><small>候选契约可检查，不发布</small></div></div></section>`}
function moduleCard(module){
  const active=module.status==='active';
  return `<article class="admin-panel dm-module-card ${active?'':'is-retired'}" data-dm-module-card="${esc(module.module_id)}"><header class="dm-module-card-head"><div><span class="admin-kicker">${esc(module.category_label)}</span><h3>${esc(module.label)}</h3><p>${esc(module.actual_unit||'无单位')} · ${esc(module.placement_label)}</p></div><span class="admin-status-badge">${active?'使用中':'已停用'}</span></header><div class="dm-module-aliases">${(module.aliases||[]).slice(0,4).map(alias=>`<span>${esc(alias)}</span>`).join('')}</div><div class="dm-module-actions"><button class="admin-button admin-button-outline" data-dm-edit="${esc(module.module_id)}">编辑</button><button class="admin-button admin-button-outline" data-dm-history="${esc(module.module_id)}">历史</button><button class="admin-button ${active?'admin-button-danger':'admin-button-primary'}" data-dm-toggle="${esc(module.module_id)}" data-dm-next-status="${active?'retire':'re_enable'}">${active?'停用':'重新启用'}</button></div><details class="dm-tech"><summary>高级信息</summary><p>稳定标识：${esc(module.module_id)} · 定义版本 ${esc(module.definition_version)}</p><p>分析 ${module.capabilities.analysis_visible?'开启':'关闭'} · Cloud ${module.capabilities.cloud_syncable?'开启':'关闭'} · Mini ${module.capabilities.mini_program_visible?'开启':'关闭'}</p></details></article>`;
}
function categoryCard(category){
  const active=category.status==='active';
  return `<article class="dm-category-chip ${active?'':'is-retired'}"><div><strong>${esc(category.label)}</strong><small>${category.system?'系统类别':'自定义类别'} · ${active?'可用':'已停用'}</small></div>${category.system?'':'<button class="admin-button admin-button-outline" data-dm-category-toggle="'+esc(category.category_id)+'" data-dm-next-status="'+(active?'retire':'re_enable')+'">'+(active?'停用':'重新启用')+'</button>'}</article>`;
}
async function renderManagementPage(){
  if(!state.catalog)try{await loadCatalog()}catch(error){bridge.main.innerHTML=`<section class="page admin-page"><p class="dm-form-error">${esc(friendlyError(error))}</p></section>`;return}
  bridge.main.innerHTML=`<section class="page admin-page admin-tools-page tools-template-v6 dm-management-page"><header class="admin-page-header"><div><div class="admin-breadcrumb"><span>08 / TOOLS</span><i>/</i><strong>DATA MODULES</strong></div><h1>Data Modules</h1><p>把个人真正想追踪的数值，加入同一套记录、历史与导出流程。</p></div><div class="admin-header-actions"><button class="admin-button admin-button-outline" data-dm-new-category>新建类别</button><button class="admin-button admin-button-primary" data-dm-new-module>＋ 新建记录项</button></div></header><section class="dm-management-intro"><div><span class="admin-kicker">ONE RECORDING SURFACE</span><h2>从 Daily Entry 开始，管理细节留在这里。</h2><p>普通用户只需要名称、类别和单位。内部标识、版本与能力默认隐藏。</p></div><div class="dm-flow-steps"><span>01 输入</span><span>02 预览</span><span>03 确认</span><span>04 历史</span></div></section><section class="dm-category-list"><header><span class="admin-kicker">CATEGORIES</span><h2>类别</h2></header><div>${(state.catalog.categories||[]).map(categoryCard).join('')}</div></section><section class="dm-module-grid" data-dm-module-list>${(state.catalog.modules||[]).map(moduleCard).join('')}</section>${downstreamPanel()}<p class="dm-management-note">这是隔离候选镜像。保存只进入匿名沙盒，不改正式 tracker、Cloud 或 Mini。</p></section>`;
}
function enhanceToolsOverview(){
  if(bridge.currentRoute().panel==='data-modules')return;
  const grid=$('.admin-tool-grid');if(!grid||$('.dm-tools-entry'))return;
  const card=document.createElement('button');card.type='button';card.className='admin-panel admin-operation-card dm-tools-entry';card.dataset.dmOpenManage='true';card.innerHTML='<header class="admin-panel-header"><div><span class="admin-kicker">03 / DATA MODULES</span><h2>Track what matters.</h2></div><span class="admin-card-arrow">↗</span></header><p>新增自己的数值记录项，沿用 Daily Entry、History 和 Export。</p><div class="admin-card-footer"><span>REGISTRY-DRIVEN · LOCAL ONLY</span><strong>Manage Data Modules <i>→</i></strong></div>';
  grid.appendChild(card);
}
async function enhanceBodyPage(){
  const bodyView=bridge.currentRoute().view;
  if(bodyView!=='body'||$('.dm-body-shelf')||state.bodyShelfBusy)return;
  state.bodyShelfBusy=true;
  try{if(!state.catalog)await loadCatalog();const exported=await get('/api/data-modules/export');const records=exported.records||[];const latest=new Map();records.forEach(item=>{if(!latest.has(item.module_id))latest.set(item.module_id,item)});const modules=(state.catalog.modules||[]).filter(item=>item.status==='active'&&['summary','main','detail'].includes(item.placement));const categories=[...new Set(modules.map(item=>item.category_id))];if($('.dm-body-shelf'))return;const shelf=document.createElement('section');shelf.className='dm-body-shelf';shelf.innerHTML=`<header><div><span class="eyebrow">PERSONAL EXTENSIONS</span><h2>自定义记录项</h2><p>新增模块和 Body 原有记录一起出现在同一份档案里。</p></div><button class="admin-button admin-button-outline" data-dm-open-manage>管理记录项 →</button></header><div class="dm-body-groups">${categories.map(category=>`<div class="dm-body-group"><span>${esc(categoryLabel(category))}</span><div>${modules.filter(item=>item.category_id===category).map(item=>{const row=latest.get(item.module_id);return `<article class="dm-body-card"><strong>${esc(item.label)}</strong><b>${esc(row?formatValue(row.value,item.display_unit||item.actual_unit):'暂无')}</b><small>${esc(row?.date||'尚未记录')}</small><button data-dm-history="${esc(item.module_id)}">查看历史</button></article>`}).join('')}</div></div>`).join('')}</div>`;$('.archive-heading')?.insertAdjacentElement('afterend',shelf)}catch(error){console.warn('[Data Module Mirror] Body shelf unavailable',error)}finally{state.bodyShelfBusy=false}}
function enhanceQuickPage(){
  if(bridge.currentRoute().view!=='quick')return;const phase=$('.entry-page .phase');if(phase)phase.textContent='正式 Web 交互镜像：保存只写入匿名候选沙盒。';if(!$('.dm-entry-hint'))$('.entry-page .actions')?.insertAdjacentHTML('afterend','<p class="dm-entry-hint">想追踪新的数值？直接写进来。未识别时会在这里建立新的记录项，不需要重新输入。</p>')}
function renderCurrent(){
  const route=bridge.currentRoute();
  if(route.view==='tools'&&route.params.get('panel')==='data-modules')renderManagementPage();
  else{enhanceQuickPage();enhanceToolsOverview();enhanceBodyPage()}
}
bridge.installParseOverride(async original=>{
  const raw=$('#raw-entry')?.value.trim();if(!raw){return original()}
  try{
    const discovery=await post('/api/data-modules/discover',{raw});
    if(discovery.kind==='known'){await openRecordPreview(raw,discovery.preview);return}
    if(discovery.kind==='new_candidate'){
      // Existing first-party fields stay on the established parser. Everything
      // else is offered as a generic extension candidate.
      if(!/(体重|体脂|排便|睡眠|步数|热量|蛋白|碳水|脂肪|训练|有氧|备注|weight|calorie|protein|sleep|steps|training|cardio)/i.test(discovery.candidate.label)){
        state.entryRaw=raw;openModuleForm({mode:'create',candidate:discovery.candidate});return
      }
    }
    if(discovery.kind==='not_data_module')return original();
  }catch(error){
    if(error?.payload?.code&&!['MODULE_NOT_RECOGNIZED','MODULE_DATE_REQUIRED'].includes(error.payload.code)){bridge.showToast(friendlyError(error));return}
  }
  return original();
});
window.addEventListener('fitness-ledger-pet:route-change',()=>{setTimeout(renderCurrent,0)});
document.addEventListener('click',event=>{
  const target=event.target.closest?.('[data-dm-open-manage],[data-dm-new-module],[data-dm-new-category],[data-dm-submit-definition],[data-dm-submit-category],[data-dm-confirm-record],[data-dm-history],[data-dm-edit],[data-dm-toggle],[data-dm-category-toggle],[data-dm-go-history],[data-dm-go-body]');if(!target)return;
  event.preventDefault();event.stopPropagation();
  if(target.matches('[data-dm-open-manage]')){bridge.navigate('tools',{panel:'data-modules'});return}
  if(target.matches('[data-dm-new-module]')){openModuleForm();return}
  if(target.matches('[data-dm-new-category]')){openCategoryForm();return}
  if(target.matches('[data-dm-submit-definition]')){saveDefinition();return}
  if(target.matches('[data-dm-submit-category]')){saveCategory();return}
  if(target.matches('[data-dm-confirm-record]')){confirmRecord();return}
  if(target.matches('[data-dm-history]')){showHistory(target.dataset.dmHistory);return}
  if(target.matches('[data-dm-edit]')){const module=moduleById(target.dataset.dmEdit);if(module)openModuleForm({mode:'edit',module});return}
  if(target.matches('[data-dm-toggle]')){toggleModule(target.dataset.dmToggle,target.dataset.dmNextStatus);return}
  if(target.matches('[data-dm-category-toggle]')){toggleCategory(target.dataset.dmCategoryToggle,target.dataset.dmNextStatus);return}
  if(target.matches('[data-dm-go-history]')){const moduleId=state.activePreview?.candidates?.[0]?.module_id;closeOverlay();if(moduleId)showHistory(moduleId);return}
  if(target.matches('[data-dm-go-body]')){closeOverlay();bridge.navigate('body');return}
},true);
async function toggleModule(moduleId,action){
  const module=moduleById(moduleId);if(!module)return;
  try{const preview=await post('/api/data-modules/product-definition-preview',{kind:'module',action,module_id:moduleId,values:{}});await post('/api/data-modules/definition-save',{preview,confirmed:true});await loadCatalog();bridge.showToast(action==='retire'?'记录项已停用，历史仍然保留。':'记录项已重新启用。');renderManagementPage()}catch(error){bridge.showToast(friendlyError(error))}
}
async function toggleCategory(categoryId,action){
  try{const preview=await post('/api/data-modules/product-definition-preview',{kind:'category',action,category_id:categoryId,changes:{}});await post('/api/data-modules/definition-save',{preview,confirmed:true});await loadCatalog();bridge.showToast(action==='retire'?'类别已停用，新记录会被阻止。':'类别已重新启用。');await renderManagementPage()}catch(error){bridge.showToast(friendlyError(error))}
}
const baseMirrorNavigate=bridge.navigate;
bridge.navigate=(...args)=>{const result=baseMirrorNavigate(...args);renderCurrent();return result};
window.addEventListener('hashchange',()=>setTimeout(renderCurrent,0));
window.__fitnessLedgerFormalMirrorReady=true;
renderCurrent();
}
