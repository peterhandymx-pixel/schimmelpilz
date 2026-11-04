"""Competent court for a place, from the official German directory of places and courts (Orts- und Gerichtsverzeichnis).

Only the subject area, postal code and place name leave the server; no names or case data. Results are cached for a week.
"""
import html
import re
import time
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi import APIRouter, Depends, HTTPException, Query

DIRECTORY = 'https://www.justizadressen.nrw.de/de/justiz/gericht'
# Subject areas offered by the directory that the app uses.
AREAS = {'zivil', 'familie', 'nachlass', 'mahn', 'insolvver', 'insolv', 'zwangsvoll', 'arbeit', 'sozial', 'verwaltung', 'finanz', 'betreu', 'grundbuch'}
CACHE_SECONDS = 7 * 24 * 3600
_cache = {}


class DirectoryUnavailable(RuntimeError):
    pass


def _text(fragment):
    return html.unescape(re.sub(r'<[^>]+>', '', fragment.replace('<wbr>', ''))).strip()


def _address(block, label):
    match = re.search(r'<strong>' + label + r'</strong><br>(.*?)</address>', block, re.S)
    if not match:
        return []
    return [line for line in (_text(part) for part in match.group(1).split('<br>')) if line]


def parse(page):
    """Courts in the order the directory lists them (first instance first), plus its notice if the place was ambiguous."""
    start = page.find('Gesucht wurde')
    if start < 0:
        # Several places or streets share the postal code but not the court: the directory asks which one is meant.
        intro = re.search(r'<p>([^<]*(?:<a [^>]*>[^<]*</a>[^<]*)*(?:Bitte wählen|bitte wählen)[^<]*(?:<[^>]+>[^<]*)*?)</p>', page, re.S)
        choices = [{'label': _text(label), 'query': html.unescape(query)} for query, label in
                   re.findall(r'<a href="' + re.escape(DIRECTORY) + r'\?([^"]*key=[^"]*)">(?:<i[^>]*></i>)?\s*(.*?)</a>', page, re.S)]
        notice = re.search(r'<div class="alert[^"]*">(.*?)</div>', page, re.S)
        return {'courts': [], 'choices': choices, 'notice': _text(intro.group(1)) if intro else _text(notice.group(1)) if notice else ''}
    body = page[start:]
    courts = []
    for heading, block in re.findall(r'<h6>(.*?)</h6>(.*?)(?=<h6>|<footer|$)', body, re.S):
        name, _, remark = heading.partition('<br>')
        name = _text(name)
        if not name or 'gericht' not in name.lower() and 'staatsanwaltschaft' not in name.lower():
            continue
        phone = re.search(r'<span>Telefon:</span>\s*([^<]+)', block)
        xjustiz = re.search(r'XJustiz-ID:</span>\s*([^<]+)', block)
        website = re.search(r'<span>Internet:</span>\s*<a href="([^"]+)"', block)
        courts.append({'name': name, 'remark': _text(remark), 'postal': _address(block, 'Postanschrift'), 'street': _address(block, 'Lieferanschrift'),
                       'phone': phone.group(1).strip() if phone else '', 'xjustiz_id': xjustiz.group(1).strip() if xjustiz else '',
                       'website': website.group(1) if website else ''})
    return {'courts': courts, 'choices': [], 'notice': ''}


# A choice the directory offered (street or place) is sent back as given; only its own parameters are accepted.
CHOICE = re.compile(r'^(?:(?:key|ang|plz|ort|str)=[\w%+!.\-]*&?)+$')


def lookup(area, postal_code, place, choice=''):
    key = (area, postal_code, place.lower(), choice)
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < CACHE_SECONDS:
        return hit[1]
    query = choice or urlencode({'ang': area, 'plzort': f'{postal_code} {place}'.strip()})
    request = Request(f'{DIRECTORY}?{query}', headers={'User-Agent': 'Mozilla/5.0 (Schimmelpilz court lookup)'})
    try:
        with urlopen(request, timeout=12) as response:
            page = response.read(2_000_000).decode('utf-8', 'replace')
    except (URLError, TimeoutError, OSError) as error:
        raise DirectoryUnavailable(str(error)) from error
    result = {**parse(page), 'source': f'{DIRECTORY}?{query}', 'checked_at': time.strftime('%Y-%m-%d')}
    if result['courts']:
        _cache[key] = (time.time(), result)
    return result


def router(require_user):
    routes = APIRouter()

    @routes.get('/api/courts/lookup')
    def find(area: str = Query(max_length=20), plz: str = Query(default='', pattern=r'^(\d{5})?$'), ort: str = Query(default='', max_length=60), choice: str = Query(default='', max_length=300), user: dict = Depends(require_user)):
        if area not in AREAS:
            raise HTTPException(422, 'unknown_area')
        if choice and (not CHOICE.match(choice) or f'ang={area}' not in choice):
            raise HTTPException(422, 'invalid_choice')
        if not choice and not plz and len(ort.strip()) < 2:
            raise HTTPException(422, 'place_required')
        try:
            return lookup(area, plz, re.sub(r'[^\w\s\-.äöüÄÖÜß]', '', ort).strip(), choice)
        except DirectoryUnavailable:
            raise HTTPException(503, 'directory_unavailable') from None

    return routes
