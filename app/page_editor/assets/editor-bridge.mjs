import {mountEditorPage} from './editor.bundle.js';

const root=document.querySelector('[data-editor-page]');
const initial=JSON.parse(document.getElementById('editor-initial-state').textContent);
const basis={protocol:'page-editor-v1',generation:initial.generation,
  baseRevisionId:initial.baseRevisionId,editingFrom:'current',draftBasis:null,stageId:null};
const prefix=`/manage/pages/${encodeURIComponent(initial.pageId)}/edit/`;
let csrf=document.querySelector('[name=csrfmiddlewaretoken]').value;
let pending=null;
const fail=code=>Object.assign(new Error(code),{code});
const refusal=(code,status,saveOutcome)=>Object.assign(fail(code),{status,outcomeKnown:saveOutcome&&[400,401,403,404,408,409,411,413,415].includes(status)});
function changedIdentity(){
  pending=null;csrf='';
  for(const key of Object.keys(initial.values))delete initial.values[key];
  for(const field of initial.fields){field.rawHtml='';field.approvedHtml=null;}
  const script=document.getElementById('editor-initial-state');
  if(script)script.textContent='';
  throw fail('EDITOR_IDENTITY_CHANGED');
}

async function json(url,options={},saveOutcome=false){
  let response;
  try{response=await fetch(url,{credentials:'same-origin',cache:'no-store',redirect:'error',...options});}
  catch{throw fail('EDITOR_OUTCOME_UNKNOWN');}
  let value;
  try{value=await response.json();}catch{throw refusal(response.status===401?'EDITOR_SESSION_ENDED':'EDITOR_UNAVAILABLE',response.status,saveOutcome);}
  if(!response.ok)throw refusal(value&&typeof value.code==='string'?value.code:response.status===401?'EDITOR_SESSION_ENDED':'EDITOR_UNAVAILABLE',response.status,saveOutcome);
  return value;
}

async function session({refresh=false}={}){
  const identity=await json('/manage/session/');
  if(identity.authenticated!==true||identity.userId!==initial.actorId)changedIdentity();
  const value=await json(prefix+'state/');
  if(value.userId!==initial.actorId)changedIdentity();
  if(!Number.isSafeInteger(value.generation)||typeof value.csrfToken!=='string'||!Array.isArray(value.fields))throw fail('EDITOR_UNAVAILABLE');
  if(!refresh&&value.generation!==basis.generation)throw fail('EDITOR_SESSION_ENDED');
  if(Object.keys(initial.values).some(field=>!value.fields.includes(field)))throw fail('EDITOR_FIELDS_FORBIDDEN');
  csrf=value.csrfToken;
  if(refresh)basis.generation=value.generation;
  return value;
}

function post(action,body){
  return json(prefix+action+'/',{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':csrf},body},action==='save');
}

async function check(changes){
  const state=await session();
  if(state.baseRevisionId!==basis.baseRevisionId)throw fail('EDITOR_BASE_CONFLICT');
  return post('check',JSON.stringify({...basis,changes}));
}

async function save({changes,checkReceipt,operationId}){
  await session(); // Identity/current permissions, but a replay may have an old base.
  if(pending&&pending.operationId!==operationId)throw fail('EDITOR_OUTCOME_UNKNOWN');
  if(!pending)pending={operationId,body:JSON.stringify({...basis,changes,checkReceipt,operationId}),unknown:false};
  let result;
  try{result=await post('save',pending.body);}catch(error){
    if(error.outcomeKnown&&!pending.unknown)pending=null;
    else{pending.unknown=true;error.outcomeKnown=false;}
    throw error;
  }
  const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/u;
  if(!result||typeof result!=='object'||Array.isArray(result)
      ||JSON.stringify(Object.keys(result).sort())!==JSON.stringify(['action','gone','operation_id','replay','result_code','result_id'])
      ||result.operation_id!==operationId||typeof result.replay!=='boolean'||typeof result.gone!=='boolean'
      ||typeof result.result_id!=='string'||!uuid.test(result.result_id)
      ||result.action!==(initial.owner?'commit_owner':'commit_employee')||result.result_code!=='applied'){
    pending.unknown=true;throw fail('EDITOR_OUTCOME_UNKNOWN');
  }
  if(!result.gone&&typeof result.result_id==='string')basis.baseRevisionId=result.result_id;
  pending=null;
  return result;
}

const link=document.querySelector('[data-editor-stylesheet]');
if(!link.sheet)await new Promise((resolve,reject)=>{
  const timer=setTimeout(()=>reject(fail('EDITOR_UNAVAILABLE')),5000);
  link.addEventListener('load',()=>{clearTimeout(timer);resolve();},{once:true});
  link.addEventListener('error',()=>{clearTimeout(timer);reject(fail('EDITOR_UNAVAILABLE'));},{once:true});
});
mountEditorPage({root,initialState:initial,styleSheet:link.sheet,check,save,
  draft:async()=>{throw fail('EDITOR_CAPABILITY_UNAVAILABLE');},
  reauth:async()=>{const result=await session({refresh:true});return {...result,sameUser:true};}});
