"""PDF for the beA / electronic court submission: PDF/A-2b identification and the ERVV checks that can be tested locally.

§ 2 Abs. 1 ERVV requires a printable, copyable and, where possible, searchable PDF with embedded fonts; the ERVB set
file-name rules (letters incl. umlauts and ß, digits, underscore, hyphen, one dot before the extension, at most 90 characters).
This module adds the PDF/A-2b markers (XMP metadata with pdfaid, sRGB output intent, file identifier) and reports what it
finds. It is not a certified PDF/A validator; the report says so.
"""
import io
import re
import unicodedata
from datetime import datetime, timezone
from xml.sax.saxutils import escape

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, DecodedStreamObject, DictionaryObject, NameObject, NumberObject, TextStringObject

STANDARD_14 = {'Courier', 'Courier-Bold', 'Courier-Oblique', 'Courier-BoldOblique', 'Helvetica', 'Helvetica-Bold', 'Helvetica-Oblique', 'Helvetica-BoldOblique',
               'Times-Roman', 'Times-Bold', 'Times-Italic', 'Times-BoldItalic', 'Symbol', 'ZapfDingbats'}
MAX_NAME = 90


def ervb_filename(name: str, extension: str = '.pdf') -> str:
    """File name allowed by the ERVB: German letters, digits, _ and -, at most 90 characters including the extension."""
    stem = unicodedata.normalize('NFC', name).strip()
    stem = re.sub(r'\s+', '_', stem)
    stem = re.sub(r'[^0-9A-Za-zÄÖÜäöüß_\-]', '', stem.replace('/', '-').replace('.', '-'))
    stem = re.sub(r'_+', '_', stem).strip('_-') or 'Schriftsatz'
    return stem[:MAX_NAME - len(extension)] + extension


def srgb_profile() -> bytes:
    from PIL import ImageCms
    return ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()


def xmp(title: str, author: str, moment: datetime) -> bytes:
    stamp = moment.strftime('%Y-%m-%dT%H:%M:%S+00:00')
    return f'''<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about="" xmlns:pdfaid="http://www.aiim.org/pdfa/ns/id/" xmlns:dc="http://purl.org/dc/elements/1.1/"
     xmlns:xmp="http://ns.adobe.com/xap/1.0/" xmlns:pdf="http://ns.adobe.com/pdf/1.3/">
   <pdfaid:part>2</pdfaid:part>
   <pdfaid:conformance>B</pdfaid:conformance>
   <dc:format>application/pdf</dc:format>
   <dc:title><rdf:Alt><rdf:li xml:lang="x-default">{escape(title)}</rdf:li></rdf:Alt></dc:title>
   <dc:creator><rdf:Seq><rdf:li>{escape(author)}</rdf:li></rdf:Seq></dc:creator>
   <xmp:CreateDate>{stamp}</xmp:CreateDate>
   <xmp:ModifyDate>{stamp}</xmp:ModifyDate>
   <xmp:CreatorTool>Rechtsassistentin Schimmelpilz</xmp:CreatorTool>
   <pdf:Producer>Rechtsassistentin Schimmelpilz</pdf:Producer>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>'''.encode('utf-8')


def fonts(reader: PdfReader):
    """(name, embedded) for every font used on the pages, including fonts inside form XObjects."""
    seen, found = set(), []

    def walk(resources, depth=0):
        if not resources or depth > 5:
            return
        resources = resources.get_object()
        for font in (resources.get('/Font') or {}).values():
            font = font.get_object()
            key = id(font)
            if key in seen:
                continue
            seen.add(key)
            subtype = font.get('/Subtype')
            name = str(font.get('/BaseFont', '')).lstrip('/')
            if subtype == '/Type3':
                found.append((name or 'Type3', True)); continue
            descriptor = font.get('/FontDescriptor')
            if subtype == '/Type0':
                descendants = font.get('/DescendantFonts') or []
                descriptor = descendants[0].get_object().get('/FontDescriptor') if descendants else None
            descriptor = descriptor.get_object() if descriptor else None
            embedded = bool(descriptor and any(key in descriptor for key in ('/FontFile', '/FontFile2', '/FontFile3')))
            found.append((name.split('+')[-1] if name else 'unbenannt', embedded))
        for xobject in (resources.get('/XObject') or {}).values():
            xobject = xobject.get_object()
            if xobject.get('/Subtype') == '/Form':
                walk(xobject.get('/Resources'), depth + 1)

    for page in reader.pages:
        walk(page.get('/Resources'))
    return found


