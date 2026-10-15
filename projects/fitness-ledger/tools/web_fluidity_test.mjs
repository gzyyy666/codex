import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const source=fs.readFileSync(new URL('../web_desktop/frontend/app.js',import.meta.url),'utf8');
const lines=source.split(/\r?\n/);
const named=prefix=>{const found=lines.filter(line=>line.startsWith(prefix));assert.equal(found.length,1,prefix);return found[0]};
const sandbox={state:{dictionary:[{movement_id:'a',display_name:'推',aliases:['ＰＲＥＳＳ']},{movement_id:'b',display_name:'肩部 推举',english_name:'Shoulder Press'}],movements:[]}};
vm.createContext(sandbox);
vm.runInContext([
  named('const normalizeTrainingText='),named('const movementDefinitions='),named('const movementNames='),
  named('let movementNameIndexSource='),named('function movementDefinitionForToken(')
].join('\n'),sandbox);
const match=token=>vm.runInContext(`movementDefinitionForToken(${JSON.stringify(token)})?.movement_id`,sandbox);
assert.equal(match('肩部 推举 20kg'),'b','longest contained name wins');
assert.equal(match('ＰＲＥＳＳ'),'a','NFKC aliases remain recognized');
assert.equal(match('unknown'),undefined);
sandbox.state.dictionary=[{movement_id:'c',display_name:'PRESS',aliases:['肩部 推举']}];
assert.equal(match('ＰＲＥＳＳ'),'c','dictionary refresh invalidates old candidates');
assert.equal(match('肩部 推举'),'c','renamed/merged aliases use the new definition');
sandbox.state.dictionary=[];sandbox.state.movements=[{movement_id:'fallback',english_name:'Press'}];
assert.equal(match('press'),'fallback','movement projection remains the fallback');

// A pending auxiliary service must not block primary route hydration.
let resolveSync,requests=[];
Object.assign(sandbox,{URLSearchParams,requestAnimationFrame:callback=>setTimeout(callback,0),window:{dispatchEvent(){},setTimeout},CustomEvent:function(){},updateSyncNav(){},publishGuardianBodyRegions(){},refreshVisibleBodyAfterHydration(){},api:path=>{requests.push(path);return path.includes('cloud-sync')?new Promise(resolve=>{resolveSync=resolve}):Promise.resolve([])}});
vm.runInContext([
 named('const WEB_STATE_ENDPOINTS='),named('const loadedWebSlots='),named('function webSlotsForRoute('),
 named('async function refreshWebState('),named('async function ensureWebSlots('),named('function primaryWebSlots('),
 named('async function ensureRouteData('),named('function loadRouteSupplement(')
].join('\n'),sandbox);
await vm.runInContext("ensureRouteData({view:'quick'})",sandbox);
assert.equal(requests.some(path=>path.includes('cloud-sync')),false);
vm.runInContext("loadRouteSupplement({view:'quick'})",sandbox);
await new Promise(resolve=>setTimeout(resolve,20));
assert.equal(typeof resolveSync,'function');
resolveSync({sync_status:'SYNCED'});
await new Promise(resolve=>setTimeout(resolve,0));
assert.equal(sandbox.state.syncStatus.sync_status,'SYNCED');
console.log('web_fluidity_test: PASS (matching refresh, aliases, fallback, nonblocking auxiliary hydration)');
