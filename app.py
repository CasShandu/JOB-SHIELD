from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_cors import CORS
import sqlite3, math, re, secrets
from werkzeug.security import generate_password_hash, check_password_hash

DB = "jobshield.db"
app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)
app.secret_key = secrets.token_hex(24)

# --- Plan quotas (monthly) ---
PLAN_QUOTAS = {
    "free": 20,
    "standard": 100,
    "premium": None  # None = unlimited
}

# ---------------- DB helpers ----------------
def get_conn():
    return sqlite3.connect(DB)

def query_jobs():
    conn = get_conn()
    cur = conn.cursor()
    rows = cur.execute("SELECT id, company, title, min_experience, skills, location FROM employers").fetchall()
    conn.close()
    jobs = []
    for r in rows:
        jobs.append({
            "id": r[0],
            "company": r[1],
            "title": r[2],
            "min_experience": r[3],
            "skills": r[4],
            "location": r[5]
        })
    return jobs

def insert_employer(company, title, min_experience, skills, location):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO employers (company,title,min_experience,skills,location) VALUES (?,?,?,?,?)",
        (company, title, min_experience, skills, location)
    )
    conn.commit()
    conn.close()

def insert_user(name, email, password_hash, plan='free'):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (name,email,password_hash,plan) VALUES (?,?,?,?)",
        (name, email, password_hash, plan)
    )
    conn.commit()
    conn.close()

def get_user_by_email(email):
    conn = get_conn()
    cur = conn.cursor()
    row = cur.execute(
        "SELECT id,name,email,password_hash,plan,searches_used FROM users WHERE email = ?", 
        (email,)
    ).fetchone()
    conn.close()
    return row

def get_user_by_id(uid):
    conn = get_conn()
    cur = conn.cursor()
    row = cur.execute(
        "SELECT id,name,email,password_hash,plan,searches_used FROM users WHERE id = ?", 
        (uid,)
    ).fetchone()
    conn.close()
    return row

def update_user_plan(user_id, plan):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET plan=?, searches_used=0 WHERE id=?", (plan, user_id))
    conn.commit()
    conn.close()

