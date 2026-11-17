"""Download-only all-day calendar events from explicitly recorded dates."""
import json
import uuid
from datetime import date, timedelta
from . import pdf_fonts
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response


def text(value):
    return str(value).replace('\\','\\\\').replace('\r\n','\n').replace('\r','\n').replace('\n','\\n').replace(';','\\;').replace(',','\\,')


def fold(line):
    pieces=[];current='';size=0
    for char in line:
        length=len(char.encode('utf-8'))
        if size+length>75:
            pieces.append(current);current=' ';size=1
        current+=char;size+=length
    pieces.append(current)
    return '\r\n'.join(pieces)


def calendar(events,stamp,alarm_days):
    lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Schimmelpilz//Manual case dates//DE','CALSCALE:GREGORIAN','METHOD:PUBLISH']
    for item in events:
        day=date.fromisoformat(item['due_on'])
        if day==date.max:
            raise HTTPException(422,'Date too far in future for calendar end')
        if item.get('time'):
            # Appointments with a time: one hour, in local (floating) time.
            start=day.isoformat().replace('-','')+'T'+item['time'].replace(':','')+'00'
            hour,minute=map(int,item['time'].split(':'));end_hour=min(hour+1,23)
            when=['DTSTART:'+start,'DTEND:'+day.isoformat().replace('-','')+'T%02d%02d00'%(end_hour,minute if end_hour>hour else 59)]
        else:
            when=['DTSTART;VALUE=DATE:'+day.isoformat().replace('-',''),'DTEND;VALUE=DATE:'+(day+timedelta(days=1)).isoformat().replace('-','')]
        lines.extend(['BEGIN:VEVENT','UID:'+item['uid']+'@schimmelpilz.local','DTSTAMP:'+stamp,*when,'SUMMARY:'+text(item['title']),'DESCRIPTION:'+text(item['note']),'STATUS:CONFIRMED','TRANSP:'+('OPAQUE' if item.get('time') else 'TRANSPARENT')])
        if alarm_days:
            lines.extend(['BEGIN:VALARM','TRIGGER:-P'+str(alarm_days)+'D','ACTION:DISPLAY','DESCRIPTION:'+text(item['title']),'END:VALARM'])
        lines.append('END:VEVENT')
    lines.append('END:VCALENDAR')
    return ('\r\n'.join(fold(line) for line in lines)+'\r\n').encode('utf-8')


WEEKDAYS = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']


