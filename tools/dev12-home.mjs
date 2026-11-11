// DEV-12 host-only approved-home authority validator/generator. No network, subprocess or writes.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';

const repo=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const NS='656be4b8-5666-5ef9-bc1c-d2e3677a7e78';
const HOME_ID='e80c3de1-feea-4847-b550-325a825ffc0e';
const FILES={
  approved:['work/public-light-v4.html',128*1024,'815f8918963a64ec653827a530288f69fafd332a9eb05e0d5e320a5476b77ad7'],
  gallery:['app/content/dev10_gallery.json',256*1024,'9db5b026d6affa4668e2ca19268d8663355c1e22504f6aba6aa1676ed3d41b3b'],
  b:['app/content/dev09b_articles_slice.json',64*1024,'2936561288256d42968363afe90147678aa6fc88bbdff9faf21fde1c2d986639'],
  e:['app/content/dev09e_services_catalog.json',16*1024,'beffdfdbacc6a24a71c68ee692f03be262f67745b8425e1ce9b204b8d15ca9e9'],
  g:['app/content/dev09g_service_roots.json',8*1024,'956c35fb5697acb23b039a980d1915228bd1100f1884ebece3fcd909ace365db'],
  h:['app/content/dev09h_service_details.json',64*1024,'439dea21aa4257e934e0781faec982bb05157d5a734171ced58086df4e8bd52a'],
  i:['app/content/dev09i_planned_maintenance.json',48*1024,'fa0e85ba9640ffa45916e810bece20e949698b3dbe82f9ead99750210b98a5cf'],
  j:['app/content/dev09j_leading_price_details.json',40*1024,'e091047ae5272fa9834d828d5ed73e1fbc914a41faa07e4367b9787ad0a8934d'],
  k:['app/content/dev09k_diagnostics_branch.json',48*1024,'9980c60a1a2ee354ef156c7f9695cfc76ec051f798dfe3610a95f3e29c473e67'],
  package:['app/content/dev12_home_profile.json',128*1024,null],
};
const DESIGN_FILE_CAP=4*1024*1024,DESIGN_TOTAL_CAP=32*1024*1024;

