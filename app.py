# -*- coding: utf-8 -*-
"""
Ferma Jaj SaaS v4 — multi-tenant
Uruchomienie: python3 app.py
"""
from flask import Flask, request, redirect, flash, session, jsonify, send_file
from markupsafe import Markup
from flask import render_template_string
from datetime import datetime, date, timedelta
import os, io, json

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-zmien-na-produkcji")

from datetime import timedelta
app.permanent_session_lifetime = timedelta(days=30)

from db import get_db, get_setting, save_setting, init_db
from auth import (login_required, farm_required, superadmin_required,
                  current_user, current_farm, login_user, register_user,
                  get_user_farms, create_farm, user_can_access_farm,
                  change_password, init_auth)
from devices import send_command, ping_device, ESP32_FIRMWARE

# ─── MODUŁY ROZSZERZEŃ ───────────────────────────────────────────────────────
from routes import register_routes

# ─── HELPER: pobierz gid z sesji ─────────────────────────────────────────────
def gid():
    return session.get("farm_id")

def gs(key, default=""):
    return get_setting(key, default, gid())

# ─── BAZOWY SZABLON HTML ──────────────────────────────────────────────────────
BASE = """<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ferma Jaj{% if farm_name %} — {{ farm_name }}{% endif %}</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,sans-serif;background:#f5f5f0;color:#2c2c2a;font-size:15px}
nav{background:#fff;border-bottom:1px solid #e0ddd4;padding:0 12px;display:flex;align-items:center;gap:2px;position:sticky;top:0;z-index:200;height:48px}
nav .logo{font-weight:700;font-size:15px;color:#534AB7;padding-right:12px;white-space:nowrap}
.nb-item{position:relative}
.nb-link{display:flex;align-items:center;gap:4px;padding:0 10px;height:48px;text-decoration:none;color:#5f5e5a;font-size:13px;white-space:nowrap;border-bottom:2px solid transparent;cursor:pointer;background:none;border-top:none;border-left:none;border-right:none;font-family:inherit}
.nb-link:hover,.nb-link.on{color:#2c2c2a;border-bottom-color:#534AB7}
.nb-link .arr{font-size:9px;opacity:0.5;transition:transform .15s}
.nb-item:hover .arr{transform:rotate(180deg)}
.nb-drop{display:none;position:absolute;top:48px;left:0;background:#fff;border:1px solid #e0ddd4;border-radius:10px;box-shadow:0 4px 16px rgba(0,0,0,0.08);min-width:180px;padding:4px;z-index:300}
.nb-item:hover .nb-drop{display:block}
.nb-drop a{display:block;padding:8px 14px;color:#2c2c2a;text-decoration:none;font-size:13px;border-radius:6px;white-space:nowrap}
.nb-drop a:hover{background:#f5f5f0}
.nb-drop a.on{color:#534AB7;font-weight:500;background:#EEEDFE}
.nb-sep{height:1px;background:#e0ddd4;margin:4px 0}
.nb-right{margin-left:auto;display:flex;align-items:center;gap:4px}
.farm-badge{background:#EEEDFE;color:#3C3489;border-radius:20px;padding:3px 10px;font-size:12px;font-weight:500;white-space:nowrap;max-width:150px;overflow:hidden;text-overflow:ellipsis}
.farm-badge{background:#EEEDFE;color:#3C3489;border-radius:6px;padding:3px 10px;font-size:12px;font-weight:500;margin-left:4px}
.wrap{max-width:980px;margin:0 auto;padding:14px}
h1{font-size:19px;font-weight:500;margin-bottom:14px}
h2{font-size:14px;font-weight:500;margin:16px 0 8px;color:#444}
.card{background:#fff;border:1px solid #e0ddd4;border-radius:12px;padding:14px;margin-bottom:12px}
.g2{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.g3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}
.g4{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
@media(max-width:600px){.g3,.g4{grid-template-columns:1fr 1fr}.g2{grid-template-columns:1fr}}
.stat{text-align:center;padding:10px 4px}
.stat .v{font-size:24px;font-weight:500;line-height:1.2}
.stat .l{font-size:11px;color:#888;margin-top:3px}
.stat .s{font-size:11px;color:#5f5e5a;margin-top:2px}
.al{padding:9px 13px;border-radius:8px;margin-bottom:8px;font-size:13px}
.ald{background:#FCEBEB;border:1px solid #F7C1C1;color:#791F1F}
.alw{background:#FAEEDA;border:1px solid #FAC775;color:#633806}
.alok{background:#EAF3DE;border:1px solid #C0DD97;color:#27500A}
label{display:block;font-size:12px;color:#5f5e5a;margin:8px 0 3px}
input,select,textarea{width:100%;padding:8px 10px;border:1px solid #d3d1c7;border-radius:8px;font-size:14px;background:#fff;color:#2c2c2a}
input:focus,select:focus,textarea:focus{outline:none;border-color:#7F77DD}
.btn{display:inline-block;padding:8px 16px;border-radius:8px;border:1px solid transparent;font-size:14px;cursor:pointer;text-decoration:none;font-weight:500;line-height:1.2}
.bp{background:#534AB7;color:#fff;border-color:#534AB7}.bp:hover{background:#3C3489}
.bo{background:#fff;color:#534AB7;border-color:#AFA9EC}.bo:hover{background:#EEEDFE}
.bg{background:#3B6D11;color:#fff}.br{background:#A32D2D;color:#fff}
.bsm{padding:5px 10px;font-size:12px}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;padding:7px 8px;border-bottom:1px solid #e0ddd4;font-weight:500;font-size:12px;color:#5f5e5a}
td{padding:7px 8px;border-bottom:1px solid #f0ede4;vertical-align:middle}
tr:last-child td{border-bottom:none}
.badge{display:inline-block;padding:2px 7px;border-radius:10px;font-size:11px;font-weight:500}
.b-blue{background:#E6F1FB;color:#0C447C}.b-green{background:#EAF3DE;color:#27500A}
.b-gray{background:#F1EFE8;color:#444}.b-red{background:#FCEBEB;color:#791F1F}
.b-amber{background:#FAEEDA;color:#633806}.b-purple{background:#EEEDFE;color:#3C3489}
.flash{padding:9px 13px;border-radius:8px;margin-bottom:10px;font-size:13px;background:#EAF3DE;color:#27500A;border:1px solid #C0DD97}
.relay-card{border:1px solid #e0ddd4;border-radius:10px;padding:12px 8px;text-align:center;background:#fff;cursor:pointer}
.relay-on{border-color:#3B6D11;background:#f4faf0}
.tog{display:inline-block;width:44px;height:24px;background:#d3d1c7;border-radius:12px;position:relative;transition:background .2s}
.tog.on{background:#3B6D11}
.tog::after{content:'';position:absolute;top:3px;left:3px;width:18px;height:18px;background:#fff;border-radius:50%;transition:transform .2s}
.tog.on::after{transform:translateX(20px)}
code{background:#f0ede4;padding:2px 6px;border-radius:4px;font-size:12px}
.nowrap{white-space:nowrap}
</style>
</head>
<body>
<nav>
  <span class="logo">&#x1F413; Ferma</span>
  {% if farm_id %}
  <span class="farm-badge" title="{{ farm_name }}">{{ farm_name }}</span>
  <a href="/" class="nb-link {{ 'on' if p=='dash' }}">Dashboard</a>
  <div class="nb-item">
    <span class="nb-link {{ 'on' if p in ['prod','stado'] }}">Hodowla <span class="arr">&#9660;</span></span>
    <div class="nb-drop">
      <a href="/produkcja" class="{{ 'on' if p=='prod' }}">Produkcja jaj</a>
      <a href="/stado" class="{{ 'on' if p=='stado' }}">Stado</a>
      <div class="nb-sep"></div>
      <a href="/dzienne-czynnosci">Czynności dzienne</a>
    </div>
  </div>
  <div class="nb-item">
    <span class="nb-link {{ 'on' if p in ['zam','mag'] }}">Sprzedaż <span class="arr">&#9660;</span></span>
    <div class="nb-drop">
      <a href="/zamowienia" class="{{ 'on' if p=='zam' }}">Zamówienia</a>
      <a href="/klienci">Klienci</a>
      <a href="/magazyn" class="{{ 'on' if p=='mag' }}">Magazyn jaj</a>
    </div>
  </div>
  <div class="nb-item">
    <span class="nb-link {{ 'on' if p in ['wyd','pasza','woda'] }}">Zasoby <span class="arr">&#9660;</span></span>
    <div class="nb-drop">
      <a href="/wydatki" class="{{ 'on' if p=='wyd' }}">Wydatki</a>
      <a href="/pasza" class="{{ 'on' if p=='pasza' }}">Pasza</a>
      <a href="/pasza/predykcja">Predykcja paszy</a>
      <a href="/woda" class="{{ 'on' if p=='woda' }}">Woda</a>
      <a href="/energia">Energia</a>
      <div class="nb-sep"></div>
      <a href="/wyposazenie" class="{{ 'on' if p=='wyp' }}">Wyposażenie</a>
    </div>
  </div>
  <div class="nb-item">
    <span class="nb-link {{ 'on' if p in ['gpio','urz','kal'] }}">Sterowanie <span class="arr">&#9660;</span></span>
    <div class="nb-drop">
      <a href="/sterowanie" class="{{ 'on' if p=='gpio' }}">Tryby sterowania</a>
      <a href="/gpio" class="{{ 'on' if p=='gpio' }}">GPIO / przekaźniki</a>
      <a href="/gpio/pwm">LED PWM</a>
      <a href="/urzadzenia" class="{{ 'on' if p=='urz' }}">Urządzenia slave</a>
      <div class="nb-sep"></div>
      <a href="/pojenie">Pojenie</a>
      <a href="/kalendarz" class="{{ 'on' if p=='kal' }}">Kalendarz</a>
      <div class="nb-sep"></div>
      <a href="/integracje/esphome">ESPHome</a>
      <a href="/integracje/supla">Supla</a>
    </div>
  </div>
  <div class="nb-item">
    <span class="nb-link {{ 'on' if p=='ana' }}">Analityka <span class="arr">&#9660;</span></span>
    <div class="nb-drop">
      <a href="/analityka" class="{{ 'on' if p=='ana' }}">Wykresy</a>
      <a href="/pasza/analityka">Analiza paszy</a>
      <a href="/pasza/skladniki-baza">Baza składników</a>
    </div>
  </div>
  {% endif %}
  <div class="nb-right">
    <a href="/wybierz-gospodarstwo" class="nb-link {{ 'on' if p=='farms' }}" title="Zmień gospodarstwo">&#x1F3E1;</a>
    <div class="nb-item">
      <span class="nb-link">{{ login }} <span class="arr">&#9660;</span></span>
      <div class="nb-drop" style="right:0;left:auto">
        <a href="/konto">Moje konto</a>
        <a href="/import/xlsx">Import xlsx</a>
        <a href="/ustawienia">Ustawienia</a>
        {% if rola == 'superadmin' %}
        <div class="nb-sep"></div>
        <a href="/admin" class="{{ 'on' if p=='admin' }}">Panel admina</a>
        <a href="/admin/farm-assign">Przypisz farmy</a>
        {% endif %}
        <div class="nb-sep"></div>
        <a href="/logout" style="color:#A32D2D">Wyloguj</a>
      </div>
    </div>
  </div>
</nav>
<div class="wrap">
{% with msgs = get_flashed_messages() %}{% if msgs %}{% for m in msgs %}<div class="flash">{{ m }}</div>{% endfor %}{% endif %}{% endwith %}
{{ content }}
</div>
</body></html>"""

