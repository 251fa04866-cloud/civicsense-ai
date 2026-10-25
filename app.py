import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "complaints.db"

st.set_page_config(page_title="CivicSense AI", page_icon="🏙️", layout="wide")

CATEGORIES = ["Road / Pothole", "Garbage / Sanitation", "Water Leakage", "Drainage / Sewage", "Streetlight", "Other"]
STATUSES = ["Submitted", "Under Review", "In Progress", "Resolved"]


def connect_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect_db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT NOT NULL,
            location TEXT NOT NULL,
            severity TEXT NOT NULL,
            score INTEGER NOT NULL,
            priority TEXT NOT NULL,
            reason TEXT NOT NULL,
            duplicate_of INTEGER,
            status TEXT NOT NULL DEFAULT 'Submitted',
            created_at TEXT NOT NULL
        )""")


def score_complaint(category, description, severity, location):
    text = (description + " " + category).lower()
    score = {"Low": 15, "Medium": 35, "High": 55, "Critical": 70}[severity]
    reasons = [f"User-reported severity: {severity.lower()}"]

    rules = [
        (("accident", "injury", "injured", "dangerous", "life threatening", "open manhole", "electric wire", "electrocution"), 25, "possible immediate safety risk"),
        (("flood", "flooding", "burst pipe", "major leak", "sewage overflow", "overflowing sewage"), 18, "possible infrastructure or sanitation hazard"),
        (("school", "hospital", "bus stop", "main road", "highway", "market"), 8, "location may affect many people"),
        (("small", "minor", "slight"), -8, "description indicates a potentially minor issue"),
    ]
    for keywords, points, reason in rules:
        if any(word in text for word in keywords):
            score += points
            reasons.append(reason)
    score = max(0, min(100, score))
    if score >= 80:
        priority = "Critical"
    elif score >= 60:
        priority = "High"
    elif score >= 35:
        priority = "Medium"
    else:
        priority = "Low"
    if not location.strip():
        reasons.append("location missing; follow-up needed")
    return score, priority, "; ".join(reasons).capitalize() + "."


def get_complaints():
    with connect_db() as conn:
        rows = conn.execute("SELECT * FROM complaints ORDER BY created_at DESC, id DESC").fetchall()
    return [dict(row) for row in rows]


def find_duplicate(description, category, location, rows, exclude_id=None):
    candidates = [r for r in rows if r["id"] != exclude_id]
    if not candidates:
        return None, 0.0
    texts = [f"{r['category']} {r['description']} {r['location']}" for r in candidates]
    new_text = f"{category} {description} {location}"
    matrix = TfidfVectorizer(stop_words="english", ngram_range=(1, 2)).fit_transform(texts + [new_text])
    sims = cosine_similarity(matrix[-1], matrix[:-1]).flatten()
    best_idx = int(sims.argmax())
    best_score = float(sims[best_idx])
    if best_score >= 0.42:
        return candidates[best_idx], best_score
    return None, best_score


init_db()
st.title("🏙️ CivicSense AI")
st.caption("Intelligent Civic Complaint Prioritization System · Student prototype")

citizen_tab, dashboard_tab, about_tab = st.tabs(["📝 Report a Complaint", "📊 Admin Dashboard", "ℹ️ About"])

with citizen_tab:
    st.subheader("Submit a civic complaint")
    st.write("Describe the problem clearly. The system estimates urgency and checks for similar reports.")
    with st.form("complaint_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Your name (or initials)", max_chars=80)
            category = st.selectbox("Complaint category", CATEGORIES)
            location = st.text_input("Location / area", placeholder="e.g., Main road near the bus stop")
        with col2:
            severity = st.select_slider("How severe is it?", options=["Low", "Medium", "High", "Critical"], value="Medium")
            st.caption("Critical means a possible immediate threat. For a real emergency, contact the appropriate emergency service directly.")
        description = st.text_area("Complaint description", placeholder="Explain what happened, where, and who may be affected…", max_chars=1200, height=130)
        submitted = st.form_submit_button("Analyze and submit", type="primary", use_container_width=True)

    if submitted:
        if not name.strip() or not location.strip() or len(description.strip()) < 10:
            st.error("Please enter a name/initials, location, and a description of at least 10 characters.")
        else:
            rows = get_complaints()
            duplicate, similarity = find_duplicate(description.strip(), category, location.strip(), rows)
            score, priority, reason = score_complaint(category, description.strip(), severity, location.strip())
            if duplicate:
                reason += f" Similar report #{duplicate['id']} detected ({similarity:.0%} text similarity); staff should verify before merging."
            created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with connect_db() as conn:
                cur = conn.execute("""INSERT INTO complaints
                    (name, category, description, location, severity, score, priority, reason, duplicate_of, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Submitted', ?)""",
                    (name.strip(), category, description.strip(), location.strip(), severity, score, priority, reason,
                     duplicate["id"] if duplicate else None, created_at))
                complaint_id = cur.lastrowid
            st.success(f"Complaint submitted successfully. Your complaint ID is #{complaint_id}.")
            st.metric("Estimated priority", priority, f"Priority score: {score}/100")
            st.info("Why this priority? " + reason)
            if duplicate:
                st.warning(f"This may be similar to complaint #{duplicate['id']} ({similarity:.0%} similarity). This is a suggestion, not a confirmed duplicate.")
            else:
                st.success("No strong text-similarity match found in current reports.")

