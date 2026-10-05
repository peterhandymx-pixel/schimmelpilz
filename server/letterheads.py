"""Preserve letterhead PDF page content and compose draft text in a chosen frame."""
import io
import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.sax.saxutils import escape

from pypdf import PdfReader, PdfWriter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer


def office_path():
    root = Path(__file__).resolve().parents[1]
    choices = [os.getenv('SOFFICE_PATH'), shutil.which('soffice'), shutil.which('soffice.exe'), str(root / 'data/libreoffice/program/soffice.exe'), 'C:/Program Files/LibreOffice/program/soffice.exe']
    return next((value for value in choices if value and Path(value).is_file()), None)


def normalize(source, output):
    if source.suffix.lower() == '.pdf':
        shutil.copyfile(source, output)
    else:
        office = office_path()
        if not office:
            raise ValueError('converter_unavailable')
        with TemporaryDirectory(prefix='schimmelpilz-office-') as temporary:
            folder = Path(temporary)
            # Separate profile, macros disabled, no interaction with desktop documents.
            profile = folder / 'profile'
            registry = profile / 'user/registrymodifications.xcu'
            registry.parent.mkdir(parents=True)
            registry.write_text('<?xml version="1.0"?><oor:items xmlns:oor="http://openoffice.org/2001/registry"><item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop></item><item oor:path="/org.openoffice.Office.Common/Load"><prop oor:name="UpdateLinkMode" oor:op="fuse"><value>0</value></prop></item></oor:items>', encoding='utf-8')
            subprocess.run([office, '-env:UserInstallation=' + profile.as_uri(), '--headless', '--nologo', '--norestore', '--convert-to', 'pdf:writer_pdf_Export', '--outdir', str(folder), str(source.resolve())], check=True, capture_output=True, timeout=60, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            result = folder / (source.stem + '.pdf')
            if not result.is_file():
                raise ValueError('conversion_failed')
            shutil.copyfile(result, output)
    reader = PdfReader(output)
    if reader.is_encrypted or not 1 <= len(reader.pages) <= 2:
        raise ValueError('one_or_two_pages_required')
    dimensions = []
    for page in reader.pages:
        # Plain letter paper only; reject interactive actions rather than preserve them.
        if page.get('/Annots') or page.rotation or list(page.mediabox.lower_left) != [0, 0] or page.cropbox != page.mediabox:
            raise ValueError('plain_pdf_required')
        width, height = float(page.mediabox.width), float(page.mediabox.height)
        if not 140 * mm <= width <= 250 * mm or not 200 * mm <= height <= 360 * mm or width >= height:
            raise ValueError('portrait_letter_paper_required')
        dimensions.append((width, height))
    if any(dim != dimensions[0] for dim in dimensions):
        raise ValueError('matching_page_sizes_required')
    # Remove document actions/attachments while retaining each page's drawing instructions.
    writer = PdfWriter()
    for page in reader.pages:
        for key in ('/AA', '/A'):
            if key in page:
                del page[key]
        writer.add_page(page)
    with output.open('wb') as stream:
        writer.write(stream)
    return {'pages': len(reader.pages), 'width_mm': round(dimensions[0][0] / mm, 2), 'height_mm': round(dimensions[0][1] / mm, 2)}


def compose_pdf(body, template, layout):
    reader = PdfReader(template) if template else None
    size = (float(reader.pages[0].mediabox.width), float(reader.pages[0].mediabox.height)) if reader else (210 * mm, 297 * mm)
    left, right, top, bottom = (layout[name] * mm for name in ('left_mm', 'right_mm', 'top_mm', 'bottom_mm'))
    if size[0] - left - right < 70 * mm or size[1] - top - bottom < 70 * mm:
        raise ValueError('body_frame_too_small')
    # Bundled Bitstream Vera font provides embedded glyphs including German umlauts.
    import reportlab
    font_path = Path(reportlab.__file__).parent / 'fonts/Vera.ttf'
    if 'SchimmelpilzBody' not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont('SchimmelpilzBody', str(font_path)))
    font_size = layout.get('font_size', 11)
    style = ParagraphStyle('Body', fontName='SchimmelpilzBody', fontSize=font_size, leading=font_size * 1.45, spaceAfter=0, splitLongWords=True)
    overlay = io.BytesIO()
    document = SimpleDocTemplate(overlay, pagesize=size, leftMargin=left, rightMargin=right, topMargin=top, bottomMargin=bottom, title='Schimmelpilz Entwurf')
    paragraphs = []
    for line in body.replace('\r\n', '\n').replace('\r', '\n').split('\n'):
        if line:
            paragraphs.append(Paragraph(escape(line).replace('\t', '    '), style))
        else:
            paragraphs.append(Spacer(1, font_size * 1.45))
    document.build(paragraphs or [Paragraph(' ', style)])
    contents = PdfReader(overlay)
    writer = PdfWriter()
    for index, content in enumerate(contents.pages):
        if reader:
            # Reset clone caching so reusing a template page never reuses a merged stream.
            writer.reset_translation(reader)
            base = writer.add_page(reader.pages[min(index, len(reader.pages) - 1)])
            base.merge_page(content)
        else:
            writer.add_page(content)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()
