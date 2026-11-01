/* Bounded simple-table capability. No DOM parser, TableMap, CSS or allocation
   proportional to declared spans is used by the geometry proof. */
const LIMIT=20000;
function fail(code='EDITOR_TABLE_UNSUPPORTED'){const error=new Error(code);error.code=code;throw error;}
export function proveTableGeometry(tables){
  if(!Array.isArray(tables))fail();let slots=0;
  for(const table of tables){if(!table||!Array.isArray(table.rows)||!table.rows.length||table.rows.length>LIMIT)fail();let width=null;
    for(const row of table.rows){if(!row||!Array.isArray(row.cells)||!row.cells.length)fail();if(width===null)width=row.cells.length;if(width!==row.cells.length||row.cells.length>LIMIT-slots)fail('EDITOR_TABLE_GEOMETRY_LIMIT');
      for(const cell of row.cells)if(!cell||(cell.rowspan??1)!==1||(cell.colspan??1)!==1)fail();slots+=row.cells.length;
    }
  }return Object.freeze({slots,tableCount:tables.length});
}

export function proveDocumentTables(doc){
  const tables=[];let visited=0,slots=0;
  doc.descendants((node,pos,parent)=>{if(++visited>40000)fail('EDITOR_NODE_BUDGET');
    if(node.type.name==='esTableBlock'&&(node.childCount!==1||node.firstChild.type.name!=='table'))fail();
    if(node.type.name!=='table')return;
    if(parent?.type.name!=='esTableBlock'||node.childCount>LIMIT||!node.childCount)fail();
    const rows=[];let head=false,body=false;
    node.forEach(row=>{if(row.type.name!=='tableRow'||!row.childCount||row.childCount>LIMIT)fail();if(row.childCount>LIMIT-slots)fail('EDITOR_TABLE_GEOMETRY_LIMIT');slots+=row.childCount;const section=row.attrs.esSection;if(section==='head'){if(head||body)fail();head=true;}else if(section==='body')body=true;else fail();const cells=[];
      row.forEach(cell=>{if(cell.type.name!==(section==='head'?'tableHeader':'tableCell')||cell.childCount!==1||cell.firstChild.type.name!=='paragraph'||cell.attrs.colspan!==1||cell.attrs.rowspan!==1)fail();if(section==='head'&&![null,'col'].includes(cell.attrs.esScope))fail();const p=cell.firstChild;if(p.attrs.esUnwrapped!==true||['align','mt','mr','mb','ml','anchor'].some(key=>p.attrs[key]!==null&&p.attrs[key]!==undefined))fail();p.forEach(child=>{if(!['text','hardBreak'].includes(child.type.name))fail();});cells.push({rowspan:1,colspan:1});});rows.push({cells});
    });tables.push({rows});
  });return Object.freeze({...proveTableGeometry(tables),pmNodes:visited});
}

function compactChildren(element){const result=[];for(const node of element.childNodes){if(node.nodeType!==1)return null;result.push(node);}return result;}
export function simpleTableJson(element,inline,{remainingSlots=LIMIT,remainingPM=40000}={}){
  try{
    if(element.localName!=='table'||[...element.attributes].some(attr=>attr.name!=='data-es-cellpad'))return null;
    const raw=element.getAttribute('data-es-cellpad');if(raw!==null&&!/^(?:[0-9]|[12][0-9]|3[0-2])$/.test(raw))return null;
    if(element.querySelector('table,caption,[data-es-protected],[data-es-image],[data-es-slot],[data-es-parent]'))return null;
    const sections=compactChildren(element);if(!sections||!sections.length||sections.some(section=>!['thead','tbody'].includes(section.localName)||section.attributes.length)||sections.filter(x=>x.localName==='thead').length>1||sections.filter(x=>x.localName==='tbody').length>1||sections[0].localName==='tbody'&&sections.length!==1)return null;
    // Preflight actual unit geometry and synthetic PM overhead before creating
    // row/cell/paragraph JSON. Spans never control a dense allocation.
    let slots=0,width=null,pmNodes=2;
    for(const section of sections){const children=compactChildren(section);if(!children)return null;if(section.localName==='thead'&&children.length!==1)return null;
      for(const row of children){if(row.localName!=='tr'||row.attributes.length)return null;const cells=compactChildren(row);if(!cells?.length)return null;if(width===null)width=cells.length;if(width!==cells.length||cells.length>remainingSlots-slots)return null;slots+=cells.length;pmNodes+=1+cells.length*2;if(pmNodes>remainingPM)return null;
        for(const cell of cells){const head=section.localName==='thead';if(cell.localName!==(head?'th':'td')||[...cell.attributes].some(attr=>!head||attr.name!=='scope')||head&&cell.hasAttribute('scope')&&cell.getAttribute('scope')!=='col')return null;
          const stack=[...cell.childNodes];while(stack.length){const child=stack.pop();if(child.nodeType===3){if(child.data)pmNodes++;}else if(child.nodeType===1&&['br','strong','em','u','s','sub','sup','span','a'].includes(child.localName)){if(child.localName==='br')pmNodes++;else stack.push(...child.childNodes);}else return null;if(pmNodes>remainingPM)return null;}
        }
      }
    }if(!slots)return null;
    const rows=[],geometry=[];
    for(const section of sections){const children=compactChildren(section);if(!children)return null;if(section.localName==='thead'&&children.length!==1)return null;
      for(const row of children){if(row.localName!=='tr'||row.attributes.length)return null;const cells=compactChildren(row);if(!cells||!cells.length)return null;const isHead=section.localName==='thead',content=[];
        for(const cell of cells){if(cell.localName!==(isHead?'th':'td')||[...cell.attributes].some(attr=>!isHead||attr.name!=='scope')||isHead&&cell.hasAttribute('scope')&&cell.getAttribute('scope')!=='col')return null;
          content.push({type:isHead?'tableHeader':'tableCell',attrs:{colspan:1,rowspan:1,...(isHead?{esScope:cell.getAttribute('scope')}: {})},content:[{type:'paragraph',attrs:{esUnwrapped:true},content:inline(cell.childNodes)}]});
        }rows.push({type:'tableRow',attrs:{esSection:isHead?'head':'body'},content});geometry.push({cells:content.map(()=>({rowspan:1,colspan:1}))});
      }
    }proveTableGeometry([{rows:geometry}]);return {type:'esTableBlock',content:[{type:'table',attrs:{esCellPad:raw===null?null:Number(raw)},content:rows}]};
  }catch{return null;}
}

