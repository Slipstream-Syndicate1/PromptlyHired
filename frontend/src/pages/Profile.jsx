import { useEffect, useState } from "react";
import { api } from "../api/client";
import AvatarUpload from "../components/AvatarUpload.jsx";
import ResumePanel from "../components/ResumePanel.jsx";
import { useAuth } from "../context/AuthContext.jsx";

const defaultNotificationPrefs = {
  email_enabled: false,
  categories: [],
  reminder_offsets_hours: [24],
};

const normalizeNotificationPrefs = (value) => ({
  ...defaultNotificationPrefs,
  ...(value || {}),
  categories: Array.isArray(value?.categories) ? value.categories : [],
  reminder_offsets_hours: Array.isArray(value?.reminder_offsets_hours)
    ? value.reminder_offsets_hours
    : [24],
});

export default function Profile() {
  const { user, setUser, logout } = useAuth();
  const [name, setName] = useState(user?.name ?? "");
  const [resume, setResume] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [preferredLocation, setPreferredLocation] = useState(
    user?.preferred_location ?? "",
  );
  const [includeRemote, setIncludeRemote] = useState(
    user?.include_remote ?? true,
  );
  const [notificationPrefs, setNotificationPrefs] = useState(
    normalizeNotificationPrefs(user?.notification_preferences),
  );
  const [prefsBusy, setPrefsBusy] = useState(false);

  useEffect(() => {
    setNotificationPrefs(
      normalizeNotificationPrefs(user?.notification_preferences),
    );
  }, [user]);

  useEffect(() => {
    api
      .getActiveResume()
      .then(setResume)
      .catch((err) => setError(err.message));
  }, []);

  const save = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      setUser(await api.updateProfile({ name }));
      setMessage("Saved.");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const savePreferences = async (event) => {
    event.preventDefault();
    setPrefsBusy(true);
    setError("");
    setMessage("");
    try {
      setUser(
        await api.updateProfile({
          preferred_location: preferredLocation.trim() || null,
          include_remote: includeRemote,
        }),
      );
      setMessage("Recommendation preferences saved.");
    } catch (err) {
      setError(err.message);
    } finally {
      setPrefsBusy(false);
    }
  };

  const notificationCategories = [
    { value: "interview_coming_up", label: "Interview coming up" },
    { value: "offer_deadline_coming_up", label: "Offer deadline coming up" },
    {
      value: "application_deadline_coming_up",
      label: "Application deadline coming up",
    },
    {
      value: "coffee_chat_event_coming_up",
      label: "Coffee chat event coming up",
    },
    {
      value: "networking_event_coming_up",
      label: "Networking event coming up",
    },
  ];

  const reminderOptions = [
    { value: 2, label: "2 hours prior" },
    { value: 24, label: "1 day prior" },
    { value: 48, label: "2 days prior" },
    { value: 168, label: "1 week prior" },
  ];

  const toggleCategory = (value) => {
    setNotificationPrefs((current) => ({
      ...current,
      categories: current.categories.includes(value)
        ? current.categories.filter((item) => item !== value)
        : [...current.categories, value],
    }));
  };

  const toggleReminder = (value) => {
    setNotificationPrefs((current) => ({
      ...current,
      reminder_offsets_hours: current.reminder_offsets_hours.includes(value)
        ? current.reminder_offsets_hours.filter((item) => item !== value)
        : [...current.reminder_offsets_hours, value].sort((a, b) => a - b),
    }));
  };

  const saveNotifications = async (event) => {
    event.preventDefault();
    setPrefsBusy(true);
    setError("");
    setMessage("");
    try {
      setUser(
        await api.updateProfile({
          notification_preferences: {
            email_enabled: notificationPrefs.email_enabled,
            categories: notificationPrefs.categories,
            reminder_offsets_hours: notificationPrefs.reminder_offsets_hours,
          },
        }),
      );
      setMessage("Notification settings saved.");
    } catch (err) {
      setError(err.message);
    } finally {
      setPrefsBusy(false);
    }
  };

  return (
    <main className="page profile-page">
      <div className="page-header">
        <h1>Profile</h1>
      </div>

      {error && <div className="alert error">{error}</div>}
      {message && <div className="alert info">{message}</div>}

      {/* Resume first: it is the thing the whole product is built around. */}
      <ResumePanel resume={resume} onChange={setResume} user={user} />

      <div className="card">
        <AvatarUpload user={user} onChange={setUser} />
      </div>

      <form className="card" onSubmit={save}>
        <label className="field">
          <span>Name</span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={120}
          />
        </label>
        <label className="field">
          <span>Email</span>
          <input value={user?.email ?? ""} disabled />
        </label>
        <button className="btn primary block" type="submit" disabled={busy}>
          {busy ? "Saving…" : "Save changes"}
        </button>
      </form>

      <form className="card" onSubmit={savePreferences}>
        <h2 className="section-title" style={{ marginTop: 0 }}>
          Job recommendations
        </h2>
        <p className="fine-print">
          Recommendations search for the job titles in your resume. Leave the
          location blank to use the one on your resume.
        </p>
        <label className="field">
          <span>Preferred location</span>
          <input
            value={preferredLocation}
            onChange={(e) => setPreferredLocation(e.target.value)}
            maxLength={120}
            placeholder="e.g. Calgary, AB"
          />
        </label>
        <label
          className="field"
          style={{ flexDirection: "row", alignItems: "center", gap: 10 }}
        >
          <input
            type="checkbox"
            checked={includeRemote}
            onChange={(e) => setIncludeRemote(e.target.checked)}
            style={{ width: "auto", margin: 0 }}
          />
          <span style={{ margin: 0 }}>Include remote jobs</span>
        </label>
        <button
          className="btn primary block"
          type="submit"
          disabled={prefsBusy}
        >
          {prefsBusy ? "Saving…" : "Save preferences"}
        </button>
      </form>

      <form className="card" onSubmit={saveNotifications}>
        <h2 className="section-title" style={{ marginTop: 0 }}>
          Notifications
        </h2>

        <label
          className="field"
          style={{ flexDirection: "row", alignItems: "center", gap: 10 }}
        >
          <input
            type="checkbox"
            checked={Boolean(notificationPrefs.email_enabled)}
            onChange={(e) =>
              setNotificationPrefs((current) => ({
                ...current,
                email_enabled: e.target.checked,
              }))
            }
            style={{ width: "auto", margin: 0 }}
          />
          <span style={{ margin: 0 }}>Receive email notifications</span>
        </label>

        <div style={{ marginTop: 12, marginBottom: 8 }}>
          <strong>Notifications To Receive</strong>
        </div>
        <div style={{ display: "grid", gap: 8 }}>
          {notificationCategories.map((option) => (
            <label key={option.value} className="field" style={{ margin: 0 }}>
              <span style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <input
                  type="checkbox"
                  checked={notificationPrefs.categories.includes(option.value)}
                  onChange={() => toggleCategory(option.value)}
                  style={{ width: "auto", margin: 0 }}
                />
                <span>{option.label}</span>
              </span>
            </label>
          ))}
        </div>

        <div style={{ marginTop: 20, marginBottom: 8 }}>
          <strong>Reminder Timing</strong>
        </div>
        <div style={{ display: "grid", gap: 8 }}>
          {reminderOptions.map((option) => (
            <label key={option.value} className="field" style={{ margin: 0 }}>
              <span style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <input
                  type="checkbox"
                  checked={notificationPrefs.reminder_offsets_hours.includes(
                    option.value,
                  )}
                  onChange={() => toggleReminder(option.value)}
                  style={{ width: "auto", margin: 0 }}
                />
                <span>{option.label}</span>
              </span>
            </label>
          ))}
        </div>

        <button
          className="btn primary block"
          type="submit"
          disabled={prefsBusy}
        >
          {prefsBusy ? "Saving…" : "Save notifications"}
        </button>
      </form>

      <button className="btn danger block" onClick={logout}>
        Sign out
      </button>
    </main>
  );
}
