"""Bounded text extraction in a short-lived subprocess; never executes uploads."""
import json
import sys
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

MAX_UNITS = 80
MAX_UNIT_CHARS = 12000
MAX_TOTAL_CHARS = 120000


def extract(path):
    suffix = path.suffix.lower()
    if suffix not in {".pdf", ".docx"}:
        return {"status": "unsupported", "error_code": "unsupported", "units": [], "truncated": False, "unit_kind": "section"}
    units, truncated, remaining = [], False, MAX_TOTAL_CHARS
    kind = "page" if suffix == ".pdf" else "section"
    if suffix == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(path)
        if reader.is_encrypted:
            raise ValueError("encrypted")
        total = len(reader.pages)
        items = reader.pages[:MAX_UNITS]
        truncated = total > MAX_UNITS
        def get_text(page):
            contents = page.get_contents()
            if contents and len(contents.get_data()) > 10 * 1024 * 1024:
                raise ValueError("size_limit")
            return page.extract_text() or ""
    else:
        with ZipFile(path) as archive:
            infos = archive.infolist()
            if len(infos) > 2000 or sum(item.file_size for item in infos) > 20 * 1024 * 1024:
                raise ValueError("size_limit")
            info = archive.getinfo("word/document.xml")
            if info.file_size > 5 * 1024 * 1024:
                raise ValueError("size_limit")
            xml = archive.read(info)
        if b"<!DOCTYPE" in xml.upper() or b"<!ENTITY" in xml.upper():
            raise ValueError("invalid_document")
        body = ET.fromstring(xml).find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}body")
        if body is None:
            raise ValueError("invalid_document")
        ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        # Each nonempty body paragraph/table is a section, never a guessed page.
        items = []
        for block in body:
            parts = []
            for node in block.iter():
                if node.tag == ns + "t":
                    parts.append(node.text or "")
                elif node.tag in {ns + "tab", ns + "tc"}:
                    parts.append("\t")
                elif node.tag in {ns + "br", ns + "p"}:
                    parts.append("\n")
            text = "".join(parts).strip()
            if text:
                items.append(text)
        truncated = len(items) > MAX_UNITS
        items = items[:MAX_UNITS]
        get_text = lambda text: text
    for index, item in enumerate(items, 1):
        text = get_text(item).replace("\x00", "").strip()
        kept = text[:min(MAX_UNIT_CHARS, remaining)]
        truncated |= len(kept) < len(text)
        units.append({"unit_no": index, "text": kept})
        remaining -= len(kept)
        if remaining <= 0:
            truncated = True
            break
    return {"status": "ready" if any(unit["text"] for unit in units) else "no_text", "unit_kind": kind, "units": units or [{"unit_no": 1, "text": ""}], "truncated": truncated, "error_code": None}


if __name__ == "__main__":
    try:
        result = extract(Path(sys.argv[1]))
    except Exception as error:
        code = str(error) if str(error) in {"encrypted", "size_limit"} else "invalid_document"
        result = {"status": "failed", "error_code": code, "units": [], "truncated": False, "unit_kind": "page" if Path(sys.argv[1]).suffix.lower() == ".pdf" else "section"}
    print(json.dumps(result, ensure_ascii=True))
