/* PriceV1 in RAM only. The server owns decimal/text acceptance and publication. */
const own=(value,key)=>Object.hasOwn(value,key);
const UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
function fail(code){const error=new Error(code);error.code=code;throw error;}
function keys(value,names){if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).length!==names.length||names.some(name=>!own(value,name)))fail('PRICE_SHAPE_INVALID');}
function id(value){if(typeof value!=='string'||!UUID.test(value))fail('PRICE_ID_INVALID');}
function newUuid(){const bytes=crypto.getRandomValues(new Uint8Array(16));bytes[6]=(bytes[6]&15)|64;bytes[8]=(bytes[8]&63)|128;const hex=[...bytes].map(value=>value.toString(16).padStart(2,'0')).join('');return hex.slice(0,8)+'-'+hex.slice(8,12)+'-'+hex.slice(12,16)+'-'+hex.slice(16,20)+'-'+hex.slice(20);}
function scrub(value){if(value&&typeof value==='object'){for(const key of Object.keys(value)){scrub(value[key]);delete value[key];}if(Array.isArray(value))value.length=0;}}
export function validatePrice(value){
  if(value===null)return null;
  keys(value,['columns','rows']);if(!Array.isArray(value.columns)||!Array.isArray(value.rows))fail('PRICE_SHAPE_INVALID');
  if(value.columns.length>32||value.rows.length>500)fail('PRICE_LIMIT');
  const columns=new Set(),rows=new Set();let count=0;
  for(const column of value.columns){keys(column,['id','label']);id(column.id);if(columns.has(column.id)||typeof column.label!=='string')fail('PRICE_SHAPE_INVALID');columns.add(column.id);}
  for(const row of value.rows){keys(row,['id','label','cells']);id(row.id);if(rows.has(row.id)||typeof row.label!=='string'||!Array.isArray(row.cells))fail('PRICE_SHAPE_INVALID');rows.add(row.id);const seen=new Set();
    for(const cell of row.cells){if(!cell||!columns.has(cell.column_id)||seen.has(cell.column_id))fail('PRICE_SHAPE_INVALID');seen.add(cell.column_id);count++;
      if(cell.kind==='text'){keys(cell,['column_id','kind','text']);if(typeof cell.text!=='string')fail('PRICE_SHAPE_INVALID');}
      else if(cell.kind==='amount'){keys(cell,['column_id','kind','amount','from']);if(typeof cell.amount!=='string'||typeof cell.from!=='boolean')fail('PRICE_SHAPE_INVALID');}
      else fail('PRICE_SHAPE_INVALID');
    }
  }
  if(count>10000)fail('PRICE_LIMIT');
  return structuredClone(value);
}

