// DEV-09G host-only bounded validator/generator. No filesystem writes or network.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const MAP = 'docs/analytics-route-map.csv';
const RTE = 'docs/analytics-route-evidence.csv';
const PACKAGE = 'app/content/dev09g_service_roots.json';
const MAP_SHA = 'c1d542d0761ffbdb9fc58c9227fc94144515ab18c3155952a93dc6fb4d1bbad8';
const RTE_SHA = 'c3a8a395fb4ed55fef6027a58014ce5decaadda7c559870bf06247c2fbeb79bc';
const PACKAGE_SHA = '956c35fb5697acb23b039a980d1915228bd1100f1884ebece3fcd909ace365db';
const SPECS = [
  { page_id: '729b10a3-709e-41c0-a71f-0d376a2b8586', map_id: 'MAP-012',
    url: '/services/remont/', position: 2, name: 'Ремонт', h1: 'Ремонт',
    title: 'Ремонт | Автосервис «Эстакада»',
    source: 'work/site-audit/crawl/ca4ab73dc69f37051a6f.html',
    sourceSha: '249c910d6e6340f652587f14c3cdea20c5c7befe21adf9f42719f16e7bd289a5',
    artifact: 'work/remont.html', artifactSha: 'cf7352e8dd14cae5059b3bf583586f32266882b47a44eff3d5119269dd4564c3', count: 17 },
  { page_id: 'ec990108-25c4-4ae9-961f-13487e63e938', map_id: 'MAP-014',
    url: '/services/drugie-uslugi/', position: 4, name: 'Другие Услуги', h1: 'Другие Услуги',
    title: 'Другие Услуги | Автосервис «Эстакада»',
    source: 'work/site-audit/crawl/32ee0e4b4942a75ffa9e.html',
    sourceSha: '25a3204a9ddb323e93b37b60887d78c6680d3978d8026cb7c8818b1ad4eeb78d',
    artifact: 'work/drugie-uslugi.html', artifactSha: '50c2c6c412d9ff93c7581816d7323eb541dc00c0b0878cca50ccadbc7446af1d', count: 5 },
];
const CAPS = new Map([[MAP, 256*1024], [RTE, 512*1024], [PACKAGE, 16*1024]]);
for (const spec of SPECS) { CAPS.set(spec.source, 64*1024); CAPS.set(spec.artifact, 64*1024); }
const ALLOWED = new Set(CAPS.keys());
const PARENT = 'f39af842-05a7-4101-af9a-2fc320d457d0';

