# -*- coding: utf-8 -*-
"""
app.py ── 台灣補助整合平台後端
執行： python app.py   然後開 http://127.0.0.1:5001
需要套件： pip install flask authlib requests python-dotenv
"""

import os
import uuid
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv

# 從專案根目錄的 .env 檔載入環境變數（金鑰等）
load_dotenv()

# 允許本機 http 進行 Google OAuth 驗證
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

DB_NAME = 'subsidies.db'

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET', 'subsidy_secret_key_xyz')

# ─────────────────────────────────────────────
# Google OAuth 設定（金鑰一律從環境變數讀取，不寫死）
# ⚠️ 舊的 client secret 已外流，請務必到 Google Cloud Console 重新產生一組。
# ─────────────────────────────────────────────
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')

# Google Maps JavaScript API 金鑰（選用）
# 有填 → 消費地圖 / 行程規劃改用 Google 地圖底圖 + 真實導航路線；
# 沒填 → 自動退回 Leaflet + OpenStreetMap（功能不受影響）。
# 需在 Google Cloud Console 啟用「Maps JavaScript API」與「Directions API」，
# 並把金鑰限制到 HTTP referer（localhost:5001 與正式網域）避免被盜用。
GOOGLE_MAPS_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY', '')

if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
    raise RuntimeError(
        '缺少 Google OAuth 金鑰。請先設定環境變數 GOOGLE_CLIENT_ID 與 '
        'GOOGLE_CLIENT_SECRET（可參考 .env.example），再啟動 app.py。'
    )

oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

# ─────────────────────────────────────────────
# Facebook 登入（選用）── 只有在 .env 填了金鑰時才啟用
# ─────────────────────────────────────────────
FACEBOOK_CLIENT_ID = os.environ.get('FACEBOOK_CLIENT_ID')
FACEBOOK_CLIENT_SECRET = os.environ.get('FACEBOOK_CLIENT_SECRET')
if FACEBOOK_CLIENT_ID and FACEBOOK_CLIENT_SECRET:
    oauth.register(
        name='facebook',
        client_id=FACEBOOK_CLIENT_ID,
        client_secret=FACEBOOK_CLIENT_SECRET,
        access_token_url='https://graph.facebook.com/v18.0/oauth/access_token',
        authorize_url='https://www.facebook.com/v18.0/dialog/oauth',
        api_base_url='https://graph.facebook.com/v18.0/',
        client_kwargs={'scope': 'email public_profile'},
    )

# ─────────────────────────────────────────────
# LINE 登入（選用）── 只有在 .env 填了金鑰時才啟用
# ─────────────────────────────────────────────
LINE_CLIENT_ID = os.environ.get('LINE_CLIENT_ID')
LINE_CLIENT_SECRET = os.environ.get('LINE_CLIENT_SECRET')
if LINE_CLIENT_ID and LINE_CLIENT_SECRET:
    oauth.register(
        name='line',
        client_id=LINE_CLIENT_ID,
        client_secret=LINE_CLIENT_SECRET,
        access_token_url='https://api.line.me/oauth2/v2.1/token',
        authorize_url='https://access.line.me/oauth2/v2.1/authorize',
        api_base_url='https://api.line.me/',
        client_kwargs={
            # 只用 profile（不含 openid），改用 LINE Profile API 拿資料，
            # 避免解 id_token 時遇到 HS256 被擋的問題。
            'scope': 'profile',
            'token_endpoint_auth_method': 'client_secret_post',
        },
    )


def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def rows_to_dicts(rows):
    return [dict(r) for r in rows]


def _finish_login(user_info):
    """把使用者存進 session 與資料庫，完成登入（各種登入方式共用）。"""
    session['user'] = user_info
    conn = get_db()
    conn.execute(
        'INSERT OR IGNORE INTO users (google_id, email, name, picture) VALUES (?, ?, ?, ?)',
        (user_info.get('sub'), user_info.get('email'),
         user_info.get('name'), user_info.get('picture'))
    )
    conn.commit()
    conn.close()


def _provider_not_ready(name):
    """某個社群登入還沒在 .env 設定金鑰時，顯示友善提示而不是報錯。"""
    key = name.upper()
    return (
        f'<div style="font-family:sans-serif;max-width:480px;margin:80px auto;'
        f'text-align:center;line-height:1.8">'
        f'<h2>{name} 登入尚未設定</h2>'
        f'<p>請先在 <code>.env</code> 填入 <b>{key}_CLIENT_ID</b> 與 '
        f'<b>{key}_CLIENT_SECRET</b>，並重新啟動網站。</p>'
        f'<p><a href="/">← 返回登入頁</a></p></div>'
    )


