"""Operational commands.

    python -m app.tasks doctor    # verify every integration really works

The scheduled digest and reminder jobs belonged to the application-tracker
version of this product and were removed with it.
"""

from __future__ import annotations

import sys


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    command = args[0] if args else "doctor"
    if command == "doctor":
        from app import doctor

        return doctor.run()
    if command == "reminders":
        from app.services.notifications import send_upcoming_reminders

        count = send_upcoming_reminders()
        print(f"Sent {count} reminder email(s).")
        return 0

    print(f"Unknown task: {command}. Expected: doctor or reminders", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
