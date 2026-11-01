// Pure actual PriceModel boundaries. No DOM/browser/server acceptance claim.
import assert from 'node:assert/strict';
import {webcrypto} from 'node:crypto';
import {PriceModel,validatePrice} from '../app/page_editor/assets/price-editor.mjs';
const cases=[];
let serial=1;
const id=()=>`00000000-0000-4000-8000-${String(serial++).padStart(12,'0')}`;
const run=(name,fn)=>{fn();cases.push({id:name,status:'PASS'});};
const frozen=model=>JSON.stringify(model.read());
const refusesUnchanged=(model,fn)=>{const before=frozen(model);assert.throws(fn);assert.equal(frozen(model),before);};
const matrix=(rows,columns)=>{
  const cols=Array.from({length:columns},()=>({id:id(),label:'Column'}));
  return {columns:cols,rows:Array.from({length:rows},()=>({id:id(),label:'Row',
    cells:cols.map(column=>({column_id:column.id,kind:'text',text:''}))}))};
};
run('TP1-M001-null-create-types-detached-raw-money',()=>{
  const model=new PriceModel(null,{idFactory:id});assert.equal(model.read(),null);
  model.create();assert.deepEqual(model.read(),{columns:[],rows:[]});
  model.addColumn();model.addRow();
  let value=model.read(),row=value.rows[0].id,column=value.columns[0].id;
  assert.deepEqual(value.rows[0].cells,[{column_id:column,kind:'text',text:''}]);
  for(const cell of [{kind:'text',text:'<script>literal</script>'},
    {kind:'amount',amount:'0',from:false},{kind:'amount',amount:'1e-2',from:true},
    {kind:'amount',amount:'999999999.99',from:false},{kind:'amount',amount:'not-money',from:false}]){
    model.setCell(row,column,cell);assert.deepEqual(model.read().rows[0].cells[0],{column_id:column,...cell});
  }
  model.renameRow(row,'🚀'.repeat(501));model.setCell(row,column,{kind:'text',text:'🚀'.repeat(1001)});
  assert.equal([...model.read().rows[0].label].length,501);assert.equal([...model.read().rows[0].cells[0].text].length,1001);
  value=model.read();value.rows[0].label='outside mutation';assert.notEqual(model.read().rows[0].label,value.rows[0].label);
  model.remove();assert.equal(model.read(),null);
});
run('TP1-M003-identity-bindings-structural-atomicity',()=>{
  const model=new PriceModel(matrix(2,2),{idFactory:id}),initial=model.read();
  const [r0,r1]=initial.rows.map(row=>row.id),[c0,c1]=initial.columns.map(column=>column.id);
  model.setCell(r0,c0,{kind:'text',text:'R0-C0'});model.setCell(r0,c1,{kind:'amount',amount:'0',from:true});
  model.renameRow(r0,'renamed');model.renameColumn(c0,'renamed column');
  model.moveRow(r0,1);model.moveColumn(c0,1);
  let value=model.read();assert.deepEqual(value.rows.map(row=>row.id),[r1,r0]);assert.deepEqual(value.columns.map(column=>column.id),[c1,c0]);
  assert.equal(value.rows.find(row=>row.id===r0).cells.find(cell=>cell.column_id===c0).text,'R0-C0');
  model.addRow();model.addColumn();value=model.read();
  assert.equal(new Set(value.rows.map(row=>row.id)).size,3);assert.equal(new Set(value.columns.map(column=>column.id)).size,3);
  for(const row of value.rows)assert.deepEqual(new Set(row.cells.map(cell=>cell.column_id)),new Set(value.columns.map(column=>column.id)));
  model.removeColumn(c1);model.removeRow(r1);value=model.read();
  assert.ok(value.rows.every(row=>row.cells.every(cell=>cell.column_id!==c1)));assert.ok(!value.rows.some(row=>row.id===r1));
  refusesUnchanged(model,()=>model.setCell(id(),c0,{kind:'text',text:'missing row'}));
});
run('TP1-M005-real-10000cells-500rows-32columns-no-truncation',()=>{
  const source=matrix(500,20),model=new PriceModel(source,{idFactory:id});
  const last=source.rows.at(-1),column=source.columns.at(-1);
  model.setCell(last.id,column.id,{kind:'amount',amount:'999999999.99',from:true});
  assert.equal(model.read().rows.length,500);assert.equal(model.read().rows.reduce((n,row)=>n+row.cells.length,0),10000);
  assert.equal(model.read().rows.at(-1).cells.find(cell=>cell.column_id===column.id).amount,'999999999.99');
  refusesUnchanged(model,()=>model.addColumn());refusesUnchanged(model,()=>model.addRow());
  const wide=new PriceModel(matrix(1,32),{idFactory:id});refusesUnchanged(wide,()=>wide.addColumn());
  assert.equal(wide.read().columns.length,32);
});
run('TP1-M007-sparse-missing-cells-stay-absent-until-explicit-action',()=>{
  const source=matrix(2,3);source.rows[0].cells=[];source.rows[1].cells.splice(1,1);
  assert.deepEqual(validatePrice(source),source);
  const model=new PriceModel(source,{idFactory:id});assert.deepEqual(model.read(),source);
  model.renameRow(source.rows[0].id,'only a label');assert.deepEqual(model.read().rows[0].cells,[]);
  model.setCell(source.rows[0].id,source.columns[1].id,{kind:'text',text:''});
  assert.deepEqual(model.read().rows[0].cells,[{column_id:source.columns[1].id,kind:'text',text:''}]);
  model.addColumn();assert.equal(model.read().rows[0].cells.length,2);
  model.destroy();assert.throws(()=>model.read());assert.throws(()=>model.addRow());
});
run('TP1-M003-default-factory-http-browser-getRandomValues-without-randomUUID',()=>{
  const original=Object.getOwnPropertyDescriptor(globalThis,'crypto');let calls=0;
  try{
    Object.defineProperty(globalThis,'crypto',{configurable:true,value:Object.freeze({
      getRandomValues(values){calls++;return webcrypto.getRandomValues(values);}
    })});
    assert.equal(typeof globalThis.crypto.randomUUID,'undefined');
    const model=new PriceModel(null);model.create();model.addColumn();model.addColumn();model.addRow();model.addRow();
    const value=model.read(),identities=[...value.columns,...value.rows].map(item=>item.id);
    assert.equal(identities.length,4);assert.equal(new Set(identities).size,4);
    for(const identity of identities)assert.match(identity,/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
    assert.ok(calls>=4,'actual node webcrypto.getRandomValues was not exercised');
  }finally{
    if(original)Object.defineProperty(globalThis,'crypto',original);else delete globalThis.crypto;
  }
});
run('TP1-M004-invalid-shape-bool-kind-bindings-refused-source-unchanged',()=>{
  const good=matrix(1,1),source=structuredClone(good);
  assert.deepEqual(validatePrice(good),good);assert.deepEqual(good,source);
  for(const change of [value=>value.columns.push({...value.columns[0]}),
    value=>value.rows[0].cells.push({...value.rows[0].cells[0]}),
    value=>value.rows[0].cells[0].column_id=id(),
    value=>value.rows[0].cells[0]={column_id:value.columns[0].id,kind:'amount',amount:1,from:false},
    value=>value.rows[0].cells[0]={column_id:value.columns[0].id,kind:'amount',amount:'0',from:'false'}]){
    const bad=structuredClone(good);change(bad);assert.throws(()=>validatePrice(bad));assert.deepEqual(good,source);
  }
  const model=new PriceModel(good,{idFactory:id});refusesUnchanged(model,()=>model.replace({columns:[],rows:source.rows}));
});
console.log(JSON.stringify({status:'PASS',scope:'pure-actual-PriceModel-no-browser-no-server',cases}));
