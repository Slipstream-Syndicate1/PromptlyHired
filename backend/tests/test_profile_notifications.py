import uuid


def test_profile_notifications_defaults_and_updates(client, auth):
    headers, _, _ = auth()

    profile = client.get("/api/profile", headers=headers)
    assert profile.status_code == 200
    data = profile.json()
    assert data["notification_preferences"]["email_enabled"] is False
    assert data["notification_preferences"]["categories"] == []
    assert data["notification_preferences"]["reminder_offsets_hours"] == [24]

    payload = {
        "notification_preferences": {
            "email_enabled": True,
            "categories": [
                "interview_coming_up",
                "offer_deadline_coming_up",
                "application_deadline_coming_up",
            ],
            "reminder_offsets_hours": [2, 24, 168],
        }
    }
    updated = client.patch("/api/profile", json=payload, headers=headers)
    assert updated.status_code == 200
    body = updated.json()
    assert body["notification_preferences"]["email_enabled"] is True
    assert body["notification_preferences"]["categories"] == [
        "interview_coming_up",
        "offer_deadline_coming_up",
        "application_deadline_coming_up",
    ]
    assert body["notification_preferences"]["reminder_offsets_hours"] == [2, 24, 168]


def test_profile_notifications_reject_invalid_category(client, auth):
    headers, _, _ = auth()
    r = client.patch(
        "/api/profile",
        json={
            "notification_preferences": {
                "email_enabled": True,
                "categories": ["bad_category"],
                "reminder_offsets_hours": [6],
            }
        },
        headers=headers,
    )
    assert r.status_code == 422
