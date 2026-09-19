"""Contracts for Session filtering and optional Web effects."""

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import unquote


PROJECT = Path(__file__).resolve().parents[1]


def edge_path() -> Path | None:
    for root in (os.environ.get("PROGRAMFILES(X86)", ""), os.environ.get("PROGRAMFILES", "")):
        candidate = Path(root) / "Microsoft/Edge/Application/msedge.exe"
        if candidate.is_file():
            return candidate
    return None


def browser_contract(app: str) -> None:
    edge = edge_path()
    if edge is None:
        return
    index = (PROJECT / "web_desktop/frontend/index.html").read_text(encoding="utf-8")
    script = re.search(r'<script type="module" src="app\.js(?:\?[^" ]+)?"></script>', index).group(0)
    harness = """
const ok=value=>({ok:true,status:200,json:async()=>value});let testSync=false,syncStatusReads=0;
localStorage.setItem('fitness-ledger.ui-language.v1','zh');let petGreeting='';window.addEventListener('fitness-ledger-pet:intent',event=>{if(event.detail?.type==='home-entry')petGreeting=event.detail.summary?.greeting||''});
window.fetch=async path=>{const url=String(path);
 if(url.includes('/api/today'))return ok({date:'2099-01-02',body:{'Weight (kg)':70.2},diet:{'Calories (kcal)':2100},training:{split:'Push'}});
 if(url.includes('/api/recent'))return ok([{date:'2099-01-02',weight:70.2,calories:2100,split:'Push'},{date:'2099-01-01',weight:70.1,calories:2050,split:'Pull'},{date:'2089-12-31',weight:70,calories:2000,split:'Legs'},{date:'2089-12-30',weight:69.9,calories:1950,split:'Rest'}]);
 if(url.includes('/api/body'))return ok([{Date:'2099-01-02','Weight (kg)':70.2},{Date:'2099-01-01','Weight (kg)':70.1},{Date:'2089-12-31','Weight (kg)':70},{Date:'2089-12-30','Weight (kg)':69.9},{Date:'2089-12-29','Weight (kg)':69.8},{Date:'2089-12-28','Weight (kg)':69.7},{Date:'2089-12-27','Weight (kg)':69.6}]);
 if(url.includes('/api/training-organization'))return ok({session_themes:[{theme_id:'theme:push',display_name:'Push',active:true},{theme_id:'theme:pull',display_name:'Pull',active:true}],movement_categories:[]});
 if(url.includes('/api/training'))return ok([{Date:'2099-01-02',session_theme_ids:['theme:push'],movement_refs:[]},{Date:'2099-01-01',session_theme_ids:['theme:push'],movement_refs:[]}]);
 if(url.includes('/api/movements'))return ok([{movement_id:'CHEST_001',display_name:'卧推',english_name:'Bench Press',muscle_group:'Chest',history_count:1,active:true},{movement_id:'BACK_001',display_name:'引体向上',english_name:'Pull-up',muscle_group:'Back',history_count:0,active:true},{movement_id:'SHOULDER_001',display_name:'哑铃推肩',english_name:'Dumbbell Shoulder Press',muscle_group:'Shoulder',history_count:0,active:true},{movement_id:'ARM_001',display_name:'二头弯举',english_name:'Biceps Curl',muscle_group:'Arms',history_count:0,active:true},{movement_id:'LEG_001',display_name:'深蹲',english_name:'Squat',muscle_group:'Legs',history_count:0,active:true}]);
 if(url.includes('/api/cloud-sync/status')){if(!testSync)return ok({sync_status:'SYNCED'});syncStatusReads++;return ok({sync_status:syncStatusReads>=3?'SYNCED':'LOCAL_NEWER',auto_sync_enabled:true,upload_provider_ready:true})}
 if(url.includes('/api/cloud-sync/sync')){const error=Error('simulated timeout');error.name='AbortError';throw error}
 if(url.includes('/api/archive-health'))return ok({status:'OK',issue_count:0});
 if(url.includes('/api/build-info'))return ok({status:'PREVIEW'});
 if(url.includes('/api/undo-status'))return ok({available:false});
 if(url.includes('/api/data-modules/llm-template'))return ok({prompt_template:'请输出中文字段',fields:[]});
 if(url.includes('/api/analysis-export/initialization-prompt'))return ok({prompt_template:'分析工作流初始化内容'});
 return ok([])};
window.addEventListener('error',event=>{const report=document.createElement('div');report.id='web-session-effects-report';report.dataset.value=encodeURIComponent(JSON.stringify({runtimeError:String(event.error?.stack||event.message||event)}));document.body.appendChild(report)});window.addEventListener('unhandledrejection',event=>{const report=document.createElement('div');report.id='web-session-effects-report';report.dataset.value=encodeURIComponent(JSON.stringify({runtimeError:String(event.reason?.stack||event.reason)}));document.body.appendChild(report)});
"""
    assertions = """
const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
await wait(250);navigate('training');await wait(80);
const themeLabels=[...document.querySelectorAll('.theme-cn')].map(node=>node.textContent.trim());
const themeEnglishLabels=[...document.querySelectorAll('.theme-en')].map(node=>node.textContent.trim());
const fontPair=selector=>{const node=document.querySelector(selector);return node?[parseFloat(getComputedStyle(node).fontSize),parseFloat(getComputedStyle(node.nextElementSibling).fontSize)]:[]};const themeChineseFonts=fontPair('.body-theme-control .theme-cn');document.querySelector('[data-training-theme="theme:push"]')?.click();await wait(80);const themeDetailChineseFonts=fontPair('.body-theme-control.is-active .theme-cn'),themeDetailChineseInactiveFonts=fontPair('.body-theme-control:not(.is-active) .theme-cn'),themeCardStates=[...document.querySelectorAll('.body-theme-control')].map(node=>({id:node.dataset.trainingTheme,active:node.classList.contains('is-active')}));
navigate('tools');await wait(80);
const switches=[...document.querySelectorAll('[data-web-effect]')];
const switchesInRail=switches.every(node=>node.closest('.admin-workspace-rail'));
const switchesHidden=switches.length===0;
testSync=true;syncStatusReads=0;const syncOutcome=await autoSyncAfterSave(),autoSyncStatusReads=syncStatusReads;
navigate('home');await wait(80);const homeText=document.querySelector('.home-page')?.innerText||'';
navigate('quick');await wait(80);const quickText=document.querySelector('.entry-page')?.innerText||'';
const recentDates=[...document.querySelectorAll('.entry-recent-compact .compact-record strong')].map(node=>node.textContent.trim());const recentHistoryCorrect=JSON.stringify(recentDates)===JSON.stringify(['2099-01-01','2089-12-31','2089-12-30'])&&!quickText.includes('RECENT SAVED')&&!quickText.includes('最近保存');const viewAllAtBottom=document.querySelector('.entry-recent-compact .entry-recent-view-all')===document.querySelector('.entry-recent-compact')?.lastElementChild;
navigate('training');await wait(80);const trainingText=document.querySelector('.training-theme-page')?.innerText||'';
setUiLanguage('en');navigate('home');await wait(80);const englishHomeText=document.querySelector('.home-page')?.innerText||'';const englishGreeting=petGreeting;
navigate('quick');await wait(100);const englishQuickText=document.querySelector('.entry-page')?.innerText||'',englishEntryViewLabel=document.querySelector('.entry-recent-compact .entry-recent-view-all')?.textContent.trim()||'',englishHistoryHeader=document.querySelector('.entry-recent-compact .rail-head')?.innerText||'';const englishEntryHistory=englishEntryViewLabel==='View all →'&&!englishHistoryHeader.includes('RECENT SAVED');
navigate('training');await wait(100);document.querySelector('[data-training-theme="theme:push"]')?.click();await wait(80);const englishThemeChinese=[...document.querySelectorAll('.theme-cn')].map(node=>node.textContent.trim()),englishThemeNames=[...document.querySelectorAll('.theme-en')].map(node=>node.textContent.trim()),themeEnglishFonts=fontPair('.body-theme-control.is-active .theme-cn'),themeEnglishInactiveFonts=fontPair('.body-theme-control:not(.is-active) .theme-cn');const themeFontHierarchy=themeChineseFonts[0]>themeChineseFonts[1]&&themeDetailChineseFonts[0]>themeDetailChineseFonts[1]&&themeDetailChineseInactiveFonts[0]>themeDetailChineseInactiveFonts[1]&&themeEnglishFonts[1]>themeEnglishFonts[0]&&themeEnglishInactiveFonts[1]>themeEnglishInactiveFonts[0];
const englishButtons=englishHomeText.includes('Log today')&&englishHomeText.includes('Movement archive');
const englishEntrySupport=englishQuickText.includes('Today’s Training Log')&&englishQuickText.includes('LLM Entry Template');
const themeBilingual=themeLabels.includes('推')&&themeEnglishLabels.includes('PUSH');
const themeEnglishSelected=englishThemeChinese.includes('推')&&englishThemeNames.includes('PUSH');
setUiLanguage('zh');navigate('home');await wait(80);const chinesePetRegions=window.__fitnessLedgerGuardianBodyRegions||[];const chinesePetLabels=chinesePetRegions.length===2&&chinesePetRegions.every(item=>item.themeId&&item.key===item.themeId&&String(item.label).length>0);const chinesePetGreeting=/早上好|下午好|晚上好/.test(petGreeting);
navigate('body');await wait(100);document.querySelector('[data-open-weight-average]')?.click();await wait(20);const weightDialog=document.querySelector('#weight-average-dialog'),weightDialogChinese=weightDialog?.querySelector('h2')?.textContent.trim()==='七日体重均值对比',weightDialogFrosted=(getComputedStyle(weightDialog?.querySelector('form')).backdropFilter||'').includes('blur');weightDialog?.close();setUiLanguage('en');navigate('body');await wait(100);document.querySelector('[data-open-weight-average]')?.click();await wait(20);const weightDialogEnglish=document.querySelector('#weight-average-dialog')?.querySelector('h2')?.textContent.trim()==='Seven-day average comparison'&&document.querySelector('#weight-average-result')?.textContent.includes('Change');document.querySelector('#weight-average-dialog')?.close();setUiLanguage('zh');
navigate('tools',{});await wait(160);document.querySelector('[data-ui-language-toggle]')?.click();await wait(160);const toolsLanguageToggleWorks=document.documentElement.dataset.flUiLanguage==='en'&&!/[\u3400-\u9fff]/.test((document.querySelector('main')?.innerText||'').replace(document.querySelector('[data-ui-language-toggle]')?.textContent||'', ''));setUiLanguage('zh');
navigate('tools',{panel:'sync'});await wait(120);setUiLanguage('en');navigate('tools',{panel:'sync'});await wait(220);const cloud=document.querySelector('.cloud-sync-business'),cloudText=cloud?.innerText||'';const cloudEnglishComplete=!/[\u3400-\u9fff]/.test(cloudText);
navigate('tools',{});await wait(180);const cjkText=scope=>{const walker=document.createTreeWalker(scope,NodeFilter.SHOW_TEXT),nodes=[];let node;while(node=walker.nextNode())if(/[\u3400-\u9fff]/.test(node.nodeValue||''))nodes.push(node.nodeValue.trim());return nodes};const interfaceCjk=scope=>{const walker=document.createTreeWalker(scope,NodeFilter.SHOW_TEXT),nodes=[];let node;while(node=walker.nextNode()){const parent=node.parentElement;if(parent&&!parent.closest('pre,textarea,code,[data-user-content],.phone-inbox-item strong')&&/[\u3400-\u9fff]/.test(node.nodeValue||''))nodes.push(node.nodeValue.trim())}return nodes};const languageToggleText=document.querySelector('[data-ui-language-toggle]')?.textContent.trim()||'';const toolsOverviewCjk=cjkText(document.querySelector('main')).filter(text=>text!==languageToggleText);const toolsOverviewEnglishComplete=toolsOverviewCjk.length===0;const dataModulesEntryPresent=Boolean(document.querySelector('.dm-tools-entry'));document.querySelector('.dm-tools-entry')?.click();await wait(160);window.__fitnessLedgerFormalMirrorBridge?.navigate('tools',{panel:'data-modules'});await wait(1000);const dataModulesEnglishComplete=Boolean(document.querySelector('.dm-management-page'))&&cjkText(document.querySelector('main')).length===0;const dataModulesRoute=window.__fitnessLedgerFormalMirrorBridge?.currentRoute?.(),dataModulesPanel=dataModulesRoute?.params?.get('panel')||'';document.querySelector('[data-dm-new-module]')?.click();await wait(120);const dataModuleFormCjk=cjkText(document.querySelector('#overlay-root'));const dataModuleFormEnglishComplete=Boolean(document.querySelector('#overlay-root .dm-modal'))&&dataModuleFormCjk.length===0;document.querySelector('#overlay-root [data-close]')?.click();await wait(40);navigate('tools',{});await wait(140);
state.phoneInbox={status:'ready',items:[{_id:'test-phone-item',received_at:0,text:'今日训练：推举 3 组'}],error:'',notice:'',busy:false,cached:false};renderPhoneInboxModal();const phoneInboxEnglishComplete=interfaceCjk(document.querySelector('#overlay-root')).length===0&&document.querySelector('#overlay-root .phone-inbox-item pre')?.textContent.includes('今日训练');const inboxSyncError=new Error('offline');inboxSyncError.code='PHONE_INBOX_SYNC_FAILED';inboxSyncError.localItems=[{_id:'cached-phone-item',received_at:0,text:'缓存训练内容'}];state.phoneInboxClient={listRecent:async()=>{throw inboxSyncError}};state.phoneInbox={status:'ready',items:[],error:'',notice:'',busy:false,cached:false};await refreshPhoneDailyRecords();const phoneInboxCachedSyncEnglishBeforeToggle=state.phoneInbox.cached&&interfaceCjk(document.querySelector('#overlay-root')).length===0&&(document.querySelector('#overlay-root')?.innerText||'').includes('Cloud sync failed (PHONE_INBOX_SYNC_FAILED)');setUiLanguage('zh');renderPhoneInboxModal();const phoneInboxCachedSyncChinese=(document.querySelector('#overlay-root')?.innerText||'').includes('云端同步失败')&&!(document.querySelector('#overlay-root')?.innerText||'').includes('Cloud sync failed');setUiLanguage('en');renderPhoneInboxModal();const phoneInboxCachedSyncEnglishAfterToggle=interfaceCjk(document.querySelector('#overlay-root')).length===0&&(document.querySelector('#overlay-root')?.innerText||'').includes('Cloud sync failed (PHONE_INBOX_SYNC_FAILED)'),phoneInboxCachedSyncEnglishComplete=phoneInboxCachedSyncEnglishBeforeToggle&&phoneInboxCachedSyncEnglishAfterToggle;state.phoneInboxClient=null;state.phoneInbox={status:'auth',items:[],error:phoneInboxError({code:'PHONE_INBOX_ACCOUNT_REQUIRED'}),notice:'',busy:false,cached:false};renderPhoneInboxModal();const phoneInboxAuthCjkNow=interfaceCjk(document.querySelector('#overlay-root')),phoneInboxAuthEnglishComplete=Boolean(document.querySelector('#overlay-root .phone-inbox-login'))&&phoneInboxAuthCjkNow.length===0;state.phoneInbox={status:'ready',items:[{_id:'test-phone-item',received_at:0,text:'删除确认保留用户原文'}],error:'',notice:'',busy:false,cached:false};confirmPhoneInboxDelete('test-phone-item');const phoneInboxDeleteEnglishComplete=interfaceCjk(document.querySelector('#overlay-root')).length===0&&document.querySelector('#overlay-root .phone-inbox-item pre')?.textContent.includes('删除确认保留用户原文');await openDataModuleLlmTemplate();const llmTemplateEnglishComplete=Boolean(document.querySelector('#overlay-root .entry-template-prompt'));await openAnalysisLlmInitializationPrompt();const analysisPromptEnglishComplete=Boolean(document.querySelector('#overlay-root .entry-template-prompt'));document.querySelector('#overlay-root').innerHTML='';
navigate('tools',{panel:'health'});await wait(180);const dataCheckMain=document.querySelector('main'),dataCheckText=(dataCheckMain?.innerText||'')+' '+(document.querySelector('#overlay-root')?.innerText||'');const dataCheckEnglishComplete=!/[\u3400-\u9fff]/.test(dataCheckText);const dataCheckCjk=cjkText(document.querySelector('#overlay-root')),dataCheckMainCjk=cjkText(dataCheckMain);
navigate('tools',{panel:'export'});await wait(160);const exportText=document.querySelector('.analysis-export-page')?.innerText||'';const exportCopyEnglish=exportText.includes('Which change do you want to understand?')&&!exportText.includes('想看清哪一段变化');const exportEnglishComplete=cjkText(document.querySelector('main')).length===0;
navigate('dictionary');await wait(140);const dictionaryCjk=cjkText(document.querySelector('main'));const dictionaryEnglishComplete=dictionaryCjk.length===0;
navigate('tools',{});await wait(140);document.querySelector('[data-session-themes-tool]')?.click();await wait(120);const themeManagerText=document.querySelector('#overlay-root')?.innerText||'';const themeManagerCjk=cjkText(document.querySelector('#overlay-root'));const themeManagerEnglishComplete=themeManagerCjk.length>0?false:Boolean(document.querySelector('#overlay-root .modal'))&&!/[\u3400-\u9fff]/.test(themeManagerText);document.querySelector('#overlay-root [data-close]')?.click();await wait(30);
navigate('dictionary');await wait(100);document.querySelector('[data-movement-categories-tool]')?.click();await wait(120);const movementManagerText=document.querySelector('#overlay-root')?.innerText||'';const movementManagerEnglishComplete=Boolean(movementManagerText)&&!/[\u3400-\u9fff]/.test(movementManagerText);
const result={themeLabels,themeEnglishLabels,themeBilingual,themeEnglishSelected,themeFontHierarchy,themeChineseFonts,themeDetailChineseFonts,themeDetailChineseInactiveFonts,themeEnglishFonts,themeEnglishInactiveFonts,themeCardStates,themeLanguage:document.documentElement.dataset.flUiLanguage,themeCardClass:document.querySelector('.body-theme-control')?.className,recentHistoryCorrect,viewAllAtBottom,englishEntryHistory,weightDialogChinese,weightDialogEnglish,weightDialogFrosted,switchCount:switches.length,switchesInRail,switchesHidden,syncOutcome:syncOutcome?.status||null,autoSyncStatusReads,homeBilingual:homeText.includes('健身记录')&&homeText.includes('记录今天')&&homeText.includes('查看动作档案'),quickBilingual:quickText.includes('Write the day.')&&quickText.includes('开始整理')&&quickText.includes('撤销上次保存'),trainingChinese:trainingText.includes('训练记录')&&trainingText.includes('最新训练在前'),englishButtons,englishEntrySupport,chinesePetLabels,chinesePetGreeting,phoneInboxEnglishComplete,phoneInboxCachedSyncEnglishComplete,phoneInboxAuthEnglishComplete,phoneInboxDeleteEnglishComplete,llmTemplateEnglishComplete,analysisPromptEnglishComplete,cloudBusiness:Boolean(cloud),cloudHasUserStatus:Boolean(cloud?.querySelector('.cloud-sync-user-grid')),cloudHidesRoute:Boolean(!cloud?.querySelector('.admin-route-track')&&!cloud?.querySelector('.admin-verification-panel')),cloudAdvancedClosed:Boolean(cloud?.querySelector('.cloud-sync-advanced:not([open])')),cloudEnglishComplete,toolsOverviewEnglishComplete,toolsLanguageToggleWorks,dataCheckEnglishComplete,exportCopyEnglish,exportEnglishComplete,dictionaryEnglishComplete,themeManagerEnglishComplete,movementManagerEnglishComplete,dataModulesEntryPresent,dataModulesEnglishComplete,dataModuleFormEnglishComplete,dataModuleFormCjk,dataModulesPanel};
const report=document.createElement('div');report.id='web-session-effects-report';report.dataset.value=encodeURIComponent(JSON.stringify(result));document.body.appendChild(report);
"""
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-web-effects-") as temp:
        page = Path(temp) / "index.html"
        shutil.copy2(PROJECT / "web_desktop/frontend/styles.css", page.parent / "styles.css")
        shutil.copy2(PROJECT / "web_desktop/frontend/final-pass.css", page.parent / "final-pass.css")
        shutil.copy2(PROJECT / "web_desktop/frontend/formal-mirror-data-modules.js", page.parent / "formal-mirror-data-modules.js")
        shutil.copy2(PROJECT / "web_desktop/frontend/formal-mirror-data-modules.css", page.parent / "formal-mirror-data-modules.css")
        shutil.copy2(PROJECT / "web_desktop/frontend/formal-mirror-review-hub.css", page.parent / "formal-mirror-review-hub.css")
        page.write_text(index.replace(script, f'<script type="module">\n{harness}\n{app}\n{assertions}\n</script>'), encoding="utf-8")
        browser_run = subprocess.run([str(edge), "--headless=new", "--disable-gpu", "--allow-file-access-from-files", "--virtual-time-budget=6000", "--dump-dom", page.as_uri()], check=True, capture_output=True, text=True, encoding="utf-8", timeout=25)
        output = browser_run.stdout
    match = re.search(r'id="web-session-effects-report" data-value="([^"]+)"', output)
    assert match, f"Web effects report was not rendered: {output[-1200:]}\n{browser_run.stderr}"
    result = json.loads(unquote(match.group(1)))
    assert "runtimeError" not in result, result
    assert "推" in result["themeLabels"] and "PUSH" in result["themeEnglishLabels"] and result["themeBilingual"] is True and result["themeEnglishSelected"] is True and result["themeFontHierarchy"], result
    assert result["recentHistoryCorrect"] and result["viewAllAtBottom"] and result["englishEntryHistory"], result
    assert result["weightDialogChinese"] and result["weightDialogEnglish"] and result["weightDialogFrosted"], result
    assert result["dataModulesPanel"] == "data-modules", result
    assert result["switchCount"] == 0 and result["switchesHidden"], result
    assert result["syncOutcome"] is None and result["autoSyncStatusReads"] == 1, result
    assert all(result[key] is True for key in ("homeBilingual", "quickBilingual", "trainingChinese", "englishButtons", "englishEntrySupport", "chinesePetLabels", "chinesePetGreeting", "phoneInboxEnglishComplete", "phoneInboxCachedSyncEnglishComplete", "phoneInboxAuthEnglishComplete", "phoneInboxDeleteEnglishComplete", "llmTemplateEnglishComplete", "analysisPromptEnglishComplete", "cloudBusiness", "cloudHasUserStatus", "cloudHidesRoute", "cloudAdvancedClosed", "cloudEnglishComplete", "toolsOverviewEnglishComplete", "toolsLanguageToggleWorks", "dataCheckEnglishComplete", "exportCopyEnglish", "exportEnglishComplete", "dictionaryEnglishComplete", "themeManagerEnglishComplete", "movementManagerEnglishComplete", "dataModulesEntryPresent", "dataModulesEnglishComplete", "dataModuleFormEnglishComplete")), f"{result}\n{browser_run.stderr}"


