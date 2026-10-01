const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const refresh = fs.readFileSync(path.join(__dirname, '../static/app.js'), 'utf8')
  .split('\n').find(line => line.startsWith('async function refreshState('));
async function reopen(confirmed, selectedRoom = null) {
  const data = {projects:{p:{floor_plans:['a'], rooms:[
    {id:'unreviewed',plan_id:'a',floor:'Needs floor assignment'},
    {id:'reviewed',plan_id:'a',floor:'Selected floor'}]}},
    assets:{a:{id:'a',project_id:'p',construction_selection:{confirmed,floor:'Selected floor'}}},jobs:{}};
  const c = {pid:'p',rid:selectedRoom,planId:null,state:null,pollBusy:false,
    lastSignature:'',drawMode:false,modalType:'',window:{},
    document:{activeElement:{tagName:'BODY'}}, localStorage:{setItem(){}},
    fetch:async()=>({ok:true,json:async()=>data}),renderShell(){},renderMain(){},updateJobs(){},
    toast(message){throw Error(message)}};
  c.P=()=>c.state?.projects[c.pid]; c.R=()=>c.P()?.rooms.find(r=>r.id===c.rid);
  c.A=id=>c.state?.assets[id];
  vm.createContext(c);vm.runInContext(refresh,c);await c.refreshState(true);return c;
}
(async()=>{
  assert.equal((await reopen(true)).rid,'reviewed');
  assert.equal((await reopen(false)).rid,'unreviewed');
  assert.equal((await reopen(true,'unreviewed')).rid,'unreviewed');
  console.log('Reopening defaults to the confirmed construction floor and preserves explicit selections');
})().catch(e=>{console.error(e);process.exitCode=1});
