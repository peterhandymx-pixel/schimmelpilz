import {useEffect, useRef, useState} from 'react';
import {getDocument, GlobalWorkerOptions} from 'pdfjs-dist';
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';

GlobalWorkerOptions.workerSrc = workerUrl;
const fontFiles = import.meta.glob('/node_modules/pdfjs-dist/standard_fonts/*', {query:'?url', import:'default', eager:true});
const cmapFiles = import.meta.glob('/node_modules/pdfjs-dist/cmaps/*.bcmap', {query:'?url', import:'default', eager:true});
const wasmFiles = import.meta.glob('/node_modules/pdfjs-dist/wasm/*.wasm', {query:'?url', import:'default', eager:true});
const assetUrls = Object.fromEntries(Object.entries({...fontFiles, ...cmapFiles, ...wasmFiles}).map(([path, url]) => [path.split('/').pop(), url]));
class LocalPdfAssets {
  async fetch({filename}) {
    const url = assetUrls[filename];
    if (!url) throw new Error('PDF asset unavailable');
    const response = await fetch(url);
    if (!response.ok) throw new Error('PDF asset failed');
    return new Uint8Array(await response.arrayBuffer());
  }
}

export default function PdfPreview({src, lang, title}) {
  const de = lang === 'de', canvas = useRef(null);
  const [pdf, setPdf] = useState(null), [page, setPage] = useState(1), [busy, setBusy] = useState(true), [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    setPdf(null); setPage(1); setError(''); setBusy(true);
    const loading = getDocument({url:src, isEvalSupported:false, useWorkerFetch:false, BinaryDataFactory:LocalPdfAssets});
    loading.promise.then(document => { if (active) setPdf(document); }).catch(() => { if (active) { setError(de ? 'PDF-Vorschau konnte nicht geladen werden.' : 'Could not load PDF preview.'); setBusy(false); } });
    return () => { active = false; loading.destroy(); };
  }, [src]);
  useEffect(() => {
    if (!pdf || !canvas.current) return;
    let active = true, rendering;
    setBusy(true); setError('');
    pdf.getPage(page).then(sheet => {
      if (!active) return;
      const viewport = sheet.getViewport({scale:1.6});
      const surface = canvas.current;
      surface.width = Math.ceil(viewport.width); surface.height = Math.ceil(viewport.height);
      rendering = sheet.render({canvasContext:surface.getContext('2d'), viewport});
      return rendering.promise;
    }).then(() => { if (active) setBusy(false); }).catch(failure => { if (active && failure.name !== 'RenderingCancelledException') { setError(de ? 'Seite konnte nicht angezeigt werden.' : 'Could not render this page.'); setBusy(false); } });
    return () => { active = false; rendering?.cancel(); };
  }, [pdf, page]);
  return <section className="pdf-canvas-preview" aria-label={title}><div className="pdf-canvas-controls"><button type="button" className="desk-button" disabled={!pdf || page === 1 || busy} onClick={() => setPage(value => value-1)}>{de ? 'Vorherige Seite' : 'Previous page'}</button><span>{pdf ? `${de ? 'Seite' : 'Page'} ${page} ${de ? 'von' : 'of'} ${pdf.numPages}` : '…'}</span><button type="button" className="desk-button" disabled={!pdf || page === pdf.numPages || busy} onClick={() => setPage(value => value+1)}>{de ? 'Nächste Seite' : 'Next page'}</button></div>{busy && <p role="status">{de ? 'PDF wird angezeigt …' : 'Rendering PDF …'}</p>}{error && <p className="storage-error" role="alert">{error}</p>}<canvas ref={canvas} role="img" aria-label={`${title} · ${de ? 'Seite' : 'Page'} ${page}`} /></section>;
}
