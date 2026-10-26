import streamlit as st
import sqlite3, os, re
import pandas as pd
from datetime import datetime
from difflib import SequenceMatcher

st.set_page_config(page_title="CivicSense AI", page_icon="🏙️", layout="wide")
DB=os.environ.get("CIVICSENSE_DB","civicsense.db")
CATEGORIES=["Road / Pothole","Water Supply","Drainage / Sewage","Garbage / Sanitation","Streetlight","Electricity","Public Safety","Parks / Public Property","Other"]
STATUSES=["Submitted","Under Review","In Progress","Resolved","Rejected"]
PRIORITIES=["Critical","High","Medium","Low"]

def conn():
    c=sqlite3.connect(DB,check_same_thread=False); c.row_factory=sqlite3.Row; return c
def init():
    with conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS complaints(
        id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, citizen_name TEXT, category TEXT,
        location TEXT, severity INTEGER, description TEXT, priority TEXT, score INTEGER,
        reason TEXT, status TEXT DEFAULT 'Submitted', duplicate_of INTEGER, duplicate_similarity INTEGER)""")
def norm(s): return re.sub(r"[^a-z0-9 ]"," ",str(s).lower()).strip()
def sim(a,b): return int(SequenceMatcher(None,norm(a),norm(b)).ratio()*100)
def data():
    with conn() as c: return pd.read_sql_query("SELECT * FROM complaints ORDER BY id DESC",c)
def assess(cat,sev,desc,loc):
    t=norm(desc); score=sev*14; why=[f"Reported severity {sev}/5"]
    critical=["fire","live wire","electric shock","collapse","gas leak","injured","open manhole","flooding","accident"]
    high=["no water","sewage","overflow","major pothole","dark road","broken pole","hospital","school","traffic"]
    if any(x in t for x in critical): score+=30; why.append("Possible immediate safety risk keywords")
    elif any(x in t for x in high): score+=18; why.append("High-impact issue keywords")
    if cat in ["Public Safety","Electricity","Drainage / Sewage"]: score+=12; why.append("Category may pose health/safety risk")
    if cat in ["Water Supply","Garbage / Sanitation"]: score+=6; why.append("Essential service/community health impact")
    if any(x in t for x in ["many people","whole street","entire area","main road","hospital","school"]): score+=8; why.append("May affect multiple people")
    if loc.strip(): score+=4
    score=min(100,score)
    priority="Critical" if score>=75 else "High" if score>=55 else "Medium" if score>=35 else "Low"
    return priority,score,"; ".join(why)
def duplicate(cat,loc,desc):
    df=data(); bestid=None; best=0
    for r in df.itertuples():
        v=int(sim(desc,r.description)*.75+sim(loc,r.location)*.15+(10 if cat==r.category else 0))
        if v>best: best,bestid=v,r.id
    return (bestid,best) if bestid and best>=68 else (None,best)
def submit(name,cat,loc,sev,desc):
    p,s,why=assess(cat,sev,desc,loc); did,ds=duplicate(cat,loc,desc)
    with conn() as c:
        cur=c.execute("INSERT INTO complaints(created_at,citizen_name,category,location,severity,description,priority,score,reason,status,duplicate_of,duplicate_similarity) VALUES(?,?,?,?,?,?,?,?,?,'Submitted',?,?)",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),name.strip() or "Anonymous",cat,loc.strip(),sev,desc.strip(),p,s,why,did,ds if did else 0))
        c.commit(); return cur.lastrowid,p,s,why,did,ds
def admin_login():
    try: u=st.secrets["admin"]["username"]; pw=st.secrets["admin"]["password"]
    except Exception: u=os.getenv("CIVICSENSE_ADMIN_USER","admin"); pw=os.getenv("CIVICSENSE_ADMIN_PASSWORD","")
    if not pw:
        st.error("Admin access is not configured. Add [admin] username and password in Streamlit app Secrets.")
        st.code('[admin]\nusername = "civic_admin"\npassword = "replace-with-a-long-unique-password"')
        return False
    if st.session_state.get("logged_in"): return True
    with st.form("login"):
        st.subheader("Admin login"); user=st.text_input("Username"); password=st.text_input("Password",type="password")
        if st.form_submit_button("Log in",use_container_width=True):
            if user==u and password==pw: st.session_state.logged_in=True; st.rerun()
            else: st.error("Incorrect username or password.")
    return False

init()
st.title("🏙️ CivicSense AI")
st.caption("Intelligent Civic Complaint Prioritization System · Student prototype")
report,admin,about=st.tabs(["📝 Report a Complaint","📊 Admin Dashboard","ℹ️ About"])
with report:
    st.subheader("Submit a civic complaint")
    with st.form("complaint",clear_on_submit=True):
        a,b=st.columns(2)
        with a:
            name=st.text_input("Your name (optional)")
            cat=st.selectbox("Complaint category",CATEGORIES)
            loc=st.text_input("Location / area",placeholder="Main road near bus stop")
        with b:
            sev=st.slider("How severe is it?",1,5,3)
            st.caption("For immediate emergencies, contact the appropriate emergency service.")
        desc=st.text_area("Complaint description",height=140,placeholder="Explain what happened, where, and who may be affected...")
        go=st.form_submit_button("Analyze and submit",type="primary",use_container_width=True)
    if go:
        if not loc.strip() or not desc.strip(): st.error("Location and description are required.")
        else:
            cid,p,s,why,did,ds=submit(name,cat,loc,sev,desc)
            st.success(f"Complaint submitted successfully. ID: #{cid}")
            x,y=st.columns(2); x.metric("Estimated priority",p); y.metric("Priority score",f"{s}/100")
            st.info("Why this priority? "+why)
            if did: st.warning(f"Possible duplicate of complaint #{did} ({ds}% similarity). Staff should verify; it is not automatically merged.")
            else: st.success("No strong similar report found.")
            st.caption("Automated scores are estimates and require human review.")
with admin:
    st.subheader("Complaint management dashboard")
    if admin_login():
        if st.button("Log out"): st.session_state.logged_in=False; st.rerun()
        df=data()
        if df.empty: st.info("No complaints yet.")
        else:
            a,b,c,d=st.columns(4)
            a.metric("Total complaints",len(df)); b.metric("Critical / High",int(df.priority.isin(["Critical","High"]).sum()))
            c.metric("In progress",int((df.status=="In Progress").sum())); d.metric("Resolved",int((df.status=="Resolved").sum()))
            st.markdown("### Filter and prioritize")
            x,y,z=st.columns(3)
            with x: ps=st.multiselect("Priority",PRIORITIES,default=PRIORITIES)
            with y: ss=st.multiselect("Status",STATUSES,default=STATUSES)
            with z: cs=st.multiselect("Category",CATEGORIES,default=CATEGORIES)
            filtered=df[df.priority.isin(ps)&df.status.isin(ss)&df.category.isin(cs)]
            cols=["id","created_at","category","location","description","priority","score","status","duplicate_of","duplicate_similarity"]
            st.dataframe(filtered[cols],use_container_width=True,hide_index=True)
            st.markdown("### Update complaint status")
            choices={f"#{r.id} — {r.category} — {r.location[:30]}":int(r.id) for r in df.itertuples()}
            label=st.selectbox("Complaint ID",list(choices)); cid=choices[label]
            current=str(df.loc[df.id==cid,"status"].iloc[0])
            new=st.selectbox("New status",STATUSES,index=STATUSES.index(current))
            if st.button("Save status",type="primary"):
                with conn() as c: c.execute("UPDATE complaints SET status=? WHERE id=?",(new,cid)); c.commit()
                st.success("Status updated."); st.rerun()
            st.markdown("### Complaints by priority")
            st.bar_chart(df.priority.value_counts().reindex(PRIORITIES,fill_value=0))
            st.markdown("### Duplicate review queue")
            dup=df[df.duplicate_of.notna()]
            if dup.empty: st.write("No potential duplicates flagged.")
            else: st.dataframe(dup[["id","duplicate_of","duplicate_similarity","category","location","description"]],use_container_width=True,hide_index=True)
            st.download_button("Download complaints as CSV",df.to_csv(index=False).encode(), "civic_complaints.csv","text/csv")
with about:
    st.subheader("About CivicSense AI")
    st.write("A student prototype that estimates complaint priority, suggests similar reports, tracks status, visualizes trends, and exports CSV.")
    st.markdown("- Explainable priority scoring\n- Duplicate similarity suggestions\n- Admin dashboard and status tracking\n- Charts and CSV export")
    st.warning("Not an official government service. Do not submit sensitive personal information. Similarity and priority results can be wrong and need human review.")
    st.markdown("**Production upgrades:** managed PostgreSQL storage, staff roles, map coordinates, photo uploads, notifications, audit logs, and multilingual support.")
