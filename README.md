# CivicSense AI — Full Student Prototype

## Features
- Complaint submission
- Explainable priority scoring (Critical/High/Medium/Low)
- Similar-report/duplicate suggestions
- Admin login, filters, status updates
- Dashboard metrics, chart, CSV export

## Deploy on Streamlit Community Cloud
1. Upload `app.py` and `requirements.txt` to the root of your GitHub repository.
2. Choose Deploy an app; branch `main`; main file path `app.py`.
3. In Manage app → Settings → Secrets, add:
```toml
[admin]
username = "civic_admin"
password = "replace-with-a-long-unique-password"
```
4. Save, wait for redeploy, then test submission and admin login.

## Local run
```bash
pip install -r requirements.txt
streamlit run app.py
```
For local admin login, set environment variables `CIVICSENSE_ADMIN_USER` and `CIVICSENSE_ADMIN_PASSWORD`, or create `.streamlit/secrets.toml` with the TOML above.

## Important
Uses SQLite by default. Streamlit Cloud local files may not persist reliably through restarts/rebuilds. For production, connect a managed PostgreSQL database and use proper access controls. This is a student prototype, not an official emergency service.
