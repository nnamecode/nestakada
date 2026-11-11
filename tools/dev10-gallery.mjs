// DEV-10 host-only gallery authority validator/generator. No network, subprocess or writes.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';

const repo=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const FILES={
  map:['docs/analytics-route-map.csv',128*1024,'c1d542d0761ffbdb9fc58c9227fc94144515ab18c3155952a93dc6fb4d1bbad8'],
  media:['docs/media-inventory.csv',256*1024,'2be3bf2b24ca589c9eaf88a040ee80ed098417667e5c04db89ca669332155ad0'],
  approved:['work/gallery-of-works.html',64*1024,'5e9e5bbbdfdcae7a85a2575be441f209a3d32fb91b65169f2202c4c055bebc3d'],
  oldRoot:['work/site-audit/gallery.html',128*1024,'89dea67b4dc41ff1520a9db31d38ca8d11c12a39f9c2c7c942ef94c0ca8cc974'],
  oldPage2:['work/site-audit/gallery-page-2.html',64*1024,'6e4bd964bb6f769ecb23250a907ba56ef6b4fc1a9c44907e9d99f2e845535d46'],
  package:['app/content/dev10_gallery.json',512*1024,null],
};
const MAP_ORDER=['MAP-114','MAP-113','MAP-112','MAP-111','MAP-109','MAP-106','MAP-102','MAP-099','MAP-096','MAP-092','MAP-086','MAP-081','MAP-076','MAP-070','MAP-061','MAP-056','MAP-036'];
const PAGE2=MAP_ORDER.slice(10);
const COUNTS=new Map(Object.entries({'MAP-036':7,'MAP-056':12,'MAP-061':8,'MAP-070':10,'MAP-076':8,'MAP-081':7,'MAP-086':25,'MAP-092':14,'MAP-096':15,'MAP-099':11,'MAP-102':21,'MAP-106':9,'MAP-109':13,'MAP-111':32,'MAP-112':9,'MAP-113':9,'MAP-114':4}));
const NS='4db16416-1035-5b77-84cf-c0d4ea7e9154';
const HOME_ID='e80c3de1-feea-4847-b550-325a825ffc0e';
const ROOT_ID=uuid5('page:MAP-008');
const SOURCE_CAP=64*1024, SOURCE_TOTAL_CAP=512*1024, PHOTO_CAP=1024*1024, PHOTO_TOTAL_CAP=48*1024*1024;