def check(data: bytes) -> dict:
    issues, notes = [], []
    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted:
        return {'ok': False, 'issues': ['Die Datei ist verschlüsselt oder kennwortgeschützt; das beA nimmt sie so nicht an.'], 'notes': [], 'pages': 0}
    root = reader.trailer['/Root']
    names = root.get('/Names')
    if root.get('/OpenAction') or (names and '/JavaScript' in names.get_object()):
        issues.append('Die Datei enthält Skripte oder automatische Aktionen.')
    if root.get('/AcroForm'):
        notes.append('Die Datei enthält Formularfelder; vor dem Versand ausfüllen und möglichst als ausgedrucktes PDF speichern.')
    found = fonts(reader)
    missing = sorted({name for name, embedded in found if not embedded})
    if missing:
        issues.append('Nicht eingebettete Schriften: ' + ', '.join(missing) + ' (§ 2 Abs. 1 ERVV verlangt eingebettete Schriften).')
    text = ''.join((page.extract_text() or '') for page in reader.pages[:5]).strip()
    if not found or not text:
        notes.append('Keine Textebene gefunden (z. B. Scan). Durchsuchbarkeit nach § 2 Abs. 1 ERVV, soweit technisch möglich: vorher Texterkennung ausführen.')
    if len(data) > 200 * 1024 * 1024:
        issues.append('Die Datei ist größer als 200 MB.')
    return {'ok': not issues, 'issues': issues, 'notes': notes, 'pages': len(reader.pages), 'fonts': len(found)}


def to_pdfa(data: bytes, title: str, author: str = '') -> bytes:
    """Mark the PDF as PDF/A-2b: XMP metadata, sRGB output intent, file identifier, no encryption."""
    reader = PdfReader(io.BytesIO(data))
    writer = PdfWriter(clone_from=reader)
    moment = datetime.now(timezone.utc).replace(microsecond=0)
    metadata = DecodedStreamObject()
    metadata.set_data(xmp(title, author, moment))
    metadata.update({NameObject('/Type'): NameObject('/Metadata'), NameObject('/Subtype'): NameObject('/XML')})
    writer._root_object[NameObject('/Metadata')] = writer._add_object(metadata)
    profile = DecodedStreamObject()
    profile.set_data(srgb_profile())
    profile.update({NameObject('/N'): NumberObject(3)})
    intent = DictionaryObject({NameObject('/Type'): NameObject('/OutputIntent'), NameObject('/S'): NameObject('/GTS_PDFA1'),
                               NameObject('/OutputConditionIdentifier'): TextStringObject('sRGB IEC61966-2.1'), NameObject('/Info'): TextStringObject('sRGB IEC61966-2.1'),
                               NameObject('/DestOutputProfile'): writer._add_object(profile)})
    writer._root_object[NameObject('/OutputIntents')] = ArrayObject([writer._add_object(intent)])
    for key in ('/OpenAction', '/AA'):
        if key in writer._root_object:
            del writer._root_object[key]
    stamp = moment.strftime("D:%Y%m%d%H%M%S+00'00'")
    writer.add_metadata({'/Title': title, '/Author': author, '/Producer': 'Rechtsassistentin Schimmelpilz', '/Creator': 'Rechtsassistentin Schimmelpilz',
                         '/CreationDate': stamp, '/ModDate': stamp})
    writer.generate_file_identifiers()
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()