def main() -> None:
    app = (PROJECT / "web_desktop/frontend/app.js").read_text(encoding="utf-8")
    pet = (PROJECT / "web_desktop/frontend/tools-css3d-panels.js").read_text(encoding="utf-8")
    css = (PROJECT / "web_desktop/frontend/final-pass.css").read_text(encoding="utf-8")
    index = (PROJECT / "web_desktop/frontend/index.html").read_text(encoding="utf-8")
    mirror = (PROJECT / "web_desktop/frontend/formal-mirror-data-modules.js").read_text(encoding="utf-8")

    active_ids = app.split("trainingThemeIds=function()", 1)[1].split("sessionThemeRows=function", 1)[0]
    assert "ids.push('__unthemed__')" not in active_ids
    assert "sessionThemeMembership(record).size===0" not in active_ids
    assert "data-web-effect=\"guardian\"" in app
    assert "data-web-effect=\"trophyCursor\"" in app
    assert "fitness-ledger.web-effect.guardian.v1" in app
    assert "fitness-ledger.web-effect.trophy-cursor.v1" in app
    assert "fitness-ledger-effects:change" in pet
    assert "data-fl-guardian-pet=\"off\"" in css
    assert "data-fl-trophy-cursor=\"off\"" in css
    assert "app.js?v=20260916-web-i18n-history-r10" in index
    assert "formal-mirror-data-modules.js?v=20260916-web-i18n-history-r10" in index
    assert "final-pass.css?v=20260916-web-i18n-history-r10" in index
    assert "搜索备注、饮食内容或日期…" in app
    assert "饮食摘要" in app
    assert "查看详情" in app
    assert "data-ui-language-toggle" in app
    assert "UI_LANGUAGE_PREF" in app
    assert ".collectiveos-dashboard{min-height:0!important;align-content:start!important}" in css
    assert "archive-title-cn" in app
    assert "tools-css3d-panels.js?v=20260916-web-i18n-history-r10" in app
    assert "搜索备注或日期…" in app
    assert "全部时间" in app
    assert "打开记录" in app
    assert "先记录。 <em>再整理。</em>" in app
    assert "Raw first. <em>Structure second.</em>" in app
    assert "按住 · 查看最近训练" in app
    assert "movement-group header p" not in app
    assert "shellLocaleObserver" not in app
    assert "document.documentElement.dataset.flUiLanguage==='en'" in mirror
    entry_aside = app.split("function compactEntryAside(){", 1)[1].split("\nquickPage=function()", 1)[0]
    assert "state.recent.filter(r=>!t.date||String(r.date||'')!==String(t.date)).slice(0,3)" in entry_aside
    assert "entry-recent-view-all" in entry_aside and "RECENT SAVED" not in entry_aside
    assert "Which change do you want to understand?" in app
    assert "Today’s Training Log" in app and "LLM Entry Template" in app
    browser_contract(app)
    print("FITNESS_LEDGER_WEB_SESSION_EFFECTS_OK")


if __name__ == "__main__":
    main()