def R(html, p=""):
    uid, login, rola = current_user()
    farm_id, farm_name = current_farm()
    return render_template_string(BASE,
        content=Markup(html), p=p,
        login=login or "", rola=rola,
        farm_id=farm_id, farm_name=farm_name)

def login_page(error=""):
    html = (
        '<div style="min-height:80vh;display:flex;align-items:center;justify-content:center">'
        '<div style="background:#fff;border:1px solid #e0ddd4;border-radius:16px;padding:40px 36px;width:100%;max-width:380px">'
        '<div style="font-size:36px;text-align:center;margin-bottom:8px">🐓</div>'
        '<h1 style="text-align:center;font-size:22px;font-weight:500;margin-bottom:6px">Ferma Jaj</h1>'
        '<p style="text-align:center;font-size:13px;color:#888;margin-bottom:24px">System zarządzania fermą</p>'
        + (f'<div class="al ald" style="margin-bottom:12px">{error}</div>' if error else "")
        + '<form method="POST">'
        '<label>Login lub email</label><input name="login" autofocus autocomplete="username">'
        '<label>Hasło</label><input name="haslo" type="password" autocomplete="current-password">'
        '<br><button class="btn bp" style="width:100%;margin-top:12px">Zaloguj się</button>'
        '</form>'
        '<hr style="margin:20px 0;border:none;border-top:1px solid #e0ddd4">'
        '<p style="text-align:center;font-size:13px;color:#888">Nie masz konta? '
        '<a href="/rejestracja" style="color:#534AB7">Zarejestruj się</a></p>'
        '</div></div>'
    )
    from flask import render_template_string
    return render_template_string(
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Logowanie — Ferma Jaj</title>'
        '<style>*{box-sizing:border-box;margin:0;padding:0}body{font-family:system-ui,sans-serif;background:#f5f5f0;color:#2c2c2a}'
        'label{display:block;font-size:12px;color:#5f5e5a;margin:8px 0 3px}'
        'input{width:100%;padding:9px 11px;border:1px solid #d3d1c7;border-radius:8px;font-size:15px;background:#fff}'
        '.btn{display:inline-block;padding:10px;border-radius:8px;border:none;font-size:15px;cursor:pointer;font-weight:500}'
        '.bp{background:#534AB7;color:#fff}.al{padding:9px 13px;border-radius:8px;font-size:13px}'
        '.ald{background:#FCEBEB;border:1px solid #F7C1C1;color:#791F1F}'
        '</style></head><body>' + html + '</body></html>'
    )

# ─── AUTH ROUTES ─────────────────────────────────────────────────────────────
@app.route("/login", methods=["GET","POST"])
def login():
    if session.get("user_id"):
        return redirect("/")
    if request.method == "POST":
        u = login_user(request.form.get("login",""), request.form.get("haslo",""))
        if u:
            session.permanent = True
            session["user_id"] = u["id"]
            session["login"]   = u["login"]
            session["rola"]    = u["rola"]
            farms = get_user_farms(u["id"])
            if len(farms) == 1:
                session["farm_id"]   = farms[0]["id"]
                session["farm_name"] = farms[0]["nazwa"]
            return redirect(request.args.get("next","/wybierz-gospodarstwo"))
        return login_page("Nieprawidłowy login lub hasło")
    return login_page()

@app.route("/rejestracja", methods=["GET","POST"])
def rejestracja():
    db = get_db()
    otwarta = db.execute("SELECT wartosc FROM system_config WHERE klucz='rejestracja_otwarta'").fetchone()
    db.close()
    if otwarta and otwarta["wartosc"] != "1":
        return login_page("Rejestracja jest wyłączona. Skontaktuj się z administratorem.")
    if request.method == "POST":
        email = request.form.get("email","").strip()
        login_val = request.form.get("login","").strip()
        haslo = request.form.get("haslo","")
        haslo2= request.form.get("haslo2","")
        nazwa_farm = request.form.get("nazwa_farm","Moje Gospodarstwo").strip()
        if haslo != haslo2:
            flash("Hasła nie są identyczne.")
            return redirect("/rejestracja")
        if len(haslo) < 6:
            flash("Hasło musi mieć min. 6 znaków.")
            return redirect("/rejestracja")
        uid, err = register_user(email, login_val, haslo)
        if err:
            flash(err)
            return redirect("/rejestracja")
        gid_new = create_farm(uid, nazwa_farm)
        session.permanent = True
        session["user_id"]   = uid
        session["login"]     = login_val
        session["rola"]      = "user"
        session["farm_id"]   = gid_new
        session["farm_name"] = nazwa_farm
        flash("Konto i gospodarstwo utworzone. Witaj!")
        return redirect("/")
    from flask import render_template_string
    html = (
        '<div style="min-height:80vh;display:flex;align-items:center;justify-content:center">'
        '<div style="background:#fff;border:1px solid #e0ddd4;border-radius:16px;padding:40px 36px;width:100%;max-width:420px">'
        '<div style="font-size:36px;text-align:center;margin-bottom:8px">🐓</div>'
        '<h1 style="text-align:center;font-size:20px;font-weight:500;margin-bottom:20px">Nowe konto</h1>'
        '<form method="POST">'
        '<label>Email</label><input name="email" type="email" required>'
        '<label>Login (nazwa użytkownika)</label><input name="login" required>'
        '<label>Hasło</label><input name="haslo" type="password" required>'
        '<label>Powtórz hasło</label><input name="haslo2" type="password" required>'
        '<label>Nazwa pierwszego gospodarstwa</label><input name="nazwa_farm" placeholder="np. Ferma Kowalskich" value="Moje Gospodarstwo">'
        '<br><button class="btn bp" style="width:100%;margin-top:12px">Utwórz konto</button>'
        '</form>'
        '<p style="text-align:center;font-size:13px;color:#888;margin-top:16px">'
        '<a href="/login" style="color:#534AB7">Mam już konto</a></p>'
        '</div></div>'
    )
    return render_template_string(
        '<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Rejestracja — Ferma Jaj</title>'
        '<style>*{box-sizing:border-box;margin:0;padding:0}body{font-family:system-ui,sans-serif;background:#f5f5f0}'
        'label{display:block;font-size:12px;color:#5f5e5a;margin:8px 0 3px}'
        'input{width:100%;padding:9px 11px;border:1px solid #d3d1c7;border-radius:8px;font-size:15px;background:#fff}'
        '.btn{display:inline-block;padding:10px;border-radius:8px;border:none;font-size:15px;cursor:pointer;font-weight:500}'
        '.bp{background:#534AB7;color:#fff}'
        '</style></head><body>' + html + '</body></html>'
    )

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ─── WYBÓR GOSPODARSTWA ───────────────────────────────────────────────────────
@app.route("/wybierz-gospodarstwo", methods=["GET","POST"])
@login_required
def wybierz_gospodarstwo():
    uid, login_val, rola = current_user()
    if request.method == "POST":
        action = request.form.get("action","")
        if action == "wybierz":
            farm_id_val = int(request.form.get("farm_id",0))
            if user_can_access_farm(uid, farm_id_val):
                db = get_db()
                f = db.execute("SELECT nazwa FROM gospodarstwa WHERE id=?", (farm_id_val,)).fetchone()
                db.close()
                session["farm_id"]   = farm_id_val
                session["farm_name"] = f["nazwa"] if f else ""
                return redirect("/")
        elif action == "nowe":
            nazwa = request.form.get("nazwa","").strip()
            if nazwa:
                gid_new = create_farm(uid, nazwa, request.form.get("opis",""))
                session["farm_id"]   = gid_new
                session["farm_name"] = nazwa
                flash("Gospodarstwo '" + nazwa + "' utworzone.")
                return redirect("/")
    farms = get_user_farms(uid)
    current_gid = session.get("farm_id")
    w = "".join(
        '<tr>'
        '<td style="font-weight:500">' + f["nazwa"] + '</td>'
        '<td style="color:#888;font-size:12px">' + (f["opis"] or "") + '</td>'
        '<td><span class="badge b-purple">' + f["moja_rola"] + '</span></td>'
        '<td>'
        '<form method="POST" style="display:inline">'
        '<input type="hidden" name="action" value="wybierz">'
        '<input type="hidden" name="farm_id" value="' + str(f["id"]) + '">'
        '<button class="btn ' + ('bg' if f["id"]==current_gid else 'bp') + ' bsm">'
        + ('Aktywne' if f["id"]==current_gid else 'Wybierz') + '</button>'
        '</form>'
        '</td></tr>'
        for f in farms
    )
    html = (
        '<h1>Twoje gospodarstwa</h1>'
        '<div class="card" style="overflow-x:auto">'
        '<table><thead><tr><th>Nazwa</th><th>Opis</th><th>Rola</th><th></th></tr></thead>'
        '<tbody>' + (w or '<tr><td colspan=4 style="color:#888;text-align:center;padding:20px">Brak gospodarstw</td></tr>') + '</tbody></table></div>'
        '<div class="card"><b>Nowe gospodarstwo</b>'
        '<form method="POST" style="margin-top:10px">'
        '<input type="hidden" name="action" value="nowe">'
        '<div class="g2">'
        '<div><label>Nazwa</label><input name="nazwa" required placeholder="np. Ferma Kowalskich"></div>'
        '<div><label>Opis (opcjonalnie)</label><input name="opis"></div>'
        '</div>'
        '<br><button class="btn bp">Utwórz gospodarstwo</button>'
        '</form></div>'
    )
    return R(html, "farms")

# ─── HEALTH ───────────────────────────────────────────────────────────────────
@app.route("/health")
def health():
    return jsonify({"status":"ok","time":datetime.now().isoformat()})

# ─── DASHBOARD ────────────────────────────────────────────────────────────────
# ─── HELPER: kafelki czynności dla dashboardu ─────────────────────────────────
_CZYN_DEF = [
    ("poidla","Poidła","💧"),("karmidla","Karmidła","🌾"),("pasza","Pasza","🌽"),
    ("jaja","Jaja","🥚"),("scioka","Ściółka","🏚"),("leki","Witaminy","💊"),
    ("bramka","Bramka","🚪"),("posprzatan","Sprzątanie","🧹"),
]

def _kafelki_czynnosci(g, db_cz=None):
    if db_cz is None:
        db_cz = get_db()
    d = date.today().isoformat()
    wpis = db_cz.execute(
        "SELECT czynnosci FROM dzienne_czynnosci WHERE gospodarstwo_id=? AND data=?",
        (g, d)
    ).fetchone()
    db_cz.close()
    zaznaczone = json.loads(wpis["czynnosci"]) if wpis else []
    n_ok  = len(zaznaczone)
    n_all = len(_CZYN_DEF)
    pct   = round(n_ok / n_all * 100) if n_all else 0
    kolor = "#3B6D11" if pct >= 80 else "#BA7517" if pct >= 50 else "#A32D2D"

    tiles = ""
    for k, l, ico in _CZYN_DEF:
        on = k in zaznaczone
        chk = "checked" if on else ""
        cls = "tile tile-on" if on else "tile"
        onchange = "this.closest('label').classList.toggle('tile-on',this.checked)"
        tiles += (
            f'<label style="cursor:pointer">'
            f'<input type="checkbox" name="cz" value="{k}" {chk}'
            f' style="display:none" onchange="{onchange}">'
            f'<div class="{cls}">'
            f'<div style="font-size:22px;line-height:1">{ico}</div>'
            f'<div style="font-size:11px;font-weight:500;margin-top:4px">{l}</div>'
            f'</div></label>'
        )

    bar_style = (
        f'width:{pct}%;background:{kolor};'
        'height:100%;border-radius:4px;transition:width .3s'
    )
    return (
        '<style>'
        '.tile{border:2px solid #e0ddd4;border-radius:12px;padding:10px 6px;text-align:center;'
        'background:#fff;transition:border-color .15s,background .15s;min-height:72px;'
        'display:flex;flex-direction:column;align-items:center;justify-content:center}'
        '.tile-on{border-color:#3B6D11!important;background:#EAF3DE!important}'
        '.tiles-g{display:grid;grid-template-columns:repeat(8,1fr);gap:6px}'
        '@media(max-width:700px){.tiles-g{grid-template-columns:repeat(4,1fr)}}'
        '</style>'
        f'<div class="card" style="margin-bottom:10px">'
        f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px">'
        f'<b>Czynności dzienne</b>'
        f'<div style="flex:1;background:#e0ddd4;border-radius:4px;height:6px">'
        f'<div style="{bar_style}"></div></div>'
        f'<span style="font-size:13px;color:{kolor};font-weight:500">{n_ok}/{n_all}</span>'
        f'</div>'
        f'<form method="POST" action="/dashboard-czynnosci">'
        f'<div class="tiles-g">{tiles}</div>'
        f'<button type="submit" class="btn bg bsm" style="margin-top:10px;width:100%">Zapisz</button>'
        f'</form></div>'
    )


