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
try:
    from supla_oauth import register_supla_oauth_routes
except ImportError:
    register_supla_oauth_routes = None
from produkcja_views import register_produkcja
from sprzedaz_views import register_sprzedaz
from backup_views import register_backup

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
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{% if farm_name %}{{ farm_name }} — {% endif %}Ferma Jaj</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,-apple-system,sans-serif;background:#f5f5f0;color:#2c2c2a;font-size:15px}

/* ─── NAV ──────────────────────────────────────────────────────── */
nav{background:#fff;border-bottom:2px solid #e0ddd4;position:sticky;top:0;z-index:1000;height:52px}
.nb{display:flex;align-items:center;height:52px;padding:0 16px;gap:0}
.nb-logo{font-weight:700;font-size:15px;color:#534AB7;text-decoration:none;white-space:nowrap;margin-right:10px}
.nb-farm{background:#EEEDFE;color:#3C3489;border-radius:6px;padding:2px 8px;font-size:11px;font-weight:500;white-space:nowrap;max-width:110px;overflow:hidden;text-overflow:ellipsis;margin-right:6px}
.nb-links{display:flex;align-items:center;flex:1}
.nb-right{display:flex;align-items:center;margin-left:auto;flex-shrink:0}

/* Linki i dropdowny */
.ni{position:relative}
.nl{display:flex;align-items:center;gap:3px;padding:0 10px;height:52px;font-size:13px;font-weight:500;color:#5f5e5a;text-decoration:none;white-space:nowrap;cursor:pointer;background:none;border:none;border-bottom:3px solid transparent;font-family:inherit;-webkit-tap-highlight-color:transparent;touch-action:manipulation;user-select:none;transition:color .1s}
.nl:hover,.nl.on{color:#2c2c2a;border-bottom-color:#534AB7}
.nl .ar{font-size:8px;opacity:.4;transition:transform .15s;margin-left:1px}
.ni.op>.nl .ar{transform:rotate(180deg)}
.nd{display:none;position:absolute;top:52px;left:0;background:#fff;border:1px solid #ddd;border-radius:10px;box-shadow:0 6px 24px rgba(0,0,0,.12);min-width:200px;padding:4px;z-index:2000}
.nd-r{right:0;left:auto}
.ni.op>.nd{display:block}
.nd a{display:flex;align-items:center;padding:9px 14px;color:#2c2c2a;text-decoration:none;font-size:13px;border-radius:7px;white-space:nowrap;gap:8px}
.nd a:hover{background:#f5f5f0}
.nd a.on{color:#534AB7;font-weight:600;background:#EEEDFE}
.nd-sep{height:1px;background:#eee;margin:3px 6px}
.nd-hd{padding:6px 14px 2px;font-size:10px;font-weight:600;color:#aaa;text-transform:uppercase;letter-spacing:.5px}

/* Hamburger */
.hbg{display:none;flex-direction:column;justify-content:center;gap:5px;width:44px;height:44px;padding:10px;cursor:pointer;background:none;border:none;margin-left:6px;flex-shrink:0;-webkit-tap-highlight-color:transparent}
.hbg span{display:block;width:22px;height:2px;background:#534AB7;border-radius:2px;transition:all .22s}
.hbg.op span:nth-child(1){transform:translateY(7px) rotate(45deg)}
.hbg.op span:nth-child(2){opacity:0}
.hbg.op span:nth-child(3){transform:translateY(-7px) rotate(-45deg)}

/* Drawer */
.dr{display:none;position:fixed;inset:52px 0 0 0;background:#fff;z-index:999;overflow-y:auto;-webkit-overflow-scrolling:touch}
.dr.op{display:block}
.dr-sec{border-bottom:1px solid #f0ede4}
.dr-hd{display:flex;align-items:center;justify-content:space-between;padding:15px 18px;font-size:15px;font-weight:600;color:#2c2c2a;cursor:pointer;user-select:none;-webkit-tap-highlight-color:transparent}
.dr-ar{font-size:10px;color:#bbb;transition:transform .2s}
.dr-sec.op .dr-ar{transform:rotate(180deg)}
.dr-bd{display:none;padding-bottom:4px}
.dr-sec.op .dr-bd{display:block}
.dr-bd a{display:block;padding:12px 28px;font-size:14px;color:#5f5e5a;text-decoration:none;-webkit-tap-highlight-color:transparent}
.dr-bd a.on{color:#534AB7;font-weight:600}
.dr-fl{display:block;padding:15px 18px;font-size:15px;font-weight:500;color:#2c2c2a;text-decoration:none;border-bottom:1px solid #f0ede4;-webkit-tap-highlight-color:transparent}
.dr-fl.on{color:#534AB7;font-weight:700}
.dr-ft{padding:16px 18px;display:flex;justify-content:space-between;align-items:center;border-top:2px solid #eee;margin-top:4px}

@media(max-width:768px){.nb-links,.nb-right .ni{display:none}.hbg{display:flex}}

/* ─── LAYOUT ───────────────────────────────────────────────────── */
.wrap{max-width:980px;margin:0 auto;padding:14px}
h1{font-size:20px;font-weight:600;margin-bottom:14px}
h2{font-size:14px;font-weight:600;margin:16px 0 8px;color:#444}
.card{background:#fff;border:1px solid #e0ddd4;border-radius:12px;padding:14px;margin-bottom:12px}
.g2{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.g3{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.g4{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
@media(max-width:720px){.g3,.g4{grid-template-columns:1fr 1fr}}
@media(max-width:480px){.g2{grid-template-columns:1fr}.g3,.g4{grid-template-columns:1fr 1fr}}
.stat{text-align:center;padding:10px 4px}
.stat .v{font-size:24px;font-weight:600;line-height:1.2}
.stat .l{font-size:11px;color:#888;margin-top:3px}
.stat .s{font-size:11px;color:#5f5e5a;margin-top:2px}
.al{padding:9px 13px;border-radius:8px;margin-bottom:8px;font-size:13px}
.ald{background:#FCEBEB;border:1px solid #F7C1C1;color:#791F1F}
.alw{background:#FAEEDA;border:1px solid #FAC775;color:#633806}
.alok{background:#EAF3DE;border:1px solid #C0DD97;color:#27500A}
label{display:block;font-size:12px;color:#5f5e5a;margin:8px 0 3px}
input,select,textarea{width:100%;padding:9px 10px;border:1px solid #d3d1c7;border-radius:8px;font-size:15px;background:#fff;color:#2c2c2a;-webkit-appearance:none;appearance:none}
input:focus,select:focus,textarea:focus{outline:none;border-color:#7F77DD}
.btn{display:inline-flex;align-items:center;padding:9px 16px;border-radius:8px;border:1px solid transparent;font-size:14px;cursor:pointer;text-decoration:none;font-weight:500;line-height:1;-webkit-tap-highlight-color:transparent;touch-action:manipulation;gap:4px}
.bp{background:#534AB7;color:#fff;border-color:#534AB7}.bp:hover{background:#3C3489}
.bo{background:#fff;color:#534AB7;border-color:#AFA9EC}.bo:hover{background:#EEEDFE}
.bg{background:#3B6D11;color:#fff}.br{background:#A32D2D;color:#fff}
.bsm{padding:5px 10px;font-size:12px}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;padding:8px;border-bottom:1px solid #e0ddd4;font-weight:500;font-size:12px;color:#5f5e5a}
td{padding:7px 8px;border-bottom:1px solid #f0ede4;vertical-align:middle}
tr:last-child td{border-bottom:none}
.badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:500}
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
code{background:#f0ede4;padding:2px 5px;border-radius:4px;font-size:12px}
.nowrap{white-space:nowrap}
</style>
</head>
<body>
<nav>
<div class="nb">
  <a href="/" class="nb-logo">&#x1F413; Ferma</a>
  {% if farm_id %}
  <span class="nb-farm" title="{{ farm_name }}">{{ farm_name }}</span>
  <div class="nb-links">
    <a href="/" class="nl {{ 'on' if p=='dash' }}">Dashboard</a>
    <a href="/produkcja" class="nl {{ 'on' if p in ['prod','stado'] }}">Hodowla</a>
    <a href="/sprzedaz" class="nl {{ 'on' if p in ['zam','mag','sprzedaz'] }}">Sprzeda&#380;</a>

    <div class="ni">
      <button class="nl {{ 'on' if p in ['wyd','pasza','woda','stado'] }}">Zasoby <span class="ar">&#9660;</span></button>
      <div class="nd">
        <a href="/stado" class="{{ 'on' if p=='stado' }}">&#x1F414; Stado</a>
        <div class="nd-sep"></div>
        <a href="/wydatki" class="{{ 'on' if p=='wyd' }}">&#x1F4B8; Wydatki</a>
        <a href="/pasza" class="{{ 'on' if p=='pasza' }}">&#x1F33E; Pasza</a>
        <a href="/pasza/mieszalnik">&#x2697;&#xFE0F; Mieszalnik</a>
        <a href="/pasza/zuzycie">&#x1F4CA; Zużycie paszy</a>
        <a href="/woda" class="{{ 'on' if p=='woda' }}">&#x1F4A7; Woda</a>
        <a href="/energia">&#x26A1; Energia</a>
        <div class="nd-sep"></div>
        <a href="/wyposazenie">&#x1F527; Wyposa&#380;enie</a>
      </div>
    </div>

    <div class="ni">
      <button class="nl {{ 'on' if p in ['gpio','urz','kal','harm'] }}">Sterowanie <span class="ar">&#9660;</span></button>
      <div class="nd">
        <a href="/sterowanie" class="{{ 'on' if p=='gpio' }}">&#x26A1; Panel sterowania</a>
        <a href="/harmonogramy" class="{{ 'on' if p=='harm' }}">&#x23F0; Harmonogramy</a>
        <div class="nd-sep"></div>
        <a href="/gpio">&#x1F50C; GPIO</a>
        <a href="/urzadzenia" class="{{ 'on' if p=='urz' }}">&#x1F4F1; Urz&#261;dzenia</a>
        <a href="/supla">&#x2601;&#xFE0F; Supla</a>
        <div class="nd-sep"></div>
        <a href="/ustawienia/farma">&#x2699;&#xFE0F; Ustawienia</a>
      </div>
    </div>

    <div class="ni">
      <button class="nl {{ 'on' if p=='ana' }}">Analityka <span class="ar">&#9660;</span></button>
      <div class="nd">
        <a href="/analityka" class="{{ 'on' if p=='ana' }}">&#x1F4CA; Wykresy</a>
        <a href="/pasza/analityka">&#x1F9EA; Analiza paszy</a>
        <a href="/pasza/skladniki-baza">&#x1F4DA; Baza sk&#322;adnik&#243;w</a>
      </div>
    </div>
  </div>

  <div class="nb-right">
    <div class="ni">
      <button class="nl" style="font-size:12px">{{ login }} <span class="ar">&#9660;</span></button>
      <div class="nd nd-r">
        <a href="/konto">&#x1F464; Moje konto</a>
        <a href="/wybierz-gospodarstwo">&#x1F3E0; Zmie&#324; farm&#281;</a>
        <a href="/ustawienia/farma">&#x2699;&#xFE0F; Ustawienia farmy</a>
        <a href="/import/xlsx">&#x1F4C2; Import xlsx</a>
        {% if rola == 'superadmin' %}
        <div class="nd-sep"></div>
        <a href="/admin" class="{{ 'on' if p=='admin' }}">&#x1F6E1;&#xFE0F; Panel admina</a>
        {% endif %}
        <div class="nd-sep"></div>
        <a href="/wyloguj" style="color:#A32D2D;font-weight:600">&#x1F6AA; Wyloguj</a>
      </div>
    </div>
  </div>

  <button class="hbg" id="hbg" onclick="nbToggle(event)">
    <span></span><span></span><span></span>
  </button>

  {% else %}
  <div style="margin-left:auto">
    <a href="/login" class="nl">Zaloguj</a>
  </div>
  {% endif %}
</div>
</nav>

{% if farm_id %}
<div class="dr" id="dr">
  <a href="/" class="dr-fl {{ 'on' if p=='dash' }}" onclick="drClose()">&#x1F3E0; Dashboard</a>

  <a href="/produkcja" class="dr-fl {{ 'on' if p in ['prod','stado'] }}" onclick="drClose()">&#x1F414; Hodowla</a>

  <a href="/sprzedaz" class="dr-fl {{ 'on' if p in ['zam','mag','sprzedaz'] }}" onclick="drClose()">&#x1F4E6; Sprzeda&#380;</a>

  <div class="dr-sec" id="ds-zas">
    <div class="dr-hd" onclick="drSec('ds-zas')">
      <span>&#x1F33E; Zasoby</span><span class="dr-ar">&#9660;</span>
    </div>
    <div class="dr-bd">
      <a href="/stado" class="{{ 'on' if p=='stado' }}" onclick="drClose()">&#x1F414; Stado</a>
      <a href="/wydatki" class="{{ 'on' if p=='wyd' }}" onclick="drClose()">Wydatki</a>
      <a href="/pasza" class="{{ 'on' if p=='pasza' }}" onclick="drClose()">Pasza</a>
      <a href="/pasza/mieszalnik" onclick="drClose()">Mieszalnik</a>
      <a href="/woda" class="{{ 'on' if p=='woda' }}" onclick="drClose()">Woda</a>
      <a href="/energia" onclick="drClose()">Energia</a>
      <a href="/wyposazenie" onclick="drClose()">Wyposa&#380;enie</a>
    </div>
  </div>

  <div class="dr-sec" id="ds-ste">
    <div class="dr-hd" onclick="drSec('ds-ste')">
      <span>&#x26A1; Sterowanie</span><span class="dr-ar">&#9660;</span>
    </div>
    <div class="dr-bd">
      <a href="/sterowanie" onclick="drClose()">Panel sterowania</a>
      <a href="/harmonogramy" class="{{ 'on' if p=='harm' }}" onclick="drClose()">&#x23F0; Harmonogramy</a>
      <a href="/gpio" onclick="drClose()">GPIO</a>
      <a href="/urzadzenia" class="{{ 'on' if p=='urz' }}" onclick="drClose()">Urz&#261;dzenia</a>
      <a href="/supla" onclick="drClose()">Supla</a>
      <a href="/ustawienia/farma" onclick="drClose()">Ustawienia</a>
    </div>
  </div>

  <div class="dr-sec" id="ds-ana">
    <div class="dr-hd" onclick="drSec('ds-ana')">
      <span>&#x1F4CA; Analityka</span><span class="dr-ar">&#9660;</span>
    </div>
    <div class="dr-bd">
      <a href="/analityka" class="{{ 'on' if p=='ana' }}" onclick="drClose()">Wykresy</a>
      <a href="/pasza/analityka" onclick="drClose()">Analiza paszy</a>
      <a href="/pasza/skladniki-baza" onclick="drClose()">Baza sk&#322;adnik&#243;w</a>
    </div>
  </div>

  <div class="dr-ft">
    <span style="font-size:13px;color:#888">{{ login }} &middot; {{ farm_name }}</span>
    <div style="display:flex;gap:14px">
      <a href="/konto" style="font-size:13px;color:#534AB7">Konto</a>
      <a href="/wyloguj" style="font-size:13px;color:#A32D2D;font-weight:700">Wyloguj</a>
    </div>
  </div>
</div>
{% endif %}

<script>
(function(){
  // Desktop dropdowny — klik (działa na iOS i desktop)
  document.querySelectorAll('.ni').forEach(function(ni){
    var btn = ni.querySelector('.nl');
    if(!btn) return;
    btn.addEventListener('click',function(e){
      e.stopPropagation();
      var was = ni.classList.contains('op');
      document.querySelectorAll('.ni.op').forEach(function(x){x.classList.remove('op');});
      if(!was) ni.classList.add('op');
    });
    ni.querySelectorAll('.nd a').forEach(function(a){
      a.addEventListener('click',function(e){
        e.stopPropagation();
        document.querySelectorAll('.ni.op').forEach(function(x){x.classList.remove('op');});
      });
    });
  });
  document.addEventListener('click',function(){
    document.querySelectorAll('.ni.op').forEach(function(x){x.classList.remove('op');});
  });

  // Mobile hamburger + drawer
  function nbToggle(e){
    if(e) e.stopPropagation();
    var d=document.getElementById('dr'),b=document.getElementById('hbg');
    if(!d) return;
    var op=!d.classList.contains('op');
    d.classList.toggle('op',op);
    b.classList.toggle('op',op);
    document.body.style.overflow=op?'hidden':'';
  }
  function drClose(){
    var d=document.getElementById('dr'),b=document.getElementById('hbg');
    if(d){d.classList.remove('op');}
    if(b){b.classList.remove('op');}
    document.body.style.overflow='';
  }
  function drSec(id){
    document.getElementById(id).classList.toggle('op');
  }
  window.nbToggle=nbToggle;
  window.drClose=drClose;
  window.drSec=drSec;

  // Auto-otwórz aktywną sekcję w drawerze
  var act=document.querySelector('.dr-bd a.on');
  if(act){var s=act.closest('.dr-sec');if(s)s.classList.add('op');}
})();
</script>

{% for msg in get_flashed_messages() %}
<div class="flash" style="max-width:980px;margin:8px auto 0">{{ msg }}</div>
{% endfor %}
<div class="wrap">{{ content }}</div>
</body>
</html>
"""

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
@app.route("/wyloguj")
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


@app.route("/produkcja/dodaj", methods=["POST"])
@farm_required
def produkcja_dodaj():
    g = gid()
    d     = request.form.get("data", date.today().isoformat())
    jaja  = int(request.form.get("jaja_zebrane", 0) or 0)
    pasza = float(request.form.get("pasza_wydana_kg", 0) or 0)
    uwagi = request.form.get("uwagi", "")
    db = get_db()
    ex = db.execute("SELECT id FROM produkcja WHERE gospodarstwo_id=? AND data=?", (g, d)).fetchone()
    if ex:
        db.execute("UPDATE produkcja SET jaja_zebrane=?, pasza_wydana_kg=?, uwagi=? WHERE id=?",
                   (jaja, pasza, uwagi, ex["id"]))
    else:
        db.execute("INSERT INTO produkcja(gospodarstwo_id,data,jaja_zebrane,jaja_sprzedane,cena_sprzedazy,pasza_wydana_kg,uwagi) VALUES(?,?,?,0,0,?,?)",
                   (g, d, jaja, pasza, uwagi))
    db.commit(); db.close()
    flash("Zapisano: " + str(jaja) + " jaj (" + d + ")")
    return redirect("/")


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
    ostatnie = db.execute("SELECT data, jaja_zebrane FROM produkcja WHERE gospodarstwo_id=? ORDER BY data DESC LIMIT 7", (g,)).fetchall()
    zam_dzis = db.execute("SELECT COUNT(*) as c FROM zamowienia WHERE gospodarstwo_id=? AND data_dostawy=date('now') AND status NOT IN ('dostarczone','anulowane')", (g,)).fetchone()["c"]
    urzadz = db.execute("SELECT * FROM urzadzenia WHERE gospodarstwo_id=? AND aktywne=1 ORDER BY nazwa", (g,)).fetchall()
    kal = db.execute("SELECT * FROM kalendarz WHERE gospodarstwo_id=? AND aktywne=1 AND nastepne<=date('now','+7 days') ORDER BY nastepne LIMIT 3", (g,)).fetchall()
    klienci = db.execute("SELECT id,nazwa FROM klienci WHERE gospodarstwo_id=? ORDER BY nazwa", (g,)).fetchall()
    zamow_aktywne = db.execute("""SELECT z.id,z.data_dostawy,z.ilosc,z.cena_za_szt,k.nazwa as kn FROM zamowienia z
        LEFT JOIN klienci k ON z.klient_id=k.id
        WHERE z.gospodarstwo_id=? AND z.status IN ('nowe','potwierdzone')
        ORDER BY z.data_dostawy LIMIT 5""", (g,)).fetchall()
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

    # ── STAŁE KAFELKI STEROWANIA ─────────────────────────────────────────
    FIXED_CH = [
        ("swiatlo_kurnik",   "💡", "Światło kurnik",    "swiatlo"),
        ("swiatlo_obejscie", "💡", "Światło obejście",  "swiatlo"),
        ("swiatlo_gniazda",  "💡", "Światło gniazda",   "swiatlo"),
        ("wentylacja",       "💨", "Wentylacja",         "wentylacja"),
        ("dozowanie_paszy",  "🌾", "Dozowanie paszy",    "pojenie"),
        ("dozowanie_wody",   "💧", "Dozowanie wody",     "pojenie"),
    ]
    db2 = get_db()
    kanal_cfg = {}
    for fkey, fico, flabel, fkat in FIXED_CH:
        cfg = db2.execute(
            "SELECT ks.urzadzenie_id, ks.kanal, ks.opis, uc.stan "
            "FROM kanal_sterowanie ks "
            "LEFT JOIN urzadzenia_kanaly uc "
            "  ON uc.urzadzenie_id=ks.urzadzenie_id AND uc.kanal=ks.kanal "
            "WHERE ks.gospodarstwo_id=? AND ks.kategoria=? "
            "ORDER BY ks.id LIMIT 1", (g, fkat)).fetchone()
        kanal_cfg[fkey] = dict(cfg) if cfg else None
    woda_dzis  = float(db2.execute("SELECT COALESCE(SUM(litry),0) as s FROM woda_reczna WHERE gospodarstwo_id=? AND data=date('now')", (g,)).fetchone()["s"] or 0)
    prad_dzis  = float(db2.execute("SELECT COALESCE(SUM(kwh),0) as s FROM prad_odczyty WHERE gospodarstwo_id=? AND data=date('now')", (g,)).fetchone()["s"] or 0)
    pasza_dzis = float(db2.execute("SELECT COALESCE(SUM(pasza_wydana_kg),0) as s FROM produkcja WHERE gospodarstwo_id=? AND data=date('now')", (g,)).fetchone()["s"] or 0)
    db2.close()

    def _kaf(fkey, fico, flabel, fkat):
        cfg = kanal_cfg.get(fkey)
        on  = bool(cfg and cfg.get("stan"))
        ok  = cfg is not None
        did = cfg["urzadzenie_id"] if cfg else None
        kan = cfg["kanal"] if cfg else None
        bc  = "#3B6D11" if on else ("#7F77DD" if ok else "#e0ddd4")
        bg  = "#f4faf0" if on else "#fff"
        dot = ("<span style='color:#3B6D11;font-weight:600'>● ON</span>" if on
               else ("<span style='color:#888'>○ OFF</span>" if ok
               else "<span style='color:#bbb;font-size:10px'>⚙ ustaw</span>"))
        ns  = "false" if on else "true"
        oc  = ("tR(" + str(did) + ",'" + str(kan) + "'," + ns + ")" if (ok and did and kan)
               else "window.location='/sterowanie'")
        return (
            "<div style='border:2px solid " + bc + ";border-radius:12px;padding:12px 6px;"
            "text-align:center;background:" + bg + ";cursor:pointer;transition:all .15s;"
            "touch-action:manipulation' onclick=\"" + oc + "\">"
            "<div style='font-size:24px;line-height:1'>" + fico + "</div>"
            "<div style='font-size:11px;font-weight:600;margin-top:5px;color:#2c2c2a;line-height:1.3'>" + flabel + "</div>"
            "<div style='font-size:10px;margin-top:3px'>" + dot + "</div>"
            "</div>"
        )

    kafelki_ster = "".join(_kaf(*ch) for ch in FIXED_CH)
    zuzycia_kaf = (
        "<div style='border:2px solid #e0ddd4;border-radius:12px;padding:12px 6px;background:#fff'>"
        "<div style='font-size:24px;text-align:center'>📊</div>"
        "<div style='font-size:11px;font-weight:600;text-align:center;margin-top:5px;color:#2c2c2a'>Zużycia dziś</div>"
        "<div style='margin-top:6px;font-size:11px'>"
        "<div style='display:flex;justify-content:space-between;padding:2px'><span>💧</span><b>" + str(round(woda_dzis,1)) + " L</b></div>"
        "<div style='display:flex;justify-content:space-between;padding:2px'><span>🌾</span><b>" + str(round(pasza_dzis,1)) + " kg</b></div>"
        "<div style='display:flex;justify-content:space-between;padding:2px'><span>⚡</span><b>" + str(round(prad_dzis,2)) + " kWh</b></div>"
        "</div></div>"
    )

    sterowanie_html = (
        "<div class='card' style='margin-bottom:12px'>"
        "<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:12px'>"
        "<b>Sterowanie</b>"
        "<a href='/sterowanie' style='font-size:12px;color:#534AB7'>Konfiguruj →</a>"
        "</div>"
        "<div style='display:grid;grid-template-columns:repeat(7,1fr);gap:8px'>"
        + kafelki_ster + zuzycia_kaf +
        "</div>"
        "<script>function tR(d,c,s){"
        "fetch('/sterowanie/cmd',{method:'POST',headers:{'Content-Type':'application/json'},"
        "body:JSON.stringify({urzadzenie_id:d,kanal:c,stan:s})})"
        ".then(r=>r.json()).then(function(j){if(j.ok)location.reload();"
        "else alert('Blad: '+(j.msg||'?'));});"
        "}"
        "</script>"
        "</div>"
    )

    # Data po polsku
    _dni_pl = ['Poniedziałek','Wtorek','Środa','Czwartek','Piątek','Sobota','Niedziela']
    _mies_pl = ['stycznia','lutego','marca','kwietnia','maja','czerwca','lipca','sierpnia','września','października','listopada','grudnia']
    _dzisiaj = date.today()
    _data_str = f'{_dni_pl[_dzisiaj.weekday()]}, {_dzisiaj.day} {_mies_pl[_dzisiaj.month-1]} {_dzisiaj.year}'


    # Formularz "Zebrane jaja" — mini historia + wybór daty
    _ostatnie_html = ""
    for _r in ostatnie:
        _ostatnie_html += (
            "<div style='background:#f5f5f0;border-radius:6px;padding:3px 8px;font-size:11px;white-space:nowrap'>"
            "<span style='color:#888'>" + _r["data"][5:] + "</span> "
            "<b>" + str(_r["jaja_zebrane"]) + "</b>"
            "</div>"
        )
    _jaja_form = (
        "<div class='card'>"
        "<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:8px'>"
        "<b>Zebrane jaja</b>"
        + ("<span style='font-size:12px;color:#3B6D11;font-weight:500'>dziś: " + str(dzis["jaja_zebrane"]) + " szt.</span>"
           if dzis else "<span style='font-size:12px;color:#aaa'>brak wpisu na dziś</span>")
        + "</div>"
        + ("<div style='display:flex;gap:4px;flex-wrap:wrap;margin-bottom:10px'>" + _ostatnie_html + "</div>"
           if _ostatnie_html else "")
        + "<form method='POST' action='/produkcja/dodaj'>"
        + "<div style='display:flex;gap:8px;align-items:flex-end'>"
        + "<div style='flex:1'><label>Szt. jaj</label>"
        + "<input name='jaja_zebrane' type='number' min='0' value='"
        + (str(dzis["jaja_zebrane"]) if dzis else "")
        + "' style='font-size:20px;text-align:center' required></div>"
        + "<div><label>Data</label>"
        + "<input name='data' type='date' value='" + date.today().isoformat() + "' style='font-size:13px'></div>"
        + "</div>"
        + "<input type='hidden' name='pasza_wydana_kg' value='" + str(pdz) + "'>"
        + "<button class='btn bg' style='width:100%;margin-top:10px;padding:11px'>Zapisz</button>"
        + "</form></div>"
    )

    html = (
        '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">'
        '<h1 style="margin-bottom:0">Dashboard</h1>'
        '<span style="font-size:14px;color:#5f5e5a;font-weight:500">' + _data_str + '</span>'
        '</div>'
        + al_html
        + '<div class="g4" style="margin-bottom:10px">'
        '<div class="card stat"><div class="v" style="color:' + ('#A32D2D' if nies<70 else '#3B6D11') + '">' + str(nies) + '%</div><div class="l">Nieśność 7 dni</div><div class="s">' + str(kur) + ' niosek</div></div>'
        '<div class="card stat"><div class="v">' + str(mag_stan) + '</div><div class="l">Jaj w magazynie</div><div class="s">zarezerwowane: ' + str(zarez) + '</div></div>'
        '<div class="card stat"><div class="v" style="color:#3B6D11">' + str(round(zysk,0)) + ' zł</div><div class="l">Przychód miesiąc</div><div class="s">wydatki: ' + str(round(wyd,0)) + ' zł</div></div>'
        '<div class="card stat"><div class="v">' + str(round(zysk-wyd,0)) + ' zł</div><div class="l">Zysk miesiąc</div></div>'
        '</div>'
        + sterowanie_html
        + _kafelki_czynnosci(g)
        + '<div class="g2">'

        # Formularz 1: Zebrane jaja
        + _jaja_form

        # Formularz 2: Szybka sprzedaż → /sprzedaz
        + '<div class="card"><b>Sprzedaż — dziś</b>'
        + '<form method="POST" action="/sprzedaz" style="margin-top:10px">'
        + '<input type="hidden" name="data" value="' + date.today().isoformat() + '">'
        + '<label>Sprzedane (szt)</label>'
        + '<input name="jaja_sprzedane" type="number" min="0" value="0" id="sp_d" oninput="cWd()" style="font-size:18px;text-align:center">'
        + '<label>Cena/szt (zł)</label>'
        + '<input name="cena_sprzedazy" type="number" step="0.01" value="' + gs('cena_jajka','1.20') + '" id="cn_d" oninput="cWd()">'
        + '<div style="background:#f5f5f0;border-radius:6px;padding:6px 10px;font-size:13px;margin:4px 0">Wartość: <b id="wrd">0.00 zł</b></div>'
        + '<label>Klient</label>'
        + '<select name="klient_id"><option value="">— anonimowa —</option>'
        + "".join('<option value="' + str(k["id"]) + '">' + k["nazwa"] + '</option>' for k in klienci)
        + '</select>'
        + '<label>Typ płatności</label>'
        + '<select name="typ_sprzedazy"><option value="gotowka">Gotówka</option><option value="przelew">Przelew</option><option value="nastepnym_razem">Następnym razem</option><option value="z_salda">Z salda</option></select>'
        + '<br><button class="btn bp" style="width:100%;margin-top:10px;padding:11px">Zapisz sprzedaż</button>'
        + '<script>function cWd(){var s=parseFloat(document.getElementById("sp_d").value)||0,c=parseFloat(document.getElementById("cn_d").value)||0;document.getElementById("wrd").textContent=(s*c).toFixed(2)+" zł";}cWd();</script>'
        + '</form></div>'

        # Formularz 3: Pasza + Woda
        + '<div class="card" style="margin-top:4px">'
        + '<b>Pasza i woda — dziś</b>'
        + '<form method="POST" action="/dzienne/media" style="margin-top:10px">'
        + '<input type="hidden" name="data" value="' + date.today().isoformat() + '">'
        + '<div class="g2">'
        + '<div><label>Pasza dodana (kg)</label>'
        + '<input name="pasza_kg" type="number" step="0.1" min="0" placeholder="kg"></div>'
        + '<div><label>Woda dolana (litry)</label>'
        + '<input name="woda_l" type="number" step="0.5" min="0" placeholder="L"></div>'
        + '</div>'
        + '<button class="btn bo bsm" style="margin-top:8px">Zapisz mediów</button>'
        + '</form></div>'
    )
    return R(html, "dash")


# ─── PRODUKCJA ────────────────────────────────────────────────────────────────
# Produkcja i klienci przeniesione do produkcja_views.py

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

# Klienci przeniesione do produkcja_views.py

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
    prefill_nazwa = request.args.get("nazwa","")
    prefill_kat   = request.args.get("kategoria","Zboże/pasza")

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
        # Aktualizuj magazyn pasz/suplementów
        if kat in ("Zboże/pasza","Witaminy/suplementy") and naz and il > 0:
            ex = db.execute("SELECT id FROM stan_magazynu WHERE gospodarstwo_id=? AND nazwa=? AND kategoria=?", (g,naz,kat)).fetchone()
            if ex:
                db.execute("UPDATE stan_magazynu SET stan=stan+?,cena_aktualna=? WHERE id=?", (il,cj,ex["id"]))
            else:
                db.execute("INSERT INTO stan_magazynu(gospodarstwo_id,kategoria,nazwa,jednostka,stan,cena_aktualna) VALUES(?,?,?,?,?,?)",
                           (g,kat,naz,jedn,il,cj))
            # Zaktualizuj też cenę w bazie składników (PLN/T) jeśli cena znana
            if cj > 0:
                cena_t = round(cj * 1000, 2)  # zł/kg → PLN/T
                db.execute("UPDATE skladniki_baza SET cena_pln_t=? WHERE LOWER(TRIM(nazwa))=LOWER(TRIM(?))",
                           (cena_t, naz))
        db.commit(); db.close()
        flash("Wydatek zapisany" + (f" — cena {naz}: {round(cj,2)} zł/kg" if cj > 0 and naz else "") + ".")
        return redirect(request.form.get("next","/wydatki"))

    kat_opt = "".join(
        '<option value="' + k + '" ' + ('selected' if k==prefill_kat else '') + '>' + k + '</option>'
        for k in KATEGORIE)

    js = """
<script>
function calc(){
  var il=parseFloat(document.getElementById('il').value)||0,
      cj=parseFloat(document.getElementById('cj').value)||0;
  document.getElementById('tot').textContent=(il*cj).toFixed(2)+' zł';
}
var _sc=null;
function szukajN(q){
  if(q.length<2){document.getElementById('wyd-sug').style.display='none';return;}
  if(!_sc){fetch('/api/wszystkie-skladniki').then(r=>r.json()).then(d=>{_sc=d;_show(q,d);});return;}
  _show(q,_sc);
}
function _show(q,data){
  var f=data.filter(d=>d.nazwa.toLowerCase().includes(q.toLowerCase())).slice(0,8);
  var el=document.getElementById('wyd-sug');
  if(!f.length){el.style.display='none';return;}
  el.innerHTML=f.map(function(d){
    return '<div style="padding:8px 12px;cursor:pointer;border-bottom:1px solid #f0ede4" onclick="wybN(this)" '
      +'data-nazwa="'+d.nazwa+'" data-kat="'+d.kategoria+'" data-cena="'+d.cena+'">'
      +'<b>'+d.nazwa+'</b>'
      +'<span style="color:#888;font-size:12px;margin-left:6px">('+d.kategoria+')</span>'
      +(d.cena>0?'<span style="float:right;color:#534AB7">'+d.cena+' zł/kg</span>':'')
      +'</div>';
  }).join('');
  el.style.display='block';
}
function wybN(el){
  var nazwa=el.dataset.nazwa, kat=el.dataset.kat, cena=parseFloat(el.dataset.cena)||0;
  document.getElementById('wyd-n').value=nazwa;
  document.getElementById('wyd-sug').style.display='none';
  var sel=document.getElementById('kat-sel');
  if(kat==='zboze'||kat==='bialkowe') sel.value='Zboże/pasza';
  else if(['premiks','mineralne','naturalny_dodatek'].includes(kat)) sel.value='Witaminy/suplementy';
  if(cena>0){document.getElementById('cj').value=cena;calc();}
  fetch('/api/skladnik-info?nazwa='+encodeURIComponent(nazwa))
    .then(r=>r.json()).then(function(info){
      var ib=document.getElementById('info-box');
      if(info.info){ib.textContent=info.info;ib.style.display='block';}
      else{ib.style.display='none';}
    });
}
document.addEventListener('click',function(e){
  if(!e.target.closest('#wyd-sug')&&!e.target.closest('#wyd-n'))
    document.getElementById('wyd-sug').style.display='none';
});
</script>"""

    html = (
        '<h1>Dodaj wydatek</h1>'
        '<div class="card"><form method="POST">'
        '<input type="hidden" name="next" value="' + request.args.get("next","/wydatki") + '">'
        '<div class="g2">'
        '<div><label>Data</label><input name="data" type="date" value="' + date.today().isoformat() + '"></div>'
        '<div><label>Kategoria</label><select name="kategoria" id="kat-sel">' + kat_opt + '</select></div>'
        '</div>'
        '<label>Nazwa składnika / produktu</label>'
        '<div style="position:relative">'
        '<input name="nazwa" id="wyd-n" required autocomplete="off"'
        ' value="' + prefill_nazwa + '"'
        ' placeholder="Zacznij pisać: Pszenica, Kukurydza, Dolmix..."'
        ' oninput="szukajN(this.value)">'
        '<div id="wyd-sug" style="display:none;position:absolute;top:100%;left:0;right:0;'
        'background:#fff;border:1px solid #d3d1c7;border-radius:0 0 8px 8px;'
        'z-index:100;max-height:220px;overflow-y:auto;box-shadow:0 4px 12px rgba(0,0,0,.1)">'
        '</div></div>'
        '<div id="info-box" style="display:none;background:#EEEDFE;border-radius:6px;'
        'padding:6px 12px;font-size:12px;color:#3C3489;margin-top:4px"></div>'
        '<div class="g3" style="margin-top:8px">'
        '<div><label>Ilość</label><input name="ilosc" type="number" step="0.01" id="il" oninput="calc()"></div>'
        '<div><label>Jednostka</label><select name="jednostka">'
        '<option value="kg">kg</option><option value="szt">szt</option>'
        '<option value="l">l</option><option value="op">opak.</option>'
        '</select></div>'
        '<div><label>Cena/jedn. (zł)</label><input name="cena_jednostkowa" type="number" step="0.01" id="cj" oninput="calc()"></div>'
        '</div>'
        '<div style="background:#f5f5f0;border-radius:8px;padding:10px;margin-top:8px;font-size:14px">'
        'Łącznie: <b id="tot">0.00 zł</b></div>'
        '<div class="g2">'
        '<div><label>Dostawca</label><input name="dostawca"></div>'
        '<div><label>Uwagi</label><input name="uwagi"></div>'
        '</div>'
        '<br><button class="btn bp">Zapisz wydatek</button>'
        '<a href="/wydatki" class="btn bo" style="margin-left:8px">Anuluj</a>'
        '</form></div>'
        + js
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
    g = gid(); db = get_db()
    skladniki = db.execute("SELECT * FROM stan_magazynu WHERE gospodarstwo_id=? AND kategoria IN ('Zboże/pasza','Witaminy/suplementy') ORDER BY nazwa", (g,)).fetchall()
    mieszania = db.execute("SELECT m.*,r.nazwa as rn FROM mieszania m LEFT JOIN receptura r ON m.receptura_id=r.id WHERE m.gospodarstwo_id=? ORDER BY m.data DESC LIMIT 30", (g,)).fetchall()
    db.close()
    w_skl = ""
    for s in skladniki:
        niski = s["stan"] < (s["min_zapas"] or 0) and (s["min_zapas"] or 0) > 0
        kol = "#A32D2D" if niski else "#2c2c2a"
        alert = " ⚠️" if niski else ""
        w_skl += (
            "<tr>"
            "<td style='font-weight:500'>" + s["nazwa"] + alert + "</td>"
            "<td style='font-weight:600;color:" + kol + "'>" + str(round(s["stan"],1)) + " " + s["jednostka"] + "</td>"
            "<td style='color:#888'>" + str(round(s["cena_aktualna"],2)) + " zł/kg</td>"
            "<td class='nowrap'>"
            "<a href='/magazyn/korekta/" + str(s["id"]) + "' class='btn bo bsm'>Korekta</a> "
            "<a href='/wydatki/dodaj?nazwa=" + s["nazwa"] + "&kategoria=" + s["kategoria"] + "&next=/pasza' class='btn bp bsm'>+ Zakup</a>"
            "</td></tr>"
        )
    w_mies = ""
    for m in mieszania:
        w_mies += (
            "<tr>"
            "<td style='font-size:12px;color:#888'>" + m["data"][:10] + "</td>"
            "<td>" + (m["rn"] or "—") + "</td>"
            "<td style='font-weight:600'>" + str(round(m["ilosc_kg"],1)) + " kg</td>"
            "<td style='color:#888;font-size:11px'>" + (m["uwagi"] or "") + "</td>"
            "<td class='nowrap'>"
            "<a href='/pasza/mieszanie/" + str(m["id"]) + "/edytuj' class='btn bo bsm'>Edytuj</a> "
            "<a href='/pasza/mieszanie/" + str(m["id"]) + "/usun' class='btn br bsm' onclick=\"return confirm('Usunąć? Składniki wrócą do magazynu.')\">✕</a>"
            "</td></tr>"
        )
    html = (
        "<h1>Pasza</h1>"
        "<div style='display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap'>"
        "<a href='/pasza/mieszaj' class='btn bp bsm'>+ Zarejestruj mieszanie</a>"
        "<a href='/pasza/mieszalnik' class='btn bg bsm'>⚗️ Mieszalnik</a>"
        "<a href='/pasza/receptury' class='btn bo bsm'>Receptury</a>"
        "<a href='/pasza/analityka' class='btn bo bsm'>Analityka</a>"
        "</div>"
        "<div class='g2'>"
        "<div class='card'><b>Składniki w magazynie</b>"
        "<div style='overflow-x:auto'><table style='margin-top:8px'><thead><tr>"
        "<th>Składnik</th><th>Stan</th><th>Cena/kg</th><th></th>"
        "</tr></thead>"
        "<tbody>" + (w_skl or "<tr><td colspan=4 style='color:#888;padding:12px'>Brak — dodaj przez Wydatki → Zboże/pasza</td></tr>") + "</tbody>"
        "</table></div>"
        "<a href='/wydatki/dodaj?kategoria=Zboże%2Fpasza&next=/pasza' class='btn bo bsm' style='display:inline-block;margin-top:10px'>+ Dodaj zakup składnika</a>"
        "</div>"
        "<div class='card'><b>Historia mieszań</b>"
        "<div style='overflow-x:auto'><table style='margin-top:8px'><thead><tr>"
        "<th>Data</th><th>Receptura</th><th>Ilość</th><th>Uwagi</th><th></th>"
        "</tr></thead>"
        "<tbody>" + (w_mies or "<tr><td colspan=5 style='color:#888;padding:12px'>Brak historii</td></tr>") + "</tbody>"
        "</table></div></div>"
        "</div>"
    )
    return R(html, "pasza")


@app.route("/magazyn/korekta/<int:sid>", methods=["GET","POST"])
@farm_required
def magazyn_korekta(sid):
    g = gid(); db = get_db()
    s = db.execute("SELECT * FROM stan_magazynu WHERE id=? AND gospodarstwo_id=?", (sid, g)).fetchone()
    if not s: db.close(); return redirect("/pasza")
    if request.method == "POST":
        nowy = float(request.form.get("stan", s["stan"]) or 0)
        cena = float(request.form.get("cena", s["cena_aktualna"]) or 0)
        roznica = nowy - float(s["stan"] or 0)
        db.execute("UPDATE stan_magazynu SET stan=?,cena_aktualna=? WHERE id=?", (nowy, cena, sid))
        if abs(roznica) > 0.01:
            db.execute("INSERT INTO wydatki(gospodarstwo_id,data,kategoria,nazwa,ilosc,jednostka,cena_jednostkowa,wartosc_total,uwagi) VALUES(?,?,?,?,?,?,?,?,?)",
                (g, date.today().isoformat(), s["kategoria"], s["nazwa"],
                 abs(roznica), s["jednostka"], cena, abs(roznica)*cena,
                 request.form.get("powod","korekta")))
        db.commit(); db.close()
        flash("Korekta zapisana: " + s["nazwa"] + " → " + str(nowy) + " " + s["jednostka"])
        return redirect("/pasza")
    db.close()
    html = (
        "<h1>Korekta stanu: " + s["nazwa"] + "</h1>"
        "<div class='card'><form method='POST'>"
        "<div class='al alw'>Aktualny stan w systemie: <b>" + str(round(float(s["stan"]),1)) + " " + s["jednostka"] + "</b><br>"
        "Wpisz stan rzeczywisty po przeliczeniu. Różnica zostanie zapisana w wydatkach.</div>"
        "<div class='g2' style='margin-top:12px'>"
        "<div><label>Stan rzeczywisty (" + s["jednostka"] + ")</label>"
        "<input name='stan' type='number' step='0.1' value='" + str(round(float(s["stan"]),1)) + "' required style='font-size:22px;text-align:center'></div>"
        "<div><label>Cena aktualna (zł/kg)</label>"
        "<input name='cena' type='number' step='0.01' value='" + str(round(float(s["cena_aktualna"]),2)) + "'></div>"
        "</div>"
        "<label style='margin-top:10px'>Powód korekty</label>"
        "<select name='powod'>"
        "<option value='inwentaryzacja'>Inwentaryzacja — przeliczenie ręczne</option>"
        "<option value='ubytki naturalne'>Ubytki naturalne (wilgoć, rozsyp)</option>"
        "<option value='korekta pomyłki'>Korekta wcześniejszej pomyłki</option>"
        "<option value='dosypanie bez paragonu'>Dosypanie bez paragonu</option>"
        "</select>"
        "<br><button class='btn bp' style='margin-top:12px;width:100%;padding:12px'>Zapisz korektę</button>"
        "<a href='/pasza' class='btn bo' style='display:block;text-align:center;margin-top:8px'>Anuluj</a>"
        "</form></div>"
    )
    return R(html, "pasza")


@app.route("/pasza/mieszanie/<int:mid>/edytuj", methods=["GET","POST"])
@farm_required
def pasza_mieszanie_edytuj(mid):
    g = gid(); db = get_db()
    m = db.execute("SELECT * FROM mieszania WHERE id=? AND gospodarstwo_id=?", (mid, g)).fetchone()
    if not m: db.close(); return redirect("/pasza")
    recs = db.execute("SELECT * FROM receptura WHERE gospodarstwo_id=? ORDER BY aktywna DESC,nazwa", (g,)).fetchall()
    if request.method == "POST":
        nowa = float(request.form.get("ilosc_kg", m["ilosc_kg"]) or 0)
        stara = float(m["ilosc_kg"] or 0)
        roznica = nowa - stara
        rid = request.form.get("receptura_id") or m["receptura_id"]
        if abs(roznica) > 0.01 and rid:
            for s in db.execute("SELECT * FROM receptura_skladnik WHERE receptura_id=?", (rid,)).fetchall():
                korekta = roznica * float(s["procent"]) / 100
                db.execute("UPDATE stan_magazynu SET stan=MAX(0,stan-?) WHERE id=? AND gospodarstwo_id=?",
                           (korekta, s["magazyn_id"], g))
        db.execute("UPDATE mieszania SET receptura_id=?,ilosc_kg=?,uwagi=? WHERE id=? AND gospodarstwo_id=?",
                   (rid, nowa, request.form.get("uwagi",""), mid, g))
        db.commit(); db.close()
        diff_str = (", korekta magazynu: " + ("+" if roznica>0 else "") + str(round(roznica,1)) + " kg") if abs(roznica)>0.01 else ""
        flash("Mieszanie zaktualizowane" + diff_str + ".")
        return redirect("/pasza")
    opt = "".join(
        "<option value='" + str(r["id"]) + "' " + ("selected" if r["id"]==m["receptura_id"] else "") + ">"
        + ("✓ " if r["aktywna"] else "") + r["nazwa"] + "</option>"
        for r in recs)
    db.close()
    html = (
        "<h1>Edytuj mieszanie</h1>"
        "<div class='card'><form method='POST'>"
        "<div class='al alw'>Zmiana ilości automatycznie koryguje stan magazynu o różnicę.</div>"
        "<label style='margin-top:12px'>Data</label>"
        "<input value='" + m["data"][:10] + "' disabled style='color:#888;background:#f5f5f0'>"
        "<label>Receptura</label><select name='receptura_id'>" + opt + "</select>"
        "<label>Ilość paszy (kg)</label>"
        "<input name='ilosc_kg' type='number' step='0.5' value='" + str(round(float(m["ilosc_kg"]),1)) + "' required style='font-size:22px;text-align:center'>"
        "<label>Uwagi</label><input name='uwagi' value='" + (m["uwagi"] or "") + "'>"
        "<br><button class='btn bp' style='margin-top:12px;width:100%;padding:12px'>Zapisz zmiany</button>"
        "<a href='/pasza' class='btn bo' style='display:block;text-align:center;margin-top:8px'>Anuluj</a>"
        "</form></div>"
    )
    return R(html, "pasza")


@app.route("/pasza/mieszanie/<int:mid>/usun")
@farm_required
def pasza_mieszanie_usun(mid):
    g = gid(); db = get_db()
    m = db.execute("SELECT * FROM mieszania WHERE id=? AND gospodarstwo_id=?", (mid, g)).fetchone()
    if m:
        if m["receptura_id"]:
            for s in db.execute("SELECT * FROM receptura_skladnik WHERE receptura_id=?", (m["receptura_id"],)).fetchall():
                zwrot = float(m["ilosc_kg"] or 0) * float(s["procent"]) / 100
                db.execute("UPDATE stan_magazynu SET stan=stan+? WHERE id=? AND gospodarstwo_id=?",
                           (zwrot, s["magazyn_id"], g))
        db.execute("DELETE FROM mieszania WHERE id=?", (mid,))
        db.commit()
        flash("Mieszanie usunięto — składniki zwrócono do magazynu.")
    db.close(); return redirect("/pasza")


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
    g = gid(); db = get_db()
    recs = db.execute(
        "SELECT r.*, COUNT(rs.id) as n_skl, ROUND(SUM(rs.procent)*100,1) as suma_pct "
        "FROM receptura r LEFT JOIN receptura_skladnik rs ON rs.receptura_id=r.id "
        "WHERE r.gospodarstwo_id=? GROUP BY r.id ORDER BY r.aktywna DESC, r.nazwa", (g,)).fetchall()
    db.close()
    SEZON = {"caly_rok":"Cały rok","lato":"Lato","zima":"Zima","wiosna":"Wiosna","jesien":"Jesień"}
    cards = ""
    for r in recs:
        sezon = SEZON.get(r["sezon"] or "caly_rok", "Cały rok")
        sp = r["suma_pct"] or 0
        pc = "#3B6D11" if 98<=sp<=102 else "#A32D2D"
        rid2 = r["id"]
        cards += (
            "<div class='card' style='margin-bottom:10px;border-left:4px solid "
            + ("#3B6D11" if r["aktywna"] else "#e0ddd4") + "'>"
            "<div style='display:flex;align-items:center;gap:10px;flex-wrap:wrap'>"
            "<div style='flex:1'>"
            "<div style='display:flex;align-items:center;gap:8px'>"
            "<b style='font-size:16px'>" + r["nazwa"] + "</b>"
            + (" <span class='badge b-green'>✓ Aktywna</span>" if r["aktywna"] else "") + "</div>"
            "<div style='font-size:12px;color:#888;margin-top:3px'>"
            + sezon + " · " + str(r["n_skl"]) + " składn. · "
            "<span style='color:" + pc + ";font-weight:500'>suma: " + str(sp) + "%</span>"
            + "</div></div>"
            "<div style='display:flex;gap:6px;flex-wrap:wrap'>"
            "<a href='/pasza/receptura/" + str(rid2) + "/podglad' class='btn bo bsm'>👁 Podgląd</a>"
            "<a href='/pasza/receptura/" + str(rid2) + "/edytuj' class='btn bo bsm'>✏️ Edytuj</a>"
            + ("" if r["aktywna"] else "<a href='/pasza/receptura/" + str(rid2) + "/aktywuj' class='btn bg bsm'>Aktywuj</a>")
            + "<a href='/pasza/receptura/" + str(rid2) + "/duplikuj' class='btn bo bsm'>Duplikuj</a>"
            + "<a href='/pasza/receptura/" + str(rid2) + "/usun' class='btn br bsm' onclick=\"return confirm('Usunąć?')\">✕</a>"
            + "</div></div></div>"
        )
    html = (
        "<h1>Receptury paszy</h1>"
        "<div style='display:flex;gap:8px;margin-bottom:14px;flex-wrap:wrap'>"
        "<a href='/pasza/receptura/dodaj' class='btn bp bsm'>+ Nowa receptura</a>"
        "<a href='/pasza/analityka' class='btn bo bsm'>Analityka</a>"
        "<a href='/pasza/skladniki-roczne' class='btn bo bsm'>Zapotrzebowanie roczne</a>"
        "</div>"
        + (cards or "<div class='card'><p style='color:#888;text-align:center;padding:20px'>Brak receptur.</p></div>")
    )
    return R(html, "pasza")


@app.route("/pasza/receptura/<int:rid>/podglad")
@farm_required
def pasza_receptura_podglad(rid):
    g = gid(); db = get_db()
    r = db.execute("SELECT * FROM receptura WHERE id=? AND gospodarstwo_id=?", (rid,g)).fetchone()
    if not r: db.close(); return redirect("/pasza/receptury")
    sklady = db.execute(
        "SELECT rs.procent, sm.nazwa, sm.stan, "
        "COALESCE(sb.bialko_pct,0) as bialko, COALESCE(sb.cena_pln_t,0) as cena_t "
        "FROM receptura_skladnik rs JOIN stan_magazynu sm ON rs.magazyn_id=sm.id "
        "LEFT JOIN skladniki_baza sb ON LOWER(TRIM(sb.nazwa))=LOWER(TRIM(sm.nazwa)) "
        "WHERE rs.receptura_id=? ORDER BY rs.procent DESC", (rid,)).fetchall()
    mies = db.execute(
        "SELECT data,ilosc_kg FROM mieszania WHERE receptura_id=? AND gospodarstwo_id=? "
        "ORDER BY data DESC LIMIT 5", (rid,g)).fetchall()
    db.close()
    suma = sum(float(s["procent"] or 0) for s in sklady)
    koszt_t = sum(float(s["cena_t"] or 0)*float(s["procent"] or 0) for s in sklady)
    SEZON = {"caly_rok":"Cały rok","lato":"Lato","zima":"Zima","wiosna":"Wiosna","jesien":"Jesień"}
    sc = "#3B6D11" if 0.98<=suma<=1.02 else "#A32D2D"
    rows = ""
    for s in sklady:
        p = float(s["procent"] or 0)
        bw = min(100, round(p*100, 0))
        rows += (
            "<tr>"
            "<td><b>" + s["nazwa"] + "</b><br>"
            "<div style='width:120px;background:#e0ddd4;border-radius:3px;height:6px;margin-top:3px'>"
            "<div style='width:" + str(int(bw)) + "%;background:#534AB7;height:100%;border-radius:3px'></div></div></td>"
            "<td style='text-align:right;font-weight:700;font-size:15px'>" + str(round(p*100,1)) + "%</td>"
            "<td style='text-align:right'>" + str(round(50*p,2)) + " kg</td>"
            "<td style='text-align:right'>" + str(round(100*p,2)) + " kg</td>"
            "<td style='text-align:right;color:#888'>" + str(round(float(s["stan"] or 0),1)) + " kg</td>"
            "<td style='text-align:right;font-size:12px'>"
            + (str(round(s["bialko"]*p,2)) + "%" if s["bialko"] else "—") + "</td></tr>"
        )
    mies_html = "".join(
        "<div style='display:flex;justify-content:space-between;padding:4px 0;font-size:13px;"
        "border-bottom:1px solid #f0ede4'><span style='color:#888'>" + m["data"][:10]
        + "</span><b>" + str(round(m["ilosc_kg"],1)) + " kg</b></div>"
        for m in mies)
    import json as _j
    skl_js = _j.dumps([{"n":s["nazwa"],"p":float(s["procent"] or 0)} for s in sklady])
    html = (
        "<div style='display:flex;align-items:center;gap:10px;margin-bottom:12px;flex-wrap:wrap'>"
        "<h1 style='margin-bottom:0'>" + r["nazwa"] + "</h1>"
        + (" <span class='badge b-green'>✓ Aktywna</span>" if r["aktywna"] else "")
        + "<div style='margin-left:auto;display:flex;gap:6px;flex-wrap:wrap'>"
        "<a href='/pasza/receptura/" + str(rid) + "/edytuj' class='btn bp bsm'>✏️ Edytuj</a>"
        "<a href='/pasza/receptura/" + str(rid) + "/aktywuj' class='btn bg bsm'>Aktywuj</a>"
        "<a href='/pasza/mieszalnik?rid=" + str(rid) + "' class='btn bo bsm'>⚗️ Mieszaj</a>"
        "<a href='/pasza/receptury' class='btn bo bsm'>← Lista</a>"
        "</div></div>"
        "<div class='g2'>"
        "<div>"
        "<div class='card'>"
        "<div style='display:flex;justify-content:space-between;margin-bottom:10px'>"
        "<b>Składniki receptury</b>"
        "<span style='color:" + sc + ";font-weight:600'>suma: " + str(round(suma*100,1)) + "%</span></div>"
        "<div style='overflow-x:auto'><table style='font-size:13px'><thead><tr>"
        "<th>Składnik</th><th style='text-align:right'>Udział</th>"
        "<th style='text-align:right'>na 50 kg</th><th style='text-align:right'>na 100 kg</th>"
        "<th style='text-align:right'>Magazyn</th><th style='text-align:right'>Białko wkł.</th>"
        "</tr></thead><tbody>" + rows + "</tbody>"
        "<tfoot><tr style='border-top:2px solid #e0ddd4;font-weight:700'>"
        "<td>SUMA</td>"
        "<td style='text-align:right;color:" + sc + "'>" + str(round(suma*100,1)) + "%</td>"
        "<td style='text-align:right'>" + str(round(50*suma,1)) + " kg</td>"
        "<td style='text-align:right'>" + str(round(100*suma,1)) + " kg</td>"
        "<td colspan=2></td></tr></tfoot></table></div></div>"
        "<div class='card' style='margin-top:0'>"
        "<b>Kalkulator partii</b>"
        "<label style='margin-top:10px'>Ile kg chcę zmieszać?</label>"
        "<input type='number' id='ckg' value='50' step='5' min='5' oninput='cP(this.value)' style='font-size:22px;text-align:center'>"
        "<div id='cr' style='margin-top:10px;font-size:13px'></div>"
        "<a href='/pasza/mieszalnik?rid=" + str(rid) + "' class='btn bg bsm' style='margin-top:10px;display:block;text-align:center'>⚗️ Otwórz mieszalnik</a>"
        "</div></div>"
        "<div>"
        "<div class='card'><b>Informacje</b><div style='margin-top:8px;font-size:13px'>"
        "<div style='padding:4px 0;border-bottom:1px solid #f0ede4'><span style='color:#888'>Sezon:</span> <b>"
        + SEZON.get(r["sezon"] or "caly_rok","Cały rok") + "</b></div>"
        "<div style='padding:4px 0;border-bottom:1px solid #f0ede4'><span style='color:#888'>Składniki:</span> <b>"
        + str(len(sklady)) + "</b></div>"
        "<div style='padding:4px 0;border-bottom:1px solid #f0ede4'><span style='color:#888'>Koszt PLN/T:</span> <b>"
        + str(round(koszt_t,0)) + "</b></div>"
        "<div style='padding:4px 0'><span style='color:#888'>Koszt 100 kg:</span> <b>"
        + str(round(koszt_t/10,0)) + " PLN</b></div></div>"
        "<a href='/pasza/receptura/" + str(rid) + "/sezon-form' class='btn bo bsm' style='margin-top:10px'>Zmień sezon</a>"
        "</div>"
        + ("<div class='card' style='margin-top:0'><b>Ostatnie mieszania</b><div style='margin-top:8px'>" + mies_html + "</div></div>" if mies else "")
        + "<div class='card' style='margin-top:0'><b>Analityka odżywcza</b>"
        "<p style='font-size:12px;color:#888;margin:6px 0'>Białko, Ca, energia vs normy.</p>"
        "<a href='/pasza/analityka?rid=" + str(rid) + "' class='btn bp bsm'>Otwórz →</a></div>"
        "</div></div>"
        "<script>var _sk=" + skl_js + ";"
        "function cP(kg){kg=parseFloat(kg)||0;"
        "var h='';_sk.forEach(function(s){h+='<tr><td>'+s.n+'</td><td style=\"text-align:right;font-weight:600\">'+(Math.round(kg*s.p*100)/100)+' kg</td></tr>';});"
        "document.getElementById('cr').innerHTML='<table style=\"width:100%;font-size:12px\">'+h+'</table>';}"
        "cP(50);</script>"
    )
    return R(html, "pasza")


@app.route("/pasza/receptura/dodaj", methods=["GET","POST"])
@app.route("/pasza/receptura/<int:rid>/edytuj", methods=["GET","POST"])
@farm_required
def pasza_receptura_form(rid=None):
    g = gid(); db = get_db()
    mag_skl = db.execute("SELECT id,nazwa,stan FROM stan_magazynu WHERE gospodarstwo_id=? ORDER BY nazwa", (g,)).fetchall()
    if request.method == "POST":
        nazwa = request.form.get("nazwa","").strip()
        sezon = request.form.get("sezon","caly_rok")
        if not nazwa:
            flash("Podaj nazwę receptury."); db.close(); return redirect(request.url)
        if rid:
            db.execute("UPDATE receptura SET nazwa=?,sezon=? WHERE id=? AND gospodarstwo_id=?", (nazwa,sezon,rid,g))
            db.execute("DELETE FROM receptura_skladnik WHERE receptura_id=?", (rid,))
        else:
            rid = db.execute("INSERT INTO receptura(gospodarstwo_id,nazwa,sezon,aktywna) VALUES(?,?,?,0)", (g,nazwa,sezon)).lastrowid
        mag_ids  = request.form.getlist("mag_id")
        procenty = request.form.getlist("procent")
        nowe_n   = request.form.getlist("nowa_nazwa") + [""]*len(mag_ids)
        for mv, pv, nn in zip(mag_ids, procenty, nowe_n):
            pct = float(pv or 0)
            if pct <= 0: continue
            if mv:
                db.execute("INSERT INTO receptura_skladnik(receptura_id,magazyn_id,procent) VALUES(?,?,?)", (rid,int(mv),pct))
            elif nn.strip():
                ex = db.execute("SELECT id FROM stan_magazynu WHERE gospodarstwo_id=? AND LOWER(nazwa)=LOWER(?)", (g,nn.strip())).fetchone()
                mid2 = ex["id"] if ex else db.execute("INSERT INTO stan_magazynu(gospodarstwo_id,kategoria,nazwa,jednostka,stan) VALUES(?,?,?,?,0)", (g,"Zboże/pasza",nn.strip(),"kg")).lastrowid
                db.execute("INSERT INTO receptura_skladnik(receptura_id,magazyn_id,procent) VALUES(?,?,?)", (rid,mid2,pct))
        db.commit(); db.close()
        flash("Receptura zapisana.")
        return redirect("/pasza/receptura/"+str(rid)+"/podglad")
    rec = None; existing = []
    if rid:
        rec = db.execute("SELECT * FROM receptura WHERE id=? AND gospodarstwo_id=?", (rid,g)).fetchone()
        if not rec: db.close(); return redirect("/pasza/receptury")
        existing = db.execute(
            "SELECT rs.procent,rs.magazyn_id,sm.nazwa FROM receptura_skladnik rs "
            "JOIN stan_magazynu sm ON rs.magazyn_id=sm.id WHERE rs.receptura_id=? ORDER BY rs.procent DESC", (rid,)).fetchall()
    db.close()
    SEZONY = [("caly_rok","🗓 Cały rok"),("wiosna","🌱 Wiosna"),("lato","☀️ Lato"),("jesien","🍂 Jesień"),("zima","❄️ Zima")]
    sc = (rec["sezon"] if rec else "caly_rok") or "caly_rok"
    sezon_opts = "".join("<option value='"+v+"' "+("selected" if sc==v else "")+">"+l+"</option>" for v,l in SEZONY)
    def _row(mag_id="", proc=0):
        p100 = round(float(proc)*100, 1) if proc else 0
        bw = min(100, round(float(proc or 0)*100, 0))
        opts = "".join("<option value='"+str(s["id"])+"' "+("selected" if str(s["id"])==str(mag_id) else "")+">"+s["nazwa"]+"</option>" for s in mag_skl)
        return (
            "<tr class='sr'>"
            "<td style='padding:4px'>"
            "<select name='mag_id' style='width:100%;margin-bottom:4px'><option value=''>— wybierz —</option>"+opts+"</select>"
            "<input name='nowa_nazwa' placeholder='lub wpisz ręcznie' style='width:100%;font-size:12px;color:#888'>"
            "</td>"
            "<td style='padding:4px'>"
            "<div style='display:flex;align-items:center;gap:6px'>"
            "<input name='procent' type='number' step='0.001' min='0' max='1' value='"+str(proc)+"' oninput='upd()' style='width:90px;text-align:right;font-size:16px'>"
            "<span style='font-size:13px;color:#888'>= <span class='pd'>"+str(p100)+"</span>%</span>"
            "</div></td>"
            "<td style='padding:4px;width:90px'>"
            "<div style='background:#e0ddd4;border-radius:4px;height:10px;width:80px'>"
            "<div class='pb' style='width:"+str(int(bw))+"%;background:#534AB7;height:100%;border-radius:4px'></div></div>"
            "</td>"
            "<td style='padding:4px'><button type='button' onclick=\"this.closest('tr').remove();upd()\" class='btn br bsm'>✕</button></td>"
            "</tr>"
        )
    rows_html = "".join(_row(s["magazyn_id"], s["procent"]) for s in existing)
    for _ in range(max(3, 5-len(existing))): rows_html += _row()
    # Pusty wiersz do addRow - zbuduj opcje
    empty_opts = "".join("<option value='"+str(s["id"])+"'>"+s["nazwa"]+"</option>" for s in mag_skl)
    html = (
        "<h1>"+("Edytuj: "+rec["nazwa"] if rec else "Nowa receptura")+"</h1>"
        "<div class='card'><form method='POST'>"
        "<div class='g2'>"
        "<div><label>Nazwa receptury</label>"
        "<input name='nazwa' required value='"+((rec["nazwa"] if rec else "") or "")+"' style='font-size:16px'></div>"
        "<div><label>Sezon stosowania</label><select name='sezon'>"+sezon_opts+"</select></div>"
        "</div>"
        "<div style='display:flex;justify-content:space-between;align-items:center;margin:16px 0 8px'>"
        "<h2 style='margin:0'>Składniki receptury</h2>"
        "<div style='display:flex;align-items:center;gap:10px'>"
        "Suma: <b id='sv' style='font-size:20px;color:#888'>0%</b>"
        "<button type='button' onclick='addR()' class='btn bo bsm'>+ Dodaj wiersz</button>"
        "</div></div>"
        "<div style='background:#EEEDFE;border-radius:8px;padding:8px 12px;font-size:12px;color:#3C3489;margin-bottom:8px'>"
        "Podaj udział jako ułamek dziesiętny: <b>0.55</b> = 55%, <b>0.09</b> = 9%, <b>0.005</b> = 0.5%</div>"
        "<div style='overflow-x:auto'><table style='width:100%;border-collapse:collapse'>"
        "<thead><tr><th>Składnik</th><th>Udział (0–1)</th><th>Udział %</th><th></th></tr></thead>"
        "<tbody id='sb'>"+rows_html+"</tbody></table></div>"
        "<div style='margin-top:12px;padding:12px;background:#f5f5f0;border-radius:8px;font-size:15px'>"
        "Suma: <b id='sbig' style='font-size:22px'>0</b>% <span id='si' style='font-size:13px'></span></div>"
        "<br><button class='btn bp' style='width:100%;padding:14px;font-size:16px'>💾 Zapisz recepturę</button>"
        "<a href='"+("/pasza/receptura/"+str(rid)+"/podglad" if rid else "/pasza/receptury")+"' class='btn bo' style='display:block;text-align:center;margin-top:8px'>Anuluj</a>"
        "</form></div>"
        "<script>"
        "function upd(){"
        "  var ii=document.querySelectorAll('#sb [name=procent]'),s=0;"
        "  ii.forEach(function(i){var v=parseFloat(i.value)||0;s+=v;"
        "    var t=i.closest('tr');"
        "    var pd=t.querySelector('.pd');if(pd)pd.textContent=Math.round(v*1000)/10;"
        "    var pb=t.querySelector('.pb');if(pb)pb.style.width=Math.min(100,v*100)+'%';});"
        "  var p=Math.round(s*1000)/10;"
        "  var sv=document.getElementById('sv');sv.textContent=p+'%';sv.style.color=p>=98&&p<=102?'#3B6D11':'#A32D2D';"
        "  document.getElementById('sbig').textContent=p;"
        "  var si=document.getElementById('si');"
        "  si.textContent=p<98||p>102?'⚠ powinna wynosić 100%':'✓ OK';"
        "  si.style.color=p<98||p>102?'#A32D2D':'#3B6D11';}"
        "function addR(){"
        "  var tr=document.createElement('tr');tr.className='sr';"
        "  var oo='<option value=\"\">— wybierz —</option>"
        + empty_opts.replace("'", "\\'") +
        "';"
        "  tr.innerHTML='<td style=\"padding:4px\"><select name=\"mag_id\" style=\"width:100%;margin-bottom:4px\">'+oo+'</select>"
        "<input name=\"nowa_nazwa\" placeholder=\"lub wpisz ręcznie\" style=\"width:100%;font-size:12px;color:#888\"></td>"
        "<td style=\"padding:4px\"><div style=\"display:flex;align-items:center;gap:6px\">"
        "<input name=\"procent\" type=\"number\" step=\"0.001\" min=\"0\" max=\"1\" oninput=\"upd()\" style=\"width:90px;text-align:right;font-size:16px\">"
        "<span style=\"font-size:13px;color:#888\">= <span class=\"pd\">0</span>%</span></div></td>"
        "<td style=\"padding:4px\"><div style=\"background:#e0ddd4;border-radius:4px;height:10px;width:80px\">"
        "<div class=\"pb\" style=\"width:0%;background:#534AB7;height:100%;border-radius:4px\"></div></div></td>"
        "<td style=\"padding:4px\"><button type=\"button\" onclick=\"this.closest(' + \"'tr'\" + ').remove();upd()\" class=\"btn br bsm\">✕</button></td>';"
        "  document.getElementById('sb').appendChild(tr);}"
        "upd();</script>"
    )
    return R(html, "pasza")


@app.route("/pasza/receptura/<int:rid>/aktywuj")
@farm_required
def pasza_receptura_aktywuj(rid):
    g = gid(); db = get_db()
    db.execute("UPDATE receptura SET aktywna=0 WHERE gospodarstwo_id=?", (g,))
    db.execute("UPDATE receptura SET aktywna=1 WHERE id=? AND gospodarstwo_id=?", (rid,g))
    db.commit(); db.close(); flash("Receptura aktywowana.")
    return redirect("/pasza/receptury")


@app.route("/pasza/receptura/<int:rid>/duplikuj")
@farm_required
def pasza_receptura_duplikuj(rid):
    g = gid(); db = get_db()
    r = db.execute("SELECT * FROM receptura WHERE id=? AND gospodarstwo_id=?", (rid,g)).fetchone()
    if not r: db.close(); return redirect("/pasza/receptury")
    nid = db.execute("INSERT INTO receptura(gospodarstwo_id,nazwa,sezon,aktywna) VALUES(?,?,?,0)",
                     (g, r["nazwa"]+" (kopia)", r["sezon"])).lastrowid
    for s in db.execute("SELECT * FROM receptura_skladnik WHERE receptura_id=?", (rid,)).fetchall():
        db.execute("INSERT INTO receptura_skladnik(receptura_id,magazyn_id,procent) VALUES(?,?,?)", (nid,s["magazyn_id"],s["procent"]))
    db.commit(); db.close(); flash("Receptura zduplikowana.")
    return redirect("/pasza/receptura/"+str(nid)+"/edytuj")


@app.route("/pasza/receptura/<int:rid>/usun")
@farm_required
def pasza_receptura_usun(rid):
    g = gid(); db = get_db()
    r = db.execute("SELECT aktywna FROM receptura WHERE id=? AND gospodarstwo_id=?", (rid,g)).fetchone()
    if r and r["aktywna"]:
        flash("Nie można usunąć aktywnej receptury."); db.close(); return redirect("/pasza/receptury")
    db.execute("DELETE FROM receptura WHERE id=? AND gospodarstwo_id=?", (rid,g))
    db.commit(); db.close(); flash("Receptura usunięta.")
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
        'fetch("/sterowanie/cmd",{method:"POST",'
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
        '<td><span class="badge ' + ('b-green' if f["aktywne"] else 'b-gray') + '">' + ('aktywna' if f["aktywne"] else 'nieaktywna') + '</span></td>'
        '<td class="nowrap">'
        '<form method="POST" action="/admin/farm/' + str(f["id"]) + '/toggle" style="display:inline">'
        '<button class="btn bo bsm">' + ('Wyłącz' if f["aktywne"] else 'Włącz') + '</button></form> '
        '<form method="POST" action="/admin/farm/' + str(f["id"]) + '/usun" style="display:inline" '
        'onsubmit="return confirm(' + "'" + 'Dezaktywować farmę?' + "'" + ')">' 
        '<button class="btn br bsm">Usuń</button></form>'
        '</td></tr>'
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
if register_supla_oauth_routes:
    register_supla_oauth_routes(app)
register_produkcja(app)
register_sprzedaz(app)
register_backup(app)

# ─── START ────────────────────────────────────────────────────────────────────
@app.route("/admin/farm/<int:fid>/usun", methods=["POST"])
@login_required
@superadmin_required
def admin_farm_usun(fid):
    db = get_db()
    # Nie pozwól usunąć farmy do której ktoś jest zalogowany
    db.execute("DELETE FROM uzytkownicy_gospodarstwa WHERE gospodarstwo_id=?", (fid,))
    db.execute("UPDATE gospodarstwa SET aktywne=0 WHERE id=?", (fid,))
    db.commit(); db.close()
    flash("Farma usunięta (dezaktywowana).")
    return redirect("/admin")

@app.route("/admin/farm/<int:fid>/toggle", methods=["POST"])
@login_required
@superadmin_required
def admin_farm_toggle(fid):
    db = get_db()
    db.execute("UPDATE gospodarstwa SET aktywne=1-aktywne WHERE id=?", (fid,))
    db.commit(); db.close()
    flash("Status farmy zmieniony.")
    return redirect("/admin")


def startup():
    init_db()
    init_auth()
    try:
        from scheduler import start as _sched_start
        _sched_start()
    except Exception as e:
        print(f"Scheduler start error: {e}")


if __name__ == "__main__":
    startup()
    print("\n" + "="*54)
    print("  FERMA JAJ SaaS v5 — multi-tenant")
    print("  http://localhost:5000")
    print("  Domyślny admin: admin / ferma2024")
    print("="*54 + "\n")
    app.run(host="0.0.0.0", port=5000, debug=False)