export class PriceModel{
  #value;#factory;#before;#destroyed=false;
  constructor(value,{idFactory=newUuid,beforeMutation=()=>{}}={}){this.#value=validatePrice(value);this.#factory=idFactory;this.#before=beforeMutation;}
  #live(){if(this.#destroyed)fail('PRICE_DESTROYED');}
  read(){this.#live();return structuredClone(this.#value);}
  #commit(value,notify=true){this.#live();const next=validatePrice(value);if(notify)this.#before();scrub(this.#value);this.#value=next;}
  replace(value){this.#commit(value,false);}
  #table(){this.#live();if(this.#value===null)fail('PRICE_TABLE_REQUIRED');return structuredClone(this.#value);}
  #newId(value){const result=this.#factory();id(result);if([...value.columns,...value.rows].some(item=>item.id===result))fail('PRICE_ID_COLLISION');return result;}
  #find(items,identity){const index=items.findIndex(item=>item.id===identity);if(index<0)fail('PRICE_ID_UNKNOWN');return index;}
  create(){this.#live();if(this.#value!==null)fail('PRICE_TABLE_EXISTS');this.#commit({columns:[],rows:[]});}
  remove(){this.#commit(null);}
  addRow(){const value=this.#table();if(value.rows.length>=500||value.rows.reduce((n,row)=>n+row.cells.length,0)+value.columns.length>10000)fail('PRICE_LIMIT');const identity=this.#newId(value);value.rows.push({id:identity,label:'',cells:value.columns.map(column=>({column_id:column.id,kind:'text',text:''}))});this.#commit(value);return identity;}
  addColumn(){const value=this.#table();if(value.columns.length>=32||value.rows.reduce((n,row)=>n+row.cells.length,0)+value.rows.length>10000)fail('PRICE_LIMIT');const identity=this.#newId(value);value.columns.push({id:identity,label:''});for(const row of value.rows)row.cells.push({column_id:identity,kind:'text',text:''});this.#commit(value);return identity;}
  renameRow(identity,label){const value=this.#table();value.rows[this.#find(value.rows,identity)].label=label;this.#commit(value);}
  renameColumn(identity,label){const value=this.#table();value.columns[this.#find(value.columns,identity)].label=label;this.#commit(value);}
  removeRow(identity){const value=this.#table();value.rows.splice(this.#find(value.rows,identity),1);this.#commit(value);}
  removeColumn(identity){const value=this.#table();value.columns.splice(this.#find(value.columns,identity),1);for(const row of value.rows)row.cells=row.cells.filter(cell=>cell.column_id!==identity);this.#commit(value);}
  #move(items,identity,delta){if(delta!==-1&&delta!==1)fail('PRICE_MOVE_INVALID');const index=this.#find(items,identity),target=index+delta;if(target<0||target>=items.length)fail('PRICE_MOVE_BOUNDARY');[items[index],items[target]]=[items[target],items[index]];}
  moveRow(identity,delta){const value=this.#table();this.#move(value.rows,identity,delta);this.#commit(value);}
  moveColumn(identity,delta){const value=this.#table();this.#move(value.columns,identity,delta);this.#commit(value);}
  setCell(rowId,columnId,cell){const value=this.#table();this.#find(value.columns,columnId);const row=value.rows[this.#find(value.rows,rowId)];if(!cell||typeof cell!=='object'||own(cell,'column_id'))fail('PRICE_SHAPE_INVALID');const next={column_id:columnId,...structuredClone(cell)},index=row.cells.findIndex(item=>item.column_id===columnId);if(index<0)row.cells.push(next);else row.cells[index]=next;this.#commit(value);}
  destroy(){if(this.#destroyed)return;scrub(this.#value);this.#value=null;this.#factory=null;this.#before=null;this.#destroyed=true;}
}

export function mountPriceEditor({root,before,initial,invalidate,canEdit=()=>true,onError=()=>{}}={}){
  if(!(root instanceof HTMLElement)||typeof invalidate!=='function')fail('PRICE_MOUNT_INVALID');
  const host=document.createElement('section');host.className='es-price-editor';host.dataset.priceEditor='';
  root.insertBefore(host,before||null);let page=0,destroyed=false;const modes=new Map();
  const model=new PriceModel(initial,{beforeMutation:()=>{if(destroyed||!canEdit())fail('PRICE_EDIT_BLOCKED');invalidate();}});
  const node=(tag,text)=>{const element=document.createElement(tag);if(text!==undefined)element.textContent=text;return element;};
  function action(label,name,identity={},disabled=false){const element=node('button',label);element.type='button';element.dataset.priceAction=name;Object.assign(element.dataset,identity);element.disabled=disabled;return element;}
  function input(label,value,data,multiline=false){const wrapper=node('label',label+' '),element=node(multiline?'textarea':'input');if(!multiline)element.type='text';else element.rows=3;element.value=value;element.setAttribute('aria-label',label);Object.assign(element.dataset,data);wrapper.append(element);return wrapper;}
  function wipe(){for(const element of host.querySelectorAll('input,textarea,select')){element.value='';if(element.type==='checkbox')element.checked=false;}host.replaceChildren();}
  function render(){if(destroyed)return;wipe();const value=model.read();host.append(node('h2','Прайс'));
    const status=node('p');status.dataset.priceStatus='';status.setAttribute('role','status');host.append(status);
    if(value===null){host.append(node('p','Прайс отсутствует. Создание изменит только данные в открытой вкладке.'),action('Создать прайс','create'));return;}
    const count=node('p',`${value.rows.length} строк · ${value.columns.length} колонок · ${value.rows.reduce((n,row)=>n+row.cells.length,0)} ячеек`);count.dataset.priceCount='';host.append(count);
    host.append(action('Добавить строку','add-row'),action('Добавить колонку','add-column'),action('Удалить весь прайс из редактируемых данных','remove'));
    const pages=Math.max(1,Math.ceil(value.rows.length/20));page=Math.max(0,Math.min(page,pages-1));const pager=node('div');pager.className='es-price-pages';const pageText=node('span',`Страница ${page+1} из ${pages}`);pageText.dataset.pricePage=String(page+1);pager.append(action('Предыдущие строки','previous',{},page===0),pageText,action('Следующие строки','next',{},page===pages-1));host.append(pager);
    const scroll=node('div');scroll.className='es-price-scroll';const table=node('table'),head=node('thead'),heading=node('tr');heading.append(node('th','Услуга / строка'));
    for(const [index,column]of value.columns.entries()){const th=node('th');th.scope='col';th.dataset.priceColumn=column.id;th.append(input('Название колонки',column.label,{priceColumnLabel:column.id}),action('←','left-column',{columnId:column.id},index===0),action('→','right-column',{columnId:column.id},index===value.columns.length-1),action('Удалить колонку','remove-column',{columnId:column.id}));heading.append(th);}head.append(heading);table.append(head);const body=node('tbody');
    for(let index=page*20;index<Math.min(value.rows.length,(page+1)*20);index++){const row=value.rows[index],tr=node('tr');tr.dataset.priceRow=row.id;const label=node('th');label.scope='row';label.append(input('Название строки',row.label,{priceRowLabel:row.id}),action('↑','up-row',{rowId:row.id},index===0),action('↓','down-row',{rowId:row.id},index===value.rows.length-1),action('Удалить строку','remove-row',{rowId:row.id}));tr.append(label);
      for(const column of value.columns){const td=node('td');td.dataset.priceCell='';td.dataset.rowId=row.id;td.dataset.columnId=column.id;const cell=row.cells.find(item=>item.column_id===column.id),key=row.id+':'+column.id,mode=modes.get(key)||(cell?.kind==='amount'?'amount':cell?.text?'text':'empty');const wrapper=node('label','Вид ячейки '),select=node('select');select.dataset.priceKind='';select.setAttribute('aria-label','Вид ячейки');for(const [val,title]of[['empty','Пусто'],['text','Текст'],['amount','Сумма']]){const option=node('option',title);option.value=val;select.append(option);}select.value=mode;wrapper.append(select);td.append(wrapper);
        if(mode==='text')td.append(input('Текст',cell?.kind==='text'?cell.text:'',{priceText:''},true));
        if(mode==='amount'){td.append(input('Сумма',cell?.kind==='amount'?cell.amount:'',{priceAmount:''}));const from=node('label','От '),checkbox=node('input');checkbox.type='checkbox';checkbox.dataset.priceFrom='';checkbox.setAttribute('aria-label','От');checkbox.checked=cell?.kind==='amount'?cell.from:false;from.append(checkbox);td.append(from);}tr.append(td);
      }body.append(tr);
    }table.append(body);scroll.append(table);host.append(scroll);
  }
  function error(exception){const status=host.querySelector('[data-price-status]');if(status)status.textContent=exception?.code==='PRICE_LIMIT'?'Достигнут предел структуры прайса. Данные не изменены.':'Правка не выполнена. Данные остаются в памяти вкладки.';onError(exception);}
  function edit(event){const target=event.target;if(!(target instanceof HTMLElement))return;
    const kind=target.matches('[data-price-kind]'),from=target.matches('[data-price-from]');if((event.type==='input'&&(kind||from))||(event.type==='change'&&!kind&&!from))return;
    if(!canEdit()){render();return;}
    try{
      if(target.matches('[data-price-row-label]'))model.renameRow(target.dataset.priceRowLabel,target.value);
      else if(target.matches('[data-price-column-label]'))model.renameColumn(target.dataset.priceColumnLabel,target.value);
      else{const parent=target.closest('[data-price-cell]');if(!parent)return;const rowId=parent.dataset.rowId,columnId=parent.dataset.columnId;const row=model.read().rows.find(item=>item.id===rowId),old=row.cells.find(item=>item.column_id===columnId);
        if(kind){const mode=target.value;if(!['empty','text','amount'].includes(mode))fail('PRICE_SHAPE_INVALID');model.setCell(rowId,columnId,mode==='amount'?{kind:'amount',amount:old?.kind==='amount'?old.amount:'',from:old?.kind==='amount'?old.from:false}:{kind:'text',text:mode==='text'&&old?.kind==='text'?old.text:''});modes.set(rowId+':'+columnId,mode);render();}
        else if(target.matches('[data-price-text]'))model.setCell(rowId,columnId,{kind:'text',text:target.value});
        else if(target.matches('[data-price-amount]'))model.setCell(rowId,columnId,{kind:'amount',amount:target.value,from:old?.kind==='amount'?old.from:false});
        else if(from)model.setCell(rowId,columnId,{kind:'amount',amount:old?.kind==='amount'?old.amount:'',from:target.checked});
      }
    }catch(exception){render();error(exception);}
  }
  function click(event){const button=event.target.closest?.('button[data-price-action]');if(!button||!host.contains(button))return;const name=button.dataset.priceAction;if(name==='previous'||name==='next'){page+=name==='next'?1:-1;render();return;}if(!canEdit())return;
    try{const row=button.dataset.rowId,column=button.dataset.columnId;switch(name){case'create':model.create();break;case'remove':model.remove();modes.clear();break;case'add-row':model.addRow();break;case'add-column':model.addColumn();break;case'remove-row':model.removeRow(row);break;case'remove-column':model.removeColumn(column);break;case'up-row':model.moveRow(row,-1);break;case'down-row':model.moveRow(row,1);break;case'left-column':model.moveColumn(column,-1);break;case'right-column':model.moveColumn(column,1);break;default:return;}render();}catch(exception){error(exception);}
  }
  const beforeInput=event=>{if(!canEdit())event.preventDefault();};
  host.addEventListener('beforeinput',beforeInput);host.addEventListener('input',edit);host.addEventListener('change',edit);host.addEventListener('click',click);render();
  return Object.freeze({read:()=>model.read(),get:()=>model.read(),validate:validatePrice,
    accept(value){const next=validatePrice(value);model.replace(next);modes.clear();render();},
    destroy(){if(destroyed)return;destroyed=true;host.removeEventListener('beforeinput',beforeInput);host.removeEventListener('input',edit);host.removeEventListener('change',edit);host.removeEventListener('click',click);model.destroy();modes.clear();wipe();host.remove();}});
}