@app.route("/")
@farm_required
def dashboard():
    g = gid()
    db = get_db()
    kur = db.execute("SELECT COALESCE(SUM(liczba),0) as s FROM stado WHERE gospodarstwo_id=? AND aktywne=1 AND gatunek='nioski'", (g,)).fetchone()["s"] or 50
    prod = db.execute("SELECT COALESCE(SUM(jaja_zebrane),0) as s, AVG(jaja_zebrane) as a FROM produkcja WHERE gospodarstwo_id=? AND data>=date('now','-7 days')", (g,)).fetchone()
    nies = round((prod["a"] or 0)/kur*100,1) if kur else 0
    mag_prod = db.execute("SELECT COALESCE(SUM(jaja_zebrane),0) as p, COALESCE(SUM(jaja_sprzedane),0) as s FROM produkcja WHERE gospodarstwo_id=?", (g,)).fetchone()
    zarez = db.execute("SELECT COALESCE(SUM(ilosc),0) as s FROM zamowienia WHERE gospodarstwo_id=? AND status IN ('nowe','potwierdzone')", (g,)).fetchone()["s"]
    mag_stan = max(0, mag_prod["p"] - mag_prod["s"])
    zysk = db.execute("SELECT COALESCE(SUM(jaja_sprzedane*cena_sprzedazy),0) as s FROM produkcja WHERE gospodarstwo_id=? AND strftime('%Y-%m',data)=strftime('%Y-%m','now')", (g,)).fetchone()["s"]
    wyd  = db.execute("SELECT COALESCE(SUM(wartosc_total),0) as s FROM wydatki WHERE gospodarstwo_id=? AND strftime('%Y-%m',data)=strftime('%Y-%m','now')", (g,)).fetchone()["s"]
    dzis = db.execute("SELECT * FROM produkcja WHERE gospodarstwo_id=? AND data=date('now')", (g,)).fetchone()
    zam_dzis = db.execute("SELECT COUNT(*) as c FROM zamowienia WHERE gospodarstwo_id=? AND data_dostawy=date('now') AND status NOT IN ('dostarczone','anulowane')", (g,)).fetchone()["c"]
    urzadz = db.execute("SELECT * FROM urzadzenia WHERE gospodarstwo_id=? AND aktywne=1 ORDER BY nazwa", (g,)).fetchall()
    kal = db.execute("SELECT * FROM kalendarz WHERE gospodarstwo_id=? AND aktywne=1 AND nastepne<=date('now','+7 days') ORDER BY nastepne LIMIT 3", (g,)).fetchall()
    db.close()

    pdz = float(gs("pasza_dzienna_kg","6"))
    al_html = ""
    if zam_dzis: al_html += '<div class="al ald">Dziś ' + str(zam_dzis) + ' zamówień do dostarczenia!</div>'
    for k in kal:
        try:
            diff = (date.fromisoformat(str(k["nastepne"])) - date.today()).days
            if diff <= 0:
                al_html += '<div class="al ald">Zaległe: <b>' + k["nazwa"] + '</b></div>'
            elif diff <= 3:
                al_html += '<div class="al alw">Za ' + str(diff) + ' dni: <b>' + k["nazwa"] + '</b></div>'
        except: pass

    # Urządzenia mini-panel
    urz_html = ""
    for u in urzadz:
        db2 = get_db()
        chs = db2.execute("SELECT * FROM urzadzenia_kanaly WHERE urzadzenie_id=? ORDER BY kanal", (u["id"],)).fetchall()
        db2.close()
        for ch in chs:
            on = bool(ch["stan"])
            urz_html += (
                '<div class="relay-card ' + ('relay-on' if on else '') + '" onclick="togDev(' + str(u["id"]) + ',\'' + ch["kanal"] + '\',' + ('false' if on else 'true') + ')">'
                '<div class="tog ' + ('on' if on else '') + '" id="tog-' + str(u["id"]) + '-' + ch["kanal"] + '"></div>'
                '<div style="font-size:11px;margin-top:4px;font-weight:500">' + ch["kanal"] + '</div>'
                '<div style="font-size:10px;color:#888">' + u["nazwa"] + '</div>'
                '</div>'
            )

    html = (
        al_html
        + '<div class="g4" style="margin-bottom:10px">'
        '<div class="card stat"><div class="v" style="color:' + ('#A32D2D' if nies<70 else '#3B6D11') + '">' + str(nies) + '%</div><div class="l">Nieśność 7 dni</div><div class="s">' + str(kur) + ' niosek</div></div>'
        '<div class="card stat"><div class="v">' + str(mag_stan) + '</div><div class="l">Jaj w magazynie</div><div class="s">zarezerwowane: ' + str(zarez) + '</div></div>'
        '<div class="card stat"><div class="v" style="color:#3B6D11">' + str(round(zysk,0)) + ' zł</div><div class="l">Przychód miesiąc</div><div class="s">wydatki: ' + str(round(wyd,0)) + ' zł</div></div>'
        '<div class="card stat"><div class="v">' + str(round(zysk-wyd,0)) + ' zł</div><div class="l">Zysk miesiąc</div></div>'
        '</div>'
        + (('<div class="card"><b>Urządzenia</b><div class="g4" style="margin-top:10px">' + urz_html + '</div></div>') if urz_html else "")
        + _kafelki_czynnosci(g)
        + '<div class="card"><b>Szybki wpis — dziś</b>'
        + ('<span style="font-size:12px;color:#3B6D11;margin-left:8px">wpisano: ' + str(dzis["jaja_zebrane"]) + ' jaj</span>' if dzis else "")
        + '<form method="POST" action="/produkcja/dodaj" style="margin-top:10px">'
        '<input type="hidden" name="data" value="' + date.today().isoformat() + '">'
        '<div class="g3">'
        '<div><label>Zebrane jaja</label><input name="jaja_zebrane" type="number" min="0" value="' + (str(dzis["jaja_zebrane"]) if dzis else "") + '"></div>'
        '<div><label>Sprzedane dziś</label><input name="jaja_sprzedane" type="number" value="' + (str(dzis["jaja_sprzedane"]) if dzis else "0") + '"></div>'
        '<div><label>Pasza wydana (kg)</label><input name="pasza_wydana_kg" type="number" step="0.1" value="' + (str(dzis["pasza_wydana_kg"]) if dzis else str(pdz)) + '"></div>'
        '</div>'
        '<br><button class="btn bg" type="submit">Zapisz dziś</button>'
        '</form></div>'
        '<script>'
        'function togDev(uid,ch,state){'
        'fetch("/urzadzenia/cmd",{method:"POST",'
        'headers:{"Content-Type":"application/json"},'
        'body:JSON.stringify({urzadzenie_id:uid,kanal:ch,stan:state})})'
        '.then(r=>r.json()).then(()=>location.reload());}'
        '</script>'
    )
    return R(html, "dash")

# ─── PRODUKCJA ────────────────────────────────────────────────────────────────
@app.route("/produkcja")
@farm_required
def produkcja():
    g = gid()
    db = get_db()
    rows = db.execute("SELECT * FROM produkcja WHERE gospodarstwo_id=? ORDER BY data DESC LIMIT 60", (g,)).fetchall()
    kur  = db.execute("SELECT COALESCE(SUM(liczba),0) as s FROM stado WHERE gospodarstwo_id=? AND aktywne=1 AND gatunek='nioski'", (g,)).fetchone()["s"] or 50
    db.close()
    w = "".join(
        '<tr><td>' + r["data"] + '</td>'
        '<td style="font-weight:500">' + str(r["jaja_zebrane"]) + '</td>'
        '<td>' + str(round(r["jaja_zebrane"]/kur*100,1) if kur else 0) + '%</td>'
        '<td>' + str(r["jaja_sprzedane"]) + '</td>'
        '<td>' + str(round(r["jaja_sprzedane"]*(r["cena_sprzedazy"] or 0),2)) + ' zł</td>'
        '<td>' + str(r["pasza_wydana_kg"]) + ' kg</td>'
        '<td style="color:#888;font-size:11px">' + (r["uwagi"] or "") + '</td></tr>'
        for r in rows
    )
    html = (
        '<h1>Produkcja</h1>'
        '<a href="/produkcja/dodaj" class="btn bp bsm" style="margin-bottom:12px">+ Dodaj wpis</a>'
        '<div class="card" style="overflow-x:auto"><table>'
        '<thead><tr><th>Data</th><th>Zebrane</th><th>Nieśność</th><th>Sprzedane</th><th>Przychód</th><th>Pasza</th><th>Uwagi</th></tr></thead>'
        '<tbody>' + (w or '<tr><td colspan=7 style="color:#888;text-align:center;padding:20px">Brak wpisów</td></tr>') + '</tbody></table></div>'
    )
    return R(html, "prod")

@app.route("/produkcja/dodaj", methods=["GET","POST"])
@farm_required
def produkcja_dodaj():
    g = gid()
    if request.method == "POST":
        db = get_db()
        d = request.form.get("data", date.today().isoformat())
        v = (g, request.form.get("jaja_zebrane",0), request.form.get("jaja_sprzedane",0),
             request.form.get("cena_sprzedazy",0), request.form.get("pasza_wydana_kg",0),
             request.form.get("uwagi",""))
        if db.execute("SELECT id FROM produkcja WHERE gospodarstwo_id=? AND data=?", (g,d)).fetchone():
            db.execute("UPDATE produkcja SET jaja_zebrane=?,jaja_sprzedane=?,cena_sprzedazy=?,pasza_wydana_kg=?,uwagi=? WHERE gospodarstwo_id=? AND data=?",
                       (request.form.get("jaja_zebrane",0), request.form.get("jaja_sprzedane",0),
                        request.form.get("cena_sprzedazy",0), request.form.get("pasza_wydana_kg",0),
                        request.form.get("uwagi",""), g, d))
        else:
            db.execute("INSERT INTO produkcja(gospodarstwo_id,data,jaja_zebrane,jaja_sprzedane,cena_sprzedazy,pasza_wydana_kg,uwagi) VALUES(?,?,?,?,?,?,?)",
                       (g, d, request.form.get("jaja_zebrane",0), request.form.get("jaja_sprzedane",0),
                        request.form.get("cena_sprzedazy",0), request.form.get("pasza_wydana_kg",0),
                        request.form.get("uwagi","")))
        db.commit(); db.close()
        flash("Wpis zapisany.")
        return redirect("/")
    pdz = gs("pasza_dzienna_kg","6")
    html = (
        '<h1>Dodaj wpis produkcji</h1><div class="card"><form method="POST">'
        '<label>Data</label><input name="data" type="date" value="' + date.today().isoformat() + '">'
        '<div class="g3">'
        '<div><label>Zebrane jaja</label><input name="jaja_zebrane" type="number" min="0"></div>'
        '<div><label>Sprzedane</label><input name="jaja_sprzedane" type="number" value="0"></div>'
        '<div><label>Cena/szt (zł)</label><input name="cena_sprzedazy" type="number" step="0.01"></div>'
        '</div>'
        '<div class="g2">'
        '<div><label>Pasza wydana (kg)</label><input name="pasza_wydana_kg" type="number" step="0.1" value="' + str(pdz) + '"></div>'
        '<div><label>Uwagi</label><input name="uwagi"></div>'
        '</div>'
        '<br><button class="btn bp">Zapisz</button>'
        '<a href="/" class="btn bo" style="margin-left:8px">Anuluj</a>'
        '</form></div>'
    )
    return R(html, "prod")

