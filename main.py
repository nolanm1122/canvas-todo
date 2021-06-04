import json
import re
from _datetime import timedelta, datetime

import requests
from canvasapi.course import Course
from dateutil import parser
from pushbullet import Pushbullet
from retry.api import retry_call
from requests.exceptions import ConnectionError
import tika
from tika import parser as tika_parser

from canvasapi.canvas import Canvas
from canvasapi.assignment import Assignment
from settings import *
from todo import Client as ToDoClient

RETRY_KWARGS = dict(exceptions=(ConnectionError,), tries=3)


def element_exists(l, key, value):
    for elem in l:
        if elem[key] == value:
            return elem, True
    return None, False


def main():
    pb = Pushbullet(PB_TOKEN)
    try:
        tika.initVM()
        todo_client = ToDoClient(TODO_REFRESH_TOKEN, TODO_CLIENT_ID)
        todo_lists = retry_call(todo_client.get_lists, **RETRY_KWARGS)
        canvas = Canvas('https://uiowa.instructure.com', CANVAS_API_KEY)
        courses = retry_call(canvas.get_courses, fkwargs=dict(enrollment_state='active'), **RETRY_KWARGS)
        for course in courses:
            if course.start_at_date < datetime.now(tz=pytz.utc) - timedelta(weeks=4*5):
                continue
            l, exists = element_exists(todo_lists, 'Name', course.name)
            if not exists:
                l = retry_call(todo_client.create_list, fargs=(course.name,), **RETRY_KWARGS)
            tasks = retry_call(todo_client.get_tasks, fargs=(l['Id'],), **RETRY_KWARGS)
            if 'Switching Theory' in course.name:
                update_switching_theory(course, l, pb, tasks, todo_client)
                continue
            for a in retry_call(course.get_assignments, fkwargs=dict(bucket='future'),
                                **RETRY_KWARGS):
                _, exists = element_exists(tasks, 'Subject', a.name)
                due_local = None
                if not exists:
                    if getattr(a, 'due_at', None):
                        due_utc = parser.parse(a.due_at)
                        due_local = due_utc.replace(tzinfo=pytz.utc).astimezone(TZ)
                        due_local = TZ.normalize(due_local) - timedelta(hours=6)
                    j = retry_call(todo_client.create_task,
                                   fargs=(a.name, getattr(a, 'html_url', ''), due_local,
                                          l['Id']), **RETRY_KWARGS)
                    if 'Digital Image Processing' in course.name:
                        fname, hw_pdf = get_hw_pdf_dip(course, a)
                        retry_call(todo_client.add_file, fargs=(j["Id"], fname, hw_pdf), **RETRY_KWARGS)
                    pb.push_note('Canvas-ToDo', json.dumps(j, indent=4, sort_keys=True))
                    print('[+] Created task - ' + a.name)
    except Exception as e:
        # pb.push_note('Canvas-ToDo', traceback.format_exc())
        raise e


def update_switching_theory(course, l, pb, tasks, todo_client):
    latest_hw_num, latest_hw = get_latest_hw_st(course)
    name = 'Homework ' + str(latest_hw_num)
    _, exists = element_exists(tasks, 'Subject', name)
    if not exists:
        r = requests.get(latest_hw.url)
        text = tika_parser.from_buffer(r.content)['content']
        due_date = parser.parse(re.findall(r'(11:59.*?2020)', text)[0])
        due_date = due_date - timedelta(hours=5)
        j = retry_call(todo_client.create_task, fargs=(name, '', due_date, l['Id']), **RETRY_KWARGS)
        retry_call(todo_client.add_file, fargs=(j["Id"], latest_hw.filename, r.content), **RETRY_KWARGS)
        print('[+] Created task - ' + name)
        pb.push_note('Canvas-ToDo', json.dumps(j, indent=4, sort_keys=True))


def get_hw_pdf_dip(c: Course, a: Assignment):
    for f in c.get_files():
        if a.name in f.filename:
            r = requests.get(f.url)
            return f.filename, r.content


def get_latest_hw_st(c: Course):
    latest = 0
    latest_f = None
    for f in c.get_files():
        matches = re.findall(r'ECE5300-hw(\d+)\.pdf', f.filename)
        if not matches:
            continue
        num = int(matches[0])
        if num > latest:
            latest = num
            latest_f = f
    return latest, latest_f


if __name__ == '__main__':
    main()