with dashboard_tab:
    st.subheader("Complaint management dashboard")
    st.warning("Demo dashboard: add authentication and role-based access before using real citizen data in production.")
    rows = get_complaints()
    if not rows:
        st.info("No complaints yet. Submit a sample complaint in the first tab to populate the dashboard.")
    else:
        df = pd.DataFrame(rows)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total complaints", len(df))
        m2.metric("Critical / High", int(df["priority"].isin(["Critical", "High"]).sum()))
        m3.metric("In progress", int(df["status"].isin(["Under Review", "In Progress"]).sum()))
        m4.metric("Resolved", int((df["status"] == "Resolved").sum()))
        st.markdown("#### Filter and prioritize")
        f1, f2 = st.columns(2)
        with f1:
            priority_filter = st.multiselect("Priority", ["Critical", "High", "Medium", "Low"], default=["Critical", "High", "Medium", "Low"])
        with f2:
            status_filter = st.multiselect("Status", STATUSES, default=STATUSES)
        filtered = df[df["priority"].isin(priority_filter) & df["status"].isin(status_filter)].copy()
        order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
        filtered["_order"] = filtered["priority"].map(order)
        filtered = filtered.sort_values(["_order", "score", "created_at"], ascending=[True, False, True])
        display_cols = ["id", "created_at", "category", "description", "location", "score", "priority", "status", "duplicate_of"]
        st.dataframe(filtered[display_cols], use_container_width=True, hide_index=True)
        st.markdown("#### Update complaint status")
        ids = [int(x) for x in df["id"].tolist()]
        selected_id = st.selectbox("Complaint ID", ids, format_func=lambda x: f"#{x} — {df.loc[df['id'] == x, 'category'].iloc[0]}")
        current_status = str(df.loc[df["id"] == selected_id, "status"].iloc[0])
        new_status = st.selectbox("New status", STATUSES, index=STATUSES.index(current_status), key="new_status")
        if st.button("Save status", type="primary"):
            with connect_db() as conn:
                conn.execute("UPDATE complaints SET status = ? WHERE id = ?", (new_status, selected_id))
            st.success(f"Complaint #{selected_id} updated to {new_status}.")
            st.rerun()
        st.markdown("#### Complaints by priority")
        counts = df["priority"].value_counts().reindex(["Critical", "High", "Medium", "Low"], fill_value=0)
        st.bar_chart(counts)
        csv = df[display_cols].to_csv(index=False).encode("utf-8")
        st.download_button("Download complaints as CSV", csv, file_name="civic_complaints.csv", mime="text/csv")

with about_tab:
    st.subheader("How the prototype works")
    st.markdown("""
    - **Priority score:** an explainable rule-based estimate using the reported severity and safety/context keywords.
    - **Duplicate detection:** TF-IDF vectorization and cosine similarity compare a new complaint with existing reports.
    - **Dashboard:** summaries, filters, priority sorting, status updates, a chart, and CSV export.

    **Limitations:** Text similarity can miss paraphrases or flag unrelated reports. Priority scores are decision support, not official risk assessments. Staff should review urgent cases and possible duplicates. The app stores data in a local SQLite database; on some free hosting deployments, local files may not persist reliably across restarts. For production, use managed persistent storage, authentication, access controls, privacy safeguards, and monitoring.
    """)
    st.caption("CivicSense AI · Educational prototype")
