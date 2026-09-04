import os, json, re, sqlite3, functools
from flask import Flask, request, jsonify, session, redirect, url_for, render_template, abort
from werkzeug.security import generate_password_hash, check_password_hash

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, os.getenv('DB_FILE','din_farm.db'))
SECRET = os.getenv('SECRET_KEY','change-this-secret-key')
ADMIN_USER = os.getenv('ADMIN_USER','admin')
ADMIN_PASS = os.getenv('ADMIN_PASS','dinfarm123')

app = Flask(__name__, template_folder=os.path.join(BASE,'templates'))
app.secret_key = SECRET
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')

def db():
    c=sqlite3.connect(DB)
    c.row_factory=sqlite3.Row
    return c

def init_db():
    con=db()
    con.executescript('''
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'viewer');
    CREATE TABLE IF NOT EXISTS kv(dashboard TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(dashboard,key));
    ''')
    if not con.execute('SELECT 1 FROM users WHERE username=?',(ADMIN_USER,)).fetchone():
        con.execute('INSERT INTO users(username,password_hash,role) VALUES(?,?,?)',(ADMIN_USER,generate_password_hash(ADMIN_PASS),'admin'))
    # Keep each dashboard's data completely separate.
    d1=open(os.path.join(BASE,'templates','dashboard1.html'),encoding='utf8').read()
    d2=open(os.path.join(BASE,'templates','dashboard2.html'),encoding='utf8').read()
    def arr(text,var):
        m=re.search(r'const '+re.escape(var)+r'\s*=\s*(\[.*?\]);',text,re.S)
        if not m: raise RuntimeError('Could not find '+var)
        return json.loads(m.group(1))
    seeds={
      ('d1','entries'):arr(d1,'SEED_ENTRIES'),
      ('d1','schedule'):arr(d1,'SEED_SCHEDULE'),
      ('d1','wapdaEvents'):[],
      ('d1','entriesSeedVersion'):None,
      ('d2','reading_overrides'):{}
    }
    seeds[('d1','entriesSeedVersion')]=str(len(seeds[('d1','entries')]))+'@'+max(x['date'] for x in seeds[('d1','entries')])
    for (dash,key),val in seeds.items():
        if not con.execute('SELECT 1 FROM kv WHERE dashboard=? AND key=?',(dash,key)).fetchone():
            con.execute('INSERT INTO kv(dashboard,key,value) VALUES(?,?,?)',(dash,key,json.dumps(val,separators=(',',':'))))
    con.commit(); con.close()

@app.before_request
def auth_gate():
    if request.endpoint in {'login','static'}: return
    if not session.get('user'):
        if request.path.startswith('/api/'):
            return jsonify(ok=False,error='Authentication required'),401
        return redirect(url_for('login',next=request.path))

def admin_required(fn):
    @functools.wraps(fn)
    def wrap(*a,**kw):
        if session.get('role')!='admin': return jsonify(ok=False,error='Admin permission required'),403
        return fn(*a,**kw)
    return wrap

@app.route('/login',methods=['GET','POST'])
def login():
    msg=''
    if request.method=='POST':
        u=request.form.get('username','').strip(); p=request.form.get('password','')
        con=db(); row=con.execute('SELECT * FROM users WHERE username=?',(u,)).fetchone(); con.close()
        if row and check_password_hash(row['password_hash'],p):
            session['user']=row['username']; session['role']=row['role']
            return redirect(request.args.get('next') or url_for('home'))
        msg='Invalid username or password.'
    return render_template('login.html',msg=msg)

@app.route('/logout')
def logout():
    session.clear(); return redirect(url_for('login'))

@app.route('/')
def home(): return render_template('home.html',user=session['user'],role=session['role'])
@app.route('/dashboard1')
def dashboard1(): return render_template('dashboard1.html')
@app.route('/dashboard2')
def dashboard2(): return render_template('dashboard2.html')

@app.route('/api/me')
def me(): return jsonify(ok=True,user=session['user'],role=session['role'])

@app.route('/api/state/<dashboard>/<key>',methods=['GET'])
def get_state(dashboard,key):
    con=db(); row=con.execute('SELECT value FROM kv WHERE dashboard=? AND key=?',(dashboard,key)).fetchone(); con.close()
    return jsonify(ok=True,value=(row['value'] if row else None))

@app.route('/api/state/<dashboard>/<key>',methods=['POST'])
@admin_required
def set_state(dashboard,key):
    body=request.get_json(silent=True) or {}
    value=body.get('value')
    if value is None: return jsonify(ok=False,error='Missing value'),400
    con=db(); con.execute('''INSERT INTO kv(dashboard,key,value,updated_at) VALUES(?,?,?,CURRENT_TIMESTAMP)
      ON CONFLICT(dashboard,key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP''',(dashboard,key,str(value)))
    con.commit(); con.close(); return jsonify(ok=True)

@app.route('/api/state/<dashboard>',methods=['GET'])
def get_all_state(dashboard):
    con=db(); rows=con.execute('SELECT key,value,updated_at FROM kv WHERE dashboard=?',(dashboard,)).fetchall(); con.close()
    return jsonify(ok=True,state={r['key']:r['value'] for r in rows},updated={r['key']:r['updated_at'] for r in rows})

@app.route('/api/users',methods=['GET'])
@admin_required
def users():
    con=db(); rows=con.execute('SELECT id,username,role FROM users ORDER BY username').fetchall(); con.close()
    return jsonify(ok=True,users=[dict(r) for r in rows])

@app.route('/api/users',methods=['POST'])
@admin_required
def add_user():
    b=request.get_json(silent=True) or {}; u=b.get('username','').strip(); p=b.get('password',''); role=b.get('role','viewer')
    if not u or not p or role not in ('admin','viewer'): return jsonify(ok=False,error='Username, password and valid role required'),400
    con=db()
    try: con.execute('INSERT INTO users(username,password_hash,role) VALUES(?,?,?)',(u,generate_password_hash(p),role)); con.commit()
    except sqlite3.IntegrityError: con.close(); return jsonify(ok=False,error='Username already exists'),409
    con.close(); return jsonify(ok=True)

@app.route('/api/users/<int:user_id>',methods=['DELETE'])
@admin_required
def del_user(user_id):
    con=db(); row=con.execute('SELECT username FROM users WHERE id=?',(user_id,)).fetchone()
    if not row: con.close(); return jsonify(ok=False,error='User not found'),404
    if row['username']==session['user']: con.close(); return jsonify(ok=False,error='You cannot delete your own account'),400
    con.execute('DELETE FROM users WHERE id=?',(user_id,)); con.commit(); con.close(); return jsonify(ok=True)

if __name__=='__main__':
    init_db()
    app.run(host='0.0.0.0',port=int(os.getenv('PORT','5000')),debug=False)