# ─── STADO ────────────────────────────────────────────────────────────────────
@app.route("/stado")
@farm_required
def stado():
    g = gid()
    db = get_db()
    rows = db.execute("SELECT * FROM stado WHERE gospodarstwo_id=? ORDER BY aktywne DESC, data_dodania DESC", (g,)).fetchall()
    db.close()
    total = sum(r["liczba"] for r in rows if r["aktywne"])
    w = "".join(
        '<tr>'
        '<td style="font-weight:500">' + r["nazwa"] + '</td>'
        '<td><span class="badge b-blue">' + r["gatunek"] + '</span></td>'
        '<td style="font-weight:500">' + str(r["liczba"]) + '</td>'
        '<td>' + (r["rasa"] or "—") + '</td>'
        '<td>' + (r["data_dodania"] or "—") + '</td>'
        '<td><span class="badge ' + ('b-green' if r["aktywne"] else 'b-gray') + '">' + ('aktywne' if r["aktywne"] else 'nieaktywne') + '</span></td>'
        '<td class="nowrap">'
        '<a href="/stado/' + str(r["id"]) + '/ubytki" class="btn br bsm">- Ubytki</a> '
        '<a href="/stado/' + str(r["id"]) + '/toggle" class="btn bo bsm">Toggle</a>'
        '</td></tr>'
        for r in rows
    )
    html = (
        '<h1>Stado</h1>'
        '<div class="g3" style="margin-bottom:12px">'
        '<div class="card stat"><div class="v">' + str(total) + '</div><div class="l">Łącznie aktywnych</div></div>'
        '<div class="card stat"><div class="v">' + str(sum(r["liczba"] for r in rows if r["aktywne"] and r["gatunek"]=="nioski")) + '</div><div class="l">Nioski</div></div>'
        '<div class="card stat"><div class="v">' + str(sum(r["liczba"] for r in rows if r["aktywne"] and r["gatunek"]=="kogut")) + '</div><div class="l">Koguty</div></div>'
        '</div>'
        '<a href="/stado/dodaj" class="btn bp bsm" style="margin-bottom:12px">+ Dodaj grupę</a>'
        '<div class="card" style="overflow-x:auto"><table>'
        '<thead><tr><th>Nazwa</th><th>Gatunek</th><th>Liczba</th><th>Rasa</th><th>Dodano</th><th>Status</th><th></th></tr></thead>'
        '<tbody>' + (w or '<tr><td colspan=7 style="color:#888;text-align:center;padding:20px">Brak wpisów stada</td></tr>') + '</tbody></table></div>'
    )
    return R(html, "stado")

@app.route("/stado/dodaj", methods=["GET","POST"])
@farm_required
def stado_dodaj():
    g = gid()
    if request.method == "POST":
        db = get_db()
        db.execute("INSERT INTO stado(gospodarstwo_id,nazwa,gatunek,liczba,data_dodania,data_urodzenia,rasa,uwagi) VALUES(?,?,?,?,?,?,?,?)",
            (g, request.form["nazwa"], request.form.get("gatunek","nioski"),
             request.form.get("liczba",0), request.form.get("data_dodania","") or None,
             request.form.get("data_urodzenia","") or None,
             request.form.get("rasa",""), request.form.get("uwagi","")))
        db.commit(); db.close()
        flash("Grupa dodana do stada.")
        return redirect("/stado")
    html = (
        '<h1>Dodaj grupę do stada</h1><div class="card"><form method="POST">'
        '<label>Nazwa grupy</label><input name="nazwa" required placeholder="np. Nioski wiosna 2024">'
        '<div class="g2">'
        '<div><label>Gatunek</label><select name="gatunek">'
        '<option value="nioski">Nioski</option><option value="kogut">Kogut(y)</option><option value="mixed">Mieszane</option>'
        '</select></div>'
        '<div><label>Liczba sztuk</label><input name="liczba" type="number" min="1" required></div>'
        '</div>'
        '<div class="g2">'
        '<div><label>Rasa</label><input name="rasa" placeholder="np. Sussex"></div>'
        '<div><label>Data dodania</label><input name="data_dodania" type="date" value="' + date.today().isoformat() + '"></div>'
        '</div>'
        '<label>Data urodzenia</label><input name="data_urodzenia" type="date">'
        '<label>Uwagi</label><textarea name="uwagi" rows="2"></textarea>'
        '<br><button class="btn bp">Dodaj</button>'
        '<a href="/stado" class="btn bo" style="margin-left:8px">Anuluj</a>'
        '</form></div>'
    )
    return R(html, "stado")

@app.route("/stado/<int:sid>/ubytki", methods=["GET","POST"])
@farm_required
def stado_ubytki(sid):
    g = gid()
    db = get_db()
    if request.method == "POST":
        ile   = int(request.form.get("ile",0))
        powod = request.form.get("powod","inne")
        r = db.execute("SELECT liczba FROM stado WHERE id=? AND gospodarstwo_id=?", (sid,g)).fetchone()
        if r and ile > 0:
            nowa = max(0, r["liczba"] - ile)
            db.execute("UPDATE stado SET liczba=? WHERE id=?", (nowa, sid))
            db.execute("INSERT INTO stado_ubytki(stado_id,gospodarstwo_id,data,ilosc,powod,uwagi) VALUES(?,?,?,?,?,?)",
                       (sid, g, date.today().isoformat(), ile, powod, request.form.get("uwagi","")))
            db.commit()
            flash(f"Ubytek {ile} szt. ({powod}). Nowy stan: {nowa}")
        db.close()
        return redirect("/stado")
    r = db.execute("SELECT * FROM stado WHERE id=? AND gospodarstwo_id=?", (sid,g)).fetchone()
    db.close()
    if not r: return redirect("/stado")
    html = (
        '<h1>Ubytki — ' + r["nazwa"] + '</h1>'
        '<p style="color:#888;font-size:13px;margin-bottom:12px">Aktualny stan: <b>' + str(r["liczba"]) + '</b> szt.</p>'
        '<div class="card"><form method="POST">'
        '<label>Liczba usuniętych sztuk</label><input name="ile" type="number" min="1" max="' + str(r["liczba"]) + '" required>'
        '<label>Powód</label><select name="powod">'
        '<option value="padniecie">Padnięcie (naturalne)</option>'
        '<option value="choroba">Padnięcie (choroba)</option>'
        '<option value="drapieznik">Atak drapieżnika</option>'
        '<option value="sprzedaz">Sprzedaż żywca</option>'
        '<option value="uboj">Ubój własny</option>'
        '<option value="inne">Inne</option>'
        '</select>'
        '<label>Uwagi</label><textarea name="uwagi" rows="2"></textarea>'
        '<br><button class="btn br">Zapisz ubytek</button>'
        '<a href="/stado" class="btn bo" style="margin-left:8px">Anuluj</a>'
        '</form></div>'
    )
    return R(html, "stado")

@app.route("/stado/<int:sid>/toggle")
@farm_required
def stado_toggle(sid):
    g = gid()
    db = get_db()
    db.execute("UPDATE stado SET aktywne=1-aktywne WHERE id=? AND gospodarstwo_id=?", (sid,g))
    db.commit(); db.close()
    flash("Status stada zmieniony.")
    return redirect("/stado")

# ─── ZAMÓWIENIA ───────────────────────────────────────────────────────────────
@app.route("/zamowienia")
@farm_required
def zamowienia():
    g = gid()
    db = get_db()
    rows = db.execute("""SELECT z.*,k.nazwa as kn,k.telefon as kt FROM zamowienia z
        LEFT JOIN klienci k ON z.klient_id=k.id
        WHERE z.gospodarstwo_id=?
        ORDER BY CASE z.status WHEN 'nowe' THEN 0 WHEN 'potwierdzone' THEN 1 ELSE 2 END, z.data_dostawy""", (g,)).fetchall()
    db.close()
    dzis = date.today().isoformat()
    sbdg = {"nowe":"b-blue","potwierdzone":"b-green","dostarczone":"b-gray","anulowane":"b-red"}
    w = "".join(
        '<tr>'
        '<td>' + r["data_dostawy"] + (' ⚠' if r["data_dostawy"]==dzis and r["status"] not in ("dostarczone","anulowane") else "") + '</td>'
        '<td>' + (r["kn"] or "—") + '</td>'
        '<td style="font-weight:500">' + str(r["ilosc"]) + ' szt.</td>'
        '<td>' + str(round(r["ilosc"]*(r["cena_za_szt"] or 0),2)) + ' zł</td>'
        '<td><span class="badge ' + sbdg.get(r["status"],"b-gray") + '">' + r["status"] + '</span></td>'
        '<td class="nowrap">'
        '<a href="/zamowienia/' + str(r["id"]) + '/status/dostarczone" class="btn bg bsm">Dostarczone</a> '
        '<a href="/zamowienia/' + str(r["id"]) + '/status/anulowane" class="btn br bsm">✕</a>'
        '</td></tr>'
        for r in rows
    )
    html = (
        '<h1>Zamówienia</h1>'
        '<div style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap">'
        '<a href="/zamowienia/dodaj" class="btn bp bsm">+ Nowe zamówienie</a>'
        '<a href="/klienci" class="btn bo bsm">Klienci</a>'
        '</div>'
        '<div class="card" style="overflow-x:auto"><table>'
        '<thead><tr><th>Dostawa</th><th>Klient</th><th>Ilość</th><th>Wartość</th><th>Status</th><th>Akcja</th></tr></thead>'
        '<tbody>' + (w or '<tr><td colspan=6 style="color:#888;text-align:center;padding:20px">Brak zamówień</td></tr>') + '</tbody></table></div>'
    )
    return R(html, "zam")

@app.route("/zamowienia/dodaj", methods=["GET","POST"])
@farm_required
def zamowienia_dodaj():
    g = gid()
    if request.method == "POST":
        db = get_db()
        db.execute("INSERT INTO zamowienia(gospodarstwo_id,klient_id,data_zlozenia,data_dostawy,ilosc,cena_za_szt,uwagi) VALUES(?,?,?,?,?,?,?)",
            (g, request.form.get("klient_id") or None, date.today().isoformat(),
             request.form.get("data_dostawy"), request.form.get("ilosc",0),
             request.form.get("cena_za_szt",0), request.form.get("uwagi","")))
        db.commit(); db.close()
        flash("Zamówienie dodane.")
        return redirect("/zamowienia")
    db = get_db()
    klienci = db.execute("SELECT id,nazwa FROM klienci WHERE gospodarstwo_id=? ORDER BY nazwa", (g,)).fetchall()
    db.close()
    opt = "".join('<option value="' + str(k["id"]) + '">' + k["nazwa"] + '</option>' for k in klienci)
    html = (
        '<h1>Nowe zamówienie</h1><div class="card"><form method="POST">'
        '<label>Klient</label><select name="klient_id"><option value="">— wybierz —</option>' + opt + '</select>'
        '<a href="/klienci/dodaj" style="font-size:12px;color:#534AB7;display:block;margin-top:4px">+ nowy klient</a>'
        '<div class="g2">'
        '<div><label>Data dostawy</label><input name="data_dostawy" type="date" value="' + (date.today()+timedelta(days=1)).isoformat() + '"></div>'
        '<div><label>Ilość jaj</label><input name="ilosc" type="number" min="1"></div>'
        '</div>'
        '<div class="g2">'
        '<div><label>Cena/szt (zł)</label><input name="cena_za_szt" type="number" step="0.01"></div>'
        '<div><label>Uwagi</label><input name="uwagi"></div>'
        '</div>'
        '<br><button class="btn bp">Zapisz</button>'
        '<a href="/zamowienia" class="btn bo" style="margin-left:8px">Anuluj</a>'
        '</form></div>'
    )
    return R(html, "zam")