@app.route('/')
def index():
    user_info = session.get('user')
    if not user_info:
        return render_template('login.html')

    g_id = user_info.get('sub')
    conn = get_db()
    cur = conn.cursor()

    db_user = cur.execute(
        "SELECT age, city, interest FROM users WHERE google_id = ?", (g_id,)
    ).fetchone()

    user_profile = {
        'name': user_info.get('name'),
        'picture': user_info.get('picture'),
        'age': db_user['age'] if db_user else None,
        'city': db_user['city'] if db_user else None,
        'interest': db_user['interest'] if db_user else None,
    }

    subsidies = rows_to_dicts(cur.execute("SELECT * FROM subsidy_list").fetchall())
    stores = rows_to_dicts(cur.execute("SELECT * FROM stores").fetchall())

    claimed = [r['subsidy_id'] for r in cur.execute(
        "SELECT subsidy_id FROM user_claims WHERE google_id = ?", (g_id,)
    ).fetchall()]

    conn.close()

    return render_template(
        'index.html',
        user=user_profile,
        subsidies=subsidies,
        stores=stores,
        claimed=claimed,
        maps_key=GOOGLE_MAPS_API_KEY
    )


@app.route('/login')
def login():
    redirect_uri = url_for('auth', _external=True)
    return google.authorize_redirect(redirect_uri)


@app.route('/login/callback')
def auth():
    token = google.authorize_access_token()
    user_info = token.get('userinfo')
    if user_info:
        _finish_login(dict(user_info))
    return redirect('/')


# 訪客快速登入（免註冊，立即體驗）
@app.route('/guest_login')
def guest_login():
    guest_id = 'guest_' + uuid.uuid4().hex[:12]
    _finish_login({
        'sub': guest_id,
        'name': '訪客',
        'email': None,
        'picture': 'https://ui-avatars.com/api/?name=Guest&background=E2858E&color=fff',
    })
    return redirect('/')


# Facebook 登入
@app.route('/login/facebook')
def login_facebook():
    fb = oauth.create_client('facebook')
    if fb is None:
        return _provider_not_ready('Facebook')
    return fb.authorize_redirect(url_for('facebook_callback', _external=True))


@app.route('/login/facebook/callback')
def facebook_callback():
    fb = oauth.create_client('facebook')
    if fb is None:
        return _provider_not_ready('Facebook')
    fb.authorize_access_token()
    profile = fb.get('me?fields=id,name,email,picture.width(200)').json()
    picture = (profile.get('picture') or {}).get('data', {}).get('url')
    _finish_login({
        'sub': 'fb_' + str(profile.get('id')),
        'name': profile.get('name'),
        'email': profile.get('email'),
        'picture': picture,
    })
    return redirect('/')


# LINE 登入
@app.route('/login/line')
def login_line():
    line = oauth.create_client('line')
    if line is None:
        return _provider_not_ready('LINE')
    return line.authorize_redirect(url_for('line_callback', _external=True))


@app.route('/login/line/callback')
def line_callback():
    line = oauth.create_client('line')
    if line is None:
        return _provider_not_ready('LINE')
    line.authorize_access_token()
    # 用 access token 直接向 LINE Profile API 拿使用者資料（不解 id_token）
    profile = line.get('v2/profile').json()
    _finish_login({
        'sub': 'line_' + str(profile.get('userId')),
        'name': profile.get('displayName'),
        'email': None,
        'picture': profile.get('pictureUrl'),
    })
    return redirect('/')


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


@app.route('/update_profile', methods=['POST'])
def update_profile():
    user_info = session.get('user')
    if not user_info:
        return jsonify({"success": False, "message": "未登入"}), 401

    data = request.get_json()
    g_id = user_info.get('sub')
    conn = get_db()
    # 確保使用者這筆存在（例如剛重建過資料庫），沒有就先自動建立，避免更新不到
    conn.execute(
        'INSERT OR IGNORE INTO users (google_id, email, name, picture) VALUES (?, ?, ?, ?)',
        (g_id, user_info.get('email'), user_info.get('name'), user_info.get('picture'))
    )
    conn.execute(
        'UPDATE users SET age = ?, city = ?, interest = ? WHERE google_id = ?',
        (data.get('age'), data.get('city'), data.get('interest'), g_id)
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "資料更新成功！"})


@app.route('/claim', methods=['POST'])
def claim():
    user_info = session.get('user')
    if not user_info:
        return jsonify({"success": False, "message": "未登入"}), 401

    data = request.get_json()
    subsidy_id = data.get('subsidy_id')
    g_id = user_info.get('sub')

    conn = get_db()
    cur = conn.cursor()
    existing = cur.execute(
        "SELECT id FROM user_claims WHERE google_id = ? AND subsidy_id = ?",
        (g_id, subsidy_id)
    ).fetchone()

    if existing:
        cur.execute("DELETE FROM user_claims WHERE id = ?", (existing['id'],))
        claimed = False
    else:
        cur.execute(
            "INSERT INTO user_claims (google_id, subsidy_id) VALUES (?, ?)",
            (g_id, subsidy_id)
        )
        claimed = True

    conn.commit()
    conn.close()
    return jsonify({"success": True, "claimed": claimed})


@app.route('/api/subsidies')
def api_subsidies():
    conn = get_db()
    data = rows_to_dicts(conn.execute("SELECT * FROM subsidy_list").fetchall())
    conn.close()
    return jsonify(data)


@app.route('/api/stores')
def api_stores():
    conn = get_db()
    data = rows_to_dicts(conn.execute("SELECT * FROM stores").fetchall())
    conn.close()
    return jsonify(data)


if __name__ == '__main__':
    # debug=True 僅供本機開發；正式部署請關閉並改用正式 WSGI 伺服器
    app.run(debug=True, port=5001)