function fail(code) { const error = new Error(code); error.code = code; throw error; }
function digest(bytes) { return crypto.createHash('sha256').update(bytes).digest('hex'); }
function inside(candidate, root) { const rel = path.relative(root, candidate); return rel === '' || (!rel.startsWith('..') && !path.isAbsolute(rel)); }
function same(left, right) { const a=path.normalize(left), b=path.normalize(right); return process.platform === 'win32' ? a.toLowerCase() === b.toLowerCase() : a === b; }
function requireFile(relative, io=fs) {
  if (!ALLOWED.has(relative) || relative.includes('..') || relative.includes('//')) fail('FILE_PATH');
  const absolute = path.resolve(repo, ...relative.split('/'));
  let stat, real; try { stat=io.lstatSync(absolute); real=io.realpathSync(absolute); } catch { fail('FILE_ACCESS'); }
  if (!inside(absolute, repo) || stat.isSymbolicLink() || !stat.isFile() || !inside(real, repo) || !same(real, absolute)) fail('FILE_BOUNDARY');
  return { absolute, size: stat.size };
}
function read(relative, io=fs) {
  const file=requireFile(relative, io), cap=CAPS.get(relative);
  if (!Number.isSafeInteger(file.size) || file.size < 1 || file.size > cap) fail('FILE_SIZE');
  let bytes; try { bytes=io.readFileSync(file.absolute); } catch { fail('FILE_ACCESS'); }
  if (!Buffer.isBuffer(bytes) || bytes.length !== file.size || bytes.length > cap) fail('FILE_SIZE');
  return bytes;
}
function text(bytes, code) { try { return new TextDecoder('utf-8',{fatal:true}).decode(bytes); } catch { fail(code); } }
function pinned(relative, sha) { const bytes=read(relative); if (digest(bytes)!==sha) fail('FILE_SHA256'); return bytes; }
function canonical(value) { return `${JSON.stringify(value,null,2)}\n`; }
function parsePackage(bytes) {
  const valueText=text(bytes,'PACKAGE_UTF8'); if (valueText.includes('\r')) fail('PACKAGE_CANONICAL');
  let value; try { value=JSON.parse(valueText); } catch { fail('PACKAGE_JSON'); }
  if (canonical(value)!==valueText) fail('PACKAGE_CANONICAL'); return value;
}
function csv(bytes) {
  const input=text(bytes,'CSV_UTF8').replace(/^\uFEFF/u,''); const rows=[]; let row=[], field='', quoted=false;
  for (let i=0;i<input.length;i+=1) { const c=input[i];
    if (quoted) { if (c==='"') { if (input[i+1]==='"') { field+='"'; i+=1; } else quoted=false; } else field+=c; }
    else if (c==='"') { if (field!=='') fail('CSV_FORMAT'); quoted=true; }
    else if (c===',') { row.push(field); field=''; }
    else if (c==='\n') { row.push(field); rows.push(row); row=[]; field=''; }
    else if (c!=='\r') field+=c;
  }
  if (quoted) fail('CSV_FORMAT'); if (row.length || field) { row.push(field); rows.push(row); }
  const header=rows.shift(); return rows.map(values => Object.fromEntries(header.map((key,index)=>[key,values[index]])));
}
function sourceFacts(bytes, spec) {
  const value=text(bytes,'SOURCE_UTF8');
  const titles=[...value.matchAll(/<title>([^<>]*)<\/title>/gu)];
  const descriptions=[...value.matchAll(/<meta name="description" content="([^"]*)">/gu)];
  const h1s=[...value.matchAll(/<h1>([^<>]*)<\/h1>/gu)];
  if (titles.length!==1 || titles[0][1]!==spec.title || descriptions.length!==1 || descriptions[0][1]!=='' ||
      h1s.length!==1 || h1s[0][1]!==spec.h1) fail('SOURCE_METADATA');
  const tiles=[...value.matchAll(
    /<a class="item-link" href="(services\/[^"?#]+)">\s*<h3>([^<>]+)<\/h3>/gu)]
    .map(match=>({name:match[2],href:`/${match[1]}`}));
  if (tiles.length !== (spec.map_id === 'MAP-012' ? 17 : 6)) fail('SOURCE_TILES');
  return tiles;
}
function approvedTiles(sourceTiles, spec) {
  const approved=structuredClone(sourceTiles);
  if (spec.map_id === 'MAP-012') {
    approved[6].name='Климат-контроль, Печка';
    approved[9].name='АКПП/МКПП/РКПП/Вариатора';
  } else {
    const excluded=approved.pop();
    if (excluded?.name !== 'Автомойка' || excluded.href !== '/services/drugie-uslugi/avtomojka')
      fail('APPROVED_EXCLUSION');
  }
  return approved;
}
function artifactTiles(bytes, spec, sourceTiles) {
  const value=text(bytes,'ARTIFACT_UTF8');
  const matches=[...value.matchAll(/<a class="service-tile" href="https:\/\/estakada-service\.ru([^"?#]+)"><span>\d+<\/span><strong>([^<>]+)<\/strong><i>↗<\/i><\/a>/gu)];
  const tiles=matches.map(match=>({name:match[2],href:match[1]}));
  if (tiles.length!==spec.count || JSON.stringify(tiles)!==JSON.stringify(approvedTiles(sourceTiles,spec)))
    fail('ARTIFACT_TILES');
  return tiles;
}
function page(spec, tiles) { return { page_id:spec.page_id,map_id:spec.map_id,url:spec.url,kind:'service_catalog',
  parent_id:PARENT,position:spec.position,name:spec.name,h1:spec.h1,title:spec.title,description:'',is_published:false,
  source:{relative_path:spec.source,sha256:spec.sourceSha},artifact:{relative_path:spec.artifact,sha256:spec.artifactSha},tiles }; }
function build() {
  const mapBytes=pinned(MAP,MAP_SHA), rteBytes=pinned(RTE,RTE_SHA), mapRows=csv(mapBytes), rteRows=csv(rteBytes);
  if (mapRows.length!==115 || rteRows.length!==115) fail('CSV_COUNT');
  const pages=SPECS.map(spec=>{
    const map=mapRows.filter(row=>row.map_id===spec.map_id), rte=rteRows.filter(row=>row.map_id===spec.map_id);
    if (map.length!==1 || rte.length!==1 || map[0].requested_path!==spec.url || map[0].source_snapshot!==spec.source ||
        map[0].source_sha256!==spec.sourceSha || map[0].source_h1!==spec.h1 || map[0].proposed_type!=='service_catalog' ||
        map[0].target_template!=='service_catalog_tiles_no_hero' || map[0].review_state!=='design_basis_present_verify_migration_before_launch' ||
        rte[0].requested_path!==spec.url || rte[0].source_sha256!==spec.sourceSha) fail('MAP_RTE_EXACT');
    const sourceBytes=pinned(spec.source,spec.sourceSha), artifactBytes=pinned(spec.artifact,spec.artifactSha);
    return page(spec,artifactTiles(artifactBytes,spec,sourceFacts(sourceBytes,spec)));
  });
  if (pages[0].tiles[6].name!=='Климат-контроль, Печка' || pages[0].tiles[9].name!=='АКПП/МКПП/РКПП/Вариатора' ||
      pages[1].tiles.some(tile=>tile.name==='Автомойка')) fail('APPROVED_DIFFERENCE');
  return {schema:'dev09-service-roots-v1',policy:'validated_approved_artifact_not_import_authority',
    inputs:{map_sha256:MAP_SHA,evidence_sha256:RTE_SHA},pages};
}
function expect(label, code, action) { try { action(); } catch(error) { if(error.code===code) return; fail(`SELFCHECK_ERROR_${label}`); } fail(`SELFCHECK_MISSED_${label}`); }
function selfcheck() {
  const expected={a:[{name:'A',href:'/services/a'}]}; const changed=structuredClone(expected); changed.a[0].name='B';
  expect('CONTENT','PACKAGE_CONTENT',()=>{if(JSON.stringify(changed)!==JSON.stringify(expected)) fail('PACKAGE_CONTENT');});
  const fake={lstatSync:()=>({size:CAPS.get(PACKAGE)+1,isSymbolicLink:()=>false,isFile:()=>true}),realpathSync:value=>value,
    readFileSync:()=>fail('SELFCHECK_OVERSIZE_READ')};
  expect('OVERSIZE','FILE_SIZE',()=>read(PACKAGE,fake));
  expect('PATH','FILE_PATH',()=>requireFile('../x',fake));
  expect('TITLE','SOURCE_METADATA',()=>sourceFacts(Buffer.from('<title>x</title><meta name="description" content=""><h1>Ремонт</h1>'),SPECS[0]));
  const source17=Array.from({length:17},(_,index)=>({name:`N${index}`,href:`/services/remont/${index}`}));
  const approved=approvedTiles(source17,SPECS[0]);
  if (approved[6].name!=='Климат-контроль, Печка' || approved[9].name!=='АКПП/МКПП/РКПП/Вариатора') fail('SELFCHECK_DELTA');
  const source6=Array.from({length:5},(_,index)=>({name:`N${index}`,href:`/services/drugie-uslugi/${index}`}));
  source6.push({name:'Автомойка',href:'/services/drugie-uslugi/avtomojka'});
  if (approvedTiles(source6,SPECS[1]).length!==5) fail('SELFCHECK_EXCLUSION');
  const wrong=structuredClone(source6); wrong.at(-1).href='/services/drugie-uslugi/other';
  expect('EXCLUSION','APPROVED_EXCLUSION',()=>approvedTiles(wrong,SPECS[1]));
  const artifactBytes=tiles=>Buffer.from(tiles.map((tile,index)=>
    `<a class="service-tile" href="https://estakada-service.ru${tile.href}"><span>${index+1}</span><strong>${tile.name}</strong><i>↗</i></a>`).join(''));
  const approved5=approvedTiles(source6,SPECS[1]);
  if (JSON.stringify(artifactTiles(artifactBytes(approved5),SPECS[1],source6))!==JSON.stringify(approved5))
    fail('SELFCHECK_ARTIFACT_VALID');
  expect('ARTIFACT_MISSING','ARTIFACT_TILES',()=>artifactTiles(artifactBytes(approved5.slice(0,-1)),SPECS[1],source6));
  expect('ARTIFACT_EXTRA','ARTIFACT_TILES',()=>artifactTiles(artifactBytes([...approved5,approved5[0]]),SPECS[1],source6));
  const reordered=structuredClone(approved5); [reordered[0],reordered[1]]=[reordered[1],reordered[0]];
  expect('ARTIFACT_REORDER','ARTIFACT_TILES',()=>artifactTiles(artifactBytes(reordered),SPECS[1],source6));
  const renamed=structuredClone(approved5); renamed[0].name='Changed';
  expect('ARTIFACT_NAME','ARTIFACT_TILES',()=>artifactTiles(artifactBytes(renamed),SPECS[1],source6));
  const repathed=structuredClone(approved5); repathed[0].href='/services/drugie-uslugi/changed';
  expect('ARTIFACT_PATH','ARTIFACT_TILES',()=>artifactTiles(artifactBytes(repathed),SPECS[1],source6));
  const boundary={lstatSync:()=>({size:1,isSymbolicLink:()=>true,isFile:()=>true}),realpathSync:value=>value};
  expect('SYMLINK','FILE_BOUNDARY',()=>requireFile(PACKAGE,boundary));
  expect('NONREGULAR','FILE_BOUNDARY',()=>requireFile(PACKAGE,{...boundary,lstatSync:()=>({size:1,isSymbolicLink:()=>false,isFile:()=>false})}));
  expect('SHORT_READ','FILE_SIZE',()=>read(PACKAGE,{...boundary,lstatSync:()=>({size:2,isSymbolicLink:()=>false,isFile:()=>true}),readFileSync:()=>Buffer.from('x')}));
  expect('CR','PACKAGE_CANONICAL',()=>parsePackage(Buffer.from('{}\r\n')));
  expect('UTF8','PACKAGE_UTF8',()=>parsePackage(Buffer.from([0xff])));
  expect('DUPLICATE','PACKAGE_CANONICAL',()=>parsePackage(Buffer.from('{"a":1,"a":2}\n')));
  process.stdout.write('{"schema":"dev09-service-roots-selfcheck-v1","status":"pass"}\n');
}
function check() {
  const expected=build(), bytes=read(PACKAGE); if(digest(bytes)!==PACKAGE_SHA) fail('PACKAGE_SHA256');
  const actual=parsePackage(bytes); if(JSON.stringify(actual)!==JSON.stringify(expected)) fail('PACKAGE_CONTENT');
  process.stdout.write(`${JSON.stringify({schema:'dev09-service-roots-check-v1',status:'pass',pages:2,tiles:22,bytes:bytes.length,writes:0,published:0})}\n`);
}
try { const mode=process.argv[2]; if(mode==='--emit') process.stdout.write(canonical(build())); else if(mode==='--check') check(); else if(mode==='--selfcheck') selfcheck(); else fail('USAGE'); }
catch(error) { process.stderr.write(`${error.code || 'VALIDATION_FAILED'}\n`); process.exitCode=1; }
