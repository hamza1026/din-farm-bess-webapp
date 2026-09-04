# Din Farm BESS Web Portal

This converts the two supplied dashboards into a real Python web application with a persistent SQLite database and role-based access.

## Important design choice
**Dashboard 1 and Dashboard 2 are NOT mixed.** Each keeps its own original interface, calculations, graphs and terminology. They use separate database keys (`d1` and `d2`), so an edit in one dashboard cannot overwrite the other dashboard's data.

The original 07-Aug-2026 through 28-Aug-2026 data is imported automatically from the supplied HTML files on first startup.

## Roles
- **Admin:** add, edit, delete and save data/schedules/events.
- **Viewer:** read-only access. The server also rejects write API calls from viewers.

## Run locally
1. Install Python 3.10+.
2. Open a terminal in this folder.
3. Create a virtual environment: `python -m venv .venv`
4. Activate it.
5. Install: `pip install -r requirements.txt`
6. Set environment variables from `.env.example` (especially `SECRET_KEY` and `ADMIN_PASS`).
7. Start: `python app.py`
8. Open `http://127.0.0.1:5000`

Default credentials if you did not set environment variables:
- username: `admin`
- password: `dinfarm123`

**Change the default password before exposing the app to the internet.**

## Production
Run behind HTTPS with a production WSGI server, e.g.:
`waitress-serve --listen=0.0.0.0:5000 app:app`

For a larger installation, SQLite can later be replaced with PostgreSQL without changing the dashboard UI architecture.

## Files
- `app.py` — Python backend, authentication, permissions and database API.
- `templates/dashboard1.html` — original Dashboard 1 UI, preserved separately.
- `templates/dashboard2.html` — original Dashboard 2 UI, preserved separately.
- `templates/login.html` — login page.
- `templates/home.html` — portal landing page.
- `din_farm.db` — created on first run and stores the central data.
