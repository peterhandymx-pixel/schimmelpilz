"""Embedded fonts for every generated PDF (Bitstream Vera, shipped with reportlab).

§ 2 Abs. 1 ERVV requires embedded fonts for documents filed electronically; the PDF standard fonts (Helvetica & Co.)
are never embedded. register() makes BODY/BOLD available, including <b>/<i> in paragraphs, and embedded_styles()
switches a reportlab stylesheet over.
"""
from pathlib import Path

BODY, BOLD, ITALIC, BOLD_ITALIC = 'SchimmelpilzBody', 'SchimmelpilzBold', 'SchimmelpilzItalic', 'SchimmelpilzBoldItalic'


def register():
    import reportlab
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    folder = Path(reportlab.__file__).parent / 'fonts'
    known = set(pdfmetrics.getRegisteredFontNames())
    for name, file in ((BODY, 'Vera.ttf'), (BOLD, 'VeraBd.ttf'), (ITALIC, 'VeraIt.ttf'), (BOLD_ITALIC, 'VeraBI.ttf')):
        if name not in known:
            pdfmetrics.registerFont(TTFont(name, str(folder / file)))
    pdfmetrics.registerFontFamily(BODY, normal=BODY, bold=BOLD, italic=ITALIC, boldItalic=BOLD_ITALIC)


def embedded_styles(stylesheet):
    """A getSampleStyleSheet() whose styles use the embedded fonts instead of Helvetica/Times/Courier."""
    register()
    for style in stylesheet.byName.values():
        name = getattr(style, 'fontName', '') or ''
        bold, italic = 'Bold' in name, ('Oblique' in name or 'Italic' in name)
        style.fontName = BOLD_ITALIC if bold and italic else BOLD if bold else ITALIC if italic else BODY
    return stylesheet