@app.route("/zamowienia/<int:zid>/status/<status>")
@farm_required
def zamowienie_status(zid, status):
    g = gid()
    db = get_db()
    row = db.execute("SELECT * FROM zamowienia WHERE id=? AND gospodarstwo_id=?", (zid,g)).fetchone()
    if row:
        db.execute("UPDATE zamowienia SET status=? WHERE id=?", (status, zid))
        if status == "dostarczone":
            td = date.today().isoformat()
            if db.execute("SELECT id FROM produkcja WHERE gospodarstwo_id=? AND data=?", (g,td)).fetchone():
                db.execute("UPDATE produkcja SET jaja_sprzedane=jaja_sprzedane+?,cena_sprzedazy=? WHERE gospodarstwo_id=? AND data=?",
                           (row["ilosc"], row["cena_za_szt"], g, td))
            else:
                db.execute("INSERT INTO produkcja(gospodarstwo_id,data,jaja_zebrane,jaja_sprzedane,cena_sprzedazy,pasza_wydana_kg) VALUES(?,?,0,?,?,0)",
                           (g, td, row["ilosc"], row["cena_za_szt"]))
        db.commit()
    db.close()
    flash("Status: " + status)
    return redirect("/zamowienia")

@app.route("/klienci")
@farm_required
def klienci():
    g = gid()
    db = get_db()
    rows = db.execute("SELECT * FROM klienci WHERE gospodarstwo_id=? ORDER BY nazwa", (g,)).fetchall()
    db.close()
    w = "".join(
        '<tr><td>' + r["nazwa"] + '</td><td>' + (r["telefon"] or "") + '</td><td>' + (r["adres"] or "") + '</td>'
        '<td><a href="/klienci/' + str(r["id"]) + '/edytuj" class="btn bo bsm">Edytuj</a></td></tr>'
        for r in rows
    )
    html = (
        '<h1>Klienci</h1><a href="/klienci/dodaj" class="btn bp bsm" style="margin-bottom:12px">+ Dodaj</a>'
        '<div class="card" style="overflow-x:auto"><table>'
        '<thead><tr><th>Nazwa</th><th>Telefon</th><th>Adres</th><th></th></tr></thead>'
        '<tbody>' + (w or '<tr><td colspan=4 style="color:#888;text-align:center;padding:16px">Brak klientów</td></tr>') + '</tbody></table></div>'
    )
    return R(html, "zam")

@app.route("/klienci/dodaj", methods=["GET","POST"])
@farm_required
def klienci_dodaj():
    g = gid()
    if request.method == "POST":
        db = get_db()
        db.execute("INSERT INTO klienci(gospodarstwo_id,nazwa,telefon,email,adres,uwagi) VALUES(?,?,?,?,?,?)",
            (g, request.form["nazwa"], request.form.get("telefon",""),
             request.form.get("email",""), request.form.get("adres",""), request.form.get("uwagi","")))
        db.commit(); db.close()
        flash("Klient dodany.")
        return redirect("/klienci")
    html = (
        '<h1>Nowy klient</h1><div class="card"><form method="POST">'
        '<label>Nazwa</label><input name="nazwa" required>'
        '<div class="g2">'
        '<div><label>Telefon</label><input name="telefon" type="tel"></div>'
        '<div><label>Email</label><input name="email" type="email"></div>'
        '</div>'
        '<label>Adres</label><textarea name="adres" rows="2"></textarea>'
        '<br><button class="btn bp">Zapisz</button>'
        '<a href="/klienci" class="btn bo" style="margin-left:8px">Anuluj</a>'
        '</form></div>'
    )
    return R(html, "zam")

@app.route("/klienci/<int:kid>/edytuj", methods=["GET","POST"])
@farm_required
def klienci_edytuj(kid):
    g = gid()
    db = get_db()
    if request.method == "POST":
        db.execute("UPDATE klienci SET nazwa=?,telefon=?,email=?,adres=?,uwagi=? WHERE id=? AND gospodarstwo_id=?",
            (request.form["nazwa"], request.form.get("telefon",""), request.form.get("email",""),
             request.form.get("adres",""), request.form.get("uwagi",""), kid, g))
        db.commit(); db.close()
        flash("Klient zaktualizowany.")
        return redirect("/klienci")
    r = db.execute("SELECT * FROM klienci WHERE id=? AND gospodarstwo_id=?", (kid,g)).fetchone()
    db.close()
    if not r: return redirect("/klienci")
    html = (
        '<h1>Edytuj klienta</h1><div class="card"><form method="POST">'
        '<label>Nazwa</label><input name="nazwa" required value="' + r["nazwa"] + '">'
        '<div class="g2">'
        '<div><label>Telefon</label><input name="telefon" value="' + (r["telefon"] or "") + '"></div>'
        '<div><label>Email</label><input name="email" value="' + (r["email"] or "") + '"></div>'
        '</div>'
        '<label>Adres</label><textarea name="adres" rows="2">' + (r["adres"] or "") + '</textarea>'
        '<label>Uwagi</label><input name="uwagi" value="' + (r["uwagi"] or "") + '">'
        '<br><button class="btn bp">Zapisz</button>'
        '<a href="/klienci" class="btn bo" style="margin-left:8px">Anuluj</a>'
        '</form></div>'
    )
    return R(html, "zam")

# ─── WYDATKI ──────────────────────────────────────────────────────────────────
KATEGORIE = ["Zboże/pasza","Witaminy/suplementy","Wyposażenie","Weterynarz","Ściółka","Prąd/gaz","Inne"]

@app.route("/wydatki")
@farm_required
def wydatki():
    g = gid()
    db = get_db()
    rows = db.execute("SELECT * FROM wydatki WHERE gospodarstwo_id=? ORDER BY data DESC LIMIT 100", (g,)).fetchall()
    sumy = db.execute("SELECT kategoria,SUM(wartosc_total) as s FROM wydatki WHERE gospodarstwo_id=? AND strftime('%Y-%m',data)=strftime('%Y-%m','now') GROUP BY kategoria", (g,)).fetchall()
    db.close()
    w = "".join(
        '<tr><td>' + r["data"] + '</td>'
        '<td><span class="badge b-blue">' + r["kategoria"] + '</span></td>'
        '<td>' + r["nazwa"] + '</td>'
        '<td>' + str(round(r["ilosc"],2)) + ' ' + r["jednostka"] + '</td>'
        '<td style="font-weight:500">' + str(round(r["wartosc_total"],2)) + ' zł</td>'
        '<td><a href="/wydatki/' + str(r["id"]) + '/usun" class="btn br bsm" onclick="return confirm(\'Usunąć?\')">✕</a></td></tr>'
        for r in rows
    )
    sumy_html = "".join(
        '<div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid #f0ede4;font-size:13px">'
        '<span>' + s["kategoria"] + '</span><span style="font-weight:500">' + str(round(s["s"],2)) + ' zł</span></div>'
        for s in sumy
    )
    html = (
        '<h1>Wydatki</h1>'
        '<a href="/wydatki/dodaj" class="btn bp bsm" style="margin-bottom:12px">+ Dodaj wydatek</a>'
        '<div class="g2" style="margin-bottom:12px">'
        '<div class="card"><b>Ten miesiąc</b><div style="margin-top:8px">' + (sumy_html or '<p style="color:#888;font-size:13px">Brak</p>') + '</div></div>'
        '<div class="card stat"><div class="v" style="color:#A32D2D">' + str(round(sum(s["s"] for s in sumy),2)) + ' zł</div><div class="l">Łącznie miesiąc</div></div>'
        '</div>'
        '<div class="card" style="overflow-x:auto"><table>'
        '<thead><tr><th>Data</th><th>Kategoria</th><th>Nazwa</th><th>Ilość</th><th>Wartość</th><th></th></tr></thead>'
        '<tbody>' + (w or '<tr><td colspan=6 style="color:#888;text-align:center;padding:16px">Brak wydatków</td></tr>') + '</tbody></table></div>'
    )
    return R(html, "wyd")

