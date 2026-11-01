const root=document.querySelector('[data-shared-editor]');
if(root){
  const input=root.querySelector('textarea'),status=root.querySelector('[data-editor-status]');
  const proposal=root.querySelector('[data-normalization]'),retry=root.querySelector('[data-retry-intent]');
  const uuidPattern=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
  let epoch=0,cleanEpoch=0,checked=null,busy=false,normalization=null,uncertain=null,basisUnavailable=false;
  const messages={
    SHARED_BUDGET_PROFILE_UNAVAILABLE:'Безопасный резерв места ещё проверяется. Ваш ввод остаётся в этой вкладке.',
    SHARED_HISTORY_COUNT_FULL:'Достигнут предел истории. Ваш ввод остаётся в этой вкладке.',
    SHARED_HISTORY_BYTES_FULL:'Недостаточно места для новой записи. Ваш ввод остаётся в этой вкладке.',
    SHARED_CHECK_RECEIPT_INVALID:'Проверка устарела. Проверьте содержимое ещё раз.',
    SHARED_NORMALIZATION_REQUIRED:'Перед сохранением проверьте нормализованный текст.',
    SHARED_CONTEXT_CONFLICT:'Основание изменилось. Ваш ввод остаётся здесь; откройте актуальный источник отдельно.',
    SHARED_INPUT_REJECTED:'HTML или основание не соответствуют требованиям. Ваш ввод остаётся здесь.',
    SHARED_MEDIA_UNAVAILABLE:'Изображение недоступно. Ваш ввод остаётся в этой вкладке.',
    SHARED_SESSION_ENDED:'Сессия завершена. Войдите снова и проверьте историю; ваш ввод остаётся здесь.',
    SHARED_BUSY:'Другая операция ещё выполняется. Ваш ввод остаётся в этой вкладке.'
  };
  const unknownMessage='Результат прежней отправки пока неизвестен. Повторите проверку её результата отдельной кнопкой. Новый ввод остаётся в этой вкладке.';
  const exact=(value,keys)=>value!==null&&typeof value==='object'&&!Array.isArray(value)&&Object.keys(value).sort().join()===keys.slice().sort().join();
  const validId=value=>typeof value==='string'&&uuidPattern.test(value);
  const fail=()=>{throw new Error('SHARED_RESPONSE_UNCONFIRMED');};
  const invalidate=()=>{checked=null;normalization=null;proposal.hidden=true;};
  function operationId(){
    const bytes=crypto.getRandomValues(new Uint8Array(16));bytes[6]=(bytes[6]&15)|64;bytes[8]=(bytes[8]&63)|128;
    const hex=Array.from(bytes,value=>value.toString(16).padStart(2,'0')).join('');
    return [hex.slice(0,8),hex.slice(8,12),hex.slice(12,16),hex.slice(16,20),hex.slice(20)].join('-');
  }
  function dto(){return {protocol:'shared-editor-v1',generation:Number(root.dataset.generation),baseRevisionId:root.dataset.base||null,sourceMode:root.dataset.sourceMode,draftBasis:root.dataset.draftId?{id:root.dataset.draftId,revision:Number(root.dataset.draftRevision)}:null,stageId:root.dataset.stageId||null,html:input.value};}
  function query(value){
    const selected=new URLSearchParams();
    if(value.sourceMode==='owner-draft'){selected.set('source','owner-draft');selected.set('draftId',value.draftBasis.id);selected.set('draftRevision',String(value.draftBasis.revision));}
    else if(value.sourceMode==='restore-stage'){selected.set('source','restore-stage');selected.set('stageId',value.stageId);}
    return selected.size?'?'+selected:'';
  }
  function url(action,selected){
    if(!['header','footer'].includes(root.dataset.kind)||!['check','draft','apply'].includes(action))fail();
    return '/manage/shared/'+root.dataset.kind+'/'+action+'/'+selected;
  }
  async function request(action,body,selected){
    const response=await fetch(url(action,selected),{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':root.querySelector('[name=csrfmiddlewaretoken]').value},body});
    try{return {response,value:await response.json()};}
    catch{throw Object.assign(new Error('SHARED_RESPONSE_UNCONFIRMED'),{authEnded:[401,403].includes(response.status)});}
  }
  function verifyContext(result,intent){
    const context=result.editorContext;
    if(!exact(context,['baseRevisionId','sourceMode','draftBasis','stageId'])||context.stageId!==null)fail();
    if(intent.action==='apply'){
      if(context.sourceMode!=='current'||context.baseRevisionId!==result.resultId||context.draftBasis!==null)fail();
    }else{
      const expected=intent.value.draftBasis?intent.value.draftBasis.revision+1:1;
      if(context.sourceMode!=='owner-draft'||context.baseRevisionId!==intent.value.baseRevisionId||!exact(context.draftBasis,['id','revision'])||context.draftBasis.id!==result.resultId||!Number.isSafeInteger(context.draftBasis.revision)||context.draftBasis.revision!==expected)fail();
    }
    if(context.baseRevisionId!==null&&!validId(context.baseRevisionId))fail();
    return context;
  }
  function acknowledge(result,intent){
    if(!result||result.ok!==true||result.operationId!==intent.value.operationId||!validId(result.resultId)||result.resultCode!=='applied'||typeof result.replay!=='boolean'||typeof result.gone!=='boolean')fail();
    const context=result.gone||result.editorContext===null?null:verifyContext(result,intent);
    uncertain=null;retry.hidden=true;invalidate();
    if(context===null){basisUnavailable=true;status.textContent='Прежняя операция подтверждена, но её основание больше недоступно. Ввод остаётся здесь; откройте актуальный источник отдельно.';return;}
    root.dataset.base=context.baseRevisionId||'';root.dataset.sourceMode=context.sourceMode;
    root.dataset.draftId=context.draftBasis?.id||'';root.dataset.draftRevision=context.draftBasis?String(context.draftBasis.revision):'';root.dataset.stageId='';
    if(epoch!==intent.epoch||input.value!==intent.value.html){status.textContent='Прежняя операция подтверждена. Новые изменения остаются в этой вкладке и ещё не сохранены.';return;}
    cleanEpoch=epoch;status.textContent=intent.action==='draft'?'Черновик сохранён отдельно. Публичная версия не изменена.':'Изменения сохранены.';
  }
  async function transmit(intent){
    const wasUncertain=uncertain!==null;
    try{
      const {response,value}=await request(intent.action,intent.body,intent.query);
      if(!response.ok){
        if(response.status===409&&value?.code==='SHARED_OPERATION_ABORTED'&&value.operationId===intent.value.operationId&&value.outcomeKnown===true){uncertain=null;retry.hidden=true;invalidate();status.textContent='Прежняя попытка завершилась без сохранения. Ваш ввод остаётся здесь. Проверьте его перед новой ручной отправкой.';return;}
        if(!wasUncertain&&value?.operationNotStarted===true&&value.ok===false&&typeof value.code==='string'){
          uncertain=null;retry.hidden=true;invalidate();status.textContent=messages[value.code]||'Действие отклонено. Ваш ввод остаётся в этой вкладке.';return;
        }
        if([401,403].includes(response.status)){throw Object.assign(new Error('SHARED_RESPONSE_UNCONFIRMED'),{authEnded:true});}
        fail();
      }
      acknowledge(value,intent);
    }catch(error){uncertain=intent;retry.hidden=false;status.textContent=(error?.authEnded?messages.SHARED_SESSION_ENDED+' ':'')+unknownMessage;}
  }
  async function check(){
    const value=dto(),captured=epoch;
    try{
      const {response,value:result}=await request('check',JSON.stringify(value),query(value));
      if(!response.ok){invalidate();status.textContent=messages[result?.code]||'Проверка не выполнена. Ваш ввод остаётся здесь.';return;}
      if(epoch!==captured||input.value!==value.html){status.textContent='Во время проверки текст изменился. Проверьте его ещё раз.';return;}
      if(!result||result.protocol!=='shared-editor-v1'||typeof result.normalisedHtml!=='string'||typeof result.normalisationChanged!=='boolean'||typeof result.checkReceipt!=='string'||result.checkReceipt.length>16384||result.baseRevisionId!==value.baseRevisionId)fail();
      if(result.normalisationChanged){invalidate();normalization={html:result.normalisedHtml,source:value.html,epoch:captured};root.querySelector('[data-normalized-html]').textContent=result.normalisedHtml;proposal.hidden=false;status.textContent='Проверьте предложенную нормализацию. До вашего подтверждения ввод не меняется.';return;}
      if(result.normalisedHtml!==value.html)fail();
      checked={proof:result.checkReceipt,html:value.html,epoch:captured};status.textContent='Проверка пройдена. Изменения ещё не применены.';
    }catch{invalidate();status.textContent='Ответ проверки не подтверждён. Ваш ввод остаётся здесь; проверьте его ещё раз.';}
  }
  input.addEventListener('input',()=>{epoch++;invalidate();});
  root.querySelector('[data-accept-normalization]').addEventListener('click',()=>{
    if(!normalization||normalization.epoch!==epoch||normalization.source!==input.value){status.textContent='Текст изменился. Повторите проверку.';return;}
    input.value=normalization.html;epoch++;invalidate();status.textContent='Нормализация принята только в редактор. Проверьте текст ещё раз.';
  });
  window.addEventListener('beforeunload',event=>{if(epoch!==cleanEpoch||uncertain||basisUnavailable){event.preventDefault();event.returnValue='';}});
  retry.addEventListener('click',async()=>{
    if(busy||!uncertain)return;
    busy=true;status.textContent='Проверяется результат прежней отправки…';
    try{await transmit(uncertain);}finally{busy=false;}
  });
  root.addEventListener('click',async event=>{
    const button=event.target.closest('button[data-action]');if(!button||busy)return;
    if(uncertain){status.textContent=unknownMessage;return;}
    if(basisUnavailable){status.textContent='Откройте актуальный источник отдельно. Ваш ввод остаётся в этой вкладке.';return;}
    const action=button.dataset.action;
    if(!['check','draft','apply'].includes(action))return;
    if(action!=='check'&&(!checked||checked.epoch!==epoch||checked.html!==input.value)){status.textContent='Сначала проверьте текущий текст.';return;}
    if(action==='apply'&&!window.confirm('Применить этот общий блок ко всему сайту?'))return;
    busy=true;
    try{
      if(action==='check'){status.textContent='Выполняется проверка…';await check();return;}
      const value={...dto(),operationId:operationId(),checkReceipt:checked.proof};
      const body=JSON.stringify(value),intent={action,body,value:JSON.parse(body),query:query(value),epoch};
      status.textContent='Отправляются изменения…';await transmit(intent);
    }finally{busy=false;}
  });
}