export function selectedTable(selection){
  const point=selection.$from;let depth=point.depth;
  while(depth>0&&point.node(depth).type.name!=='table')depth--;
  if(!depth)return null;
  if(!selection.empty)fail();
  const node=point.node(depth),rowIndex=point.index(depth),columnIndex=point.index(depth+1);
  if(point.node(depth-1).type.name!=='esTableBlock')fail();
  return {node,pos:point.before(depth),rowIndex,columnIndex,wrapperPos:point.before(depth-1)};
}

export function tableTransaction(state,selection,name,value){
  const proven=proveDocumentTables(state.doc),schema=state.schema;
  const emptyCell=head=>schema.nodes[head?'tableHeader':'tableCell'].create({colspan:1,rowspan:1,...(head?{esScope:'col'}:{})},schema.nodes.paragraph.create({esUnwrapped:true}));
  const makeRow=(head,width)=>schema.nodes.tableRow.create({esSection:head?'head':'body'},Array.from({length:width},()=>emptyCell(head)));
  let tr=state.tr.setSelection(selection);
  if(name==='tableInsert'){
    if(!selection.empty||selection.$from.depth!==1||selection.$from.parent.type.name!=='paragraph'||proven.slots>LIMIT-6||proven.pmNodes>40000-18)fail();
    const table=schema.nodes.table.create({esCellPad:4},[makeRow(true,2),makeRow(false,2),makeRow(false,2)]),wrapper=schema.nodes.esTableBlock.create(null,table);
    return tr.replaceSelectionWith(wrapper);
  }
  const selected=selectedTable(selection);if(!selected)fail('EDITOR_SELECT_TABLE');const table=selected.node,rows=[];table.forEach(row=>rows.push(row));const width=rows[0].childCount,index=selected.rowIndex,col=selected.columnIndex;
  if(name==='tablePadding'){if(typeof value!=='string'||!/^(?:[0-9]|[12][0-9]|3[0-2])$/.test(value))fail('EDITOR_TABLE_PADDING_INVALID');return tr.setNodeMarkup(selected.pos,undefined,{...table.attrs,esCellPad:Number(value)});}
  if(name==='tableAddRow'){if(proven.slots>LIMIT-width||proven.pmNodes>40000-(width*2+1))fail('EDITOR_TABLE_GEOMETRY_LIMIT');rows.splice(index+1,0,makeRow(false,width));}
  else if(name==='tableDeleteRow'){if(rows[index].attrs.esSection!=='body'||rows.length<=1)fail();rows.splice(index,1);}
  else if(name==='tableAddColumn'){if(proven.slots>LIMIT-rows.length||proven.pmNodes>40000-rows.length*2)fail('EDITOR_TABLE_GEOMETRY_LIMIT');for(let r=0;r<rows.length;r++){const cells=[];rows[r].forEach(cell=>cells.push(cell));cells.splice(col+1,0,emptyCell(rows[r].attrs.esSection==='head'));rows[r]=rows[r].copy(schema.nodes.tableRow.create(rows[r].attrs,cells).content);}}
  else if(name==='tableDeleteColumn'){if(width<=1)fail();for(let r=0;r<rows.length;r++){const cells=[];rows[r].forEach(cell=>cells.push(cell));cells.splice(col,1);rows[r]=rows[r].copy(schema.nodes.tableRow.create(rows[r].attrs,cells).content);}}
  else fail('EDITOR_COMMAND_UNSUPPORTED');
  const replacement=table.copy(schema.nodes.table.create(table.attrs,rows).content);
  tr=tr.replaceWith(selected.pos,selected.pos+table.nodeSize,replacement);
  const nextRow=Math.min(name==='tableAddRow'?index+1:index,rows.length-1),nextCol=Math.min(name==='tableAddColumn'?col+1:col,rows[0].childCount-1);
  let position=selected.pos+4;for(let r=0;r<nextRow;r++)position+=rows[r].nodeSize;for(let c=0;c<nextCol;c++)position+=rows[nextRow].child(c).nodeSize;
  return tr.setSelection(selection.constructor.create(tr.doc,position));
}