def deadline_book_pdf(rows, start, end, firm):
    """Fristenbuch: open deadlines between start and end with Vorfrist and columns for the double check by hand."""
    import io
    from xml.sax.saxutils import escape
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    pdf_fonts.register()

    base = ParagraphStyle('base', fontName=pdf_fonts.BODY, fontSize=8.8, leading=11, textColor=colors.HexColor('#1f2d26'))
    bold = ParagraphStyle('bold', parent=base, fontName=pdf_fonts.BOLD)
    red = ParagraphStyle('red', parent=bold, textColor=colors.HexColor('#9b3d3d'))
    small = ParagraphStyle('small', parent=base, fontSize=8, leading=10, textColor=colors.HexColor('#5d6b60'))
    title = ParagraphStyle('title', parent=base, fontName=pdf_fonts.BOLD, fontSize=15, leading=19, spaceAfter=3)
    cell = lambda text, style=base: Paragraph(escape(str(text or '')), style)

    def when(value):
        if not value:
            return '-'
        day = date.fromisoformat(value)
        return WEEKDAYS[day.weekday()] + ' ' + day.strftime('%d.%m.%Y')

    def box():
        mark = Table([['']], colWidths=[4 * mm], rowHeights=[4 * mm])
        mark.setStyle(TableStyle([('FONTNAME', (0, 0), (-1, -1), pdf_fonts.BODY), ('BOX', (0, 0), (-1, -1), 0.7, colors.HexColor('#1f2d26'))]))
        return mark
    header = [cell('Fristende', bold), cell('Vorfrist', bold), cell('Akte', bold), cell('Frist / Gegenstand', bold), cell('Art', bold), cell('notiert', bold), cell('erledigt', bold), cell('Kontrolle', bold)]
    table_rows = [header]
    styles = [('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LINEBELOW', (0, 0), (-1, 0), 0.8, colors.HexColor('#2f5d4d')),
              ('LINEBELOW', (0, 1), (-1, -1), 0.3, colors.HexColor('#c9d3cc')), ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
              ('LEFTPADDING', (0, 0), (-1, -1), 3), ('RIGHTPADDING', (0, 0), (-1, -1), 3)]
    for index, row in enumerate(rows, start=1):
        notfrist = row['kind'] == 'notfrist'
        table_rows.append([cell(when(row['due_on']), red if notfrist else bold), cell(when(row.get('pre_on'))), cell(row['reference']),
                           [cell(row['title'], bold if notfrist else base)] + ([cell(row['case_title'], small)] if row.get('case_title') else []),
                           cell('NOTFRIST' if notfrist else row['label'], red if notfrist else base), box(), box(), cell('')])
        if notfrist:
            styles.append(('BACKGROUND', (0, index), (-1, index), colors.HexColor('#fbefed')))
    table = Table(table_rows, colWidths=[31 * mm, 29 * mm, 34 * mm, None, 24 * mm, 18 * mm, 19 * mm, 30 * mm], repeatRows=1)
    table.setStyle(TableStyle([('FONTNAME', (0, 0), (-1, -1), pdf_fonts.BODY)] + styles))
    period = date.fromisoformat(start).strftime('%d.%m.%Y') + ' bis ' + date.fromisoformat(end).strftime('%d.%m.%Y')
    story = [Paragraph('Fristenbuch', title), cell(f'{firm} · Zeitraum {period} · {len(rows)} offene {"Frist" if len(rows) == 1 else "Fristen"}', small), Spacer(1, 6)]
    story.append(table if rows else cell('Keine offenen Fristen im gewählten Zeitraum.'))
    story += [Spacer(1, 8), cell('Spalte "notiert": Frist und Vorfrist im Kalender eingetragen; "erledigt": fristwahrende Handlung ausgeführt; "Kontrolle": Zeichen der zweiten Person (Vier-Augen-Prinzip). '
                                 'Fristen sind Rechenergebnisse aus den erfassten Daten und vor Ablauf selbst zu prüfen.', small)]

    def footer(canvas, doc):
        canvas.saveState(); canvas.setFont(pdf_fonts.BODY, 7.5); canvas.setFillColor(colors.HexColor('#5d6b60'))
        canvas.drawString(15 * mm, 9 * mm, 'Fristenbuch ' + period)
        canvas.drawRightString(landscape(A4)[0] - 15 * mm, 9 * mm, f'Seite {doc.page}')
        canvas.restoreState()

    output = io.BytesIO()
    SimpleDocTemplate(output, pagesize=landscape(A4), leftMargin=15 * mm, rightMargin=15 * mm, topMargin=14 * mm, bottomMargin=15 * mm,
                      title='Fristenbuch', author='', initialFontName=pdf_fonts.BODY).build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()


KIND_DE={'appointment':'Termin','deadline':'Frist','notfrist':'NOTFRIST','resubmission':'Wiedervorlage'}
KIND_EN={'appointment':'Appointment','deadline':'Deadline','notfrist':'STATUTORY DEADLINE','resubmission':'Follow-up'}


