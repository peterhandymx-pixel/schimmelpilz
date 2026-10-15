import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {createWorker} from 'tesseract.js';

let input='';
for await (const chunk of process.stdin){input+=chunk;if(input.length>20000)throw new Error('Input too large');}
const job=JSON.parse(input);
if(!['deu','eng','deu+eng'].includes(job.language)||!Array.isArray(job.pages)||job.pages.length<1||job.pages.length>12)throw new Error('Invalid OCR job');
const folder=path.resolve(job.model_dir);
for(const lang of job.language.split('+'))await readFile(path.join(folder,`${lang}.traineddata.gz`));
const worker=await createWorker(job.language,1,{langPath:folder,cacheMethod:'none',gzip:true,logger:()=>{},errorHandler:()=>{}});
try{
  await worker.setParameters({user_defined_dpi:'180',preserve_interword_spaces:'1'});
  const units=[];
  for(const page of job.pages){
    const {data}=await worker.recognize(await readFile(page.path));
    units.push({unit_no:page.unit_no,text:data.text,confidence:data.confidence});
  }
  process.stdout.write(JSON.stringify({units,engine:'tesseract.js-7.0.0',language:job.language}));
}finally{await worker.terminate();}
