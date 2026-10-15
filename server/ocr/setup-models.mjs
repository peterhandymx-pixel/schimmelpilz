import {mkdir,writeFile,readFile,rename} from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';

const folder=path.resolve(process.argv[2] || 'data/ocr-models');
await mkdir(folder,{recursive:true});
const manifest=[];
const hashes={deu:'f5618a8b8d07f6c7a633ce243bf075bb90f4145bb15c9264734c7cc63aa33205',eng:'ed350f3752f81ee8f38769edc14d92d997dababe23b565c59879372cc46a2468'};
for(const lang of ['deu','eng']){
  const url=`https://tessdata.projectnaptha.com/4.0.0/${lang}.traineddata.gz`;
  const target=path.join(folder,`${lang}.traineddata.gz`);
  let bytes;
  try{bytes=await readFile(target);}catch{
    const response=await fetch(url,{signal:AbortSignal.timeout(60000)});
    if(!response.ok)throw new Error(`Model download failed: ${lang}`);
    bytes=Buffer.from(await response.arrayBuffer());
    if(bytes.length>50*1024*1024 || bytes[0]!==0x1f || bytes[1]!==0x8b)throw new Error('Invalid language model');
    if(createHash('sha256').update(bytes).digest('hex')!==hashes[lang])throw new Error('Language model hash changed; review before updating');
    const pending=target+`.${process.pid}.tmp`;
    await writeFile(pending,bytes,{flag:'wx'});await rename(pending,target);
  }
  const digest=createHash('sha256').update(bytes).digest('hex');
  if(digest!==hashes[lang])throw new Error('Stored language model hash mismatch');
  manifest.push({lang,url,bytes:bytes.length,sha256:digest});
}
await writeFile(path.join(folder,'models.json'),JSON.stringify(manifest,null,2));
console.log(JSON.stringify(manifest));