function failure(code){const error=new Error(code);error.code=code;throw error}
function digest(value){return crypto.createHash('sha256').update(value).digest('hex')}
function canonical(value){return Buffer.from(JSON.stringify(value,null,2)+'\n')}
function inside(candidate,root){const relative=path.relative(root,candidate);return relative===''||(!relative.startsWith('..')&&!path.isAbsolute(relative))}
function same(a,b){a=path.normalize(a);b=path.normalize(b);return process.platform==='win32'?a.toLowerCase()===b.toLowerCase():a===b}
function safeRead(relative,cap,expectedSha=null,io=fs){
  if(typeof relative!=='string'||relative.includes('\\')||relative.includes('//')||relative.split('/').includes('..'))failure('FILE_PATH');
  const absolute=path.resolve(repo,...relative.split('/'));let stat,real,data;
  try{stat=io.lstatSync(absolute);real=io.realpathSync(absolute)}catch{failure('FILE_ACCESS')}
  if(!inside(absolute,repo)||stat.isSymbolicLink()||!stat.isFile()||!inside(real,repo)||!same(real,absolute))failure('FILE_BOUNDARY');
  if(stat.size>cap)failure('FILE_SIZE');try{data=io.readFileSync(absolute)}catch{failure('FILE_ACCESS')}
  if(data.length!==stat.size||data.length>cap)failure('FILE_SIZE');if(expectedSha!==null&&digest(data)!==expectedSha)failure('FILE_SHA256');return data;
}
function fixed(name,io=fs){const [relative,cap,sha]=FILES[name];return safeRead(relative,cap,sha,io)}
function utf8(buffer,code='UTF8_INVALID'){try{return new TextDecoder('utf-8',{fatal:true}).decode(buffer)}catch{failure(code)}}
function parseJson(buffer,code){const text=utf8(buffer,code+'_UTF8');let value;try{value=JSON.parse(text)}catch{failure(code+'_JSON')}return value}
function uuidBytes(value){const hex=value.replaceAll('-','');if(!/^[0-9a-f]{32}$/u.test(hex))failure('UUID');return Buffer.from(hex,'hex')}
function uuid5(name,namespace=NS){const bytes=crypto.createHash('sha1').update(Buffer.concat([uuidBytes(namespace),Buffer.from(name)])).digest().subarray(0,16);bytes[6]=(bytes[6]&15)|80;bytes[8]=(bytes[8]&63)|128;const hex=bytes.toString('hex');return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`}
function exactOne(values,code){if(values.length!==1)failure(code);return values[0]}
function section(html,start,end,code){const begins=[...html.matchAll(new RegExp(start,'gu'))];if(begins.length!==1)failure(code);const from=begins[0].index,after=html.indexOf(end,from);if(after<0)failure(code);return html.slice(from,after)}
function decode(value){return value.replaceAll('&amp;','&').replaceAll('&quot;','"').replaceAll('&#39;',"'").replaceAll('&nbsp;',' ').replaceAll('₽','₽')}
function text(value,code='TEXT'){const result=decode(value.replace(/<br\s*\/?\s*>/giu,'\n').replace(/<[^>]+>/gu,'')).replace(/[ \t]+/gu,' ').replace(/ *\n */gu,'\n').trim();if(!result||result.length>1000||/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/u.test(result))failure(code);return result}
function attr(value,name,code){const matches=[...value.matchAll(new RegExp(`${name}="([^"]*)"`,'gu'))];return decode(exactOne(matches,code)[1])}
function internal(value){
  const exact=new Map([['avtomojka.html','/services/avtomojka'],['gallery-of-works.html','/gallery-of-works/']]);if(exact.has(value))return exact.get(value);
  if(value.startsWith('https://estakada-service.ru')){const rest=value.slice('https://estakada-service.ru'.length)||'/';if(!rest.startsWith('/')||rest.includes('?')||rest.includes('#'))failure('INTERNAL_URL');return rest}
  if(/^\/[a-z0-9][a-z0-9\/-]*\/?$/u.test(value)||value==='/')return value;failure('INTERNAL_URL');
}
function imagePath(value){if(!/^\.\.\/media\/design-concepts\/[a-z0-9._\/-]+\.webp$/u.test(value))failure('DESIGN_PATH');return value.slice(3)}
function entries(value,regex,mapper){return [...value.matchAll(regex)].map(mapper)}
function htmlFacts(buffer,gallery){
  const html=utf8(buffer,'ARTIFACT_UTF8');
  const main=section(html,'<main id="es-main">','</main>','MAIN');
  const hero=section(main,'<section class="es-hero">','</section>','HERO'),heroCopy=section(hero,'<div class="es-hero-copy">','</div>','HERO_COPY');
  const heroImage=exactOne([...hero.matchAll(/<div class="es-hero-art"><img ([^>]+)>/gu)],'HERO_IMAGE');
  const proof=section(main,'<section class="es-proof"','</section>','PROOF');
  const advantages=entries(proof,/<article>[\s\S]*?<h2>([\s\S]*?)<\/h2><\/article>/gu,match=>text(match[1]));if(advantages.length!==8)failure('PROOF_COUNT');
  const solutions=section(main,'<section class="es-solutions"','</section>','COMPARE');
  const comparisons=entries(solutions,/<article class="es-compare-card[^"]*">([\s\S]*?)<\/article>/gu,match=>{const body=match[1],heading=exactOne([...body.matchAll(/<h2>([\s\S]*?)<\/h2>/gu)],'COMPARE_HEADING'),result=exactOne([...body.matchAll(/<div class="es-compare-result"><b>([\s\S]*?)<\/b><p>([\s\S]*?)<\/p><\/div>/gu)],'COMPARE_RESULT');return{heading:text(heading[1]),bullets:entries(body,/<li>([\s\S]*?)<\/li>/gu,item=>text(item[1])),result_mark:text(result[1]),result_text:text(result[2])}});if(comparisons.length!==3||comparisons.some(item=>item.bullets.length<4||item.bullets.length>5))failure('COMPARE_COUNT');
  const process=section(main,'<section class="es-process"','</section>','PROCESS');
  const steps=entries(process,/<li><img ([^>]+)>[\s\S]*?<h3>([\s\S]*?)<\/h3><p>([\s\S]*?)<\/p>[\s\S]*?<\/li>/gu,match=>({image_path:imagePath(attr(match[1],'src','STEP_SRC')),alt:attr(match[1],'alt','STEP_ALT'),heading:text(match[2]),text:text(match[3])}));if(steps.length!==5)failure('STEP_COUNT');
  const servicesSection=section(main,'<section class="es-section es-services"','</section>','SERVICES');
  const services=entries(servicesSection,/<a class="es-service-card" ([^>]*)>([\s\S]*?)<\/a>/gu,(match,index)=>{const image=exactOne([...match[2].matchAll(/<img ([^>]+)>/gu)],'SERVICE_IMAGE'),heading=exactOne([...match[2].matchAll(/<h3>([\s\S]*?)<\/h3>/gu)],'SERVICE_HEADING'),caption=exactOne([...match[2].matchAll(/<p>([\s\S]*?)<\/p>/gu)],'SERVICE_CAPTION');return{id:uuid5(`service:${index}`),label:text(heading[1]),caption:text(caption[1]),url:internal(attr(match[1],'href','SERVICE_HREF')),image_path:imagePath(attr(image[1],'src','SERVICE_SRC')),alt:attr(image[1],'alt','SERVICE_ALT'),fallback_visible:true}});if(services.length!==8)failure('SERVICE_COUNT');
  const pricesSection=section(main,'<section class="es-section es-prices"','</section>','PRICES');
  const tabs=entries(pricesSection,/<button type="button"[^>]*data-price="([^"]+)" data-href="([^"]+)">([\s\S]*?)<\/button>/gu,match=>({key:match[1],url:internal(match[2]),label:text(match[3])}));if(tabs.length!==6)failure('PRICE_TABS');
  const panels=new Map(entries(pricesSection,/<div class="es-price-panel" data-panel="([^"]+)"[^>]*>([\s\S]*?)<\/div>\s*(?=<div class="es-price-panel"|<a class="es-button)/gu,match=>[match[1],entries(match[2],/<div><a href="([^"]+)">([\s\S]*?)<\/a><b>([\s\S]*?)<\/b><\/div>/gu,row=>({url:internal(row[1]),label:text(row[2]),price_text:text(row[3]),fallback_visible:true}))]));
  const prices=tabs.map((tab,index)=>{const rows=panels.get(tab.key);if(!rows||rows.length<1||rows.length>8)failure('PRICE_ROWS');return{id:uuid5(`price-group:${index}`),...tab,rows:rows.map((row,rowIndex)=>({id:uuid5(`price-row:${index}:${rowIndex}`),...row}))}});
  const strip=section(main,'<section class="es-photo-strip"','</section>','PHOTO_STRIP'),stripImage=exactOne([...strip.matchAll(/<img ([^>]+)>/gu)],'PHOTO_STRIP_IMAGE');
  const worksSection=section(main,'<section class="es-section es-works"','</section>','WORKS');
  const works=entries(worksSection,/<a class="es-work-card" href="gallery-of-works\.html\?album=([0-9]+)"><img ([^>]+)>[\s\S]*?<span>([\s\S]*?)<\/span><h3>([\s\S]*?)<\/h3>/gu,(match,index)=>{const albumIndex=Number(match[1]),album=gallery.albums[albumIndex];if(!album||!album.photos?.[0])failure('WORK_ALBUM');return{id:uuid5(`work:${index}`),source_page_id:album.page_id,url:album.url,label:text(match[4]),photo_count_text:text(match[3]),image_id:uuid5(`work-image:${index}`),asset_id:album.photos[0].asset_id,alt:attr(match[2],'alt','WORK_ALT'),fallback_visible:true}});if(works.length!==6||JSON.stringify(works.map(item=>gallery.albums.findIndex(album=>album.page_id===item.source_page_id)))!==JSON.stringify([0,1,2,4,5,6]))failure('WORK_COUNT');
  const reviews=section(main,'<section class="es-section es-reviews"','</section>','REVIEWS'),reviewHeading=exactOne([...reviews.matchAll(/<h2>([\s\S]*?)<\/h2>/gu)],'REVIEW_HEADING'),reviewLink=exactOne([...reviews.matchAll(/<a class="es-video-reviews-all" href="([^"]+)">([\s\S]*?)<b>/gu)],'REVIEW_LINK');
  return{hero:{lead:text(exactOne([...heroCopy.matchAll(/<p class="es-lead">([\s\S]*?)<\/p>/gu)],'HERO_LEAD')[1]),image_path:imagePath(attr(heroImage[1],'src','HERO_SRC')),alt:attr(heroImage[1],'alt','HERO_ALT')},advantages,comparisons,steps,services,prices,photo_strip:{image_path:imagePath(attr(stripImage[1],'src','STRIP_SRC')),alt:attr(stripImage[1],'alt','STRIP_ALT')},works,reviews:{heading:text(reviewHeading[1]),url:internal(reviewLink[1]),label:text(reviewLink[2])}};
}
function pageIndex(packages){const result=new Map();for(const value of packages){for(const page of value.pages||[]){if(typeof page.url!=='string'||typeof page.page_id!=='string')failure('SOURCE_PACKAGE');if(result.has(page.url))failure('SOURCE_DUPLICATE');result.set(page.url,page)}}return result}
function formatAmount(cell){if(cell.kind!=='amount'||typeof cell.amount!=='string'||typeof cell.from!=='boolean')failure('SOURCE_PRICE');const value=Number(cell.amount);if(!Number.isFinite(value))failure('SOURCE_PRICE');return `${cell.from?'от ':''}${new Intl.NumberFormat('ru-RU',{maximumFractionDigits:2}).format(value)} ₽`.replaceAll('\u00a0',' ')}
function bindSources(profile,index){
  for(const item of profile.services)item.source_page_id=index.get(item.url)?.page_id||null;
  for(const group of profile.prices){group.source_page_id=index.get(group.url)?.page_id||null;for(const row of group.rows){const page=index.get(row.url),first=page?.price_rows?.[0];row.source_page_id=null;row.source_row_id=null;if(first&&formatAmount(first.cell)===row.price_text){row.source_page_id=page.page_id;row.source_row_id=uuid5('price-row:0',page.page_id)}}}
}
function mediaEntry(role,relative,alt){const data=safeRead(relative,DESIGN_FILE_CAP),assetId=uuid5(`asset:${relative}`);return{role,image_id:uuid5(`image:${role}`),asset_id:assetId,file_id:uuid5(`file:${relative}`),local_file:relative,storage_key:`img/${assetId}/main.webp`,kind:'main',mime:'image/webp',bytes:data.length,sha256:digest(data),alt}}
function assignImages(profile){const wanted=[['hero',profile.hero],...profile.steps.map((item,index)=>[`step-${index+1}`,item]),...profile.services.map((item,index)=>[`service-${index+1}`,item]),['photo-strip',profile.photo_strip]],media=wanted.map(([role,item])=>mediaEntry(role,item.image_path,item.alt));for(let i=0;i<wanted.length;i++){wanted[i][1].image_id=media[i].image_id;delete wanted[i][1].image_path}if(media.reduce((sum,item)=>sum+item.bytes,0)>DESIGN_TOTAL_CAP)failure('DESIGN_TOTAL');return media}
function validateBuilt(value){
  const keys=(item,wanted,code)=>{if(typeof item!=='object'||item===null||Array.isArray(item)||Object.keys(item).sort().join(',')!==[...wanted].sort().join(','))failure(code)};
  keys(value,['schema','policy','inputs','home','profile','media'],'PACKAGE_SCHEMA');if(value.schema!=='dev12-home-package-v1'||value.policy!=='approved_v4_core_owner_versioned_profile'||value.home.page_id!==HOME_ID||value.home.url!=='/'||value.profile.schema!=='home-profile-v1')failure('PACKAGE_SCHEMA');
  const profile=value.profile;if(profile.advantages.length!==8||profile.comparisons.length!==3||profile.steps.length!==5||profile.services.length!==8||profile.prices.length!==6||profile.works.length!==6||profile.media)failure('PROFILE_COUNTS');
  const rows=profile.prices.flatMap(group=>{if(group.rows.length<1||group.rows.length>8)failure('PRICE_COUNTS');return group.rows});if(rows.length!==47)failure('PRICE_COUNTS');
  const internalItems=[...profile.services,...profile.prices,...rows,...profile.works,profile.reviews];for(const item of internalItems)if(typeof item.url!=='string'||!/^\/[a-z0-9][a-z0-9\/-]*\/?$/u.test(item.url)||item.url.includes('?')||item.url.includes('#'))failure('PROFILE_URL');
  if(profile.reviews.heading!=='ОТЗЫВЫ'||profile.reviews.url!=='/reviews'||profile.reviews.label!=='ОТКРЫТЬ ВСЕ ВИДЕО-ОТЗЫВЫ')failure('REVIEWS_LOCAL');
  const media=value.media;if(media.length!==15)failure('MEDIA_COUNTS');const fields=['role','image_id','asset_id','file_id','local_file','storage_key','kind','mime','bytes','sha256','alt'];for(const item of media){keys(item,fields,'MEDIA_SCHEMA');if(item.kind!=='main'||item.mime!=='image/webp'||!/^media\/design-concepts\/[a-z0-9._\/-]+\.webp$/u.test(item.local_file)||!/^img\/[0-9a-f-]{36}\/main\.webp$/u.test(item.storage_key)||!Number.isSafeInteger(item.bytes)||item.bytes<1||item.bytes>DESIGN_FILE_CAP||!/^[0-9a-f]{64}$/u.test(item.sha256))failure('MEDIA_SCHEMA')}
  for(const field of ['role','image_id','asset_id','file_id','local_file','storage_key'])if(new Set(media.map(item=>item[field])).size!==media.length)failure('MEDIA_DUPLICATE');
  const imported=new Set(media.map(item=>item.image_id)),wanted=[profile.hero.image_id,profile.photo_strip.image_id,...profile.steps.map(item=>item.image_id),...profile.services.map(item=>item.image_id)];if(wanted.length!==15||wanted.some(id=>!imported.has(id))||new Set(wanted).size!==15)failure('MEDIA_REFERENCE');
  const allIds=[...profile.services.map(item=>item.id),...profile.prices.map(item=>item.id),...rows.map(item=>item.id),...profile.works.map(item=>item.id)];if(new Set(allIds).size!==allIds.length)failure('PROFILE_ID');
  if(profile.services.filter(item=>item.source_page_id).length!==4||rows.filter(item=>item.source_page_id).length!==2||rows.some(item=>(item.source_page_id===null)!==(item.source_row_id===null)))failure('SOURCE_BINDINGS');
  const strings=[];const walk=item=>{if(typeof item==='string')strings.push(item);else if(Array.isArray(item))item.forEach(walk);else if(item&&typeof item==='object')Object.values(item).forEach(walk)};walk(profile);if(strings.some(item=>item.includes('<script')||item.includes('<form')||item.includes('<iframe')||/^https?:\/\//u.test(item)))failure('PROFILE_UNSAFE');return value;
}
function build(){
  const approved=fixed('approved'),gallery=parseJson(fixed('gallery'),'GALLERY'),packages=['b','e','g','h','i','j','k'].map(name=>parseJson(fixed(name),'SOURCE'));
  if(gallery.schema!=='dev10-gallery-v1'||gallery.albums?.length!==17)failure('GALLERY_SCHEMA');const home=exactOne(packages[0].pages.filter(page=>page.page_id===HOME_ID&&page.url==='/'&&page.kind==='home'),'HOME_SOURCE');
  const profile={schema:'home-profile-v1',...htmlFacts(approved,gallery)};bindSources(profile,pageIndex(packages));const media=assignImages(profile);
  const result={schema:'dev12-home-package-v1',policy:'approved_v4_core_owner_versioned_profile',inputs:Object.fromEntries(Object.entries(FILES).filter(([name])=>name!=='package').map(([name,value])=>[name+'_sha256',value[2]])),home:{page_id:HOME_ID,url:'/',kind:'home',h1:home.h1,title:home.title,description:home.description,indexing_allowed:true},profile,media};
  validateBuilt(result);const encoded=canonical(result);if(encoded.length>FILES.package[1])failure('PACKAGE_SIZE');return result;
}
function parsePackage(buffer){const text=utf8(buffer,'PACKAGE_UTF8');if(text.includes('\r'))failure('PACKAGE_CANONICAL');let value;try{value=JSON.parse(text)}catch{failure('PACKAGE_JSON')}if(!canonical(value).equals(buffer))failure('PACKAGE_CANONICAL');return value}
function check(){const expected=build(),actual=validateBuilt(parsePackage(fixed('package')));if(JSON.stringify(actual)!==JSON.stringify(expected))failure('PACKAGE_CONTENT');const boundServices=actual.profile.services.filter(item=>item.source_page_id).length,boundPrices=actual.profile.prices.flatMap(group=>group.rows).filter(item=>item.source_page_id).length;process.stdout.write(JSON.stringify({schema:'dev12-home-check-v1',status:'pass',advantages:8,services:8,price_groups:6,price_rows:actual.profile.prices.flatMap(group=>group.rows).length,works:6,design_media:actual.media.length,design_bytes:actual.media.reduce((sum,item)=>sum+item.bytes,0),bound_services:boundServices,bound_prices:boundPrices,writes:0})+'\n')}
function selfcheck(){
  const expect=(code,action)=>{try{action();failure('SELFCHECK_EXPECTED')}catch(error){if(error.code!==code)throw error}};
  if(uuid5('x')===uuid5('y')||uuid5('x')!==uuid5('x'))failure('SELFCHECK_UUID');if(internal('https://estakada-service.ru/reviews')!=='/reviews'||internal('avtomojka.html')!=='/services/avtomojka')failure('SELFCHECK_URL');expect('INTERNAL_URL',()=>internal('https://evil.example/x'));expect('INTERNAL_URL',()=>internal('/reviews?q=1'));
  const fake={lstatSync(){return{size:1,isSymbolicLink(){return false},isFile(){return true}}},realpathSync(value){return value},readFileSync(){return Buffer.from('x')}};expect('FILE_PATH',()=>safeRead('../escape',1,null,fake));if(safeRead('safe',1,null,fake).length!==1)failure('SELFCHECK_FILE');expect('FILE_SIZE',()=>safeRead('safe',0,null,fake));
  const synthetic={pages:[{url:'/x',page_id:uuid5('p'),price_rows:[{cell:{kind:'amount',amount:'1500',from:true}}]}]},index=pageIndex([synthetic]);if(index.get('/x').page_id!==synthetic.pages[0].page_id||formatAmount(synthetic.pages[0].price_rows[0].cell)!=='от 1 500 ₽')failure('SELFCHECK_SOURCE');expect('SOURCE_DUPLICATE',()=>pageIndex([synthetic,synthetic]));
  const built=build(),missing=structuredClone(built);missing.profile.services.pop();expect('PROFILE_COUNTS',()=>validateBuilt(missing));const external=structuredClone(built);external.profile.reviews.url='https://example.test/';expect('PROFILE_URL',()=>validateBuilt(external));const duplicate=structuredClone(built);duplicate.media[1].asset_id=duplicate.media[0].asset_id;expect('MEDIA_DUPLICATE',()=>validateBuilt(duplicate));
  process.stdout.write('{"schema":"dev12-home-selfcheck-v1","status":"pass"}\n');
}

try{const mode=process.argv[2];if(mode==='--emit')process.stdout.write(canonical(build()));else if(mode==='--check')check();else if(mode==='--selfcheck')selfcheck();else failure('USAGE')}catch(error){process.stderr.write(`${error.code||'VALIDATION_FAILED'}\n`);process.exitCode=1}
