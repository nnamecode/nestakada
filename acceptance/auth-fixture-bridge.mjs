// Narrow runner transport. No engine access, application mutation implementation, or DB credentials.
import fs from 'node:fs';
import http from 'node:http';
try {
  let input='';for await(const chunk of process.stdin){input+=chunk;if(input.length>32768)throw new Error('size');}
  const request=JSON.parse(input), credential=JSON.parse(fs.readFileSync('/auth-fixture/control.json','utf8'));
  if(request.protocol!=='estakada-fixture-v1'||request.targetOrigin!=='http://host.docker.internal:8767'||
      !/^[a-f0-9]{48}$/u.test(request.nonce??'')||!['reset','observe','close'].includes(request.kind)||
      credential.origin!=='http://host.docker.internal:8770'||!/^[a-f0-9]{96}$/u.test(credential.token??''))throw new Error('scope');
  const reply=await new Promise((resolve,reject)=>{
    const req=http.request(`${credential.origin}/control`,{method:'POST',agent:false,headers:{authorization:`Bearer ${credential.token}`,'content-type':'application/json'}},response=>{
      let output='';response.setEncoding('utf8');response.on('data',chunk=>{output+=chunk;if(output.length>128*1024)response.destroy(new Error('size'));});
      response.on('error',reject);response.on('end',()=>{if(response.statusCode!==200)return reject(new Error('status'));try{resolve(JSON.parse(output));}catch{reject(new Error('json'));}});
    });req.on('error',reject);req.setTimeout(6000,()=>req.destroy(new Error('timeout')));req.end(JSON.stringify(request));
  });
  if(reply.protocol!==request.protocol||reply.nonce!==request.nonce||reply.targetOrigin!==request.targetOrigin||reply.ok!==true||
      (request.runId&&reply.runId!==request.runId))throw new Error('mismatch');
  process.stdout.write(JSON.stringify(reply));
} catch { process.stderr.write('AUTH_FIXED_FIXTURE_EXCHANGE_FAILED\n');process.exitCode=1; }
