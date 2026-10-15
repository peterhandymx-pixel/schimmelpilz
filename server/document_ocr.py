"""Local rasterization and OCR in a bounded disposable process."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT=Path(__file__).resolve().parents[1]
MODELS={'deu':'f5618a8b8d07f6c7a633ce243bf075bb90f4145bb15c9264734c7cc63aa33205','eng':'ed350f3752f81ee8f38769edc14d92d997dababe23b565c59879372cc46a2468'}
MAX_PIXELS=12000000


def node_path():
    bundled=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
    return os.getenv('OCR_NODE_PATH') or shutil.which('node') or (str(bundled) if bundled.is_file() else None)


def model_dir():
    return Path(os.getenv('OCR_MODEL_DIR',str(ROOT/'data/ocr-models')))


def available():
    return bool(node_path() and (ROOT/'server/ocr/node_modules/tesseract.js/package.json').is_file() and all((model_dir()/(lang+'.traineddata.gz')).is_file() for lang in MODELS))


def recognize(path,start_page,count,language):
    if not available():raise ValueError('ocr_unavailable')
    if language not in {'deu','eng','deu+eng'} or not 1<=start_page<=80 or not 1<=count<=12 or start_page+count-1>80:raise ValueError('invalid_range')
    for lang in language.split('+'):
        if hashlib.sha256((model_dir()/(lang+'.traineddata.gz')).read_bytes()).hexdigest()!=MODELS[lang]:raise ValueError('ocr_model_mismatch')
    suffix=path.suffix.lower()
    if suffix not in {'.pdf','.png','.jpg','.jpeg'}:raise ValueError('unsupported')
    pages=[]
    with TemporaryDirectory(prefix='schimmelpilz-ocr-') as temporary:
        folder=Path(temporary)
        if suffix=='.pdf':
            import pypdfium2 as pdfium
            from pypdf import PdfReader
            if PdfReader(path).is_encrypted:raise ValueError('encrypted')
            with pdfium.PdfDocument(str(path)) as pdf:
                total=len(pdf)
                if start_page>total:raise ValueError('invalid_range')
                for index in range(start_page-1,min(start_page-1+count,total)):
                    page=pdf[index]
                    try:
                        width,height=page.get_size()
                        if width*height*2.5**2>MAX_PIXELS:raise ValueError('size_limit')
                        bitmap=page.render(scale=2.5)
                        try:
                            image=bitmap.to_pil();target=folder/f'page-{index+1}.png'
                            image.save(target);image.close();pages.append({'unit_no':index+1,'path':str(target)})
                        finally:bitmap.close()
                    finally:page.close()
            kind='page'
        else:
            from PIL import Image,ImageOps
            if start_page!=1 or count!=1:raise ValueError('invalid_range')
            with Image.open(path) as image:
                if image.width*image.height>MAX_PIXELS:raise ValueError('size_limit')
                corrected=ImageOps.exif_transpose(image);rgba=corrected.convert('RGBA');background=Image.new('RGB',rgba.size,'white');background.paste(rgba,mask=rgba.getchannel('A'))
                target=folder/'image.png';background.save(target);background.close();rgba.close();corrected.close()
            pages=[{'unit_no':1,'path':str(target)}];total=1;kind='image'
        job={'pages':pages,'language':language,'model_dir':str(model_dir().resolve())}
        worker=subprocess.run([node_path(),str(ROOT/'server/ocr/worker.mjs')],input=json.dumps(job),text=True,encoding='utf-8',capture_output=True,timeout=90,check=True,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        data=json.loads(worker.stdout)
        remaining=120000;units=[];truncated=start_page!=1 or len(pages)<total
        if len(data['units'])!=len(pages):raise ValueError('ocr_failed')
        for item,expected in zip(data['units'],pages):
            if item['unit_no']!=expected['unit_no']:raise ValueError('ocr_failed')
            text=item['text'].replace('\x00','').strip();kept=text[:min(12000,remaining)]
            truncated|=len(kept)<len(text);remaining-=len(kept)
            units.append({'unit_no':item['unit_no'],'text':kept,'confidence':max(0,min(100,float(item['confidence'])))})
        return {'units':units,'truncated':truncated,'unit_kind':kind,'total_pages':total,'engine':data['engine'],'language':language,'models':{lang:MODELS[lang] for lang in language.split('+')}}


if __name__=='__main__':
    try:
        arguments=json.loads(sys.argv[2]);result=recognize(Path(sys.argv[1]),arguments['start_page'],arguments['count'],arguments['language'])
    except Exception as error:
        code=str(error) if str(error) in {'ocr_unavailable','ocr_model_mismatch','invalid_range','unsupported','encrypted','size_limit'} else 'ocr_failed'
        result={'error_code':code}
    print(json.dumps(result,ensure_ascii=True,allow_nan=False))
