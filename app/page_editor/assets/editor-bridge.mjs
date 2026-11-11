import {mountEditorPage} from './editor.bundle.js';
import {mountHomeProfileEditor} from './home-profile-editor.mjs';

const root=document.querySelector('[data-editor-page]');
const initial=JSON.parse(document.getElementById('editor-initial-state').textContent);
const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/u;
function contextNow(){return Object.fromEntries(['pageId','generation','baseRevisionId','editingFrom','draftBasis','stageId','rebase','targetCurrentId'].map(key=>[key,initial[key]??null]));}
function basis(context){return {protocol:'page-editor-v1',generation:context.generation,
  baseRevisionId:context.baseRevisionId,editingFrom:context.editingFrom,draftBasis:context.draftBasis,stageId:context.stageId};}
function selector(context){
  const query=new URLSearchParams();
  if(context.editingFrom==='owner-draft'){
    if(!context.draftBasis||!uuid.test(context.draftBasis.id)||!Number.isSafeInteger(context.draftBasis.revision)||context.draftBasis.revision<=0)throw fail('EDITOR_CONTEXT_CHANGED');
    query.set('source','owner-draft');query.set('draftId',context.draftBasis.id);query.set('draftRevision',String(context.draftBasis.revision));
    if(context.rebase===true){if(!uuid.test(context.targetCurrentId||''))throw fail('EDITOR_CONTEXT_CHANGED');query.set('rebase','1');query.set('targetCurrentId',context.targetCurrentId);}
  }else if(context.editingFrom==='restore-stage'){
    if(!uuid.test(context.stageId||''))throw fail('EDITOR_CONTEXT_CHANGED');query.set('source','restore-stage');query.set('stageId',context.stageId);
  }else if(context.editingFrom!=='current')throw fail('EDITOR_CONTEXT_CHANGED');
  return query.size?'?'+query.toString():'';
}
const prefix=`/manage/pages/${encodeURIComponent(initial.pageId)}/edit/`;
let csrf=document.querySelector('[name=csrfmiddlewaretoken]').value;
let pending=null;
const fail=code=>Object.assign(new Error(code),{code});
const refusal=(code,status,saveOutcome)=>Object.assign(fail(code),{status,outcomeKnown:saveOutcome&&[400,401,403,404,408,409,411,413,415].includes(status)});
function changedIdentity(){
  pending=null;csrf='';
  for(const key of Object.keys(initial.values))delete initial.values[key];
  for(const field of initial.fields){field.rawHtml='';field.approvedHtml=null;}
  if(initial.embeddedMedia)for(const field of Object.keys(initial.embeddedMedia))initial.embeddedMedia[field]=[];
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
  if(!refresh&&value.generation!==initial.generation)throw fail('EDITOR_SESSION_ENDED');
  if(Object.keys(initial.values).some(field=>!value.fields.includes(field)))throw fail('EDITOR_FIELDS_FORBIDDEN');
  csrf=value.csrfToken;
  if(refresh)initial.generation=value.generation;
  return value;
}