def router(db,require_user,now,pre_deadline=lambda due_on,days:None):
    routes=APIRouter()

    @routes.get('/api/tasks/calendar.ics')
    def export(case_id:uuid.UUID|None=None,alarm_days:int=Query(default=1,ge=0,le=30),lang:str=Query(default='de',pattern='^(de|en)$'),user:dict=Depends(require_user)):
        manual='Manuell erfasster Termin; keine automatische Fristberechnung.' if lang=='de' else 'Manually recorded date; no automatic legal deadline calculation.'
        with db() as connection:
            if case_id and not connection.execute('SELECT 1 FROM cases WHERE id=? AND user_id=?',(str(case_id),user['id'])).fetchone():
                raise HTTPException(404,'Case not found')
            condition=' AND id=?' if case_id else ' AND archived_at IS NULL'
            cases=connection.execute('SELECT * FROM cases WHERE user_id=?'+condition,(user['id'],str(case_id)) if case_id else (user['id'],)).fetchall()
            events=[]
            for case in cases:
                for task in connection.execute('SELECT * FROM tasks WHERE case_id=? AND completed=0 AND due_on IS NOT NULL',(case['id'],)):
                    kind=task['kind'] if 'kind' in task.keys() else 'task'
                    label=(KIND_DE if lang=='de' else KIND_EN).get(kind,'')
                    title=case['reference']+' · '+(label+': ' if label else '')+task['title']
                    events.append({'uid':'task-'+task['id'],'due_on':task['due_on'],'time':task['due_time'] if kind=='appointment' else None,'title':title,'note':manual+'\n'+case['title']+'\n'+task['note']})
                    pre=pre_deadline(task['due_on'],task['pre_days']) if 'pre_days' in task.keys() else None
                    if pre:
                        events.append({'uid':'pre-'+task['id'],'due_on':pre,'title':case['reference']+' · '+('VORFRIST' if lang=='de' else 'PRE-DEADLINE')+': '+task['title'],'note':('Fristablauf am ' if lang=='de' else 'Deadline expires on ')+task['due_on']+'\n'+case['title']})
                details=json.loads(case['details'])
                if details.get('deadline') and details.get('status')!='closed':
                    events.append({'uid':'case-deadline-'+case['id'],'due_on':details['deadline'],'title':case['reference']+' · '+(details.get('deadline_note') or ('Erfasste Aktenfrist' if lang=='de' else 'Recorded case deadline')),'note':manual+'\n'+case['title']})
        events.sort(key=lambda item:(item['due_on'],item['uid']))
        if len(events)>10000:
            raise HTTPException(413,'Too many calendar entries; export a single case')
        stamp=now()[:19].replace('-','').replace(':','')+'Z'
        return Response(calendar(events,stamp,alarm_days),media_type='text/calendar; charset=utf-8',headers={'Content-Disposition':'attachment; filename="Schimmelpilz-Termine.ics"'})

    @routes.get('/api/tasks/deadline-book.pdf')
    def deadline_book(start:date|None=None,end:date|None=None,include_tasks:bool=False,user:dict=Depends(require_user)):
        today=date.fromisoformat(now()[:10])
        start=start or today-timedelta(days=7);end=end or today+timedelta(days=60)
        if end<start or (end-start).days>731:
            raise HTTPException(422,'Invalid period')
        kinds=('deadline','notfrist','task','appointment','resubmission') if include_tasks else ('deadline','notfrist')
        rows=[]
        with db() as connection:
            allowed=user.get('allowed_cases')
            for case in connection.execute('SELECT * FROM cases WHERE user_id=? AND archived_at IS NULL',(user['id'],)):
                if allowed is not None and case['id'] not in allowed:
                    continue
                for task in connection.execute('SELECT * FROM tasks WHERE case_id=? AND completed=0 AND due_on IS NOT NULL',(case['id'],)):
                    if task['kind'] not in kinds or not start.isoformat()<=task['due_on']<=end.isoformat():
                        continue
                    rows.append({'due_on':task['due_on'],'pre_on':pre_deadline(task['due_on'],task['pre_days']),'reference':case['reference'],'case_title':case['title'],
                                 'title':task['title'],'kind':task['kind'],'label':KIND_DE.get(task['kind'],'Aufgabe')})
                details=json.loads(case['details'] or '{}')
                if details.get('deadline') and details.get('status')!='closed' and start.isoformat()<=details['deadline']<=end.isoformat():
                    rows.append({'due_on':details['deadline'],'pre_on':pre_deadline(details['deadline'],7),'reference':case['reference'],'case_title':case['title'],
                                 'title':details.get('deadline_note') or 'Aktenfrist','kind':'deadline','label':'Aktenfrist'})
            firm=connection.execute('SELECT organisation, full_name FROM users WHERE id=?',(user['id'],)).fetchone()
        rows.sort(key=lambda item:(item['due_on'],item['kind']!='notfrist',item['reference']))
        content=deadline_book_pdf(rows,start.isoformat(),end.isoformat(),(firm['organisation'] or firm['full_name']) if firm else '')
        return Response(content,media_type='application/pdf',headers={'Content-Disposition':'attachment; filename="Fristenbuch.pdf"','Cache-Control':'no-store'})

    return routes
