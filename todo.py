import json

import requests
from requests_toolbelt import MultipartEncoder


class Client:

    def __init__(self, refresh_token, client_id):
        self.refresh_token = refresh_token
        self.client_id = client_id
        self.session = requests.session()
        self.session.headers['user-agent'] = 'Microsoft To-Do/Mac/2.25.1'
        self.access_token = ''
        self.refresh_access_token()

    def refresh_access_token(self):
        form = {
            'refresh_token': self.refresh_token,
            'client_id': self.client_id,
            'resource': 'https://outlook.office.com',
            'client_info': '1',
            'scope': 'openid',
            'grant_type': 'refresh_token'
        }

        r = self.session.post('https://login.microsoft.com/common/oauth2/token', data=form)
        r.raise_for_status()
        j = r.json()
        self.access_token = j['access_token']
        self.refresh_token = j['refresh_token']
        self.session.headers['Authorization'] = 'Bearer ' + self.access_token

    def get_lists(self):
        r = self.session.get(
            'https://substrate.office.com/todo/api/v1/taskfolders/')
        return r.json()['Value']

    def create_list(self, name):
        j = {
            "SortType": 0,
            # "OrderDateTime": "2020-09-04T17:54:22.0750000Z",
            "ShowCompletedTasks": True,
            "SharingStatus": "NotShared",
            # "ThemeBackground": "mountain",
            # "ThemeColor": "dark_blue",
            "Name": name,
            "SortAscending": False
        }
        r = self.session.post(
            'https://substrate.office.com/todo/api/v1/taskfolders/', json=j)
        return r.json()

    def get_tasks(self, list_id):
        r = self.session.get(
            f'https://substrate.office.com/todo/api/v1/taskfolders/{list_id}/tasks')
        return r.json()['Value']

    def create_task(self, subject, body, due_date, list_id):
        j = {
            "Status": "NotStarted",
            "Importance": "Normal",
            "IsIgnored": False,
            "IsReminderOn": False,
            "Subject": subject,
            "Body": {
                "Content": body,
                "ContentType": "Text"
            },
        }
        if due_date:
            j["DueDateTime"] = {
                "DateTime": due_date.isoformat(),
                "TimeZone": "America/Chicago"
            }
        r = self.session.post(
            f'https://substrate.office.com/todo/api/v1/taskfolders/{list_id}/tasks', json=j)
        r.raise_for_status()
        return r.json()

    def add_file(self, task_id, fname, _bytes):
        url = f'https://substrate.office.com/todo/api/v1/tasks/{task_id}/attachments'
        j = json.dumps({'Name': fname})
        mp_encoder = MultipartEncoder(
            fields={
                'jsonMetadata': ('', j, 'application/json'),
                # plain file object, no filename or mime type produces a
                # Content-Disposition header with just the part name
                'attachment': (fname, _bytes, 'application/pdf'),
            }
        )
        r = self.session.post(url, data=mp_encoder, headers={'Content-Type': mp_encoder.content_type})
        r.raise_for_status()