@app.route("/wydatki/dodaj", methods=["GET","POST"])
@farm_required
def wydatki_dodaj():
    g = gid()
    if request.method == "POST":
        kat  = request.form.get("kategoria","Inne")
        naz  = request.form.get("nazwa","")
        il   = float(request.form.get("ilosc",0) or 0)
        jedn = request.form.get("jednostka","szt")
        cj   = float(request.form.get("cena_jednostkowa",0) or 0)
        tot  = round(il*cj,4)
        db = get_db()
        db.execute("INSERT INTO wydatki(gospodarstwo_id,data,kategoria,nazwa,ilosc,jednostka,cena_jednostkowa,wartosc_total,dostawca,uwagi) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (g, request.form.get("data",date.today().isoformat()), kat, naz, il, jedn, cj, tot,
             request.form.get("dostawca",""), request.form.get("uwagi","")))
        if kat in ("Zboże/pasza","Witaminy/suplementy") and naz and il > 0:
            ex = db.execute("SELECT id FROM stan_magazynu WHERE gospodarstwo_id=? AND nazwa=? AND kategoria=?", (g,naz,kat)).fetchone()
            if ex:
                db.execute("UPDATE stan_magazynu SET stan=stan+?,cena_aktualna=? WHERE id=?", (il,cj,ex["id"]))
            else:
                db.execute("INSERT INTO stan_magazynu(gospodarstwo_id,kategoria,nazwa,jednostka,stan,cena_aktualna) VALUES(?,?,?,?,?,?)",
                           (g,kat,naz,jedn,il,cj))
        db.commit(); db.close()
        flash("Wydatek zapisany.")
        return redirect("/wydatki")
    kat_opt = "".join('<option value="' + k + '">' + k + '</option>' for k in KATEGORIE)
    html = (
        '<h1>Dodaj wydatek</h1><div class="card"><form method="POST">'
        '<div class="g2">'
        '<div><label>Data</label><input name="data" type="date" value="' + date.today().isoformat() + '"></div>'
        '<div><label>Kategoria</label><select name="kategoria">' + kat_opt + '</select></div>'
        '</div>'
        '<label>Nazwa</label>''<div style="position:relative">''<input name="nazwa" id="wyd-n" required placeholder="np. Pszenica, Vitamix" autocomplete="off" oninput="szukajN(this.value)">''<div id="wyd-sug" style="display:none;position:absolute;top:100%;left:0;right:0;background:#fff;border:1px solid #d3d1c7;border-radius:8px;z-index:50;max-height:200px;overflow-y:auto"></div>''</div>''<script>''function szukajN(q){if(q.length<2){document.getElementById("wyd-sug").style.display="none";return;}''fetch("/api/zboze-lista").then(r=>r.json()).then(data=>{''var f=data.filter(d=>d.nazwa.toLowerCase().includes(q.toLowerCase()));''var el=document.getElementById("wyd-sug");''if(!f.length){el.style.display="none";return;}''el.innerHTML=f.slice(0,8).map(d=>"<div style=\"padding:8px 12px;cursor:pointer;border-bottom:1px solid #f0ede4\" onclick=\"wybN(\\\"" +d.nazwa+ "\\\",\\\"" +d.kategoria+ "\\\"," +d.cena+ ")\"><b>"+d.nazwa+"</b> <span style=\"color:#888;font-size:12px\">("+d.kategoria+")</span>"+(d.cena>0?" <span style=\"float:right;color:#534AB7\">" +d.cena+ " zł/kg</span>":"")+"</div>").join("");''el.style.display="block";});} ''function wybN(n,k,c){document.getElementById("wyd-n").value=n;''var sel=document.querySelector("[name=kategoria]");''if(k==="zboze"||k==="bialkowe")sel.value="Zboże/pasza";''else if(k==="premiks"||k==="mineralne"||k==="naturalny_dodatek")sel.value="Witaminy/suplementy";''if(c>0){var ci=document.querySelector("[name=cena_jednostkowa]");if(ci)ci.value=c;}''document.getElementById("wyd-sug").style.display="none";}''document.addEventListener("click",function(e){if(!e.target.closest("#wyd-sug")&&!e.target.closest("#wyd-n"))document.getElementById("wyd-sug").style.display="none";});''</script>'
        '<div class="g3">'
        '<div><label>Ilość</label><input name="ilosc" type="number" step="0.01" id="il" oninput="calc()"></div>'
        '<div><label>Jednostka</label><select name="jednostka">'
        '<option value="kg">kg</option><option value="szt">szt</option><option value="l">l</option><option value="op">opak.</option>'
        '</select></div>'
        '<div><label>Cena/jedn. (zł)</label><input name="cena_jednostkowa" type="number" step="0.01" id="cj" oninput="calc()"></div>'
        '</div>'
        '<div style="background:#f5f5f0;border-radius:8px;padding:10px;margin-top:8px;font-size:14px">Łącznie: <b id="tot">0.00 zł</b></div>'
        '<div class="g2">'
        '<div><label>Dostawca</label><input name="dostawca"></div>'
        '<div><label>Uwagi</label><input name="uwagi"></div>'
        '</div>'
        '<br><button class="btn bp">Zapisz</button>'
        '<a href="/wydatki" class="btn bo" style="margin-left:8px">Anuluj</a>'
        '</form></div>'
        '<script>function calc(){var il=parseFloat(document.getElementById("il").value)||0;var cj=parseFloat(document.getElementById("cj").value)||0;document.getElementById("tot").textContent=(il*cj).toFixed(2)+" zł";}</script>'
    )
    return R(html, "wyd")

@app.route("/wydatki/<int:wid>/usun")
@farm_required
def wydatki_usun(wid):
    g = gid()
    db = get_db()
    db.execute("DELETE FROM wydatki WHERE id=? AND gospodarstwo_id=?", (wid,g))
    db.commit(); db.close()
    flash("Wydatek usunięty.")
    return redirect("/wydatki")

# ─── PASZA ────────────────────────────────────────────────────────────────────
@app.route("/pasza")
@farm_required
def pasza():
    g = gid()
    db = get_db()
    skladniki = db.execute("SELECT * FROM stan_magazynu WHERE gospodarstwo_id=? AND kategoria IN ('Zboże/pasza','Witaminy/suplementy') ORDER BY nazwa", (g,)).fetchall()
    mieszania = db.execute("SELECT m.*,r.nazwa as rn FROM mieszania m LEFT JOIN receptura r ON m.receptura_id=r.id WHERE m.gospodarstwo_id=? ORDER BY m.data DESC LIMIT 15", (g,)).fetchall()
    receptury = db.execute("SELECT * FROM receptura WHERE gospodarstwo_id=? ORDER BY aktywna DESC, nazwa", (g,)).fetchall()
    db.close()
    pdz = float(gs("pasza_dzienna_kg","6"))
    w_skl = "".join(
        '<tr><td>' + s["nazwa"] + '</td>'
        '<td style="font-weight:500;color:' + ('#A32D2D' if s["stan"]<s["min_zapas"] and s["min_zapas"]>0 else '#2c2c2a') + '">' + str(round(s["stan"],1)) + ' ' + s["jednostka"] + '</td>'
        '<td>' + str(round(s["cena_aktualna"],2)) + ' zł</td>'
        '<td><a href="/wydatki/dodaj" class="btn bo bsm">+ Zakup</a></td></tr>'
        for s in skladniki
    )
    w_mies = "".join(
        '<tr><td>' + m["data"][:10] + '</td><td>' + (m["rn"] or "—") + '</td>'
        '<td style="font-weight:500">' + str(round(m["ilosc_kg"],1)) + ' kg</td>'
        '<td style="color:#888;font-size:11px">' + (m["uwagi"] or "") + '</td></tr>'
        for m in mieszania
    )
    html = (
        '<h1>Pasza</h1>'
        '<div style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap">'
        '<a href="/pasza/mieszaj" class="btn bp bsm">+ Zarejestruj mieszanie</a>'
        '<a href="/pasza/receptury" class="btn bo bsm">Receptury</a>'
        '</div>'
        '<div class="g2">'
        '<div class="card"><b>Składniki w magazynie</b>'
        '<p style="font-size:12px;color:#888;margin:4px 0 8px">Zakup przez <a href="/wydatki/dodaj" style="color:#534AB7">Wydatki</a></p>'
        '<div style="overflow-x:auto"><table><thead><tr><th>Składnik</th><th>Stan</th><th>Cena</th><th></th></tr></thead>'
        '<tbody>' + (w_skl or '<tr><td colspan=4 style="color:#888;padding:12px">Brak — dodaj przez Wydatki (Zboże/pasza)</td></tr>') + '</tbody></table></div></div>'
        '<div class="card"><b>Historia mieszań</b>'
        '<div style="overflow-x:auto"><table style="margin-top:8px"><thead><tr><th>Data</th><th>Receptura</th><th>Partia</th><th>Uwagi</th></tr></thead>'
        '<tbody>' + (w_mies or '<tr><td colspan=4 style="color:#888;padding:12px">Brak historii</td></tr>') + '</tbody></table></div></div>'
        '</div>'
    )
    return R(html, "pasza")

@app.route("/pasza/mieszaj", methods=["GET","POST"])
@farm_required
def pasza_mieszaj():
    g = gid()
    if request.method == "POST":
        db = get_db()
        rid   = request.form.get("receptura_id")
        ilosc = float(request.form.get("ilosc_kg",0) or 0)
        mid   = db.execute("INSERT INTO mieszania(gospodarstwo_id,data,receptura_id,ilosc_kg,uwagi) VALUES(?,?,?,?,?)",
            (g, datetime.now().isoformat(), rid or None, ilosc, request.form.get("uwagi",""))).lastrowid
        if rid and ilosc > 0:
            for s in db.execute("SELECT * FROM receptura_skladnik WHERE receptura_id=?", (rid,)).fetchall():
                wsypane = ilosc * s["procent"] / 100
                db.execute("UPDATE stan_magazynu SET stan=MAX(0,stan-?) WHERE id=? AND gospodarstwo_id=?",
                           (wsypane, s["magazyn_id"], g))
        db.commit(); db.close()
        flash("Mieszanie zarejestrowane.")
        return redirect("/pasza")
    db = get_db()
    recs = db.execute("SELECT * FROM receptura WHERE gospodarstwo_id=? ORDER BY aktywna DESC", (g,)).fetchall()
    db.close()
    opt = "".join('<option value="' + str(r["id"]) + '" ' + ('selected' if r["aktywna"] else '') + '>' + r["nazwa"] + '</option>' for r in recs)
    html = (
        '<h1>Zarejestruj mieszanie</h1><div class="card"><form method="POST">'
        '<label>Receptura</label><select name="receptura_id">' + opt + '</select>'
        '<label>Ilość (kg)</label><input name="ilosc_kg" type="number" step="0.5" min="10" max="200" value="50">'
        '<label>Uwagi</label><input name="uwagi">'
        '<br><br><button class="btn bg">Zapisz</button>'
        '<a href="/pasza" class="btn bo" style="margin-left:8px">Anuluj</a>'
        '</form></div>'
    )
    return R(html, "pasza")

@app.route("/pasza/receptury")
@farm_required
def pasza_receptury():
    g = gid()
    db = get_db()
    recs = db.execute("SELECT * FROM receptura WHERE gospodarstwo_id=? ORDER BY aktywna DESC, nazwa", (g,)).fetchall()
    db.close()
    w = "".join(
        '<tr><td>' + r["nazwa"] + '</td><td>' + r["sezon"] + '</td>'
        '<td>' + ('<span class="badge b-green">aktywna</span>' if r["aktywna"] else "") + '</td>'
        '<td>'
        '<a href="/pasza/receptura/' + str(r["id"]) + '/aktywuj" class="btn bg bsm">Aktywuj</a>'
        '</td></tr>'
        for r in recs
    )
    html = (
        '<h1>Receptury paszy</h1>'
        '<a href="/pasza/receptura/dodaj" class="btn bp bsm" style="margin-bottom:12px">+ Nowa receptura</a>'
        '<div class="card"><table><thead><tr><th>Nazwa</th><th>Sezon</th><th>Status</th><th></th></tr></thead>'
        '<tbody>' + (w or '<tr><td colspan=4 style="color:#888;text-align:center;padding:16px">Brak receptur</td></tr>') + '</tbody></table></div>'
    )
    return R(html, "pasza")

@app.route("/pasza/receptura/dodaj", methods=["GET","POST"])
@farm_required
def pasza_receptura_dodaj():
    g = gid()
    if request.method == "POST":
        db = get_db()
        rid = db.execute("INSERT INTO receptura(gospodarstwo_id,nazwa,sezon,aktywna) VALUES(?,?,?,0)",
            (g, request.form["nazwa"], request.form.get("sezon","caly_rok"))).lastrowid
        for mid_v, proc_v in zip(request.form.getlist("mag_id"), request.form.getlist("procent")):
            if mid_v and proc_v:
                db.execute("INSERT INTO receptura_skladnik(receptura_id,magazyn_id,procent) VALUES(?,?,?)",
                    (rid, int(mid_v), float(proc_v)))
        db.commit(); db.close()
        flash("Receptura dodana.")
        return redirect("/pasza/receptury")
    db = get_db()
    skladniki = db.execute("SELECT id,nazwa,jednostka FROM stan_magazynu WHERE gospodarstwo_id=? AND kategoria IN ('Zboże/pasza','Witaminy/suplementy') ORDER BY nazwa", (g,)).fetchall()
    db.close()
    opt = "".join('<option value="' + str(s["id"]) + '">' + s["nazwa"] + '</option>' for s in skladniki)
    wiersze = "".join(
        '<tr><td><select name="mag_id" style="width:100%"><option value="">— wybierz —</option>' + opt + '</select></td>'
        '<td><input name="procent" type="number" step="0.5" min="0" max="100" placeholder="%" style="width:80px"></td></tr>'
        for _ in range(8)
    )
    html = (
        '<h1>Nowa receptura</h1><div class="card"><form method="POST">'
        '<div class="g2">'
        '<div><label>Nazwa</label><input name="nazwa" required></div>'
        '<div><label>Sezon</label><select name="sezon">'
        '<option value="caly_rok">Cały rok</option><option value="lato">Lato</option>'
        '<option value="zima">Zima</option>'
        '</select></div>'
        '</div>'
        '<h2>Składniki (suma = 100%)</h2>'
        '<table><thead><tr><th>Składnik</th><th>%</th></tr></thead><tbody>' + wiersze + '</tbody></table>'
        '<br><button class="btn bp">Zapisz</button>'
        '<a href="/pasza/receptury" class="btn bo" style="margin-left:8px">Anuluj</a>'
        '</form></div>'
    )
    return R(html, "pasza")