def increment_search_count(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET searches_used = searches_used + 1 WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

# ---------------- text utilities ----------------
def tokenize(text):
    if not text:
        return []
    text = text.lower()
    toks = [t for t in re.split(r'\W+', text) if len(t) > 1]
    return toks

def build_idf(docs):
    df = {}
    N = len(docs)
    for doc in docs:
        seen = set()
        for t in tokenize(doc):
            if t not in seen:
                df[t] = df.get(t, 0) + 1
                seen.add(t)
    idf = {}
    for k, v in df.items():
        idf[k] = math.log(1 + N / v)
    return idf

def tfvec(text, idf):
    tf = {}
    for t in tokenize(text):
        tf[t] = tf.get(t, 0) + 1
    vec = {}
    for k, v in tf.items():
        vec[k] = v * idf.get(k, math.log(2.0))
    return vec

def cosine(a, b):
    num = 0.0
    na = 0.0
    nb = 0.0
    for k, v in a.items():
        num += v * b.get(k, 0.0)
        na += v * v
    for v in b.values():
        nb += v * v
    if na == 0 or nb == 0:
        return 0.0
    return num / (math.sqrt(na) * math.sqrt(nb))

def score_jobs_for_seeker(seeker_dict):
    jobs = query_jobs()
    docs = []
    for j in jobs:
        txt = f"{j['title']} {j['skills']} {j['company']} {j.get('location','')} exp{j['min_experience']}"
        docs.append(txt)
    if not docs:
        return []
    seeker_text = f"{seeker_dict.get('qualification','')} {seeker_dict.get('skills','')} {seeker_dict.get('location','')}"
    all_docs = docs + [seeker_text]
    idf = build_idf(all_docs)
    job_vecs = [tfvec(d, idf) for d in docs]
    seeker_vec = tfvec(seeker_text, idf)
    scored = []
    for i, j in enumerate(jobs):
        base = cosine(seeker_vec, job_vecs[i]) * 100.0
        se = int(seeker_dict.get('experience') or 0)
        req = int(j.get('min_experience') or 0)
        if se >= req:
            base += 12.0
        else:
            base -= (req - se) * 6.0
        score = max(0.0, min(100.0, base))
        scored.append({'job': j, 'score': round(score, 1)})
    scored.sort(key=lambda x: x['score'], reverse=True)
    return scored

# ---------------- helper: quota check ----------------
def plan_quota(plan):
    return PLAN_QUOTAS.get(plan)

def can_user_search(user_row):
    if not user_row:
        return False, "not_logged_in"
    user_id, name, email, pw, plan, used = user_row
    quota = plan_quota(plan)
    if quota is None:
        return True, None
    if used < quota:
        return True, None
    return False, "quota_exceeded"

# ---------------- routes ----------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name','').strip()
        email = request.form.get('email','').strip().lower()
        password = request.form.get('password','').strip()
        plan = request.form.get('plan','free')
        if not name or not email or not password:
            flash('Fill all fields','error')
            return redirect(url_for('register'))
        if get_user_by_email(email):
            flash('Email already registered','error')
            return redirect(url_for('register'))
        ph = generate_password_hash(password)
        insert_user(name, email, ph, plan)
        flash('Registered. Please login.','success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email','').strip().lower()
        password = request.form.get('password','').strip()
        row = get_user_by_email(email)
        if not row:
            flash('No account with that email','error')
            return redirect(url_for('login'))
        user_id, name, email_db, password_hash, plan, searches_used = row
        if not check_password_hash(password_hash, password):
            flash('Incorrect password','error')
            return redirect(url_for('login'))
        session['user'] = {'id':user_id, 'name':name, 'email':email_db, 'plan':plan}
        flash('Welcome back','success')
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('Logged out','info')
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    user = session.get('user')
    if not user:
        return redirect(url_for('login'))
    row = get_user_by_id(user['id'])
    if row:
        session['user']['plan'] = row[4]
        session['user']['searches_used'] = row[5]
    return render_template('dashboard.html', user=session['user'], quotas=PLAN_QUOTAS)

@app.route('/upgrade', methods=['POST'])
def upgrade():
    user = session.get('user')
    if not user:
        return redirect(url_for('login'))
    newplan = request.form.get('plan','free')
    update_user_plan(user['id'], newplan)
    session['user']['plan'] = newplan
    session['user']['searches_used'] = 0
    flash('Plan updated (simulated payment)','success')
    return redirect(url_for('dashboard'))

@app.route('/post_job', methods=['GET','POST'])
def post_job():
    if request.method == 'POST':
        company = request.form.get('company','').strip()
        title = request.form.get('title','').strip()
        min_experience = int(request.form.get('min_experience') or 0)
        skills = request.form.get('skills','').strip()
        location = request.form.get('location','').strip()
        insert_employer(company, title, min_experience, skills, location)
        flash('Job posted','success')
        return redirect(url_for('index'))
    return render_template('employer.html')

@app.route('/find_jobs', methods=['GET','POST'])
def find_jobs():
    user = session.get('user')
    if request.method == 'POST':
        name = request.form.get('name','').strip()
        qualification = request.form.get('qualification','').strip()
        experience = int(request.form.get('experience') or 0)
        skills = request.form.get('skills','').strip()
        location = request.form.get('location','').strip()
        if user:
            row = get_user_by_id(user['id'])
            ok, reason = can_user_search(row)
            if not ok:
                flash('Search quota exceeded. Upgrade plan.','error')
                return redirect(url_for('dashboard'))
        seeker_obj = {'name':name,'qualification':qualification,'experience':experience,'skills':skills,'location':location}
        scored = score_jobs_for_seeker(seeker_obj)
        if user:
            increment_search_count(user['id'])
        return render_template('results.html', seeker=seeker_obj, scored=scored, user=user)
    return render_template('seeker.html', user=user)

@app.route('/api/match', methods=['POST'])
def api_match():
    data = request.get_json() or {}
    seeker_obj = {
        'name': data.get('name',''),
        'qualification': data.get('qualification',''),
        'experience': int(data.get('experience') or 0),
        'skills': data.get('skills',''),
        'location': data.get('location','')
    }
    scored = score_jobs_for_seeker(seeker_obj)
    return jsonify(scored)

@app.route('/admin/reset_counters')
def admin_reset():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET searches_used = 0")
    conn.commit()
    conn.close()
    return "Reset all counters."

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
