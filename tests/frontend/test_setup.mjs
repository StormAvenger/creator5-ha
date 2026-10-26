import assert from 'node:assert/strict';
import {pathToFileURL,fileURLToPath} from 'node:url';
// Import the pure workflow helpers without mounting a UI or contacting HA.
globalThis.HTMLElement = class {};
globalThis.customElements = {get: () => undefined, define: () => {}};
const {createDashboard,createAlerts} = await import(pathToFileURL(process.argv[2] ?? fileURLToPath(new URL('../../custom_components/creator5/frontend/setup.js', import.meta.url))));
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
console.log(`${cases} frontend workflow checks passed`);