function failure(code){const e=new Error(code);e.code=code;throw e}
function digest(value){return crypto.createHash('sha256').update(value).digest('hex')}
function inside(candidate,root){const rel=path.relative(root,candidate);return rel===''||(!rel.startsWith('..')&&!path.isAbsolute(rel))}
function same(a,b){a=path.normalize(a);b=path.normalize(b);return process.platform==='win32'?a.toLowerCase()===b.toLowerCase():a===b}
function safeRead(relative,cap,expectedSha=null,io=fs){
  if(typeof relative!=='string'||relative.includes('\\')||relative.includes('//')||relative.split('/').includes('..'))failure('FILE_PATH');
  const absolute=path.resolve(repo,...relative.split('/'));let stat,real,data;
  try{stat=io.lstatSync(absolute);real=io.realpathSync(absolute)}catch{failure('FILE_ACCESS')}
  if(!inside(absolute,repo)||stat.isSymbolicLink()||!stat.isFile()||!inside(real,repo)||!same(real,absolute))failure('FILE_BOUNDARY');
  if(stat.size>cap)failure('FILE_SIZE');
  try{data=io.readFileSync(absolute)}catch{failure('FILE_ACCESS')}
  if(data.length!==stat.size||data.length>cap)failure('FILE_SIZE');
  if(expectedSha!==null&&digest(data)!==expectedSha)failure('FILE_SHA256');
  return data;
}
function fixed(name,io=fs){const [relative,cap,sha]=FILES[name];return safeRead(relative,cap,sha,io)}
function utf8(buffer,code='UTF8_INVALID'){try{return new TextDecoder('utf-8',{fatal:true}).decode(buffer)}catch{failure(code)}}
function canonical(value){return Buffer.from(JSON.stringify(value,null,2)+'\n')}
function parseCsv(buffer){
  const input=utf8(buffer,'CSV_UTF8'),table=[];let row=[],field='',quoted=false;
  for(let i=0;i<input.length;i++){const char=input[i];if(quoted){if(char==='"'){if(input[i+1]==='"'){field+='"';i++}else quoted=false}else field+=char}else if(char==='"'){if(field!=='')failure('CSV_FORMAT');quoted=true}else if(char===','){row.push(field);field=''}else if(char==='\n'){row.push(field);table.push(row);row=[];field=''}else if(char!=='\r')field+=char}
  if(quoted)failure('CSV_FORMAT');if(row.length||field){row.push(field);table.push(row)}
  const header=table.shift();if(!header?.length||new Set(header).size!==header.length)failure('CSV_FORMAT');
  return table.map(values=>{if(values.length!==header.length)failure('CSV_FORMAT');return Object.fromEntries(header.map((key,index)=>[key,values[index]]))});
}
function uuidBytes(value){const hex=value.replaceAll('-','');if(!/^[0-9a-f]{32}$/u.test(hex))failure('UUID');return Buffer.from(hex,'hex')}
function uuid5(name){const bytes=crypto.createHash('sha1').update(Buffer.concat([uuidBytes(NS),Buffer.from(name)])).digest().subarray(0,16);bytes[6]=(bytes[6]&15)|80;bytes[8]=(bytes[8]&63)|128;const hex=bytes.toString('hex');return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`}
function exactOne(rows,predicate,code){const found=rows.filter(predicate);if(found.length!==1)failure(code);return found[0]}
function checkedText(value,characters,bytes,code){if(typeof value!=='string'||value.length>characters||Buffer.byteLength(value)>bytes||/[\u0000-\u001f\u007f]/u.test(value))failure(code);return value}
function sourceUrl(href){if(!/^\/assets\/images\/resources\/[a-z0-9._\/-]+$/u.test(href)||href.includes('/medium/'))failure('SOURCE_IMAGE_URL');return 'https://estakada-service.ru'+href}
function metadataFacts(value,main){const title=[...value.matchAll(/<title>([^<>]*)<\/title>/gu)],h1=main.match(/<h1>([^<>]*)<\/h1>/u);if(title.length!==1||!h1||title[0][1].includes('&')||h1[1].includes('&'))failure('SOURCE_METADATA');return{title:checkedText(title[0][1],255,1024,'SOURCE_TEXT'),h1:checkedText(h1[1],255,1024,'SOURCE_TEXT'),h1Match:h1}}
function htmlFacts(buffer){
  const value=utf8(buffer,'SOURCE_UTF8'),marker='<div class="col-lg-9 col-md-8">',indexes=[...value.matchAll(new RegExp(marker,'gu'))];if(indexes.length!==1)failure('SOURCE_MAIN');
  const main=value.slice(indexes[0].index),metadata=metadataFacts(value,main),h1=metadata.h1Match;
  const beforeImages=main.slice(h1.index+h1[0].length,main.indexOf('<a data-fancybox="images"'));
  const paragraphs=[...beforeImages.matchAll(/<p>([^<>]*)<\/p>/gu)].map(match=>match[1]);
  const images=[...main.matchAll(/<a data-fancybox="images" href="([^"]+)"/gu)].map(match=>sourceUrl(match[1]));
  if(paragraphs.length!==1||images.length<1||paragraphs[0].includes('&'))failure('SOURCE_MAIN');
  return{title:metadata.title,h1:metadata.h1,paragraph:checkedText(paragraphs[0],4096,4096,'SOURCE_TEXT'),images};
}
function rootFacts(buffer){const value=utf8(buffer,'SOURCE_UTF8'),marker='<div class="col-lg-9 col-md-8">',indexes=[...value.matchAll(new RegExp(marker,'gu'))];if(indexes.length!==1)failure('ROOT_SOURCE');const main=value.slice(indexes[0].index),metadata=metadataFacts(value,main),images=[...main.matchAll(/<a data-fancybox="images" href="([^"]+)"/gu)].map(match=>sourceUrl(match[1]));if(images.length!==137)failure('ROOT_SOURCE');return{...metadata,images}}
function approvedAlbums(buffer){
  const value=utf8(buffer,'ARTIFACT_UTF8'),matches=[...value.matchAll(/const galleryAlbums = (\[.*\]);/gu)];if(matches.length!==1)failure('ARTIFACT_GALLERY');let albums;try{albums=JSON.parse(matches[0][1])}catch{failure('ARTIFACT_GALLERY')}
  if(!Array.isArray(albums)||albums.length!==17)failure('ARTIFACT_GALLERY');
  return albums.map(album=>{if(Object.keys(album).join(',')!=='title,count,photos'||typeof album.title!=='string'||!Number.isInteger(album.count)||!Array.isArray(album.photos)||album.photos.length!==album.count)return failure('ARTIFACT_GALLERY');const photos=album.photos.map(relative=>{if(!/^\.\.\/media\/source-site\/assets\/[0-9a-f]{64}\.(?:jpg|jpeg|png)$/u.test(relative))failure('ARTIFACT_GALLERY');return relative.slice(3)});return{title:checkedText(album.title,255,1024,'ARTIFACT_GALLERY'),count:album.count,photos}});
}
function legacyCatalog(buffer){const value=utf8(buffer,'LEGACY_UTF8');const titles=[...value.matchAll(/<div class="photogallery-meta">([^<>]+)<\/div>/gu)].map(match=>match[1]);const images=[...value.matchAll(/<a data-fancybox="images" href="([^"]+)"/gu)].map(match=>sourceUrl(match[1]));return{titles,images}}
function validateMapRows(mapRows){
  const exactIds=new Set(['MAP-008','MAP-017','MAP-018',...MAP_ORDER]);if(new Set(mapRows.map(row=>row.map_id)).size!==mapRows.length)failure('MAP_DUPLICATE');
  const selected=mapRows.filter(row=>exactIds.has(row.map_id));if(selected.length!==20||new Set(selected.map(row=>row.map_id)).size!==20)failure('MAP_EXACT');
  const root=exactOne(selected,row=>row.map_id==='MAP-008','MAP_ROOT'),page1=exactOne(selected,row=>row.map_id==='MAP-017','MAP_PAGE1'),page2=exactOne(selected,row=>row.map_id==='MAP-018','MAP_PAGE2');
  if(root.requested_path!=='/gallery-of-works/'||root.proposed_type!=='gallery_catalog'||root.target_template!=='gallery_catalog_modal'||root.source_sha256!==FILES.oldRoot[2]||root.template_artifact!==FILES.approved[0])failure('MAP_ROOT');
  if(page1.requested_path!=='/gallery-of-works/?page=1'||page1.observed_effective_path!=='/gallery-of-works/'||page1.review_state!=='verify_initial_redirect_chain')failure('MAP_PAGE1');
  if(page2.requested_path!=='/gallery-of-works/?page=2'||page2.observed_effective_path!==page2.requested_path||page2.source_sha256!==FILES.oldPage2[2]||page2.review_state!=='review_legacy_page2_subset')failure('MAP_PAGE2');
  return{root,page1,page2,albums:MAP_ORDER.map(mapId=>{const row=exactOne(selected,item=>item.map_id===mapId,'MAP_ALBUM');if(row.proposed_type!=='gallery_album'||row.review_state!=='READY-06_missing_standalone_album_design'||row.target_template!=='gallery_album_standalone_proposed'||row.observed_final_status!=='200'||!/^\/gallery-of-works\/[a-z0-9-]+$/u.test(row.requested_path)||!/^work\/site-audit\/crawl\/[0-9a-f]{20}\.html$/u.test(row.source_snapshot)||!/^[0-9a-f]{64}$/u.test(row.source_sha256))failure('MAP_ALBUM');return row})};
}
function validateInventory(rows){
  const photos=rows.filter(row=>row.role==='gallery-original');if(photos.length!==214||new Set(photos.map(row=>row.source_url)).size!==214||new Set(photos.map(row=>row.local_file)).size!==214||new Set(photos.map(row=>row.sha256)).size!==214)failure('MEDIA_EXACT');
  let total=0;for(const row of photos){const bytes=Number(row.bytes);if(row.kind!=='image'||row.status!=='downloaded'||!/^https:\/\/estakada-service\.ru\/assets\/images\/resources\/[a-z0-9._\/-]+$/u.test(row.source_url)||!/^media\/source-site\/assets\/[0-9a-f]{64}\.(?:jpg|jpeg|png)$/u.test(row.local_file)||!Number.isSafeInteger(bytes)||bytes<1||bytes>PHOTO_CAP||!/^[0-9a-f]{64}$/u.test(row.sha256))failure('MEDIA_ROW');checkedText(row.source_url,2048,2048,'MEDIA_ROW');checkedText(row.local_file,1024,1024,'MEDIA_ROW');total+=bytes}if(total>PHOTO_TOTAL_CAP)failure('MEDIA_TOTAL');return{photos,total};
}
function readAlbumSource(row){const buffer=safeRead(row.source_snapshot,SOURCE_CAP,row.source_sha256);return{buffer,facts:htmlFacts(buffer)}}
function verifyPhotoFile(row){const buffer=safeRead(row.local_file,PHOTO_CAP,row.sha256);if(buffer.length!==Number(row.bytes))failure('MEDIA_BYTES')}
function build(){
  const mapBuffer=fixed('map'),mediaBuffer=fixed('media'),approvedBuffer=fixed('approved'),oldRootBuffer=fixed('oldRoot'),oldPage2Buffer=fixed('oldPage2');
  const map=validateMapRows(parseCsv(mapBuffer)),inventory=validateInventory(parseCsv(mediaBuffer)),approved=approvedAlbums(approvedBuffer),inventoryByUrl=new Map(inventory.photos.map(row=>[row.source_url,row]));
  const sourceRows=new Map(),sourceBuffers=[];for(const row of map.albums){const source=readAlbumSource(row);sourceRows.set(row.map_id,source.facts);sourceBuffers.push(source.buffer)}if(sourceBuffers.reduce((sum,item)=>sum+item.length,0)>SOURCE_TOTAL_CAP)failure('SOURCE_TOTAL');
  const albums=MAP_ORDER.map((mapId,position)=>{const row=map.albums[position],facts=sourceRows.get(mapId),artifact=approved[position];if(artifact.title!==facts.h1||artifact.count!==COUNTS.get(mapId)||facts.images.length!==artifact.count)failure('ALBUM_AUTHORITY');const photos=facts.images.map((url,index)=>{const inventoryRow=inventoryByUrl.get(url);if(!inventoryRow||inventoryRow.local_file!==artifact.photos[index])failure('ALBUM_PHOTO_ORDER');verifyPhotoFile(inventoryRow);const assetId=uuid5('asset:'+url),fileId=uuid5('file:'+url),extension=path.posix.extname(inventoryRow.local_file);return{position:index,image_id:uuid5(`image:${mapId}:${index}`),block_id:uuid5(`block:${mapId}:${index}`),asset_id:assetId,file_id:fileId,source_url:url,local_file:inventoryRow.local_file,storage_key:`img/${assetId}/original${extension}`,bytes:Number(inventoryRow.bytes),sha256:inventoryRow.sha256,alt:`${facts.h1}, фото ${index+1}`}});return{page_id:uuid5('page:'+mapId),map_id:mapId,url:row.requested_path,kind:'gallery_album',parent_id:ROOT_ID,position,name:facts.h1,h1:facts.h1,title:facts.title,description:'',is_published:false,source:{relative_path:row.source_snapshot,sha256:row.source_sha256},paragraphs:[facts.paragraph],photos}});
  const oldRoot=legacyCatalog(oldRootBuffer),oldPage2=legacyCatalog(oldPage2Buffer),first=albums.slice(0,10),second=albums.slice(10);if(JSON.stringify(oldRoot.titles)!==JSON.stringify(first.map(album=>album.name))||JSON.stringify(oldRoot.images)!==JSON.stringify(first.flatMap(album=>album.photos.map(photo=>photo.source_url)))||JSON.stringify(oldPage2.titles)!==JSON.stringify(second.map(album=>album.name))||JSON.stringify(oldPage2.images)!==JSON.stringify(second.flatMap(album=>album.photos.map(photo=>photo.source_url))))failure('LEGACY_SUBSETS');
  const root=rootFacts(oldRootBuffer);const result={schema:'dev10-gallery-v1',policy:'exact_legacy_originals_shared_album_data',inputs:{map_sha256:FILES.map[2],media_inventory_sha256:FILES.media[2],approved_gallery_sha256:FILES.approved[2],legacy_root_sha256:FILES.oldRoot[2],legacy_page2_sha256:FILES.oldPage2[2]},root:{page_id:ROOT_ID,map_id:'MAP-008',url:'/gallery-of-works/',page2_alias:'/gallery-of-works/?page=2',kind:'gallery_catalog',parent_id:HOME_ID,position:2,name:root.h1,h1:root.h1,title:root.title,description:'',is_published:false},page2_map_ids:PAGE2,albums};
  const encoded=canonical(result);if(encoded.length>FILES.package[1])failure('PACKAGE_SIZE');return result;
}
function parsePackage(buffer){const value=utf8(buffer,'PACKAGE_UTF8');if(value.includes('\r'))failure('PACKAGE_CANONICAL');let parsed;try{parsed=JSON.parse(value)}catch{failure('PACKAGE_JSON')}if(!canonical(parsed).equals(buffer))failure('PACKAGE_CANONICAL');return parsed}
function check(){const expected=build(),actual=parsePackage(fixed('package'));if(JSON.stringify(actual)!==JSON.stringify(expected))failure('PACKAGE_CONTENT');const photos=actual.albums.flatMap(album=>album.photos);process.stdout.write(JSON.stringify({schema:'dev10-gallery-check-v1',status:'pass',pages:18,routes:19,albums:17,photos:photos.length,total_bytes:photos.reduce((sum,row)=>sum+row.bytes,0),writes:0,published:0})+'\n')}
function selfcheck(){
  const expect=(code,fn)=>{try{fn();failure('SELFCHECK_EXPECTED_FAILURE')}catch(error){if(error.code!==code)throw error}};
  if(uuid5('page:MAP-008')!==ROOT_ID||uuid5('page:MAP-008')===uuid5('page:MAP-009'))failure('SELFCHECK_UUID');
  const minimal=Buffer.from('a,b\n1,2\n');if(parseCsv(minimal)[0].a!=='1')failure('SELFCHECK_CSV');expect('CSV_FORMAT',()=>parseCsv(Buffer.from('a,a\n1,2\n')));
  const syntheticAlbums=MAP_ORDER.map((mapId,index)=>({title:mapId,count:1,photos:[`../media/source-site/assets/${digest(Buffer.from(String(index)))}.jpg`]})),artifact=Buffer.from(`<script>const galleryAlbums = ${JSON.stringify(syntheticAlbums)};</script>`);if(approvedAlbums(artifact).length!==17)failure('SELFCHECK_ARTIFACT');const extra=structuredClone(syntheticAlbums);extra.push(extra[0]);expect('ARTIFACT_GALLERY',()=>approvedAlbums(Buffer.from(`<script>const galleryAlbums = ${JSON.stringify(extra)};</script>`)));
  const source=Buffer.from('<title>T</title><div class="col-lg-9 col-md-8"><h1>H</h1><p>P</p><a data-fancybox="images" href="/assets/images/resources/1/a.jpg">');const facts=htmlFacts(source);if(facts.h1!=='H'||facts.images.length!==1)failure('SELFCHECK_SOURCE');expect('SOURCE_MAIN',()=>htmlFacts(Buffer.from('<title>T</title><div class="col-lg-9 col-md-8"><h1>H</h1><a data-fancybox="images" href="/assets/images/resources/1/a.jpg">')));
  const inventory=Array.from({length:214},(_,index)=>{const hash=digest(Buffer.from(`photo:${index}`));return{source_url:`https://estakada-service.ru/assets/images/resources/1/${index}.jpg`,kind:'image',role:'gallery-original',reference_count:'1',status:'downloaded',local_file:`media/source-site/assets/${hash}.jpg`,bytes:'1',sha256:hash,error:''}});if(validateInventory(inventory).photos.length!==214)failure('SELFCHECK_MEDIA');const duplicate=structuredClone(inventory);duplicate[1].source_url=duplicate[0].source_url;expect('MEDIA_EXACT',()=>validateInventory(duplicate));
  const root={map_id:'MAP-008',requested_path:'/gallery-of-works/',observed_effective_path:'/gallery-of-works/',observed_final_status:'200',proposed_type:'gallery_catalog',review_state:'design_basis_present_verify_migration_before_launch',source_sha256:FILES.oldRoot[2],target_template:'gallery_catalog_modal',template_artifact:FILES.approved[0]},page1={map_id:'MAP-017',requested_path:'/gallery-of-works/?page=1',observed_effective_path:'/gallery-of-works/',observed_final_status:'200',proposed_type:'gallery_catalog',review_state:'verify_initial_redirect_chain'},page2={map_id:'MAP-018',requested_path:'/gallery-of-works/?page=2',observed_effective_path:'/gallery-of-works/?page=2',observed_final_status:'200',proposed_type:'gallery_catalog',review_state:'review_legacy_page2_subset',source_sha256:FILES.oldPage2[2]},albumRows=MAP_ORDER.map((mapId,index)=>({map_id:mapId,requested_path:`/gallery-of-works/a-${index}`,observed_final_status:'200',proposed_type:'gallery_album',review_state:'READY-06_missing_standalone_album_design',target_template:'gallery_album_standalone_proposed',source_snapshot:`work/site-audit/crawl/${String(index).padStart(20,'0')}.html`,source_sha256:digest(Buffer.from(mapId))})),mapRows=[root,page1,page2,...albumRows];if(validateMapRows(mapRows).albums.length!==17)failure('SELFCHECK_MAP');expect('MAP_EXACT',()=>validateMapRows(mapRows.slice(1)));expect('MAP_DUPLICATE',()=>validateMapRows([...mapRows,mapRows[0]]));
  const fake={lstatSync(){return{size:1,isSymbolicLink(){return false},isFile(){return true}}},realpathSync(value){return value},readFileSync(){return Buffer.from('x')}};expect('FILE_PATH',()=>safeRead('../escape',1,null,fake));if(safeRead('safe',1,null,fake).length!==1)failure('SELFCHECK_FILE');expect('FILE_SIZE',()=>safeRead('safe',0,null,fake));const link={...fake,lstatSync(){return{size:1,isSymbolicLink(){return true},isFile(){return true}}}};expect('FILE_BOUNDARY',()=>safeRead('safe',1,null,link));
  if(PAGE2.length!==7||MAP_ORDER.length!==17||[...COUNTS.values()].reduce((a,b)=>a+b,0)!==214)failure('SELFCHECK_CONSTANTS');
  process.stdout.write('{"schema":"dev10-gallery-selfcheck-v1","status":"pass"}\n');
}

try{const mode=process.argv[2];if(mode==='--emit')process.stdout.write(canonical(build()));else if(mode==='--check')check();else if(mode==='--selfcheck')selfcheck();else failure('USAGE')}catch(error){process.stderr.write(`${error.code||'VALIDATION_FAILED'}\n`);process.exitCode=1}
