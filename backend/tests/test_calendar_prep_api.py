from datetime import datetime, timedelta, timezone
from uuid import uuid4


def event_payload(job_id=None):
    return {'title': 'Interview', 'date': (datetime.now(timezone.utc)+timedelta(days=3)).date().isoformat(), 'time': '12:00', 'type': 'interview', 'job_id': job_id, 'timezone': 'UTC'}


def test_calendar_ownership_and_validation(client, auth, with_job):
    h, *_ = auth()
    other, *_ = auth()
    job = with_job(h)
    payload = event_payload(job['id'])
    assert client.post('/api/calendar', headers=other, json=payload).status_code == 404
    r = client.post('/api/calendar', headers=h, json=payload)
    assert r.status_code == 201, r.text
    event = r.json()
    assert client.get('/api/calendar', headers=other).json() == []
    assert client.get(f"/api/interviews/{event['id']}/prep", headers=other).status_code == 404
    assert client.patch(f"/api/calendar/{event['id']}", headers=other, json={'title':'stolen'}).status_code == 404
    r = client.patch(f"/api/calendar/{event['id']}", headers=h, json={'time':'13:00'})
    assert r.json()['revision'] == 2
    payload.update(date='2030-03-10', time='02:30', timezone='America/New_York')
    assert client.post('/api/calendar', headers=h, json=payload).status_code == 422


def test_plan_saved_progress_chat_and_staleness(client, auth, with_job, monkeypatch):
    from app.services import interview_prep
    from app.interview_prep_schemas import PrepPlan, PrepDay, PrepTask, PrepChatAnswer
    h, *_ = auth()
    job = with_job(h)
    event = client.post('/api/calendar', headers=h, json=event_payload(job['id'])).json()
    calls = []
    def generate(context, settings):
        calls.append(context)
        return PrepPlan(summary='Study Python', personalization_notice=None, has_more_days=False, days=[PrepDay(date=datetime.now(timezone.utc).date(), minutes_budget=30, tasks=[PrepTask(id=str(uuid4()), title='Practice', category='technical', priority='high', minutes=30, instructions='Practice APIs', expected_outcome='Explain APIs', job_requirement='Python')])])
    monkeypatch.setattr(interview_prep, 'generate_plan', generate)
    monkeypatch.setattr(interview_prep, 'answer_question', lambda *a, **k: PrepChatAnswer(answer='Practice with examples.'))
    url = f"/api/interviews/{event['id']}/prep"
    assert client.get(url, headers=h).json()['plan'] is None
    body = {'daily_minutes':30,'interview_type':'technical','client_request_id':str(uuid4())}
    r = client.post(url, headers=h, json=body)
    assert r.status_code == 200, r.text
    plan = r.json()
    assert client.post(url, headers=h, json=body).json()['id'] == plan['id']
    assert len(calls) == 1
    task = plan['tasks'][0]
    assert client.patch(f"/api/interview-prep/{plan['id']}/tasks/{task['id']}", headers=h, json={'completed':True}).status_code == 200
    assert client.get(url, headers=h).json()['plan']['tasks'][0]['completed'] is True
    chat = {'message':'What should I practice?', 'client_request_id':str(uuid4())}
    messages_url = f"/api/interview-prep/{plan['id']}/messages"
    reply = client.post(messages_url, headers=h, json=chat)
    assert reply.status_code == 200, reply.text
    assert client.post(messages_url, headers=h, json=chat).json()['id'] == reply.json()['id']
    assert len(client.get(url, headers=h).json()['plan']['messages']) == 2
    client.patch(f"/api/calendar/{event['id']}", headers=h, json={'time':'14:00'})
    assert client.get(url, headers=h).json()['plan']['outdated'] is True


def test_preparation_rejects_stale_generation_and_isolates_plans(client, auth, with_job, monkeypatch):
    from app.services import interview_prep
    from app.interview_prep_schemas import PrepPlan, PrepDay, PrepTask
    h, *_ = auth()
    other, *_ = auth()
    job = with_job(h)
    event = client.post('/api/calendar', headers=h, json=event_payload(job['id'])).json()
    url = f"/api/interviews/{event['id']}/prep"
    def make_plan(context, settings):
        return PrepPlan(summary='Practice', personalization_notice=None, has_more_days=False, days=[PrepDay(date=datetime.now(timezone.utc).date(), minutes_budget=30, tasks=[PrepTask(id=str(uuid4()), title='Practice', category='technical', priority='high', minutes=30, instructions='Practice APIs', expected_outcome='Explain APIs', job_requirement='Python')])])
    def race(context, settings):
        assert client.patch(f"/api/calendar/{event['id']}", headers=h, json={'time':'13:00'}).status_code == 200
        return make_plan(context, settings)
    monkeypatch.setattr(interview_prep, 'generate_plan', race)
    body = {'daily_minutes':30,'interview_type':'technical','client_request_id':str(uuid4())}
    assert client.post(url, headers=h, json=body).status_code == 409
    assert client.get(url, headers=h).json()['plan'] is None
    monkeypatch.setattr(interview_prep, 'generate_plan', make_plan)
    plan = client.post(url, headers=h, json=body).json()
    assert 'id' in plan, plan
    assert client.get(f"/api/interview-prep/{plan['id']}/messages", headers=other).status_code == 404
    assert client.patch(f"/api/interview-prep/{plan['id']}/tasks/{plan['tasks'][0]['id']}", headers=other, json={'completed':True}).status_code == 404
    assert client.post(f"/api/interview-prep/{plan['id']}/messages", headers=other, json={'message':'test','client_request_id':str(uuid4())}).status_code == 404


def test_provider_failure_does_not_save_plan_and_retry_recovers(client, auth, with_job, monkeypatch):
    from app.services import interview_prep, ai
    h, *_ = auth()
    event = client.post('/api/calendar', headers=h, json=event_payload(with_job(h)['id'])).json()
    url = f"/api/interviews/{event['id']}/prep"
    body = {'daily_minutes':30,'interview_type':'technical','client_request_id':str(uuid4())}
    for error, status in [(ai.AIRateLimited('Quota reached'),429),(ai.AIUnavailable('Missing key'),503),(ai.AIError('Bad output'),502)]:
        def fail(*args):
            raise error
        monkeypatch.setattr(interview_prep, 'generate_plan', fail)
        assert client.post(url, headers=h, json=body).status_code == status
        assert client.get(url, headers=h).json()['plan'] is None


def test_import_is_explicit_idempotent_and_cannot_cross_accounts(client, auth):
    h, *_ = auth()
    other, *_ = auth()
    payload = event_payload()
    payload.update(id=str(uuid4()), time=None)
    first = client.post('/api/calendar', headers=h, json=payload)
    assert first.status_code == 201
    assert client.post('/api/calendar', headers=h, json=payload).json()['id'] == first.json()['id']
    assert len(client.get('/api/calendar', headers=h).json()) == 1
    assert client.post('/api/calendar', headers=other, json=payload).status_code == 409
    assert client.get(f"/api/interviews/{first.json()['id']}/prep", headers=h).status_code == 422
