import assert from 'node:assert/strict';
import {pathToFileURL,fileURLToPath} from 'node:url';
// Import the pure workflow helpers without mounting a UI or contacting HA.
globalThis.HTMLElement = class {};
globalThis.customElements = {get: () => undefined, define: () => {}};
const {createDashboard,createAlerts,fileAction} = await import(pathToFileURL(process.argv[2] ?? fileURLToPath(new URL('../../custom_components/creator5/frontend/setup.js', import.meta.url))));
let cases = 0;
const input={entryId:'synthetic',title:'Printer',path:'printer-overview'};
function dashboardHarness(existing=[], failSave=false) {
  const calls=[];
  return {calls, async callWS(data) {
    calls.push(data);
    if(data.type==='creator5/dashboard_config') return {views:[{cards:[]}]};
    if(data.type==='lovelace/dashboards/list') return existing;
    if(data.type==='lovelace/config/save' && failSave) throw new Error('Save failed');
    return {id:'new'};
  }};
}
{
  const hass=dashboardHarness();
  assert.equal(await createDashboard(hass,input),'/printer-overview');
  assert.deepEqual(hass.calls.map(c=>c.type),['creator5/dashboard_config','lovelace/dashboards/list','lovelace/dashboards/create','lovelace/config/save']);
  cases++;
}
{
  const hass=dashboardHarness([{url_path:'printer-overview'}]);
  await assert.rejects(createDashboard(hass,input),/already exists/);
  assert.equal(hass.calls.length,2); cases++;
}
{
  const hass=dashboardHarness([],true);
  await assert.rejects(createDashboard(hass,input),/new empty dashboard/);
  assert(!hass.calls.some(c=>c.type.includes('delete'))); cases++;
}
for(const path of ['../config','x?token=1','x/#y','singleword','Upper-case']) {
  const hass=dashboardHarness();
  await assert.rejects(createDashboard(hass,{...input,path}),/dashboard address/);
  assert.equal(hass.calls.length,0); cases++;
}
for (const mode of ['missing','existing','denied','save-failed']) {
  const calls=[];
  const hass={async callWS(data){assert.equal(data.type,'creator5/alert_config');return {automation_id:'creator5_alerts_synthetic_unique',config:{actions:[]}};},async callApi(method,path,body){
    calls.push({method,path,body});
    if(method==='GET') {
      if(mode==='existing') return {};
      if(mode==='denied') throw {status_code:403};
      throw {status_code:404};
    }
    if(mode==='save-failed') throw new Error('Failed');
    return {};
  }};
  const action=createAlerts(hass,{entryId:'synthetic',target:'persistent_notification.create',kinds:['completed']});
  if(mode==='missing') {assert.equal(await action,'creator5_alerts_synthetic_unique');assert.equal(calls.length,2);}
  else if(mode==='existing') {await assert.rejects(action,/already exist/);assert.equal(calls.length,1);}
  else {await assert.rejects(action);assert.equal(calls.length,mode==='denied'?1:2);}
  assert(!calls.some(c=>c.method==='DELETE'));cases++;
}
// Confirmations never execute on a declined dialog or retry a failed action.
for (const action of ['start','cancel']) {
  for (const accepted of [false,true]) {
    const calls=[];
    const hass={async callWS(data){calls.push(data); return data.type==='creator5/file_prepare' ? {token:'one-use',message:'Confirm current job'} : {state:'printing'};}};
    const result=await fileAction(hass,{entryId:'synthetic',action,filename:'part.3mf'},message=>{assert.equal(message,'Confirm current job'); return accepted;});
    assert.equal(calls.length,accepted?2:1);
    if(accepted) assert.deepEqual(calls[1],{type:'creator5/file_execute',entry_id:'synthetic',token:'one-use'});
    else assert.equal(result,null);
    cases++;
  }
}
{
  let calls=0;
  const hass={async callWS(data){calls++;if(data.type==='creator5/file_prepare')return {token:'expired',message:'Confirm'};throw new Error('Confirmation expired');}};
  await assert.rejects(fileAction(hass,{entryId:'synthetic',action:'start',filename:'part.3mf'},()=>true),/expired/);
  assert.equal(calls,2); cases++;
}
for(const accepted of [false,true]) {
  const calls=[];
  const file=new File(['; sliced\nG28\n'],'part.gcode');
  const hass={async callWS(data){calls.push(data);assert.equal(data.type,'creator5/file_prepare');return {token:'single-upload',message:'Upload only?'};},async fetchWithAuth(path,options){
    calls.push({path,options}); assert.equal(options.method,'POST');
    assert.equal(options.headers['X-Creator5-Confirmation'],'single-upload');
    assert.equal(options.body.get('file').name,'part.gcode');
    return {ok:true,async json(){return {filename:'part-unique.gcode',state:'ready'};}};
  }};
  const result=await fileAction(hass,{entryId:'synthetic',action:'upload',filename:file.name,file},()=>accepted);
  assert.equal(calls.length,accepted?2:1);
  if(accepted) assert.equal(result.state,'ready');
  assert(!calls.some(c=>c.type==='creator5/file_execute')); cases++;
}
for(const size of [0,64*1024*1024+1]) {
  let calls=0;const hass={async callWS(){calls++;}};
  await assert.rejects(fileAction(hass,{entryId:'synthetic',action:'upload',file:{size}},()=>true),/64 MiB/);
  assert.equal(calls,0); cases++;
}
for(const showInSidebar of [undefined,false,true]) {
  const hass=dashboardHarness(); await createDashboard(hass,{...input,showInSidebar});
  assert.equal(hass.calls.find(c=>c.type==='lovelace/dashboards/create').show_in_sidebar,showInSidebar??false);cases++;
}
console.log(`${cases} frontend workflow checks passed`);