function post(action,body,query='',write=false){
  if(!['check','save','draft','draft/cancel','embedded/issue'].includes(action))throw fail('EDITOR_CONTEXT_CHANGED');
  return json(prefix+action+'/'+query,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':csrf},body},write);
}

async function check(changes){
  const context=structuredClone(contextNow()),current=await session();
  const state=context.editingFrom==='current'?current:await json(prefix+'state/'+selector(context));
  if(state.baseRevisionId!==context.baseRevisionId)throw fail('EDITOR_BASE_CONFLICT');
  return post('check',JSON.stringify({...basis(context),changes}),selector(context));
}

function exactKeys(value,keys){return value&&typeof value==='object'&&!Array.isArray(value)&&JSON.stringify(Object.keys(value).sort())===JSON.stringify([...keys].sort());}
function verifyResult(result,intent){
  const isDraft=intent.action==='draft',isCancel=intent.action==='draft/cancel';
  const keys=['action','gone','operation_id','replay','result_code','result_id',...(isDraft?['draftBasis','baseRevisionId']:[])];
  const expectedAction=isDraft?(intent.context.rebase===true?'rebase_draft':'save_draft'):isCancel?'cancel_draft':initial.owner?'commit_owner':'commit_employee';
  const expectedCode=isCancel?'released':isDraft?'applied':intent.context.editingFrom==='restore-stage'?'restored':'applied';
  if(!exactKeys(result,keys)||result.operation_id!==intent.operationId||typeof result.replay!=='boolean'||typeof result.gone!=='boolean'
      ||!uuid.test(result.result_id||'')||result.action!==expectedAction||result.result_code!==expectedCode)throw fail('EDITOR_OUTCOME_UNKNOWN');
  if(isCancel&&result.result_id!==intent.context.draftBasis.id)throw fail('EDITOR_OUTCOME_UNKNOWN');
  if(isDraft&&(!exactKeys(result.draftBasis,['id','revision'])||result.draftBasis.id!==result.result_id
      ||result.draftBasis.revision!==(intent.context.draftBasis?intent.context.draftBasis.revision+1:1)
      ||!uuid.test(result.baseRevisionId||'')||result.baseRevisionId!==(intent.context.rebase===true?intent.context.targetCurrentId:intent.context.baseRevisionId)))throw fail('EDITOR_OUTCOME_UNKNOWN');
}
function acknowledge(result,intent){
  if(intent.action==='draft'&&!result.gone){
    Object.assign(initial,{baseRevisionId:result.baseRevisionId,editingFrom:'owner-draft',draftBasis:structuredClone(result.draftBasis),stageId:null,rebase:false,targetCurrentId:null});
  }else if(intent.action==='save'&&!result.gone){
    Object.assign(initial,{baseRevisionId:result.result_id,currentRevisionId:result.result_id,editingFrom:'current',draftBasis:null,stageId:null,rebase:false,targetCurrentId:null});
  }else{initial.checkReceipt=null;return;}
  initial.checkReceipt=null;history.replaceState(null,'',prefix+selector(contextNow()));
  const script=document.getElementById('editor-initial-state');if(script)script.textContent='';
}
async function transmit(action,{changes,checkReceipt,operationId,context}){
  await session(); // Identity/current permissions, but a replay may have an old base.
  const frozen=structuredClone(context);if(frozen.pageId!==initial.pageId)throw fail('EDITOR_CONTEXT_CHANGED');
  const query=selector(frozen),body=JSON.stringify({...basis(frozen),changes,checkReceipt,operationId,...(action==='draft'?{rebase:frozen.rebase===true}:{})});
  if(pending&&(pending.operationId!==operationId||pending.action!==action||pending.body!==body||pending.query!==query))throw fail('EDITOR_OUTCOME_UNKNOWN');
  if(!pending)pending={action,operationId,context:frozen,body,query,unknown:false};
  let result;
  try{result=await post(pending.action,pending.body,pending.query,true);verifyResult(result,pending);}catch(error){
    if(error?.code==='EDITOR_IDENTITY_CHANGED')throw error;
    if(error.outcomeKnown&&!pending.unknown)pending=null;
    else{pending.unknown=true;error.outcomeKnown=false;}
    throw error;
  }
  const completed=pending;pending=null;acknowledge(result,completed);return result;
}
async function cancel({operationId,context}){
  await session();if(!context.draftBasis)throw fail('EDITOR_CONTEXT_CHANGED');
  const body=JSON.stringify({generation:context.generation,draftId:context.draftBasis.id,draftRevision:context.draftBasis.revision,operationId});
  if(pending&&(pending.operationId!==operationId||pending.action!=='draft/cancel'||pending.body!==body))throw fail('EDITOR_OUTCOME_UNKNOWN');
  if(!pending)pending={action:'draft/cancel',operationId,context:structuredClone(context),body,query:'',unknown:false};
  let result;try{result=await post('draft/cancel',pending.body,'',true);verifyResult(result,pending);}
  catch(error){if(error?.code==='EDITOR_IDENTITY_CHANGED')throw error;
    if(error.outcomeKnown&&!pending.unknown)pending=null;else{pending.unknown=true;error.outcomeKnown=false;}throw error;}
  // Do not replace the user's unsaved content with current after cancellation.
  pending=null;initial.checkReceipt=null;initial.draftCancelled=true;return result;
}

const link=document.querySelector('[data-editor-stylesheet]');
if(!link.sheet)await new Promise((resolve,reject)=>{
  const timer=setTimeout(()=>reject(fail('EDITOR_UNAVAILABLE')),5000);
  link.addEventListener('load',()=>{clearTimeout(timer);resolve();},{once:true});
  link.addEventListener('error',()=>{clearTimeout(timer);reject(fail('EDITOR_UNAVAILABLE'));},{once:true});
});
const mounted=mountEditorPage({root,initialState:initial,styleSheet:link.sheet,check,save:args=>transmit('save',args),
  issueEmbedded:initial.owner?async value=>{
    const context=structuredClone(contextNow());await session();
    const result=await post('embedded/issue',JSON.stringify({generation:context.generation,baseRevisionId:context.baseRevisionId,...value}),selector(context));
    await session();return result;
  }:undefined,
  mediaSourceUrl:url=>new URL(url,location.origin).pathname+selector(contextNow()),
  listMedia:initial.owner?async({folder='',q='',after=null}={})=>{
    await session();
    const query=new URLSearchParams();if(folder)query.set('folder',folder);if(q)query.set('q',q);if(after)query.set('after',after);
    const result=await json(prefix+'media/'+(query.size?'?'+query.toString():''));
    await session();return result;
  }:undefined,
  draft:initial.owner&&initial.editingFrom!=='restore-stage'?args=>transmit('draft',args):undefined,
  cancelDraft:initial.owner?cancel:undefined,
  reauth:async()=>{const result=await session({refresh:true});return {...result,sameUser:true};}});
if(initial.owner&&Object.hasOwn(initial.values,'home_profile'))mountHomeProfileEditor({root,initial,
  invalidate:mounted.invalidate,searchSources:async q=>{await session();const query=new URLSearchParams({q});const result=await json(prefix+'sources/?'+query.toString());await session();return result;}});
