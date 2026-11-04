"""Download-only all-day calendar events from explicitly recorded dates."""
import json
import uuid
from datetime import date, timedelta
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

    return routes