@app.route("/pasza/receptura/<int:rid>/aktywuj")
@farm_required
def pasza_receptura_aktywuj(rid):
    g = gid()
    db = get_db()
    db.execute("UPDATE receptura SET aktywna=0 WHERE gospodarstwo_id=?", (g,))
    db.execute("UPDATE receptura SET aktywna=1 WHERE id=? AND gospodarstwo_id=?", (rid,g))
    db.commit(); db.close()
    flash("Receptura aktywowana.")
    return redirect("/pasza/receptury")

# ─── URZĄDZENIA ───────────────────────────────────────────────────────────────
@app.route("/urzadzenia")
@farm_required
def urzadzenia():
    g = gid()
    db = get_db()
    devs = db.execute("SELECT * FROM urzadzenia WHERE gospodarstwo_id=? ORDER BY nazwa", (g,)).fetchall()
    db.close()
    w = "".join(
        '<tr>'
        '<td style="font-weight:500">' + d["nazwa"] + '</td>'
        '<td><span class="badge b-blue">' + d["typ"].upper() + '</span></td>'
        '<td><code>' + d["ip"] + ':' + str(d["port"]) + '</code></td>'
        '<td><span class="badge ' + ('b-green' if d["status"]=="online" else 'b-red') + '">' + d["status"] + '</span></td>'
        '<td class="nowrap">'
        '<a href="/urzadzenia/' + str(d["id"]) + '" class="btn bo bsm">Panel</a> '
        '<a href="/urzadzenia/' + str(d["id"]) + '/ping" class="btn bo bsm">Ping</a>'
        '</td></tr>'
        for d in devs
    )
    html = (
        '<h1>Urządzenia wykonawcze</h1>'
        '<div style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap">'
        '<a href="/urzadzenia/dodaj" class="btn bp bsm">+ Dodaj urządzenie</a>'
        '<a href="/urzadzenia/firmware" class="btn bo bsm">Firmware ESP32</a>'
        '</div>'
        '<div class="card" style="overflow-x:auto"><table>'
        '<thead><tr><th>Nazwa</th><th>Typ</th><th>Adres</th><th>Status</th><th></th></tr></thead>'
        '<tbody>' + (w or '<tr><td colspan=5 style="color:#888;text-align:center;padding:20px">Brak urządzeń</td></tr>') + '</tbody></table></div>'
    )
    return R(html, "urz")

@app.route("/urzadzenia/dodaj", methods=["GET","POST"])
@farm_required
def urzadzenia_dodaj():
    g = gid()
    if request.method == "POST":
        db = get_db()
        n_ch = int(request.form.get("n_kanalow",4))
        did = db.execute("INSERT INTO urzadzenia(gospodarstwo_id,nazwa,typ,ip,port,api_key) VALUES(?,?,?,?,?,?)",
            (g, request.form["nazwa"], request.form.get("typ","esp32"),
             request.form["ip"], request.form.get("port",80), request.form.get("api_key",""))).lastrowid
        for i in range(1, n_ch+1):
            db.execute("INSERT INTO urzadzenia_kanaly(urzadzenie_id,kanal,opis) VALUES(?,?,?)",
                       (did, "relay"+str(i), "Przekaźnik "+str(i)))
        db.commit(); db.close()
        flash("Urządzenie dodane.")
        return redirect("/urzadzenia")
    html = (
        '<h1>Nowe urządzenie</h1><div class="card"><form method="POST">'
        '<label>Nazwa</label><input name="nazwa" required placeholder="np. ESP32 Kurnik A">'
        '<div class="g2">'
        '<div><label>Typ</label><select name="typ"><option value="esp32">ESP32</option><option value="rpi">RPi slave</option></select></div>'
        '<div><label>Liczba kanałów relay</label><input name="n_kanalow" type="number" min="1" max="8" value="4"></div>'
        '</div>'
        '<div class="g2">'
        '<div><label>Adres IP</label><input name="ip" required placeholder="192.168.1.X"></div>'
        '<div><label>Port HTTP</label><input name="port" type="number" value="80"></div>'
        '</div>'
        '<label>API Key (zalecany)</label><input name="api_key" placeholder="np. ferma-esp32-klucz-123">'
        '<br><button class="btn bp">Dodaj</button>'
        '<a href="/urzadzenia" class="btn bo" style="margin-left:8px">Anuluj</a>'
        '</form></div>'
    )
    return R(html, "urz")

@app.route("/urzadzenia/<int:did>")
@farm_required
def urzadzenia_panel(did):
    g = gid()
    db = get_db()
    dev = db.execute("SELECT * FROM urzadzenia WHERE id=? AND gospodarstwo_id=?", (did,g)).fetchone()
    if not dev: return redirect("/urzadzenia")
    chs  = db.execute("SELECT * FROM urzadzenia_kanaly WHERE urzadzenie_id=? ORDER BY kanal", (did,)).fetchall()
    logi = db.execute("SELECT * FROM gpio_log WHERE urzadzenie_id=? ORDER BY czas DESC LIMIT 20", (did,)).fetchall()
    db.close()
    ch_html = "".join(
        '<div class="relay-card ' + ('relay-on' if ch["stan"] else '') + '">'
        '<div onclick="sendCmd(' + str(did) + ',\'' + ch["kanal"] + '\',' + ('false' if ch["stan"] else 'true') + ')" style="cursor:pointer">'
        '<div class="tog ' + ('on' if ch["stan"] else '') + '"></div>'
        '<div style="font-size:12px;margin-top:6px;font-weight:500">' + ch["kanal"] + '</div>'
        '<div style="font-size:11px;color:' + ('#3B6D11' if ch["stan"] else '#888') + '">' + ('ON' if ch["stan"] else 'OFF') + '</div>'
        '</div></div>'
        for ch in chs
    )
    w_log = "".join(
        '<tr><td style="font-size:11px">' + l["czas"][:16] + '</td>'
        '<td>' + (l["kanal"] or "") + '</td>'
        '<td><span class="badge ' + ('b-green' if l["stan"] else 'b-gray') + '">' + ('ON' if l["stan"] else 'OFF') + '</span></td>'
        '<td style="font-size:11px;color:#888">' + (l["zrodlo"] or "") + '</td></tr>'
        for l in logi
    )
    html = (
        '<h1>' + dev["nazwa"] + '</h1>'
        '<div class="g3" style="margin-bottom:12px">'
        '<div class="card stat"><div class="v"><span class="badge ' + ('b-green' if dev["status"]=="online" else 'b-red') + '">' + dev["status"] + '</span></div><div class="l">Status</div></div>'
        '<div class="card stat"><div class="v"><code style="font-size:13px">' + dev["ip"] + ':' + str(dev["port"]) + '</code></div><div class="l">Adres</div></div>'
        '<div class="card stat"><div class="v">' + dev["typ"].upper() + '</div><div class="l">Typ</div></div>'
        '</div>'
        '<div class="card"><b>Kanały</b><div class="g4" style="margin-top:10px">' + (ch_html or '<p style="color:#888">Brak kanałów</p>') + '</div></div>'
        '<div class="card"><b>Log</b><div style="overflow-x:auto"><table style="margin-top:8px">'
        '<thead><tr><th>Czas</th><th>Kanał</th><th>Stan</th><th>Źródło</th></tr></thead>'
        '<tbody>' + (w_log or '<tr><td colspan=4 style="color:#888;padding:10px">Brak</td></tr>') + '</tbody></table></div></div>'
        '<a href="/urzadzenia/' + str(did) + '/ping" class="btn bo bsm">Ping / odśwież status</a>'
        '<script>'
        'function sendCmd(uid,ch,state){'
        'fetch("/urzadzenia/cmd",{method:"POST",'
        'headers:{"Content-Type":"application/json"},'
        'body:JSON.stringify({urzadzenie_id:uid,kanal:ch,stan:state})})'
        '.then(r=>r.json()).then(()=>location.reload());}'
        '</script>'
    )
    return R(html, "urz")

@app.route("/urzadzenia/cmd", methods=["POST"])
@farm_required
def urzadzenia_cmd():
    g = gid()
    data = request.get_json()
    ok, msg = send_command(data["urzadzenie_id"], data["kanal"], data["stan"], g)
    return jsonify({"ok":ok,"error":None if ok else msg})

@app.route("/urzadzenia/<int:did>/ping")
@farm_required
def urzadzenia_ping(did):
    g = gid()
    ok, msg = ping_device(did, g)
    flash(("Online" if ok else "Offline") + ": " + msg)
    return redirect("/urzadzenia/" + str(did))

@app.route("/urzadzenia/firmware")
@farm_required
def urzadzenia_firmware():
    html = (
        '<h1>Firmware ESP32</h1>'
        '<p style="color:#5f5e5a;font-size:14px;margin-bottom:12px">Wgraj przez Arduino IDE. Biblioteki: WiFi (wbudowana), WebServer (wbudowana), ArduinoJson.</p>'
        '<div class="card">'
        '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">'
        '<b>Kod źródłowy</b>'
        '<a href="/urzadzenia/firmware/download" class="btn bp bsm">Pobierz .ino</a>'
        '</div>'
        '<pre style="background:#f5f5f0;border-radius:8px;padding:14px;font-size:11px;overflow-x:auto;border:1px solid #e0ddd4;white-space:pre-wrap">'
        + ESP32_FIRMWARE.replace("<","&lt;").replace(">","&gt;")
        + '</pre></div>'
        '<div class="card"><b>Piny domyślne</b>'
        '<p style="font-size:13px;color:#5f5e5a;margin-top:8px">'
        'relay1=GPIO16, relay2=GPIO17, relay3=GPIO18, relay4=GPIO19 (active-low)<br>'
        'Wpisz ten sam API Key co w panelu urządzenia.'
        '</p></div>'
    )
    return R(html, "urz")

@app.route("/urzadzenia/firmware/download")
@farm_required
def firmware_download():
    return send_file(io.BytesIO(ESP32_FIRMWARE.encode()), mimetype="text/plain",
                     as_attachment=True, download_name="ferma_esp32.ino")

# ─── KALENDARZ ────────────────────────────────────────────────────────────────
@app.route("/kalendarz")
@farm_required
def kalendarz():
    g = gid()
    db = get_db()
    rows = db.execute("SELECT * FROM kalendarz WHERE gospodarstwo_id=? ORDER BY nastepne ASC", (g,)).fetchall()
    db.close()
    today = date.today()
    w = "".join(
        '<tr>'
        '<td style="font-weight:500">' + r["nazwa"] + '</td>'
        '<td>' + (str(r["co_ile_dni"]) + " dni" if r["co_ile_dni"] else "—") + '</td>'
        '<td style="color:' + ('#A32D2D' if r["nastepne"] and r["nastepne"] <= str(today) else '#2c2c2a') + ';font-weight:500">' + (str(r["nastepne"]) or "—") + '</td>'
        '<td>' + (str(r["ostatnie_wykonanie"]) or "—") + '</td>'
        '<td class="nowrap">'
        '<a href="/kalendarz/' + str(r["id"]) + '/wykonano" class="btn bg bsm">Wykonano</a> '
        '<a href="/kalendarz/' + str(r["id"]) + '/usun" class="btn br bsm">✕</a>'
        '</td></tr>'
        for r in rows
    )
    html = (
        '<h1>Kalendarz zdarzeń</h1>'
        '<a href="/kalendarz/dodaj" class="btn bp bsm" style="margin-bottom:12px">+ Dodaj zdarzenie</a>'
        '<div class="card" style="overflow-x:auto"><table>'
        '<thead><tr><th>Zdarzenie</th><th>Co ile</th><th>Następne</th><th>Ostatnie</th><th></th></tr></thead>'
        '<tbody>' + (w or '<tr><td colspan=5 style="color:#888;text-align:center;padding:20px">Brak zdarzeń</td></tr>') + '</tbody></table></div>'
    )
    return R(html, "kal")

