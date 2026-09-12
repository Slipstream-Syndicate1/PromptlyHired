from datetime import date, datetime, timezone

import pytest


def api():
    from app.services import interview_prep
    return interview_prep


def test_local_dates_and_rolling_window():
    slots = api().build_schedule(datetime(2026, 9, 30, 18, tzinfo=timezone.utc), 'America/Edmonton', 60,
                                 now=datetime(2026, 9, 13, 1, tzinfo=timezone.utc))
    assert len(slots) == 14
    assert slots[0].date == date(2026, 9, 12)
    assert slots[-1].date == date(2026, 9, 25)
    assert all(s.minutes == 60 for s in slots)


def test_same_day_requires_actual_availability_and_caps_clock_time():
    now = datetime(2026, 9, 12, 16, tzinfo=timezone.utc)
    interview = datetime(2026, 9, 12, 16, 40, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match='available'):
        api().build_schedule(interview, 'UTC', 60, now=now)
    slots = api().build_schedule(interview, 'UTC', 60, now=now, same_day_minutes=90)
    assert slots[0].minutes == 40


@pytest.mark.parametrize('minutes', [0, 14, 481, 30.5, True])
def test_invalid_budget_rejected(minutes):
    with pytest.raises(ValueError):
        api().build_schedule(datetime(2026, 9, 14, tzinfo=timezone.utc), 'UTC', minutes,
                             now=datetime(2026, 9, 12, tzinfo=timezone.utc))


def test_expired_and_naive_dates_rejected():
    now = datetime(2026, 9, 12, tzinfo=timezone.utc)
    for interview in [now, datetime(2026, 9, 14)]:
        with pytest.raises(ValueError):
            api().build_schedule(interview, 'UTC', 60, now=now)


def context():
    from app.interview_prep_schemas import InterviewContext
    return InterviewContext(interview_id='i1', application_id='a1', job_id='j1', status='interview',
                            starts_at=datetime(2026, 9, 14, tzinfo=timezone.utc), timezone='UTC',
                            schedule_revision='1', job_title='Engineer', company='Example',
                            job_description='Python and SQL')


def output(minutes=30, day='2026-09-12'):
    return {'summary': 'Practice Python', 'days': [{'date': day, 'tasks': [
        {'title': 'Python practice', 'category': 'technical', 'priority': 'high', 'minutes': minutes,
         'instructions': 'Implement a function', 'expected_outcome': 'A tested function',
         'job_requirement': 'Python'}]}]}


def test_plan_validates_provider_dates_budget_and_assigns_ids(monkeypatch):
    service = api()
    from app.interview_prep_schemas import PrepSettings
    from app.services import ai
    now = datetime(2026, 9, 13, tzinfo=timezone.utc)
    monkeypatch.setattr(ai, 'generate_structured', lambda *a, **kw: output(day='2026-09-13'))
    plan = service.generate_plan(context(), PrepSettings(daily_minutes=60, interview_type='technical'), now=now)
    assert plan.days[0].tasks[0].id
    assert plan.personalization_notice
    for bad in [output(61, '2026-09-13'), output(day='2026-09-15'), {'summary': 'bad', 'days': []}]:
        monkeypatch.setattr(ai, 'generate_structured', lambda *a, **kw: bad)
        with pytest.raises(ai.AIError):
            service.generate_plan(context(), PrepSettings(daily_minutes=60, interview_type='technical'), now=now)


def test_canceled_interview_never_generates():
    from app.interview_prep_schemas import PrepSettings
    c = context().model_copy(update={'status': 'canceled'})
    with pytest.raises(ValueError):
        api().generate_plan(c, PrepSettings(daily_minutes=60, interview_type='technical'), now=datetime(2026, 9, 13, tzinfo=timezone.utc))


def test_chat_is_bounded_and_does_not_change_plan(monkeypatch):
    from app.interview_prep_schemas import PrepSettings
    from app.services import ai
    service = api()
    monkeypatch.setattr(ai, 'generate_structured', lambda *a, **kw: output(day='2026-09-13'))
    plan = service.generate_plan(context(), PrepSettings(daily_minutes=60, interview_type='technical'),
                                 now=datetime(2026, 9, 13, tzinfo=timezone.utc))
    before = plan.model_dump()
    monkeypatch.setattr(ai, 'generate_structured', lambda *a, **kw: {'answer': 'Practice joins.'})
    answer = service.answer_question(context(), plan, 'How can I practice SQL?')
    assert answer.answer == 'Practice joins.'
    assert plan.model_dump() == before
    with pytest.raises(ValueError):
        service.answer_question(context(), plan, 'x' * 2001)
    monkeypatch.setattr(ai, 'generate_structured', lambda *a, **kw: {'answer': ''})
    with pytest.raises(ai.AIError):
        service.answer_question(context(), plan, 'Help')


def test_not_sure_requires_both_categories(monkeypatch):
    from app.interview_prep_schemas import PrepSettings
    from app.services import ai
    service = api()
    data = output(day='2026-09-13')
    monkeypatch.setattr(ai, 'generate_structured', lambda *a, **kw: data)
    with pytest.raises(ai.AIError):
        service.generate_plan(context(), PrepSettings(daily_minutes=60), now=datetime(2026, 9, 13, tzinfo=timezone.utc))
    data['days'][0]['tasks'].append({**data['days'][0]['tasks'][0], 'category': 'behavioral'})
    plan = service.generate_plan(context(), PrepSettings(daily_minutes=60), now=datetime(2026, 9, 13, tzinfo=timezone.utc))
    assert {task.category for task in plan.days[0].tasks} == {'technical', 'behavioral'}


def test_dst_transition_uses_local_dates_not_24_hour_intervals():
    slots = api().build_schedule(datetime(2026, 11, 2, 17, tzinfo=timezone.utc),
                                 'America/Edmonton', 60,
                                 now=datetime(2026, 10, 31, 18, tzinfo=timezone.utc))
    assert [slot.date.isoformat() for slot in slots] == ['2026-10-31', '2026-11-01']


def test_unknown_timezone_and_too_close_interview_rejected():
    now = datetime(2026, 9, 12, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match='timezone'):
        api().build_schedule(datetime(2026, 9, 14, tzinfo=timezone.utc), 'Not/AZone', 60, now=now)
    with pytest.raises(ValueError, match='minute'):
        api().build_schedule(datetime(2026, 9, 12, 0, 0, 30, tzinfo=timezone.utc), 'UTC', 60, now=now)
