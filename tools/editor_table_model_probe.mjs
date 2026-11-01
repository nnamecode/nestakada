// TP2 geometry capability only: virtual slots are not valid HTML node counts.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {proveTableGeometry,proveDocumentTables} from '../app/page_editor/assets/table-editor.mjs';
const groups=[];
const table=(rows,columns)=>({rows:Array.from({length:rows},()=>({cells:Array.from({length:columns},()=>({rowspan:1,colspan:1}))}))});
const run=(id,fn)=>{fn();groups.push({id,status:'PASS'});};
run('TP2-M005-exact20000-and-plus-one-summed-capability',()=>{
  const left=table(100,100),right=table(100,100);
  assert.deepEqual(proveTableGeometry([left,right]),{slots:20000,tableCount:2});
  assert.throws(()=>proveTableGeometry([left,right,table(1,1)]));
  assert.deepEqual(proveTableGeometry([table(100,200)]),{slots:20000,tableCount:1});
});
run('TP2-M005-unitspans-only-no-dense-declared-area',()=>{
  for(const span of [2,Number.MAX_SAFE_INTEGER,Infinity,NaN,'1000000000000000000000000000',true]){
    const value=table(1,1);value.rows[0].cells[0].colspan=span;
    const before=structuredClone(value);assert.throws(()=>proveTableGeometry([value]));assert.deepEqual(value,before);
  }
  const value=table(1,1);value.rows[0].cells[0].rowspan=2;assert.throws(()=>proveTableGeometry([value]));
});
run('TP2-M003-no-price-limits-no-invented-body-minimum',()=>{
  assert.deepEqual(proveTableGeometry([table(1,1)]),{slots:1,tableCount:1});
  assert.deepEqual(proveTableGeometry([table(501,1)]),{slots:501,tableCount:1});
  assert.deepEqual(proveTableGeometry([table(1,33)]),{slots:33,tableCount:1});
  assert.deepEqual(proveTableGeometry([]),{slots:0,tableCount:0});
});
run('TP2-M005-invalid-shape-refuses-without-source-mutation',()=>{
  const ragged={rows:[{cells:[{}]},{cells:[{},{}]}]};
  for(const value of [null,{},[null],[{}],[{rows:null}],[{rows:[{cells:null}]}], [ragged]]){
    const before=structuredClone(value);assert.throws(()=>proveTableGeometry(value));assert.deepEqual(value,before);
  }
});
run('TP2-M008-actual-ProseMirror-node-budget-is-distinct-from-slots',()=>{
  const require=createRequire('/deps/package.json'),{Schema}=require('@tiptap/pm/model');
  const schema=new Schema({nodes:{
    doc:{content:'block*'},text:{group:'inline'},
    paragraph:{group:'block',content:'inline*',attrs:{esUnwrapped:{default:true}}},
    esTableBlock:{group:'block',content:'table'},table:{content:'tableRow+'},
    tableRow:{content:'(tableCell|tableHeader)+',attrs:{esSection:{default:'body'}}},
    tableCell:{content:'paragraph',attrs:{rowspan:{default:1},colspan:{default:1}}},
    tableHeader:{content:'paragraph',attrs:{rowspan:{default:1},colspan:{default:1},esScope:{default:'col'}}}
  }});
  function document(columns){
    const rows=Array.from({length:100},()=>schema.nodes.tableRow.create(null,
      Array.from({length:columns},()=>schema.nodes.tableCell.create(null,
        schema.nodes.paragraph.create({esUnwrapped:true},schema.text('x'))))));
    return schema.nodes.doc.create(null,schema.nodes.esTableBlock.create(null,schema.nodes.table.create(null,rows)));
  }
  const accepted=document(130);let actual=0;accepted.descendants(()=>{actual++;});
  assert.ok(actual<40000);const proof=proveDocumentTables(accepted);
  assert.equal(proof.slots,13000);assert.equal(proof.tableCount,1);assert.equal(proof.pmNodes,actual);
  const exceeded=document(140);let exceededActual=0;exceeded.descendants(()=>{exceededActual++;});
  assert.ok(exceededActual>40000);assert.throws(()=>proveDocumentTables(exceeded));
  // This is an independent opening-tag/byte bound, NOT server acceptance.
  const wire='<table><tbody>'+('<tr>'+'<td>x</td>'.repeat(140)+'</tr>').repeat(100)+'</tbody></table>';
  assert.ok(Buffer.byteLength(wire)<1048576);assert.ok((wire.match(/<(?!\/)[a-z]+(?:>|\s)/g)||[]).length<20000);
});
console.log(JSON.stringify({status:'PASS',scope:'pure-geometry-not-wire-budget-not-browser',groups}));