@app.route("/kalendarz/dodaj", methods=["GET","POST"])
@farm_required
def kalendarz_dodaj():
    g = gid()
    if request.method == "POST":
        dp = request.form.get("data_pierwsza", date.today().isoformat())
        db = get_db()
        db.execute("INSERT INTO kalendarz(gospodarstwo_id,nazwa,typ,data_pierwsza,co_ile_dni,powiadomienie_dni_przed,nastepne,uwagi) VALUES(?,?,?,?,?,?,?,?)",
            (g, request.form["nazwa"], request.form.get("typ","cykliczne"), dp,
             request.form.get("co_ile_dni",0) or 0, request.form.get("powiadomienie_dni_przed",3) or 3,
             dp, request.form.get("uwagi","")))
        db.commit(); db.close()
        flash("Zdarzenie dodane.")
        return redirect("/kalendarz")
    html = (
        '<h1>Nowe zdarzenie</h1><div class="card"><form method="POST">'
        '<label>Nazwa</label><input name="nazwa" required placeholder="np. Wymiana ściółki, Dezynfekcja">'
        '<div class="g2">'
        '<div><label>Typ</label><select name="typ"><option value="cykliczne">Cykliczne</option><option value="jednorazowe">Jednorazowe</option></select></div>'
        '<div><label>Data pierwszego wykonania</label><input name="data_pierwsza" type="date" value="' + date.today().isoformat() + '"></div>'
        '</div>'
        '<div class="g2">'
        '<div><label>Powtarzaj co (dni)</label><input name="co_ile_dni" type="number" min="0" value="14"></div>'
        '<div><label>Powiadom na ile dni przed</label><input name="powiadomienie_dni_przed" type="number" value="3"></div>'
        '</div>'
        '<label>Uwagi</label><textarea name="uwagi" rows="2"></textarea>'
        '<br><button class="btn bp">Dodaj</button>'
        '<a href="/kalendarz" class="btn bo" style="margin-left:8px">Anuluj</a>'
        '</form></div>'
    )
    return R(html, "kal")

@app.route("/kalendarz/<int:kid>/wykonano")
@farm_required
def kalendarz_wykonano(kid):
    g = gid()
    db = get_db()
    r = db.execute("SELECT * FROM kalendarz WHERE id=? AND gospodarstwo_id=?", (kid,g)).fetchone()
    if r:
        today = date.today()
        if r["co_ile_dni"] and int(r["co_ile_dni"]) > 0:
            nowe = today + timedelta(days=int(r["co_ile_dni"]))
            db.execute("UPDATE kalendarz SET ostatnie_wykonanie=?,nastepne=? WHERE id=?",
                       (str(today), str(nowe), kid))
        else:
            db.execute("UPDATE kalendarz SET ostatnie_wykonanie=?,aktywne=0 WHERE id=?", (str(today), kid))
        db.commit()
        flash("Zaznaczono jako wykonane.")
    db.close()
    return redirect("/kalendarz")

@app.route("/kalendarz/<int:kid>/usun")
@farm_required
def kalendarz_usun(kid):
    g = gid()
    db = get_db()
    db.execute("DELETE FROM kalendarz WHERE id=? AND gospodarstwo_id=?", (kid,g))
    db.commit(); db.close()
    flash("Zdarzenie usunięte.")
    return redirect("/kalendarz")

# ─── KONTO UŻYTKOWNIKA ────────────────────────────────────────────────────────
@app.route("/konto", methods=["GET","POST"])
@login_required
def konto():
    uid, login_val, rola = current_user()
    if request.method == "POST":
        h1 = request.form.get("haslo","")
        h2 = request.form.get("haslo2","")
        if h1 != h2:
            flash("Hasła nie są identyczne.")
        elif len(h1) < 6:
            flash("Hasło musi mieć min. 6 znaków.")
        else:
            change_password(uid, h1)
            flash("Hasło zmienione.")
        return redirect("/konto")
    db = get_db()
    u = db.execute("SELECT * FROM uzytkownicy WHERE id=?", (uid,)).fetchone()
    db.close()
    farms = get_user_farms(uid)
    w_farm = "".join(
        '<tr><td>' + f["nazwa"] + '</td><td><span class="badge b-purple">' + f["moja_rola"] + '</span></td></tr>'
        for f in farms
    )
    html = (
        '<h1>Moje konto</h1>'
        '<div class="card">'
        '<p style="font-size:14px"><b>Login:</b> ' + (u["login"] if u else "") + '</p>'
        '<p style="font-size:14px;margin-top:4px"><b>Email:</b> ' + (u["email"] if u else "") + '</p>'
        '<p style="font-size:14px;margin-top:4px"><b>Rola:</b> ' + rola + '</p>'
        '</div>'
        '<div class="card"><b>Zmień hasło</b>'
        '<form method="POST" style="margin-top:10px">'
        '<div class="g2">'
        '<div><label>Nowe hasło</label><input name="haslo" type="password"></div>'
        '<div><label>Powtórz hasło</label><input name="haslo2" type="password"></div>'
        '</div>'
        '<br><button class="btn bp">Zmień hasło</button>'
        '</form></div>'
        '<div class="card"><b>Moje gospodarstwa</b>'
        '<table style="margin-top:8px"><thead><tr><th>Nazwa</th><th>Rola</th></tr></thead>'
        '<tbody>' + w_farm + '</tbody></table>'
        '<br><a href="/wybierz-gospodarstwo" class="btn bo bsm">Zarządzaj gospodarstwami</a>'
        '</div>'
    )
    return R(html, "konto")

# ─── SUPERADMIN ───────────────────────────────────────────────────────────────
@app.route("/admin")
@login_required
@superadmin_required
def admin():
    db = get_db()
    users = db.execute("SELECT u.*,COUNT(ug.gospodarstwo_id) as n_farm FROM uzytkownicy u LEFT JOIN uzytkownicy_gospodarstwa ug ON u.id=ug.uzytkownik_id GROUP BY u.id ORDER BY u.data_rejestracji DESC").fetchall()
    farms = db.execute("SELECT g.*,COUNT(ug.uzytkownik_id) as n_user FROM gospodarstwa g LEFT JOIN uzytkownicy_gospodarstwa ug ON g.id=ug.gospodarstwo_id GROUP BY g.id ORDER BY g.data_utworzenia DESC").fetchall()
    cfg   = db.execute("SELECT * FROM system_config").fetchall()
    db.close()
    w_users = "".join(
        '<tr>'
        '<td style="font-weight:500">' + u["login"] + '</td>'
        '<td style="color:#888;font-size:12px">' + (u["email"] or "") + '</td>'
        '<td><span class="badge ' + ('b-purple' if u["rola"]=="superadmin" else 'b-blue') + '">' + u["rola"] + '</span></td>'
        '<td>' + str(u["n_farm"]) + '</td>'
        '<td>' + (u["data_rejestracji"][:10] if u["data_rejestracji"] else "—") + '</td>'
        '<td><span class="badge ' + ('b-green' if u["aktywny"] else 'b-red') + '">' + ('aktywny' if u["aktywny"] else 'zablokowany') + '</span></td>'
        '<td class="nowrap">'
        + ('' if u["rola"]=="superadmin" else
           '<a href="/admin/user/' + str(u["id"]) + '/toggle" class="btn bo bsm">' + ('Zablokuj' if u["aktywny"] else 'Odblokuj') + '</a>')
        + '</td></tr>'
        for u in users
    )
    w_farms = "".join(
        '<tr><td style="font-weight:500">' + f["nazwa"] + '</td>'
        '<td>' + str(f["n_user"]) + '</td>'
        '<td>' + (f["data_utworzenia"][:10] if f["data_utworzenia"] else "—") + '</td>'
        '<td><span class="badge ' + ('b-green' if f["aktywne"] else 'b-gray') + '">' + ('aktywne' if f["aktywne"] else 'nieaktywne') + '</span></td>'
        '</tr>'
        for f in farms
    )
    cfg_html = "".join(
        '<tr><td>' + c["klucz"] + '</td>'
        '<td><form method="POST" action="/admin/config" style="display:flex;gap:6px">'
        '<input type="hidden" name="klucz" value="' + c["klucz"] + '">'
        '<input name="wartosc" value="' + (c["wartosc"] or "") + '" style="flex:1">'
        '<button class="btn bp bsm">Zapisz</button>'
        '</form></td></tr>'
        for c in cfg
    )
    html = (
        '<h1>Panel administratora</h1>'
        '<div class="g2" style="margin-bottom:12px">'
        '<div class="card stat"><div class="v">' + str(len(users)) + '</div><div class="l">Użytkowników</div></div>'
        '<div class="card stat"><div class="v">' + str(len(farms)) + '</div><div class="l">Gospodarstw</div></div>'
        '</div>'
        '<div class="card"><b>Użytkownicy</b>'
        '<div style="overflow-x:auto"><table style="margin-top:8px">'
        '<thead><tr><th>Login</th><th>Email</th><th>Rola</th><th>Gospodarstw</th><th>Rejestracja</th><th>Status</th><th></th></tr></thead>'
        '<tbody>' + w_users + '</tbody></table></div></div>'
        '<div class="card"><b>Gospodarstwa</b>'
        '<div style="overflow-x:auto"><table style="margin-top:8px">'
        '<thead><tr><th>Nazwa</th><th>Użytkowników</th><th>Utworzone</th><th>Status</th></tr></thead>'
        '<tbody>' + w_farms + '</tbody></table></div></div>'
        '<div class="card"><b>Konfiguracja systemu</b>'
        '<table style="margin-top:8px"><thead><tr><th>Klucz</th><th>Wartość</th></tr></thead>'
        '<tbody>' + cfg_html + '</tbody></table></div>'
    )
    return R(html, "admin")

@app.route("/admin/user/<int:uid>/toggle")
@login_required
@superadmin_required
def admin_user_toggle(uid):
    db = get_db()
    db.execute("UPDATE uzytkownicy SET aktywny=1-aktywny WHERE id=? AND rola!='superadmin'", (uid,))
    db.commit(); db.close()
    flash("Status użytkownika zmieniony.")
    return redirect("/admin")

@app.route("/admin/config", methods=["POST"])
@login_required
@superadmin_required
def admin_config():
    db = get_db()
    db.execute("INSERT OR REPLACE INTO system_config(klucz,wartosc) VALUES(?,?)",
               (request.form["klucz"], request.form.get("wartosc","")))
    db.commit(); db.close()
    flash("Konfiguracja zapisana.")
    return redirect("/admin")

# ─── REJESTRACJA MODUŁÓW (route'y tylko — bez init DB) ──────────────────────
register_routes(app)

# ─── START ────────────────────────────────────────────────────────────────────
def startup():
    init_db()
    init_auth()


if __name__ == "__main__":
    startup()
    print("\n" + "="*54)
    print("  FERMA JAJ SaaS v5 — multi-tenant")
    print("  http://localhost:5000")
    print("  Domyślny admin: admin / ferma2024")
    print("="*54 + "\n")
    app.run(host="0.0.0.0", port=5000, debug=False)
