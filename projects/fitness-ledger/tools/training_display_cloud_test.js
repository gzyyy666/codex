/* Test the actual read-only CloudBase projections with anonymous data. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const sessions = [
  {id:'s1',Date:'2099-01-01',session_theme_id:'custom',Split:'Travel Circuit',movement_items:[{movement_id:'m1',display_name:'Recorded movement',order:1,sets:[{weight:10,reps:8,sets:3}],exclude_from_progress:true}]},
  {id:'s2',Date:'2099-01-01',Split:'出差训练',movement_items:[]}
];
const rows = {fl_training_sessions:sessions,fl_movement_history:[{movement_id:'m2',date:'2099-01-01',training_session_id:'s2',order:1,sets:[],exclude_from_progress:true}],fl_movements:[{movement_id:'m1',display_name:'Recorded movement'},{movement_id:'m2',display_name:'History-only movement'}],fl_meta:[{training_organization:{session_themes:[{theme_id:'old',display_name:'Old theme',active:false}],movement_categories:[]}}]};
const db = {command:{in:values=>({in:values})},collection(name){
  let start=0,limit=50,where={};
  const query={orderBy(){return query},skip(value){start=value;return query},limit(value){limit=value;return query},where(value){where=value;return query},async get(){return {data:(rows[name]||[]).filter(item=>Object.entries(where).every(([key,value])=>value && value.in ? value.in.includes(item[key]) : item[key]===value)).slice(start,start+limit)}}};
  return query;
}};
const context = {exports:{},require:()=>({init(){},database:()=>db}),console,process:{env:{}}};
vm.createContext(context);
const source = fs.readFileSync(path.join(root,'mini_program/cloudfunctions/ledgerWebRead/index.js'),'utf8');
vm.runInContext(source+'\nexports.test={themeNames,trainingOrganizationPayload,getTrainingDayDetail};',context);
const api = context.exports.test;
const plain = value=>JSON.parse(JSON.stringify(value));
(async()=>{
  const organization=await api.trainingOrganizationPayload(sessions);
  assert.equal(organization.session_themes[0].active,false,'inactive definitions retained for history');
  assert.deepEqual(plain(api.themeNames(sessions[0],organization)),['Travel Circuit']);
  assert.deepEqual(plain(api.themeNames({theme_names:['Saved name']},{})),['Saved name']);
  assert.deepEqual(plain(api.themeNames({session_theme_ids:['old','new'],theme_names:['Old theme','New Custom']},organization)),['Old theme','New Custom']);
  assert.deepEqual(plain(api.themeNames({session_theme_ids:['a','b'],session_theme_name:'Old joined snapshot'},{session_themes:[{theme_id:'a',display_name:'A'},{theme_id:'b',display_name:'B'}]})),['A','B']);
  const first=await api.getTrainingDayDetail('s1','2099-01-01',organization);
  assert.equal(first.session.id,'s1');
  assert.equal(first.movements.length,1);
  assert.equal(first.movements[0].exclude_from_progress,true);
  assert.deepEqual(plain(first.session.theme_names),['Travel Circuit']);
  const second=await api.getTrainingDayDetail('s2','2099-01-01',organization);
  assert.equal(second.session.id,'s2');
  assert.equal(second.movements[0].movement_id,'m2');
  assert.equal(second.movements[0].exclude_from_progress,true,'history fallback retains excluded status');
  assert.deepEqual(plain(second.session.theme_names),['出差训练']);
  rows.fl_movement_history.push({movement_id:'m1',date:'2099-01-01',sets:[]});
  assert.equal((await api.getTrainingDayDetail('s2','2099-01-01',organization)).movements.length,1,'unscoped legacy history must not merge same-day sibling sessions');
  assert.equal((await api.getTrainingDayDetail('unknown','2099-01-01',organization)).session,null,'unknown id must not select same-day sibling');
  console.log('TRAINING_DISPLAY_CLOUD_OK: exact session, saved names, exclusions and history fallback');
})().catch(error=>{console.error(error);process.exitCode=1});
