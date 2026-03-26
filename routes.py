# -*- coding: utf-8 -*-
"""
routes.py — wszystkie route'y których brakowało w app.py:
  dashboard ulepszeń, produkcja-pełny, woda, energia, wyposażenie,
  dzienne, gpio, sterowanie (tryby), pojenie, supla, esphome,
  analityka, pasza-roczne, pasza-analityka, magazyn, kiosk,
  ustawienia, import xlsx, admin/farm-assign, backup sheets
"""
from flask import request, redirect, flash, session, jsonify, send_file
from datetime import datetime, date, timedelta
import io, json, threading, os, urllib.request

_TRYBY = [
    ("reczny",        "Ręczny (tylko panel)"),
    ("supla",         "Supla webhook"),
    ("gpio_rpi",      "GPIO RPi bezpośrednie"),
    ("esphome",       "ESPHome REST"),
    ("gpio+supla",    "GPIO RPi + Supla"),
    ("esphome+supla", "ESPHome + Supla"),
]

_CZYN = [
    ("poidla","Poidła","💧"), ("karmidla","Karmidła","🌾"), ("pasza","Pasza","🌽"),
    ("jaja","Jaja","🥚"),    ("scioka","Ściółka","🏚"),    ("leki","Witaminy","💊"),
    ("bramka","Bramka","🚪"),("posprzatan","Sprzątanie","🧹"),
]

_NORMY = {
    "e_min":2700,"e_max":2850,"b_min":15.5,"b_max":18.0,
    "ca_min":38.0,"ca_max":45.0,"p_min":3.5,"liz_min":7.0,"met_min":3.0,
}

_ESPHOME_YAML = """esphome:
  name: kurnik-a
  friendly_name: Kurnik A
esp32:
  board: esp32dev
wifi:
  ssid: !secret wifi_ssid
  password: !secret wifi_password
web_server:
  port: 80
api:
  password: !secret api_password
switch:
  - platform: gpio
    pin: GPIO16
    name: "Relay 1 Swiatlo"
    id: relay1
    restore_mode: ALWAYS_OFF
  - platform: gpio
    pin: GPIO17
    name: "Relay 2 Woda"
    id: relay2
    restore_mode: ALWAYS_OFF
  - platform: gpio
    pin: GPIO18
    name: "Relay 3 Pasza"
    id: relay3
    restore_mode: ALWAYS_OFF
  - platform: gpio
    pin: GPIO19
    name: "Relay 4 Wentylacja"
    id: relay4
    restore_mode: ALWAYS_OFF
sensor:
  - platform: wifi_signal
    name: "WiFi Signal"
    update_interval: 60s"""

_SKLADNIKI = [
    ("Kukurydza (śrutowana)","zboze",1000,8.5,3370,3.8,2.2,0.3,2.8,2.2,1.8,"Główne źródło energii"),
    ("Pszenica (śrutowana)","zboze",800,12.0,3090,1.8,2.5,0.6,3.5,3.3,2.0,""),
    ("Pszenżyto (śrutowane)","zboze",800,11.5,3030,1.5,2.8,0.5,3.2,3.0,1.9,""),
    ("Owies (śrutowany)","zboze",900,11.0,2770,4.5,10.0,1.0,3.4,3.9,1.7,""),
    ("Jęczmień (śrutowany)","zboze",900,11.5,2830,2.1,4.5,0.7,3.9,3.6,1.7,""),
    ("Groch (śrutowany)","bialkowe",1080,22.0,2760,1.4,5.5,1.4,4.1,15.6,2.0,"Krajowe białko"),
    ("Słonecznik (śrutowany)","bialkowe",2000,28.0,2210,9.0,18.0,3.5,9.0,9.6,5.8,""),
    ("Łubin słodki (śrutowany)","bialkowe",2000,34.0,2670,5.0,14.0,2.7,4.0,16.0,2.2,""),
    ("Soja (śrutowana)","bialkowe",1600,44.0,2990,2.8,3.5,3.2,6.5,27.0,6.0,""),
    ("Lucerna (susz)","bialkowe",3599,17.0,1670,2.5,28.0,14.0,2.5,7.0,2.5,"Wapń, pigmenty"),
    ("Kreda Pastewna Gruba","mineralne",600,0.0,0,0.0,0.0,370.0,0.3,0.0,0.0,"Wapń dla skorupek"),
    ("Kreda Pastewna Drobna","mineralne",600,0.0,0,0.0,0.0,370.0,0.3,0.0,0.0,""),
    ("Dolmix DN RE","premiks",6000,5.0,0,0.0,0.0,100.0,50.0,0.0,0.0,"Premiks wit-min"),
    ("Dolmix NoKaniball","premiks",6000,0.0,0,0.0,0.0,0.0,0.0,0.0,0.0,""),
    ("Czosnek (proszek)","naturalny_dodatek",21490,16.0,3320,0.6,7.0,2.0,4.0,0.0,0.0,"Odporność"),
    ("Imbir (proszek)","naturalny_dodatek",30000,9.0,3470,4.2,14.0,1.0,1.8,0.0,0.0,""),
    ("Kurkuma (mielona)","naturalny_dodatek",20500,9.0,3540,10.0,7.0,1.8,2.7,0.0,0.0,"Pigment żółtka"),
    ("Tymianek (susz)","naturalny_dodatek",28790,9.0,2760,4.0,18.0,12.0,2.0,0.0,0.0,""),
    ("Oregano (susz)","naturalny_dodatek",23790,9.0,2690,4.3,23.0,16.0,2.0,0.0,0.0,""),
    ("Drożdże browarniane","naturalny_dodatek",3599,45.0,2450,1.0,3.0,0.8,14.0,30.0,5.5,"Wit B"),
    ("Siemię Lniane","naturalny_dodatek",4000,24.0,4840,35.0,8.0,2.0,5.0,8.5,3.3,"Omega-3"),
    ("Susz z pokrzywy","naturalny_dodatek",5000,20.0,1800,3.0,30.0,25.0,3.0,0.0,0.0,""),
    ("Koper (susz)","naturalny_dodatek",25790,14.0,2700,3.5,22.0,21.0,3.0,0.0,0.0,""),
    ("Siemię Lniane","naturalny_dodatek",4000,24.0,4840,35.0,8.0,2.0,5.0,8.5,3.3,"Omega-3"),
]

def register_routes(app):
    from db import get_db, get_setting, save_setting
    from auth import farm_required, login_required, superadmin_required
    from app import R

    def gid(): return session.get("farm_id")
    def gs(k, d=""): return get_setting(k, d, gid())

    def _init():
        db = get_db()
        # Nowe tabele których może nie być w starej bazie
        db.executescript("""
        CREATE TABLE IF NOT EXISTS supla_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gospodarstwo_id INTEGER REFERENCES gospodarstwa(id) ON DELETE CASCADE,
            nazwa TEXT NOT NULL, server_url TEXT DEFAULT 'https://svr1.supla.org',
            token TEXT, channel_id INTEGER, aktywny INTEGER DEFAULT 1,
            powiazane_urzadzenie_id INTEGER REFERENCES urzadzenia(id),
            powiazany_kanal TEXT, ostatni_stan INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS supla_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            czas DATETIME NOT NULL, channel_id INTEGER,
            action_raw TEXT, stan INTEGER, payload TEXT,
            gospodarstwo_id INTEGER REFERENCES gospodarstwa(id));
        CREATE TABLE IF NOT EXISTS kanal_sterowanie (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gospodarstwo_id INTEGER NOT NULL REFERENCES gospodarstwa(id) ON DELETE CASCADE,
            urzadzenie_id INTEGER REFERENCES urzadzenia(id) ON DELETE CASCADE,
            kanal TEXT NOT NULL, opis TEXT DEFAULT '', tryb TEXT DEFAULT 'reczny',
            supla_channel_id INTEGER, esphome_entity TEXT DEFAULT '',
            gpio_pin INTEGER, UNIQUE(urzadzenie_id, kanal));
        CREATE TABLE IF NOT EXISTS harmonogram_pojenia (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gospodarstwo_id INTEGER NOT NULL REFERENCES gospodarstwa(id),
            nazwa TEXT NOT NULL, urzadzenie_id INTEGER REFERENCES urzadzenia(id),
            kanal TEXT, czas_otwarcia TEXT, czas_trwania_s INTEGER DEFAULT 30,
            powtarzaj_co_h INTEGER DEFAULT 4, aktywny INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS woda_reczna (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gospodarstwo_id INTEGER NOT NULL REFERENCES gospodarstwa(id) ON DELETE CASCADE,
            data DATE NOT NULL, litry REAL DEFAULT 0,
            cena_litra REAL DEFAULT 0, koszt REAL DEFAULT 0, uwagi TEXT,
            UNIQUE(gospodarstwo_id, data));
        CREATE TABLE IF NOT EXISTS prad_odczyty (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gospodarstwo_id INTEGER NOT NULL REFERENCES gospodarstwa(id) ON DELETE CASCADE,
            data DATE NOT NULL, kwh REAL DEFAULT 0,
            odczyt_licznika REAL DEFAULT 0, koszt REAL DEFAULT 0,
            UNIQUE(gospodarstwo_id, data));
        CREATE TABLE IF NOT EXISTS wyposazenie (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gospodarstwo_id INTEGER NOT NULL REFERENCES gospodarstwa(id) ON DELETE CASCADE,
            nazwa TEXT NOT NULL, kategoria TEXT DEFAULT 'inne',
            data_zakupu DATE, cena REAL DEFAULT 0,
            stan TEXT DEFAULT 'sprawne', nastepny_przeglad DATE, uwagi TEXT);
        CREATE TABLE IF NOT EXISTS dzienne_czynnosci (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gospodarstwo_id INTEGER NOT NULL REFERENCES gospodarstwa(id) ON DELETE CASCADE,
            data DATE NOT NULL, czynnosci TEXT DEFAULT '[]', notatka TEXT,
            UNIQUE(gospodarstwo_id, data));
        CREATE TABLE IF NOT EXISTS skladniki_baza (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nazwa TEXT NOT NULL UNIQUE, kategoria TEXT DEFAULT 'inne',
            cena_pln_t REAL DEFAULT 0, bialko_pct REAL DEFAULT 0,
            energia_me REAL DEFAULT 0, tluszcz_pct REAL DEFAULT 0,
            wlokno_pct REAL DEFAULT 0, wapn_g_kg REAL DEFAULT 0,
            fosfor_g_kg REAL DEFAULT 0, lizyna_g_kg REAL DEFAULT 0,
            metionina_g_kg REAL DEFAULT 0, uwagi TEXT, aktywny INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS pwm_led (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gospodarstwo_id INTEGER REFERENCES gospodarstwa(id),
            nazwa TEXT DEFAULT 'LED', pin_bcm INTEGER NOT NULL,
            jasnosc_pct INTEGER DEFAULT 80, aktywny INTEGER DEFAULT 1);
        """)
        # Kolumny produkcja - dodaj jeśli brak
        for col in ["klient_id INTEGER", "zamowienie_id INTEGER", "typ_sprzedazy TEXT DEFAULT 'gotowka'"]:
            try: db.execute(f"ALTER TABLE produkcja ADD COLUMN {col}"); db.commit()
            except: pass
        # Kolumny receptura - sezon
        for col in ["sezon_stosowania TEXT DEFAULT ''", "miesiac_od TEXT DEFAULT ''", "miesiac_do TEXT DEFAULT ''"]:
            try: db.execute(f"ALTER TABLE receptura ADD COLUMN {col}"); db.commit()
            except: pass
        # Seed składników
        if db.execute("SELECT COUNT(*) as c FROM skladniki_baza").fetchone()["c"] == 0:
            seen = set()
            for r in _SKLADNIKI:
                if r[0] not in seen:
                    seen.add(r[0])
                    db.execute("INSERT OR IGNORE INTO skladniki_baza(nazwa,kategoria,cena_pln_t,bialko_pct,energia_me,tluszcz_pct,wlokno_pct,wapn_g_kg,fosfor_g_kg,lizyna_g_kg,metionina_g_kg,uwagi) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", r)
        db.commit(); db.close()

    _init()

    # ─── HELPER send_cmd ──────────────────────────────────────────────────────
    def _send(did, kanal, stan, g):
        db = get_db()
        dev = db.execute("SELECT * FROM urzadzenia WHERE id=? AND gospodarstwo_id=?", (did, g)).fetchone()
        if not dev: db.close(); return False, "Brak urządzenia"
        if dev["typ"] == "esphome":
            path = f"/api/switch/{kanal}/{'turn_on' if stan else 'turn_off'}"; body = b""
        else:
            path = "/api/relay"; body = json.dumps({"channel": kanal, "state": bool(stan)}).encode()
        hdrs = {"Content-Type": "application/json"}
        if dev["api_key"]: hdrs["X-API-Key" if dev["typ"] != "esphome" else "X-ESPHome-Password"] = dev["api_key"]
        try:
            req = urllib.request.Request(f"http://{dev['ip']}:{dev['port']}{path}", data=body, method="POST", headers=hdrs)
            urllib.request.urlopen(req, timeout=5); ok = True; msg = "OK"
        except Exception as e: ok = False; msg = str(e)
        now = datetime.now().isoformat()
        if ok:
            db.execute("UPDATE urzadzenia_kanaly SET stan=? WHERE urzadzenie_id=? AND kanal=?", (1 if stan else 0, did, kanal))
            db.execute("UPDATE urzadzenia SET ostatni_kontakt=?,status='online' WHERE id=?", (now, did))
        db.commit(); db.close(); return ok, msg

    # ─── DASHBOARD – czynności ────────────────────────────────────────────────
    def _kafelki(g):
        db = get_db()
        w = db.execute("SELECT czynnosci FROM dzienne_czynnosci WHERE gospodarstwo_id=? AND data=?",
                       (g, date.today().isoformat())).fetchone()
        db.close()
        zaz = json.loads(w["czynnosci"]) if w else []
        n_ok = len(zaz); n_all = len(_CZYN)
        pct = round(n_ok/n_all*100) if n_all else 0
        kol = "#3B6D11" if pct >= 80 else "#BA7517" if pct >= 50 else "#A32D2D"
        tiles = ""
        for k, l, ico in _CZYN:
            on = k in zaz
            oc = "this.closest('label').classList.toggle('tile-on',this.checked)"
            tiles += (f'<label style="cursor:pointer">'
                      f'<input type="checkbox" name="cz" value="{k}" {"checked" if on else ""} style="display:none" onchange="{oc}">'
                      f'<div class="{"tile tile-on" if on else "tile"}">'
                      f'<div style="font-size:22px;line-height:1">{ico}</div>'
                      f'<div style="font-size:11px;font-weight:500;margin-top:4px">{l}</div></div></label>')
        return (
            '<style>.tile{border:2px solid #e0ddd4;border-radius:12px;padding:10px 6px;text-align:center;'
            'background:#fff;transition:border-color .15s,background .15s;min-height:72px;'
            'display:flex;flex-direction:column;align-items:center;justify-content:center}'
            '.tile-on{border-color:#3B6D11!important;background:#EAF3DE!important}'
            '.tiles-g{display:grid;grid-template-columns:repeat(8,1fr);gap:6px}'
            '@media(max-width:700px){.tiles-g{grid-template-columns:repeat(4,1fr)}}</style>'
            f'<div class="card" style="margin-bottom:10px">'
            f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px">'
            f'<b>Czynności dzienne</b>'
            f'<div style="flex:1;background:#e0ddd4;border-radius:4px;height:6px">'
            f'<div style="width:{pct}%;background:{kol};height:100%;border-radius:4px"></div></div>'
            f'<span style="font-size:13px;color:{kol};font-weight:500">{n_ok}/{n_all}</span></div>'
            f'<form method="POST" action="/dashboard-czynnosci">'
            f'<div class="tiles-g">{tiles}</div>'
            f'<button type="submit" class="btn bg bsm" style="margin-top:10px;width:100%">Zapisz</button>'
            f'</form></div>'
        )

    @app.route("/dashboard-czynnosci", methods=["POST"])
    @farm_required
    def dashboard_czynnosci():
        g = gid(); db = get_db(); d = date.today().isoformat()
        cz = request.form.getlist("cz"); dane = json.dumps(cz)
        ex = db.execute("SELECT id FROM dzienne_czynnosci WHERE gospodarstwo_id=? AND data=?", (g, d)).fetchone()
        if ex: db.execute("UPDATE dzienne_czynnosci SET czynnosci=? WHERE id=?", (dane, ex["id"]))
        else:  db.execute("INSERT INTO dzienne_czynnosci(gospodarstwo_id,data,czynnosci) VALUES(?,?,?)", (g, d, dane))
        db.commit(); db.close(); return redirect("/")

    # Nadpisz dashboard - dodaj kafelki i przekaźniki z opsem
    @app.route("/dashboard-v2")
    @farm_required
    def dashboard_v2():
        """Ulepszona wersja - użyj jeśli / nie pokazuje przekaźników"""
        g = gid(); db = get_db()
        kur = db.execute("SELECT COALESCE(SUM(liczba),0) as s FROM stado WHERE gospodarstwo_id=? AND aktywne=1 AND gatunek='nioski'", (g,)).fetchone()["s"] or 15
        p7  = db.execute("SELECT AVG(jaja_zebrane) as a FROM produkcja WHERE gospodarstwo_id=? AND data>=date('now','-7 days')", (g,)).fetchone()
        nies= round((p7["a"] or 0)/kur*100, 1) if kur else 0
        mag = db.execute("SELECT COALESCE(SUM(jaja_zebrane),0) as p, COALESCE(SUM(jaja_sprzedane),0) as s FROM produkcja WHERE gospodarstwo_id=?", (g,)).fetchone()
        zarez = db.execute("SELECT COALESCE(SUM(ilosc),0) as s FROM zamowienia WHERE gospodarstwo_id=? AND status IN ('nowe','potwierdzone')", (g,)).fetchone()["s"]
        zysk = db.execute("SELECT COALESCE(SUM(jaja_sprzedane*cena_sprzedazy),0) as s FROM produkcja WHERE gospodarstwo_id=? AND strftime('%Y-%m',data)=strftime('%Y-%m','now')", (g,)).fetchone()["s"]
        wyd  = db.execute("SELECT COALESCE(SUM(wartosc_total),0) as s FROM wydatki WHERE gospodarstwo_id=? AND strftime('%Y-%m',data)=strftime('%Y-%m','now')", (g,)).fetchone()["s"]
        dzis = db.execute("SELECT * FROM produkcja WHERE gospodarstwo_id=? AND data=date('now')", (g,)).fetchone()
        zam_d= db.execute("SELECT COUNT(*) as c FROM zamowienia WHERE gospodarstwo_id=? AND data_dostawy=date('now') AND status NOT IN ('dostarczone','anulowane')", (g,)).fetchone()["c"]
        urzadz = db.execute("SELECT * FROM urzadzenia WHERE gospodarstwo_id=? AND aktywne=1 ORDER BY nazwa", (g,)).fetchall()
        sprzed = db.execute("""SELECT p.data,p.jaja_sprzedane,p.cena_sprzedazy,
            ROUND(p.jaja_sprzedane*p.cena_sprzedazy,2) as wartosc,
            k.nazwa as kn, COALESCE(p.typ_sprzedazy,'gotowka') as typ_sprzedazy
            FROM produkcja p LEFT JOIN klienci k ON p.klient_id=k.id
            WHERE p.gospodarstwo_id=? AND p.jaja_sprzedane>0
            ORDER BY p.data DESC LIMIT 5""", (g,)).fetchall()
        db.close()
        pdz = float(gs("pasza_dzienna_kg", "6"))
        mag_stan = max(0, mag["p"] - mag["s"])

        al = f'<div class="al ald">Dziś {zam_d} zamówień do dostarczenia!</div>' if zam_d else ""

        # Przekaźniki ze wszystkich urządzeń
        urz_html = ""
        for u in urzadz:
            db2 = get_db()
            chs = db2.execute("SELECT * FROM urzadzenia_kanaly WHERE urzadzenie_id=? ORDER BY kanal", (u["id"],)).fetchall()
            db2.close()
            for ch in chs:
                on = bool(ch["stan"])
                opis = ch["opis"] or ch["kanal"]
                urz_html += (
                    f'<div class="relay-card {"relay-on" if on else ""}" '
                    f'onclick="tR({u["id"]},\'{ch["kanal"]}\',{"false" if on else "true"})" style="cursor:pointer">'
                    f'<div class="tog {"on" if on else ""}"></div>'
                    f'<div style="font-size:11px;margin-top:4px;font-weight:500">{opis}</div>'
                    f'<div style="font-size:10px;color:#888">{u["nazwa"]}</div>'
                    f'<div style="font-size:10px;color:{"#3B6D11" if on else "#aaa"}">{"ON" if on else "OFF"}</div></div>'
                )

        sp_html = "".join(
            f'<div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid #f0ede4;font-size:13px">'
            f'<span style="color:#888">{s["data"]}</span>'
            f'<span>{s["kn"] or "—"}</span>'
            f'<span style="font-weight:500">{s["jaja_sprzedane"]} szt.</span>'
            f'<span style="color:#3B6D11;font-weight:500">{s["wartosc"]} zł</span>'
            f'<span style="font-size:11px;color:#888">{s["typ_sprzedazy"] or ""}</span></div>'
            for s in sprzed
        )

        html = (
            al
            + '<div class="g4" style="margin-bottom:10px">'
            f'<div class="card stat"><div class="v" style="color:{"#A32D2D" if nies<70 else "#3B6D11"}">{nies}%</div><div class="l">Nieśność 7 dni</div><div class="s">{kur} niosek</div></div>'
            f'<div class="card stat"><div class="v">{mag_stan}</div><div class="l">Jaj w magazynie</div><div class="s">zarezerwowane: {zarez}</div></div>'
            f'<div class="card stat"><div class="v" style="color:#3B6D11">{round(zysk,0)} zł</div><div class="l">Przychód miesiąc</div><div class="s">wydatki: {round(wyd,0)} zł</div></div>'
            f'<div class="card stat"><div class="v">{round(zysk-wyd,0)} zł</div><div class="l">Zysk miesiąc</div></div></div>'
            + _kafelki(g)
            + (f'<div class="card"><b>Przekaźniki / Oświetlenie</b>'
               f'<div class="g4" style="margin-top:10px">{urz_html}</div>'
               f'<a href="/gpio" style="font-size:12px;color:#534AB7;display:block;margin-top:8px">Pełny panel sterowania →</a></div>'
               if urz_html else
               '<div class="card" style="border:1px dashed #d3d1c7">'
               '<p style="color:#888;font-size:13px;text-align:center;padding:8px">'
               'Brak urządzeń. <a href="/urzadzenia/dodaj" style="color:#534AB7">Dodaj ESP32/RPi</a> aby sterować przekaźnikami.</p></div>')
            + '<div class="card"><b>Szybki wpis — dziś</b>'
            + (f'<span style="font-size:12px;color:#3B6D11;margin-left:8px">wpisano: {dzis["jaja_zebrane"]} jaj</span>' if dzis else "")
            + '<form method="POST" action="/produkcja/dodaj" style="margin-top:10px">'
            f'<input type="hidden" name="data" value="{date.today().isoformat()}">'
            '<div class="g3">'
            f'<div><label>Zebrane jaja</label><input name="jaja_zebrane" type="number" min="0" value="{dzis["jaja_zebrane"] if dzis else ""}"></div>'
            f'<div><label>Sprzedane</label><input name="jaja_sprzedane" type="number" value="{dzis["jaja_sprzedane"] if dzis else 0}"></div>'
            f'<div><label>Pasza (kg)</label><input name="pasza_wydana_kg" type="number" step="0.1" value="{dzis["pasza_wydana_kg"] if dzis else pdz}"></div>'
            '</div><br><button class="btn bg" style="width:100%;margin-top:8px">Zapisz dziś</button></form></div>'
            + (f'<div class="card"><b>Ostatnia sprzedaż</b><div style="margin-top:8px">{sp_html}</div>'
               f'<a href="/produkcja/dodaj-pelny" class="btn bo bsm" style="margin-top:8px">Szczegółowy wpis</a></div>'
               if sp_html else
               '<div class="card"><a href="/produkcja/dodaj-pelny" class="btn bp bsm">+ Dodaj sprzedaż z przypisaniem do klienta</a></div>')
            + '<script>function tR(d,c,s){fetch("/sterowanie/cmd",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({urzadzenie_id:d,kanal:c,stan:s})}).then(r=>r.json()).then(()=>location.reload());}</script>'
        )
        return R(html, "dash")


    # ─── PRODUKCJA PEŁNA ──────────────────────────────────────────────────────
    @app.route("/produkcja/dodaj-pelny", methods=["GET","POST"])
    @farm_required
    def produkcja_pelny():
        g = gid()
        if request.method == "POST":
            d=request.form.get("data",date.today().isoformat()); db=get_db()
            jaja=int(request.form.get("jaja_zebrane",0) or 0)
            sprzed=int(request.form.get("jaja_sprzedane",0) or 0)
            cena=float(request.form.get("cena_sprzedazy",0) or 0)
            pasza=float(request.form.get("pasza_wydana_kg",0) or 0)
            kid=request.form.get("klient_id") or None
            zid=request.form.get("zamowienie_id") or None
            typ=request.form.get("typ_sprzedazy","gotowka")
            uwagi=request.form.get("uwagi","")
            ex=db.execute("SELECT id FROM produkcja WHERE gospodarstwo_id=? AND data=?",(g,d)).fetchone()
            if ex:
                db.execute("UPDATE produkcja SET jaja_zebrane=?,jaja_sprzedane=?,cena_sprzedazy=?,pasza_wydana_kg=?,klient_id=?,zamowienie_id=?,typ_sprzedazy=?,uwagi=? WHERE id=?",
                           (jaja,sprzed,cena,pasza,kid,zid,typ,uwagi,ex["id"]))
            else:
                db.execute("INSERT INTO produkcja(gospodarstwo_id,data,jaja_zebrane,jaja_sprzedane,cena_sprzedazy,pasza_wydana_kg,klient_id,zamowienie_id,typ_sprzedazy,uwagi) VALUES(?,?,?,?,?,?,?,?,?,?)",
                           (g,d,jaja,sprzed,cena,pasza,kid,zid,typ,uwagi))
            if zid and sprzed > 0:
                db.execute("UPDATE zamowienia SET status='dostarczone' WHERE id=? AND gospodarstwo_id=?", (zid,g))
            db.commit(); db.close(); flash("Zapisano."); return redirect("/")
        db=get_db()
        d_p=request.args.get("data",date.today().isoformat())
        dzis=db.execute("SELECT * FROM produkcja WHERE gospodarstwo_id=? AND data=?",(g,d_p)).fetchone()
        klienci=db.execute("SELECT id,nazwa FROM klienci WHERE gospodarstwo_id=? ORDER BY nazwa",(g,)).fetchall()
        zamow=db.execute("""SELECT z.id,z.data_dostawy,z.ilosc,k.nazwa as kn FROM zamowienia z
            LEFT JOIN klienci k ON z.klient_id=k.id
            WHERE z.gospodarstwo_id=? AND z.status IN ('nowe','potwierdzone') ORDER BY z.data_dostawy""",(g,)).fetchall()
        pdz=float(gs("pasza_dzienna_kg","6")); db.close()
        kl_opt='<option value="">— anonimowa —</option>'+"".join(
            f'<option value="{k["id"]}" {"selected" if dzis and dzis["klient_id"]==k["id"] else ""}>{k["nazwa"]}</option>'
            for k in klienci)
        zam_opt='<option value="">— bez zamówienia —</option>'+"".join(
            f'<option value="{z["id"]}" {"selected" if dzis and dzis["zamowienie_id"]==z["id"] else ""}>{z["data_dostawy"]} · {z["kn"] or "?"} · {z["ilosc"]} szt.</option>'
            for z in zamow)
        typ_opt="".join(f'<option value="{v}" {"selected" if dzis and dzis.get("typ_sprzedazy")==v else ""}>{l}</option>'
            for v,l in [("gotowka","Gotówka"),("przelew","Przelew"),("z_salda","Z salda"),("nastepnym_razem","Następnym razem")])
        html=('<h1>Wpis produkcji i sprzedaży</h1><div class="card"><form method="POST">'
            f'<label>Data</label><input name="data" type="date" value="{d_p}">'
            '<div class="g3">'
            f'<div><label>Zebrane jaja</label><input name="jaja_zebrane" type="number" value="{dzis["jaja_zebrane"] if dzis else ""}"></div>'
            f'<div><label>Sprzedane</label><input name="jaja_sprzedane" type="number" value="{dzis["jaja_sprzedane"] if dzis else 0}" id="sp" oninput="cW()"></div>'
            f'<div><label>Cena/szt (zł)</label><input name="cena_sprzedazy" type="number" step="0.01" value="{dzis["cena_sprzedazy"] if dzis else ""}" id="cn" oninput="cW()"></div>'
            '</div><div style="background:#f5f5f0;border-radius:8px;padding:8px 12px;font-size:14px;margin-top:4px">Wartość: <b id="wrt">0.00 zł</b></div>'
            '<h2>Komu sprzedano</h2><div class="g2">'
            f'<div><label>Klient</label><select name="klient_id">{kl_opt}</select>'
            '<a href="/klienci/dodaj" style="font-size:12px;color:#534AB7;display:block;margin-top:4px">+ nowy klient</a></div>'
            f'<div><label>Typ płatności</label><select name="typ_sprzedazy">{typ_opt}</select></div></div>'
            f'<label>Powiąż z zamówieniem</label><select name="zamowienie_id">{zam_opt}</select>'
            '<div class="g2" style="margin-top:8px">'
            f'<div><label>Pasza (kg)</label><input name="pasza_wydana_kg" type="number" step="0.1" value="{dzis["pasza_wydana_kg"] if dzis else pdz}"></div>'
            f'<div><label>Uwagi</label><input name="uwagi" value="{dzis["uwagi"] if dzis and dzis["uwagi"] else ""}"></div></div>'
            '<br><button class="btn bg" style="width:100%;padding:14px;font-size:16px">Zapisz</button></form></div>'
            '<script>function cW(){var s=parseFloat(document.getElementById("sp").value)||0,c=parseFloat(document.getElementById("cn").value)||0;document.getElementById("wrt").textContent=(s*c).toFixed(2)+" zł";}cW();</script>')
        return R(html,"prod")

    # ─── WODA ─────────────────────────────────────────────────────────────────
    @app.route("/woda", methods=["GET","POST"])
    @farm_required
    def woda():
        g = gid()
        if request.method == "POST":
            d=request.form.get("data",date.today().isoformat())
            litry=float(request.form.get("litry",0) or 0)
            cl=float(request.form.get("cena_litra",0) or 0) or float(gs("cena_wody_litra","0.005"))
            koszt=round(litry*cl,2); db=get_db()
            ex=db.execute("SELECT id FROM woda_reczna WHERE gospodarstwo_id=? AND data=?",(g,d)).fetchone()
            if ex: db.execute("UPDATE woda_reczna SET litry=?,cena_litra=?,koszt=?,uwagi=? WHERE id=?",(litry,cl,koszt,request.form.get("uwagi",""),ex["id"]))
            else:  db.execute("INSERT INTO woda_reczna(gospodarstwo_id,data,litry,cena_litra,koszt,uwagi) VALUES(?,?,?,?,?,?)",(g,d,litry,cl,koszt,request.form.get("uwagi","")))
            db.commit(); db.close(); flash("Zapisano."); return redirect("/woda")
        db=get_db()
        hist=db.execute("SELECT * FROM woda_reczna WHERE gospodarstwo_id=? ORDER BY data DESC LIMIT 30",(g,)).fetchall()
        mies=db.execute("SELECT strftime('%Y-%m',data) as m,SUM(litry) as l,SUM(koszt) as k FROM woda_reczna WHERE gospodarstwo_id=? GROUP BY m ORDER BY m DESC LIMIT 6",(g,)).fetchall()
        db.close(); cena=gs("cena_wody_litra","0.005")
        w="".join(f'<tr><td>{r["data"]}</td><td style="font-weight:500">{round(r["litry"],1)} L</td><td>{round(r["cena_litra"],4)} zł/L</td><td>{round(r["koszt"],2)} zł</td><td style="color:#888;font-size:11px">{r["uwagi"] or ""}</td></tr>' for r in hist)
        mh="".join(f'<div style="display:flex;justify-content:space-between;padding:4px 0;font-size:13px;border-bottom:1px solid #f0ede4"><span style="color:#888">{r["m"]}</span><span>{round(r["l"],0)} L</span><span style="font-weight:500;color:#A32D2D">{round(r["k"],2)} zł</span></div>' for r in mies)
        html=('<h1>Woda — odczyty ręczne</h1>'
            '<div class="card"><form method="POST" style="margin-top:4px">'
            f'<div class="g3"><div><label>Data</label><input name="data" type="date" value="{date.today().isoformat()}"></div>'
            '<div><label>Zużycie (litry)</label><input name="litry" type="number" step="0.1" placeholder="np. 15.5"></div>'
            f'<div><label>Cena/litr (puste={cena} zł)</label><input name="cena_litra" type="number" step="0.0001" placeholder="{cena}"></div></div>'
            '<label>Uwagi</label><input name="uwagi"><br><button class="btn bp">Zapisz</button></form></div>'
            '<div class="g2">'
            f'<div class="card"><b>Sumy miesięczne</b><div style="margin-top:8px">{mh or "<p style=\'color:#888;font-size:13px\'>Brak</p>"}</div></div>'
            '<div class="card"><b>Cena wody</b><form method="POST" action="/ustawienia/media" style="margin-top:8px">'
            f'<label>Cena wody (zł/litr)</label><input name="cena_wody_litra" type="number" step="0.0001" value="{cena}">'
            '<br><button class="btn bo bsm" style="margin-top:8px">Zapisz cenę</button></form></div></div>'
            '<div class="card" style="overflow-x:auto"><b>Historia 30 dni</b>'
            '<table style="margin-top:8px"><thead><tr><th>Data</th><th>Litry</th><th>Cena/L</th><th>Koszt</th><th>Uwagi</th></tr></thead>'
            f'<tbody>{w or "<tr><td colspan=5 style=\'color:#888;text-align:center;padding:16px\'>Brak</td></tr>"}</tbody></table></div>')
        return R(html,"woda")

    @app.route("/ustawienia/media", methods=["POST"])
    @farm_required
    def ustawienia_media():
        g = gid()
        for k in ["cena_wody_litra","cena_kwh"]:
            v = request.form.get(k)
            if v: save_setting(k, v, g)
        flash("Ceny mediów zapisane."); return redirect(request.referrer or "/")

    # ─── ENERGIA ──────────────────────────────────────────────────────────────
    @app.route("/energia", methods=["GET","POST"])
    @farm_required
    def energia():
        g = gid()
        if request.method == "POST":
            d=request.form.get("data",date.today().isoformat())
            kwh=float(request.form.get("kwh",0) or 0)
            odczyt=float(request.form.get("odczyt_licznika",0) or 0)
            cena=float(request.form.get("cena_kwh",0) or 0) or float(gs("cena_kwh","0.80"))
            koszt=round(kwh*cena,2); db=get_db()
            ex=db.execute("SELECT id FROM prad_odczyty WHERE gospodarstwo_id=? AND data=?",(g,d)).fetchone()
            if ex: db.execute("UPDATE prad_odczyty SET kwh=?,odczyt_licznika=?,koszt=? WHERE id=?",(kwh,odczyt,koszt,ex["id"]))
            else:  db.execute("INSERT INTO prad_odczyty(gospodarstwo_id,data,kwh,odczyt_licznika,koszt) VALUES(?,?,?,?,?)",(g,d,kwh,odczyt,koszt))
            db.commit(); db.close(); flash("Zapisano."); return redirect("/energia")
        db=get_db()
        hist=db.execute("SELECT * FROM prad_odczyty WHERE gospodarstwo_id=? ORDER BY data DESC LIMIT 60",(g,)).fetchall()
        mies_d=db.execute("SELECT COALESCE(SUM(kwh),0) as k, COALESCE(SUM(koszt),0) as kz FROM prad_odczyty WHERE gospodarstwo_id=? AND strftime('%Y-%m',data)=strftime('%Y-%m','now')",(g,)).fetchone()
        avg30=db.execute("SELECT AVG(kwh) as a FROM prad_odczyty WHERE gospodarstwo_id=? AND data>=date('now','-30 days')",(g,)).fetchone()["a"] or 0
        db.close()
        cena_kwh=gs("cena_kwh","0.80"); today=date.today()
        pred_kwh=round(avg30*(date(today.year,12,31)-today).days, 1)
        pred_koszt=round(pred_kwh*float(cena_kwh),2)
        al=""
        if today.month in (7,8):
            al=f'<div class="al alw">Sierpień — zaplanuj na zimę. Predykcja do 31.12: <b>{pred_kwh} kWh</b> ({pred_koszt} zł)</div>'
        w="".join(f'<tr><td>{r["data"]}</td><td style="font-weight:500">{round(r["kwh"],3)} kWh</td><td style="color:#888">{round(r["odczyt_licznika"],1) if r["odczyt_licznika"] else "—"}</td><td>{round(r["koszt"],2)} zł</td></tr>' for r in hist)
        html=(al+'<h1>Licznik energii</h1>'
            '<div class="g3" style="margin-bottom:12px">'
            f'<div class="card stat"><div class="v">{round(mies_d["k"],2)} kWh</div><div class="l">Ten miesiąc</div></div>'
            f'<div class="card stat"><div class="v" style="color:#A32D2D">{round(mies_d["kz"],2)} zł</div><div class="l">Koszt miesiąc</div></div>'
            f'<div class="card stat"><div class="v" style="color:#534AB7">{pred_kwh} kWh</div><div class="l">Predykcja do 31.12</div><div class="s">{pred_koszt} zł</div></div></div>'
            '<div class="card"><form method="POST" style="margin-top:4px">'
            f'<div class="g3"><div><label>Data</label><input name="data" type="date" value="{today.isoformat()}"></div>'
            '<div><label>Zużycie (kWh)</label><input name="kwh" type="number" step="0.001" placeholder="np. 2.450"></div>'
            f'<div><label>Stan licznika</label><input name="odczyt_licznika" type="number" step="0.1"></div></div>'
            f'<label>Cena kWh (puste={cena_kwh} zł)</label><input name="cena_kwh" type="number" step="0.01" placeholder="{cena_kwh}" style="max-width:200px">'
            '<br><button class="btn bp">Zapisz odczyt</button></form></div>'
            '<div class="card" style="overflow-x:auto"><b>Historia</b>'
            '<table style="margin-top:8px"><thead><tr><th>Data</th><th>Zużycie</th><th>Stan licznika</th><th>Koszt</th></tr></thead>'
            f'<tbody>{w or "<tr><td colspan=4 style=\'color:#888;text-align:center;padding:16px\'>Brak</td></tr>"}</tbody></table></div>')
        return R(html,"wyd")


    # ─── WYPOSAŻENIE ─────────────────────────────────────────────────────────
    @app.route("/wyposazenie")
    @farm_required
    def wyposazenie():
        g=gid(); db=get_db()
        rows=db.execute("SELECT * FROM wyposazenie WHERE gospodarstwo_id=? ORDER BY stan,nazwa",(g,)).fetchall(); db.close()
        today=date.today().isoformat()
        sbdg={"sprawne":"b-green","wymaga przeglądu":"b-amber","uszkodzone":"b-red","wycofane":"b-gray"}
        w="".join(f'<tr><td style="font-weight:500">{r["nazwa"]}</td>'
            f'<td><span class="badge b-blue">{r["kategoria"]}</span></td>'
            f'<td><span class="badge {sbdg.get(r["stan"],"b-gray")}">{r["stan"]}</span></td>'
            f'<td>{r["data_zakupu"] or "—"}</td>'
            f'<td style="color:{"#A32D2D" if r["nastepny_przeglad"] and r["nastepny_przeglad"]<=today else "#2c2c2a"}">{r["nastepny_przeglad"] or "—"}</td>'
            f'<td class="nowrap"><a href="/wyposazenie/{r["id"]}/edytuj" class="btn bo bsm">Edytuj</a> '
            f'<a href="/wyposazenie/{r["id"]}/usun" class="btn br bsm" onclick="return confirm(\'Usunąć?\')">✕</a></td></tr>'
            for r in rows)
        html=('<h1>Wyposażenie kurnika</h1>'
            '<a href="/wyposazenie/dodaj" class="btn bp bsm" style="margin-bottom:12px">+ Dodaj pozycję</a>'
            '<div class="card" style="overflow-x:auto"><table><thead><tr><th>Nazwa</th><th>Kategoria</th><th>Stan</th><th>Zakup</th><th>Przegląd</th><th></th></tr></thead>'
            f'<tbody>{w or "<tr><td colspan=6 style=\'color:#888;text-align:center;padding:20px\'>Brak</td></tr>"}</tbody></table></div>')
        return R(html,"wyp")

    def _wypos_form(action, v=None):
        v=v or {}
        KAT=["Karmidło","Poideło","Gniazdo","Oświetlenie","Grzewcze","Ogrodzenie","Narzędzia","Inne"]
        STANY=["sprawne","wymaga przeglądu","uszkodzone","wycofane"]
        ko="".join(f'<option value="{k}" {"selected" if v.get("kategoria")==k else ""}>{k}</option>' for k in KAT)
        so="".join(f'<option value="{s}" {"selected" if v.get("stan")==s else ""}>{s}</option>' for s in STANY)
        return (f'<div class="card"><form method="POST" action="{action}">'
            f'<label>Nazwa</label><input name="nazwa" required value="{v.get("nazwa","")}">'
            f'<div class="g2"><div><label>Kategoria</label><select name="kategoria">{ko}</select></div>'
            f'<div><label>Stan</label><select name="stan">{so}</select></div></div>'
            f'<div class="g3"><div><label>Data zakupu</label><input name="data_zakupu" type="date" value="{v.get("data_zakupu") or ""}"></div>'
            f'<div><label>Cena (zł)</label><input name="cena" type="number" step="0.01" value="{v.get("cena","") or ""}"></div>'
            f'<div><label>Następny przegląd</label><input name="nastepny_przeglad" type="date" value="{v.get("nastepny_przeglad") or ""}"></div></div>'
            f'<label>Uwagi</label><textarea name="uwagi" rows="2">{v.get("uwagi","")}</textarea>'
            '<br><button class="btn bp">Zapisz</button><a href="/wyposazenie" class="btn bo" style="margin-left:8px">Anuluj</a></form></div>')

    @app.route("/wyposazenie/dodaj", methods=["GET","POST"])
    @farm_required
    def wyposazenie_dodaj():
        g=gid()
        if request.method=="POST":
            db=get_db()
            db.execute("INSERT INTO wyposazenie(gospodarstwo_id,nazwa,kategoria,data_zakupu,cena,stan,nastepny_przeglad,uwagi) VALUES(?,?,?,?,?,?,?,?)",
                (g,request.form["nazwa"],request.form.get("kategoria","Inne"),
                 request.form.get("data_zakupu","") or None,float(request.form.get("cena",0) or 0),
                 request.form.get("stan","sprawne"),request.form.get("nastepny_przeglad","") or None,
                 request.form.get("uwagi","")))
            db.commit(); db.close(); flash("Dodano."); return redirect("/wyposazenie")
        return R('<h1>Nowa pozycja</h1>'+_wypos_form("/wyposazenie/dodaj"),"wyp")

    @app.route("/wyposazenie/<int:wid>/edytuj", methods=["GET","POST"])
    @farm_required
    def wyposazenie_edytuj(wid):
        g=gid(); db=get_db()
        if request.method=="POST":
            db.execute("UPDATE wyposazenie SET nazwa=?,kategoria=?,data_zakupu=?,cena=?,stan=?,nastepny_przeglad=?,uwagi=? WHERE id=? AND gospodarstwo_id=?",
                (request.form["nazwa"],request.form.get("kategoria","Inne"),
                 request.form.get("data_zakupu","") or None,float(request.form.get("cena",0) or 0),
                 request.form.get("stan","sprawne"),request.form.get("nastepny_przeglad","") or None,
                 request.form.get("uwagi",""),wid,g))
            db.commit(); db.close(); flash("Zaktualizowano."); return redirect("/wyposazenie")
        r=dict(db.execute("SELECT * FROM wyposazenie WHERE id=? AND gospodarstwo_id=?",(wid,g)).fetchone() or {}); db.close()
        return R(f'<h1>Edytuj: {r.get("nazwa","")}</h1>'+_wypos_form(f"/wyposazenie/{wid}/edytuj",r),"wyp")

    @app.route("/wyposazenie/<int:wid>/usun")
    @farm_required
    def wyposazenie_usun(wid):
        g=gid(); db=get_db()
        db.execute("DELETE FROM wyposazenie WHERE id=? AND gospodarstwo_id=?",(wid,g))
        db.commit(); db.close(); flash("Usunięto."); return redirect("/wyposazenie")

    # ─── DZIENNE CZYNNOŚCI ────────────────────────────────────────────────────
    @app.route("/dzienne", methods=["GET","POST"])
    @farm_required
    def dzienne():
        g=gid(); db=get_db()
        if request.method=="POST":
            d=date.today().isoformat(); cz=request.form.getlist("cz"); dane=json.dumps(cz)
            ex=db.execute("SELECT id FROM dzienne_czynnosci WHERE gospodarstwo_id=? AND data=?",(g,d)).fetchone()
            if ex: db.execute("UPDATE dzienne_czynnosci SET czynnosci=?,notatka=? WHERE id=?",(dane,request.form.get("nota",""),ex["id"]))
            else:  db.execute("INSERT INTO dzienne_czynnosci(gospodarstwo_id,data,czynnosci,notatka) VALUES(?,?,?,?)",(g,d,dane,request.form.get("nota","")))
            db.commit(); db.close(); flash("Zapisano."); return redirect("/dzienne")
        d=date.today().isoformat()
        wpis=db.execute("SELECT * FROM dzienne_czynnosci WHERE gospodarstwo_id=? AND data=?",(g,d)).fetchone()
        hist=db.execute("SELECT * FROM dzienne_czynnosci WHERE gospodarstwo_id=? ORDER BY data DESC LIMIT 8",(g,)).fetchall()
        db.close()
        zaz=json.loads(wpis["czynnosci"]) if wpis else []; n=len(_CZYN); tiles=""
        for k,l,ico in _CZYN:
            on=k in zaz; oc="this.closest('label').classList.toggle('tile-on',this.checked)"
            tiles+=(f'<label style="cursor:pointer">'
                    f'<input type="checkbox" name="cz" value="{k}" {"checked" if on else ""} style="display:none" onchange="{oc}">'
                    f'<div class="{"tile tile-on" if on else "tile"}">'
                    f'<div style="font-size:28px">{ico}</div>'
                    f'<div style="font-size:13px;font-weight:500;margin-top:6px">{l}</div></div></label>')
        hhtml="".join(
            f'<div style="display:flex;align-items:center;gap:8px;padding:5px 0;font-size:13px;border-bottom:1px solid #f0ede4">'
            f'<span style="min-width:80px;color:#888">{h["data"]}</span>'
            f'<div style="flex:1;background:#e0ddd4;border-radius:4px;height:8px">'
            f'<div style="width:{round(len(json.loads(h["czynnosci"] or "[]"))/n*100)}%;'
            f'background:{"#3B6D11" if len(json.loads(h["czynnosci"] or "[]"))/n>=0.8 else "#BA7517" if len(json.loads(h["czynnosci"] or "[]"))/n>=0.5 else "#A32D2D"};'
            f'height:100%;border-radius:4px"></div></div>'
            f'<span style="min-width:32px;text-align:right;font-weight:500">{len(json.loads(h["czynnosci"] or "[]"))}/{n}</span></div>'
            for h in hist)
        html=(f'<h1>Czynności — dziś {d}</h1>'
            '<style>.tile{border:2px solid #e0ddd4;border-radius:14px;padding:14px 10px;text-align:center;background:#fff;min-height:90px;display:flex;flex-direction:column;align-items:center;justify-content:center}'
            '.tile-on{border-color:#3B6D11;background:#EAF3DE}'
            '.tiles-g{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}'
            '@media(max-width:500px){.tiles-g{grid-template-columns:repeat(2,1fr)}}</style>'
            '<div class="g2"><div class="card"><form method="POST">'
            f'<div class="tiles-g">{tiles}</div>'
            f'<label style="margin-top:14px">Notatka</label>'
            f'<input name="nota" value="{wpis["notatka"] if wpis and wpis["notatka"] else ""}">'
            '<br><button class="btn bp" style="width:100%;margin-top:12px;padding:12px">Zapisz</button></form></div>'
            f'<div class="card"><b>Ostatnie dni</b><div style="margin-top:8px">{hhtml or "<p style=\'color:#888;font-size:13px\'>Brak historii</p>"}</div></div></div>'
            '<a href="/" class="btn bo bsm" style="margin-top:8px">← Dashboard</a>')
        return R(html,"dash")


    # ─── GPIO / STEROWANIE ────────────────────────────────────────────────────
    @app.route("/gpio")
    @farm_required
    def gpio_main():
        g=gid(); db=get_db()
        urzadz=db.execute("SELECT * FROM urzadzenia WHERE gospodarstwo_id=? AND aktywne=1 ORDER BY nazwa",(g,)).fetchall()
        html=('<h1>Przekaźniki GPIO</h1>'
            '<div style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap">'
            '<a href="/urzadzenia/dodaj" class="btn bp bsm">+ Dodaj urządzenie</a>'
            '<a href="/sterowanie" class="btn bo bsm">Tryby sterowania</a>'
            '<a href="/gpio/pwm" class="btn bo bsm">LED PWM</a>'
            '<a href="/pojenie" class="btn bo bsm">Pojenie</a>'
            '<a href="/integracje/esphome" class="btn bo bsm">ESPHome</a>'
            '<a href="/supla" class="btn bo bsm">Supla</a></div>')
        if not urzadz:
            html+='<div class="card"><p style="color:#888;text-align:center;padding:20px">Brak urządzeń. <a href="/urzadzenia/dodaj" style="color:#534AB7">Dodaj ESP32 lub RPi slave</a>.</p></div>'
        for u in urzadz:
            chs=db.execute("SELECT * FROM urzadzenia_kanaly WHERE urzadzenie_id=? ORDER BY kanal",(u["id"],)).fetchall()
            ch_html="".join(
                f'<div class="relay-card {"relay-on" if ch["stan"] else ""}" '
                f'onclick="tR({u["id"]},\'{ch["kanal"]}\',{"false" if ch["stan"] else "true"})" style="cursor:pointer">'
                f'<div class="tog {"on" if ch["stan"] else ""}"></div>'
                f'<div style="font-size:12px;margin-top:6px;font-weight:500">{ch["opis"] or ch["kanal"]}</div>'
                f'<div style="font-size:11px;color:{"#3B6D11" if ch["stan"] else "#aaa"}">{"ON" if ch["stan"] else "OFF"}</div></div>'
                for ch in chs)
            badge=f'<span class="badge {"b-green" if u["status"]=="online" else "b-red"}">{u["status"]}</span>'
            html+=(f'<div class="card"><div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">'
                   f'<b>{u["nazwa"]}</b><span class="badge b-blue">{u["typ"].upper()}</span>{badge}'
                   f'<code style="font-size:11px;color:#888">{u["ip"]}:{u["port"]}</code>'
                   f'<a href="/urzadzenia/{u["id"]}/ping" class="btn bo bsm" style="margin-left:auto">Ping</a>'
                   f'<a href="/urzadzenia/{u["id"]}" class="btn bo bsm">Panel</a></div>'
                   f'<div class="g4">{ch_html or "<p style=\'color:#888;font-size:13px\'>Brak skonfigurowanych kanałów</p>"}</div></div>')
        db.close()
        html+='<script>function tR(d,c,s){fetch("/sterowanie/cmd",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({urzadzenie_id:d,kanal:c,stan:s})}).then(r=>r.json()).then(()=>location.reload());}</script>'
        return R(html,"gpio")

    @app.route("/sterowanie")
    @farm_required
    def sterowanie():
        g=gid(); db=get_db()
        kanaly=db.execute("""SELECT uc.*,u.nazwa as urz_nazwa,
            ks.tryb,ks.supla_channel_id,ks.esphome_entity,ks.gpio_pin,ks.opis as kopis
            FROM urzadzenia_kanaly uc JOIN urzadzenia u ON uc.urzadzenie_id=u.id
            LEFT JOIN kanal_sterowanie ks ON ks.urzadzenie_id=uc.urzadzenie_id AND ks.kanal=uc.kanal
            WHERE u.gospodarstwo_id=? AND u.aktywne=1 ORDER BY u.nazwa,uc.kanal""",(g,)).fetchall()
        db.close()
        kol={"reczny":"b-gray","supla":"b-amber","gpio_rpi":"b-green","esphome":"b-blue","gpio+supla":"b-purple","esphome+supla":"b-purple"}
        ico={"reczny":"🖱","supla":"⚡","gpio_rpi":"🔌","esphome":"📡","gpio+supla":"🔌⚡","esphome+supla":"📡⚡"}
        w="".join(f'<tr><td style="font-weight:500">{k["urz_nazwa"]}</td><td><code>{k["kanal"]}</code></td>'
            f'<td>{k["kopis"] or k["opis"] or "—"}</td>'
            f'<td><span class="badge {kol.get(k["tryb"] or "reczny","b-gray")}">{ico.get(k["tryb"] or "reczny","")} {k["tryb"] or "reczny"}</span></td>'
            f'<td><a href="/sterowanie/kanal/{k["urzadzenie_id"]}/{k["kanal"]}" class="btn bo bsm">Konfiguruj</a></td></tr>'
            for k in kanaly)
        info="".join(f'<div style="padding:3px 0;font-size:13px"><span style="font-size:15px">{ico.get(v,"")}</span> <b>{v}</b> — {l}</div>' for v,l in _TRYBY)
        html=('<h1>Tryby sterowania per kanał</h1>'
            f'<div class="card" style="background:#EEEDFE;border-color:#AFA9EC"><b>Dostępne tryby</b><div class="g3" style="margin-top:8px">{info}</div></div>'
            '<div class="card" style="overflow-x:auto"><table><thead><tr><th>Urządzenie</th><th>Kanał</th><th>Opis</th><th>Tryb</th><th></th></tr></thead>'
            f'<tbody>{w or "<tr><td colspan=5 style=\'color:#888;text-align:center;padding:20px\'>Brak urządzeń. <a href=\'/urzadzenia/dodaj\'>Dodaj urządzenie</a></td></tr>"}</tbody></table></div>')
        return R(html,"gpio")

    @app.route("/sterowanie/kanal/<int:did>/<kanal>", methods=["GET","POST"])
    @farm_required
    def sterowanie_kanal(did, kanal):
        g=gid(); db=get_db()
        if request.method=="POST":
            tryb=request.form.get("tryb","reczny")
            sup=request.form.get("supla_channel_id") or None
            esh=request.form.get("esphome_entity","").strip()
            gpio=request.form.get("gpio_pin") or None
            opis=request.form.get("opis","").strip()
            ex=db.execute("SELECT id FROM kanal_sterowanie WHERE urzadzenie_id=? AND kanal=?",(did,kanal)).fetchone()
            if ex: db.execute("UPDATE kanal_sterowanie SET tryb=?,supla_channel_id=?,esphome_entity=?,gpio_pin=?,opis=? WHERE id=?",(tryb,sup,esh,gpio,opis,ex["id"]))
            else:  db.execute("INSERT INTO kanal_sterowanie(gospodarstwo_id,urzadzenie_id,kanal,tryb,supla_channel_id,esphome_entity,gpio_pin,opis) VALUES(?,?,?,?,?,?,?,?)",(g,did,kanal,tryb,sup,esh,gpio,opis))
            db.commit(); db.close(); flash(f"Tryb {kanal}: {tryb}"); return redirect("/sterowanie")
        dev=db.execute("SELECT * FROM urzadzenia WHERE id=? AND gospodarstwo_id=?",(did,g)).fetchone()
        ks=db.execute("SELECT * FROM kanal_sterowanie WHERE urzadzenie_id=? AND kanal=?",(did,kanal)).fetchone()
        supla=db.execute("SELECT id,nazwa,channel_id FROM supla_config WHERE gospodarstwo_id=? AND aktywny=1",(g,)).fetchall()
        db.close()
        if not dev: return redirect("/sterowanie")
        v=dict(ks) if ks else {}; tryb_cur=v.get("tryb","reczny")
        tryb_opt="".join(f'<option value="{tv}" {"selected" if tryb_cur==tv else ""}>{tl}</option>' for tv,tl in _TRYBY)
        sup_opt='<option value="">— brak —</option>'+"".join(f'<option value="{s["channel_id"]}" {"selected" if str(v.get("supla_channel_id",""))==str(s["channel_id"]) else ""}>{s["nazwa"]} (ch:{s["channel_id"]})</option>' for s in supla)
        html=(f'<h1>Tryb: {dev["nazwa"]} / {kanal}</h1><div class="card"><form method="POST">'
            f'<label>Opis kanału</label><input name="opis" value="{v.get("opis","")}" placeholder="np. Światło kurnik, Zawór wody">'
            f'<label>Tryb sterowania</label><select name="tryb" id="tryb-sel" onchange="showF(this.value)">{tryb_opt}</select>'
            f'<div id="fd-s" style="margin-top:10px"><div class="al alw"><b>Supla</b> — skonfiguruj w <a href="/supla">panelu Supla</a></div>'
            f'<label>Kanał Supla</label><select name="supla_channel_id">{sup_opt}</select></div>'
            f'<div id="fd-e" style="margin-top:10px"><div class="al alok"><b>ESPHome REST</b> — urządzenie musi mieć typ ESPHome</div>'
            f'<label>Nazwa encji ESPHome</label><input name="esphome_entity" value="{v.get("esphome_entity","")}" placeholder="relay1"></div>'
            f'<div id="fd-g" style="margin-top:10px"><div class="al alok"><b>GPIO RPi</b> — gdy app działa bezpośrednio na RPi</div>'
            f'<label>Numer pinu GPIO BCM</label><input name="gpio_pin" type="number" value="{v.get("gpio_pin","") or ""}"></div>'
            '<br><button class="btn bp">Zapisz</button><a href="/sterowanie" class="btn bo" style="margin-left:8px">Anuluj</a></form></div>'
            '<script>'
            'var _sh={"reczny":[],"supla":["s"],"gpio_rpi":["g"],"esphome":["e"],"gpio+supla":["g","s"],"esphome+supla":["e","s"]};'
            'function showF(v){["s","g","e"].forEach(function(id){document.getElementById("fd-"+id).style.display="none";});'
            '(_sh[v]||[]).forEach(function(id){document.getElementById("fd-"+id).style.display="block";});}'
            f'showF("{tryb_cur}");'
            '</script>')
        return R(html,"gpio")

    @app.route("/sterowanie/cmd", methods=["POST"])
    @farm_required
    def sterowanie_cmd():
        g=gid(); data=request.get_json()
        did=data.get("urzadzenie_id"); kanal=data.get("kanal",""); stan=data.get("stan",False)
        ok, msg = _send(did, kanal, stan, g)
        return jsonify({"ok":ok,"msg":msg})

    # ─── GPIO PWM ─────────────────────────────────────────────────────────────
    @app.route("/gpio/pwm")
    @farm_required
    def gpio_pwm():
        g=gid(); db=get_db()
        rows=db.execute("SELECT * FROM pwm_led WHERE gospodarstwo_id=? ORDER BY nazwa",(g,)).fetchall(); db.close()
        w="".join(f'<tr><td>{r["nazwa"]}</td><td>GPIO{r["pin_bcm"]}</td>'
            f'<td><input type="range" min="0" max="100" value="{r["jasnosc_pct"]}" '
            f'onchange="setPWM({r["id"]},this.value)" style="width:100px"> {r["jasnosc_pct"]}%</td>'
            f'<td><a href="/gpio/pwm/{r["id"]}/off" class="btn br bsm">Wyłącz</a></td></tr>' for r in rows)
        html=('<h1>LED PWM — ściemniacz</h1>'
            '<a href="/gpio/pwm/dodaj" class="btn bp bsm" style="margin-bottom:12px">+ Dodaj LED</a>'
            '<div class="card" style="overflow-x:auto"><table><thead><tr><th>Nazwa</th><th>Pin GPIO</th><th>Jasność</th><th></th></tr></thead>'
            f'<tbody>{w or "<tr><td colspan=4 style=\'color:#888;text-align:center;padding:20px\'>Brak kanałów LED</td></tr>"}</tbody></table></div>'
            '<script>function setPWM(id,val){fetch("/gpio/pwm/set",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({id:id,jasnosc:parseInt(val)})}).then(r=>r.json()).then(()=>location.reload());}</script>')
        return R(html,"gpio")

    @app.route("/gpio/pwm/dodaj", methods=["GET","POST"])
    @farm_required
    def gpio_pwm_dodaj():
        g=gid()
        if request.method=="POST":
            db=get_db()
            db.execute("INSERT INTO pwm_led(gospodarstwo_id,nazwa,pin_bcm,jasnosc_pct) VALUES(?,?,?,?)",
                (g,request.form["nazwa"],int(request.form.get("pin_bcm",5)),int(request.form.get("jasnosc_pct",80))))
            db.commit(); db.close(); flash("LED dodany."); return redirect("/gpio/pwm")
        html=('<h1>Nowy kanał LED PWM</h1><div class="card"><form method="POST">'
            '<label>Nazwa</label><input name="nazwa" required placeholder="np. LED kurnik">'
            '<div class="g2"><div><label>Pin GPIO BCM</label><input name="pin_bcm" type="number" value="5"></div>'
            '<div><label>Jasność startowa (%)</label><input name="jasnosc_pct" type="number" min="0" max="100" value="80"></div></div>'
            '<br><button class="btn bp">Dodaj</button><a href="/gpio/pwm" class="btn bo" style="margin-left:8px">Anuluj</a></form></div>')
        return R(html,"gpio")

    @app.route("/gpio/pwm/set", methods=["POST"])
    @farm_required
    def gpio_pwm_set():
        g=gid(); data=request.get_json(); lid=data.get("id"); jasnosc=int(data.get("jasnosc",0))
        db=get_db(); db.execute("UPDATE pwm_led SET jasnosc_pct=? WHERE id=? AND gospodarstwo_id=?",(jasnosc,lid,g)); db.commit(); db.close()
        return jsonify({"ok":True})

    @app.route("/gpio/pwm/<int:lid>/off")
    @farm_required
    def gpio_pwm_off(lid):
        g=gid(); db=get_db()
        db.execute("UPDATE pwm_led SET jasnosc_pct=0 WHERE id=? AND gospodarstwo_id=?",(lid,g))
        db.commit(); db.close(); flash("LED wyłączony."); return redirect("/gpio/pwm")

    # ─── POJENIE ─────────────────────────────────────────────────────────────
    @app.route("/pojenie")
    @farm_required
    def pojenie():
        g=gid(); db=get_db()
        rows=db.execute("SELECT h.*,u.nazwa as urz_nazwa FROM harmonogram_pojenia h LEFT JOIN urzadzenia u ON h.urzadzenie_id=u.id WHERE h.gospodarstwo_id=? ORDER BY h.czas_otwarcia",(g,)).fetchall(); db.close()
        w="".join(f'<tr><td style="font-weight:500">{r["nazwa"]}</td><td>{r["urz_nazwa"] or "—"}</td>'
            f'<td><code>{r["kanal"] or "—"}</code></td><td>{r["czas_otwarcia"] or "—"}</td>'
            f'<td>{r["czas_trwania_s"]} s</td><td>co {r["powtarzaj_co_h"]} h</td>'
            f'<td><span class="badge {"b-green" if r["aktywny"] else "b-gray"}">{"aktywne" if r["aktywny"] else "wyłączone"}</span></td>'
            f'<td class="nowrap"><a href="/pojenie/{r["id"]}/uruchom" class="btn bg bsm">▶ Uruchom</a> '
            f'<a href="/pojenie/{r["id"]}/toggle" class="btn bo bsm">{"Wyłącz" if r["aktywny"] else "Włącz"}</a></td></tr>' for r in rows)
        html=('<h1>Pojenie — harmonogram</h1>'
            '<a href="/pojenie/dodaj" class="btn bp bsm" style="margin-bottom:12px">+ Dodaj harmonogram</a>'
            '<div class="card" style="overflow-x:auto"><table><thead><tr><th>Nazwa</th><th>Urządzenie</th><th>Kanał</th><th>Godzina</th><th>Czas</th><th>Cykl</th><th>Status</th><th></th></tr></thead>'
            f'<tbody>{w or "<tr><td colspan=8 style=\'color:#888;text-align:center;padding:20px\'>Brak harmonogramów</td></tr>"}</tbody></table></div>')
        return R(html,"gpio")

    @app.route("/pojenie/dodaj", methods=["GET","POST"])
    @farm_required
    def pojenie_dodaj():
        g=gid()
        if request.method=="POST":
            db=get_db()
            db.execute("INSERT INTO harmonogram_pojenia(gospodarstwo_id,nazwa,urzadzenie_id,kanal,czas_otwarcia,czas_trwania_s,powtarzaj_co_h,aktywny) VALUES(?,?,?,?,?,?,?,1)",
                (g,request.form["nazwa"],request.form.get("urzadzenie_id") or None,
                 request.form.get("kanal","relay2"),request.form.get("czas_otwarcia","08:00"),
                 int(request.form.get("czas_trwania_s",30)),int(request.form.get("powtarzaj_co_h",4))))
            db.commit(); db.close(); flash("Dodano."); return redirect("/pojenie")
        db=get_db(); urzadz=db.execute("SELECT id,nazwa FROM urzadzenia WHERE gospodarstwo_id=? AND aktywne=1",(g,)).fetchall(); db.close()
        u_opt='<option value="">— brak —</option>'+"".join(f'<option value="{u["id"]}">{u["nazwa"]}</option>' for u in urzadz)
        html=(f'<h1>Nowy harmonogram pojenia</h1><div class="card"><form method="POST">'
            '<label>Nazwa</label><input name="nazwa" required placeholder="np. Pojenie poranne">'
            f'<div class="g2"><div><label>Urządzenie</label><select name="urzadzenie_id">{u_opt}</select></div>'
            '<div><label>Kanał (relay z zaworem)</label><select name="kanal">'
            +"".join(f'<option value="relay{i}">relay{i}</option>' for i in range(1,5))
            +'</select></div></div><div class="g3">'
            '<div><label>Godzina otwarcia</label><input name="czas_otwarcia" type="time" value="08:00"></div>'
            '<div><label>Czas trwania (s)</label><input name="czas_trwania_s" type="number" value="30" min="5" max="300"></div>'
            '<div><label>Powtarzaj co (h)</label><input name="powtarzaj_co_h" type="number" value="4" min="1" max="24"></div></div>'
            '<br><button class="btn bp">Dodaj</button><a href="/pojenie" class="btn bo" style="margin-left:8px">Anuluj</a></form></div>')
        return R(html,"gpio")

    @app.route("/pojenie/<int:hid>/toggle")
    @farm_required
    def pojenie_toggle(hid):
        g=gid(); db=get_db()
        db.execute("UPDATE harmonogram_pojenia SET aktywny=1-aktywny WHERE id=? AND gospodarstwo_id=?",(hid,g))
        db.commit(); db.close(); flash("Zmieniono."); return redirect("/pojenie")

    @app.route("/pojenie/<int:hid>/uruchom")
    @farm_required
    def pojenie_uruchom(hid):
        g=gid(); db=get_db()
        h=db.execute("SELECT * FROM harmonogram_pojenia WHERE id=? AND gospodarstwo_id=?",(hid,g)).fetchone(); db.close()
        if not h or not h["urzadzenie_id"]: flash("Skonfiguruj urządzenie i kanał."); return redirect("/pojenie")
        ok,msg=_send(h["urzadzenie_id"],h["kanal"],True,g)
        if ok:
            flash(f"Pojenie uruchomione na {h['czas_trwania_s']} s.")
            sek=h["czas_trwania_s"]; did2=h["urzadzenie_id"]; kan=h["kanal"]
            def _close():
                import time; time.sleep(sek)
                try: _send(did2,kan,False,g)
                except: pass
            threading.Thread(target=_close,daemon=True).start()
        else: flash(f"Błąd: {msg}")
        return redirect("/pojenie")


    # ─── SUPLA ────────────────────────────────────────────────────────────────
    @app.route("/supla")
    @farm_required
    def supla():
        g=gid(); db=get_db()
        configs=db.execute("SELECT s.*,u.nazwa as urz_nazwa FROM supla_config s LEFT JOIN urzadzenia u ON s.powiazane_urzadzenie_id=u.id WHERE s.gospodarstwo_id=? ORDER BY s.nazwa",(g,)).fetchall()
        logi=db.execute("SELECT * FROM supla_log WHERE gospodarstwo_id=? ORDER BY czas DESC LIMIT 20",(g,)).fetchall()
        token=get_setting("supla_webhook_token","",g); db.close(); host=request.host
        w="".join(f'<tr><td style="font-weight:500">{c["nazwa"]}</td><td><code>{c["channel_id"] or "—"}</code></td>'
            f'<td>{c["urz_nazwa"] or "—"} / {c["powiazany_kanal"] or "—"}</td>'
            f'<td><span class="badge {"b-green" if c["ostatni_stan"] else "b-gray"}">{"ON" if c["ostatni_stan"] else "OFF"}</span></td>'
            f'<td class="nowrap"><a href="/supla/{c["id"]}/edytuj" class="btn bo bsm">Edytuj</a> '
            f'<a href="/supla/{c["id"]}/usun" class="btn br bsm" onclick="return confirm(\'Usunąć?\')">✕</a></td></tr>'
            for c in configs)
        wl="".join(f'<tr><td style="font-size:11px">{l["czas"][:16]}</td><td><code>{l["channel_id"] or ""}</code></td>'
            f'<td>{l["action_raw"] or ""}</td><td><span class="badge {"b-green" if l["stan"] else "b-gray"}">{"ON" if l["stan"] else "OFF"}</span></td></tr>'
            for l in logi)
        html=('<h1>Supla — webhook</h1>'
            '<div class="card" style="border-left:3px solid #534AB7;border-radius:0 12px 12px 0">'
            f'<b>URL webhooka</b><p style="margin-top:8px"><code style="background:#EEEDFE;padding:4px 10px;border-radius:6px;font-size:14px">https://{host}/webhook/supla</code></p>'
            '<p style="font-size:12px;color:#5f5e5a;margin-top:6px">'
            'Supla Cloud → Kanał → Akcje bezpośrednie → Wyślij żądanie HTTP → POST<br>'
            f'Nagłówek: <code>X-Supla-Token: {token or "ustaw_poniżej"}</code><br>'
            'Treść: <code>{"channel_id": {{channel_id}}, "action": "{{action}}", "state": {{value}}}</code></p></div>'
            '<div class="card"><b>Token zabezpieczający webhook</b>'
            '<form method="POST" action="/supla/token" style="display:flex;gap:8px;margin-top:8px;flex-wrap:wrap">'
            f'<input name="token" value="{token}" placeholder="Losowy ciąg znaków" style="flex:1">'
            '<button class="btn bp bsm">Zapisz token</button></form></div>'
            '<a href="/supla/dodaj" class="btn bp bsm" style="margin-bottom:12px">+ Dodaj kanał Supla</a>'
            '<div class="card" style="overflow-x:auto"><b>Kanały</b>'
            '<table style="margin-top:8px"><thead><tr><th>Nazwa</th><th>Channel ID</th><th>Urządzenie/Kanał</th><th>Stan</th><th></th></tr></thead>'
            f'<tbody>{w or "<tr><td colspan=5 style=\'color:#888;text-align:center;padding:16px\'>Brak konfiguracji</td></tr>"}</tbody></table></div>'
            '<div class="card" style="overflow-x:auto"><b>Log webhooków</b>'
            '<table style="margin-top:8px"><thead><tr><th>Czas</th><th>Channel</th><th>Akcja</th><th>Stan</th></tr></thead>'
            f'<tbody>{wl or "<tr><td colspan=4 style=\'color:#888;padding:10px\'>Brak</td></tr>"}</tbody></table></div>')
        return R(html,"gpio")

    @app.route("/supla/token", methods=["POST"])
    @farm_required
    def supla_token():
        g=gid(); save_setting("supla_webhook_token",request.form.get("token","").strip(),g)
        flash("Token zapisany."); return redirect("/supla")

    @app.route("/supla/dodaj", methods=["GET","POST"])
    @farm_required
    def supla_dodaj():
        g=gid()
        if request.method=="POST":
            db=get_db()
            db.execute("INSERT INTO supla_config(gospodarstwo_id,nazwa,channel_id,powiazane_urzadzenie_id,powiazany_kanal,aktywny) VALUES(?,?,?,?,?,1)",
                (g,request.form["nazwa"],int(request.form.get("channel_id",0) or 0),
                 request.form.get("urzadzenie_id") or None,request.form.get("kanal","") or None))
            db.commit(); db.close(); flash("Kanał Supla dodany."); return redirect("/supla")
        db=get_db(); urzadz=db.execute("SELECT id,nazwa FROM urzadzenia WHERE gospodarstwo_id=? AND aktywne=1",(g,)).fetchall(); db.close()
        u_opt='<option value="">— brak —</option>'+"".join(f'<option value="{u["id"]}">{u["nazwa"]}</option>' for u in urzadz)
        k_opt="".join(f'<option value="relay{i}">relay{i}</option>' for i in range(1,5))
        html=(f'<h1>Nowy kanał Supla</h1><div class="card"><form method="POST">'
            '<label>Nazwa (opis)</label><input name="nazwa" required placeholder="np. Światło kurnik">'
            '<label>Channel ID z Supla Cloud</label><input name="channel_id" type="number" required>'
            f'<div class="g2"><div><label>Urządzenie slave</label><select name="urzadzenie_id">{u_opt}</select></div>'
            f'<div><label>Kanał urządzenia</label><select name="kanal">{k_opt}</select></div></div>'
            '<br><button class="btn bp">Dodaj</button><a href="/supla" class="btn bo" style="margin-left:8px">Anuluj</a></form></div>')
        return R(html,"gpio")

    @app.route("/supla/<int:sid>/edytuj", methods=["GET","POST"])
    @farm_required
    def supla_edytuj(sid):
        g=gid(); db=get_db()
        if request.method=="POST":
            db.execute("UPDATE supla_config SET nazwa=?,channel_id=?,powiazane_urzadzenie_id=?,powiazany_kanal=?,aktywny=? WHERE id=? AND gospodarstwo_id=?",
                (request.form["nazwa"],int(request.form.get("channel_id",0) or 0),
                 request.form.get("urzadzenie_id") or None,request.form.get("kanal","") or None,
                 1 if request.form.get("aktywny") else 0,sid,g))
            db.commit(); db.close(); flash("Zaktualizowano."); return redirect("/supla")
        c=db.execute("SELECT * FROM supla_config WHERE id=? AND gospodarstwo_id=?",(sid,g)).fetchone()
        urzadz=db.execute("SELECT id,nazwa FROM urzadzenia WHERE gospodarstwo_id=? AND aktywne=1",(g,)).fetchall(); db.close()
        if not c: return redirect("/supla")
        u_opt='<option value="">— brak —</option>'+"".join(f'<option value="{u["id"]}" {"selected" if c["powiazane_urzadzenie_id"]==u["id"] else ""}>{u["nazwa"]}</option>' for u in urzadz)
        k_opt="".join(f'<option value="relay{i}" {"selected" if c["powiazany_kanal"]==f"relay{i}" else ""}>relay{i}</option>' for i in range(1,5))
        html=(f'<h1>Edytuj kanał Supla</h1><div class="card"><form method="POST">'
            f'<label>Nazwa</label><input name="nazwa" required value="{c["nazwa"]}">'
            f'<label>Channel ID</label><input name="channel_id" type="number" value="{c["channel_id"] or ""}">'
            f'<div class="g2"><div><label>Urządzenie slave</label><select name="urzadzenie_id">{u_opt}</select></div>'
            f'<div><label>Kanał</label><select name="kanal">{k_opt}</select></div></div>'
            f'<label style="display:flex;align-items:center;gap:8px;margin-top:10px"><input type="checkbox" name="aktywny" {"checked" if c["aktywny"] else ""}> Aktywna</label>'
            '<br><button class="btn bp">Zapisz</button><a href="/supla" class="btn bo" style="margin-left:8px">Anuluj</a></form></div>')
        return R(html,"gpio")

    @app.route("/supla/<int:sid>/usun")
    @farm_required
    def supla_usun(sid):
        g=gid(); db=get_db()
        db.execute("DELETE FROM supla_config WHERE id=? AND gospodarstwo_id=?",(sid,g))
        db.commit(); db.close(); flash("Usunięto."); return redirect("/supla")

    @app.route("/webhook/supla", methods=["POST","GET"])
    def webhook_supla():
        # Obsłuż oba formaty: JSON i form-encoded
        ct = request.content_type or ""
        if "json" in ct:
            data = request.get_json(force=True, silent=True) or {}
        else:
            # form-encoded lub query string (GET dla testów)
            data = {}
            for key in ["channel_id","action","state","value","hi"]:
                v = request.form.get(key) or request.args.get(key)
                if v is not None:
                    data[key] = v

        # Parsuj channel_id
        raw_ch = data.get("channel_id") or data.get("channel",{}).get("id") if isinstance(data.get("channel"),dict) else data.get("channel_id")
        try: channel_id = int(raw_ch) if raw_ch is not None else None
        except: channel_id = None

        # Parsuj stan ON/OFF z różnych pól
        action = str(data.get("action","")).upper()
        state_raw = data.get("state")
        hi_raw = data.get("hi")
        value_raw = data.get("value")

        if action in ("TURN_ON","ON","1","HIGH"):   stan = True
        elif action in ("TURN_OFF","OFF","0","LOW"): stan = False
        elif state_raw is not None:
            if isinstance(state_raw, bool): stan = state_raw
            else: stan = str(state_raw).lower() in ("1","true","on","high")
        elif hi_raw is not None:
            stan = str(hi_raw).lower() in ("1","true","on")
        elif value_raw is not None:
            stan = str(value_raw).lower() in ("1","true","on","high")
        else:
            stan = None

        if channel_id is None:
            return jsonify({"ok":False,"msg":"no channel_id","received":data}), 400

        db = get_db()

        # Weryfikacja tokenu
        tok = db.execute(
            "SELECT wartosc FROM ustawienia WHERE klucz='supla_webhook_token' ORDER BY gospodarstwo_id DESC LIMIT 1"
        ).fetchone()
        req_token = (request.headers.get("X-Supla-Token","") or
                     request.headers.get("Authorization","").replace("Bearer ","") or
                     request.args.get("token",""))
        if tok and tok["wartosc"] and req_token != tok["wartosc"]:
            db.close()
            return jsonify({"ok":False,"msg":"invalid token","hint":"Set X-Supla-Token header"}), 403

        # Znajdź konfigurację
        cfg = db.execute(
            "SELECT * FROM supla_config WHERE channel_id=? AND aktywny=1", (channel_id,)
        ).fetchone()

        # Zaloguj
        db.execute(
            "INSERT INTO supla_log(czas,channel_id,action_raw,stan,payload,gospodarstwo_id) VALUES(?,?,?,?,?,?)",
            (datetime.now().isoformat(), channel_id, action,
             1 if stan else 0, json.dumps(data), cfg["gospodarstwo_id"] if cfg else None)
        )
        db.commit()

        wynik = {"ok":True,"channel_id":channel_id,"stan":stan,"action":action}

        if cfg and stan is not None and cfg["powiazane_urzadzenie_id"] and cfg["powiazany_kanal"]:
            ok2, msg2 = _send(cfg["powiazane_urzadzenie_id"], cfg["powiazany_kanal"], stan, cfg["gospodarstwo_id"])
            wynik["slave_ok"] = ok2; wynik["slave_msg"] = msg2
            if ok2:
                db2 = get_db()
                db2.execute("UPDATE supla_config SET ostatni_stan=? WHERE id=?", (1 if stan else 0, cfg["id"]))
                db2.commit(); db2.close()
        elif not cfg:
            wynik["warning"] = f"Brak konfiguracji dla channel_id={channel_id}"

        db.close()
        return jsonify(wynik)

    # ─── ESPHOME ─────────────────────────────────────────────────────────────
    @app.route("/integracje/esphome")
    @farm_required
    def esphome_page():
        html=('<h1>ESPHome — integracja</h1>'
            '<div class="card" style="border-left:3px solid #534AB7;border-radius:0 12px 12px 0"><b>Jak podłączyć ESPHome</b>'
            '<ol style="font-size:13px;color:#5f5e5a;margin:10px 0;list-style:decimal;margin-left:18px;line-height:2.2">'
            '<li>Pobierz szablon YAML → wgraj przez <code>esphome run kurnik_a.yaml</code></li>'
            '<li>Edytuj SSID, hasło WiFi i api_password w pliku secrets.yaml</li>'
            '<li>Panel → Sterowanie → Urządzenia → <b>Dodaj</b> → typ <b>ESPHome</b></li>'
            '<li>Wpisz IP urządzenia i api_password jako API Key</li>'
            '<li>Sterowanie → wybierz tryb <b>ESPHome REST</b> dla każdego kanału</li>'
            '</ol><a href="/integracje/esphome/config" class="btn bp bsm">Pobierz kurnik_a.yaml</a></div>'
            f'<div class="card"><b>Szablon konfiguracji</b><pre style="background:#f5f5f0;border-radius:8px;padding:14px;font-size:11px;overflow-x:auto;border:1px solid #e0ddd4;white-space:pre">{_ESPHOME_YAML}</pre></div>'
            '<div class="card"><b>ZeroTier / Tailscale — urządzenia w innej sieci</b>'
            '<pre style="background:#f5f5f0;border-radius:8px;padding:14px;font-size:12px;border:1px solid #e0ddd4;white-space:pre-wrap">'
            'Tailscale:\n  curl -fsSL https://tailscale.com/install.sh | sh\n  sudo tailscale up\n  sudo tailscale status\n\n'
            'ESP32 nie obsługuje Tailscale — użyj RPi jako gateway\nlub Cloudflare Tunnel per urządzenie.</pre></div>')
        return R(html,"gpio")

    @app.route("/integracje/esphome/config")
    @farm_required
    def esphome_config_download():
        return send_file(io.BytesIO(_ESPHOME_YAML.encode()),mimetype="text/yaml",as_attachment=True,download_name="kurnik_a.yaml")


    # ─── ANALITYKA ───────────────────────────────────────────────────────────
    @app.route("/analityka")
    @farm_required
    def analityka():
        g=gid(); db=get_db()
        kur=db.execute("SELECT COALESCE(SUM(liczba),0) as s FROM stado WHERE gospodarstwo_id=? AND aktywne=1 AND gatunek='nioski'",(g,)).fetchone()["s"] or 1
        prod=db.execute("SELECT data,jaja_zebrane,jaja_sprzedane,pasza_wydana_kg,ROUND(CAST(jaja_zebrane AS REAL)/?*100,1) as niesnosc FROM produkcja WHERE gospodarstwo_id=? ORDER BY data DESC LIMIT 90",(kur,g)).fetchall()
        wyd_kat=db.execute("SELECT kategoria,SUM(wartosc_total) as suma FROM wydatki WHERE gospodarstwo_id=? AND data>=date('now','-12 months') GROUP BY kategoria ORDER BY suma DESC",(g,)).fetchall()
        mies=db.execute("SELECT strftime('%Y-%m',data) as m,SUM(jaja_sprzedane*cena_sprzedazy) as p FROM produkcja WHERE gospodarstwo_id=? AND data>=date('now','-12 months') GROUP BY m ORDER BY m",(g,)).fetchall()
        mies_w=db.execute("SELECT strftime('%Y-%m',data) as m,SUM(wartosc_total) as w FROM wydatki WHERE gospodarstwo_id=? AND data>=date('now','-12 months') GROUP BY m ORDER BY m",(g,)).fetchall()
        db.close()
        prod_r=list(reversed(prod))
        daty=[r["data"] for r in prod_r]; niesn=[r["niesnosc"] for r in prod_r]
        zebrane=[r["jaja_zebrane"] for r in prod_r]; pasza=[r["pasza_wydana_kg"] for r in prod_r]
        wl=[r["kategoria"] for r in wyd_kat]; wv=[round(r["suma"],2) for r in wyd_kat]
        md={r["m"]:round(r["p"] or 0,2) for r in mies}; wd={r["m"]:round(r["w"] or 0,2) for r in mies_w}
        all_m=sorted(set(list(md)+list(wd)))
        pv=[md.get(m,0) for m in all_m]; wv2=[wd.get(m,0) for m in all_m]
        zv=[round(p-w,2) for p,w in zip(pv,wv2)]
        _mn=["","Sty","Lut","Mar","Kwi","Maj","Cze","Lip","Sie","Wrz","Paź","Lis","Gru"]
        def _pm(ym):
            try: y,m=ym.split("-"); return _mn[int(m)]+"'"+y[2:]
            except: return ym
        ml=[_pm(m) for m in all_m]
        _kol={"Zboże/pasza":"#534AB7","Witaminy/suplementy":"#1D9E75","Weterynarz":"#D85A30","Wyposażenie":"#BA7517","Prąd/gaz":"#185FA5","Ściółka":"#888780","Inne":"#9a9890"}
        wc=[_kol.get(l,"#AFA9EC") for l in wl]
        import json as _j
        html=('<h1>Wykresy i analityka</h1>'
            '<div class="card"><b>Nieśność i zebrane jaja — ostatnie 90 dni</b><canvas id="ch1" height="80"></canvas></div>'
            '<div class="g2"><div class="card"><b>Wydatki wg kategorii — 12 mies.</b><canvas id="ch2" height="160"></canvas></div>'
            '<div class="card"><b>Przychody vs wydatki — 12 mies.</b><canvas id="ch3" height="160"></canvas></div></div>'
            '<div class="card"><b>Zużycie paszy — 90 dni (kg)</b><canvas id="ch4" height="70"></canvas></div>'
            '<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script><script>'
            f'const DATY={_j.dumps(daty)},NIESN={_j.dumps(niesn)},ZEBR={_j.dumps(zebrane)},PASZA={_j.dumps(pasza)};'
            f'const WL={_j.dumps(wl)},WV={_j.dumps(wv)},WC={_j.dumps(wc)};'
            f'const ML={_j.dumps(ml)},PV={_j.dumps(pv)},WV2={_j.dumps(wv2)},ZV={_j.dumps(zv)};'
            'const F={family:"system-ui,sans-serif",size:12},G={color:"rgba(0,0,0,0.06)"};Chart.defaults.font=F;'
            'new Chart(document.getElementById("ch1"),{type:"line",data:{labels:DATY,datasets:['
            '{label:"Nieśność %",data:NIESN,borderColor:"#534AB7",backgroundColor:"rgba(83,74,183,0.08)",tension:0.3,pointRadius:2,yAxisID:"y1"},'
            '{label:"Zebrane szt.",data:ZEBR,borderColor:"#1D9E75",backgroundColor:"rgba(29,158,117,0.08)",tension:0.3,pointRadius:2,yAxisID:"y2"}]},'
            'options:{responsive:true,interaction:{mode:"index"},scales:{y1:{position:"left",grid:G},y2:{position:"right",grid:{drawOnChartArea:false}}},plugins:{legend:{labels:{font:F}}}}});'
            'new Chart(document.getElementById("ch2"),{type:"doughnut",data:{labels:WL,datasets:[{data:WV,backgroundColor:WC,borderWidth:2}]},options:{responsive:true,plugins:{legend:{position:"right",labels:{font:F,boxWidth:12}}}}});'
            'new Chart(document.getElementById("ch3"),{type:"bar",data:{labels:ML,datasets:['
            '{label:"Przychód",data:PV,backgroundColor:"rgba(29,158,117,0.7)"},'
            '{label:"Wydatki",data:WV2,backgroundColor:"rgba(216,90,48,0.7)"},'
            '{label:"Zysk",data:ZV,type:"line",borderColor:"#534AB7",tension:0.3,pointRadius:3}]},'
            'options:{responsive:true,scales:{y:{grid:G}},plugins:{legend:{labels:{font:F}}}}});'
            'new Chart(document.getElementById("ch4"),{type:"bar",data:{labels:DATY,datasets:[{label:"Pasza (kg)",data:PASZA,backgroundColor:"rgba(186,117,23,0.6)",borderRadius:3}]},options:{responsive:true,scales:{y:{grid:G}},plugins:{legend:{labels:{font:F}}}}});'
            '</script>')
        return R(html,"ana")

    # ─── PASZA ROCZNE + ANALITYKA ─────────────────────────────────────────────
    @app.route("/pasza/receptura/<int:rid>/sezon-form", methods=["GET","POST"])
    @farm_required
    def pasza_sezon_form(rid):
        g=gid(); db=get_db()
        if request.method=="POST":
            db.execute("UPDATE receptura SET sezon_stosowania=?,miesiac_od=?,miesiac_do=? WHERE id=? AND gospodarstwo_id=?",
                (request.form.get("sezon_stosowania",""),request.form.get("miesiac_od",""),request.form.get("miesiac_do",""),rid,g))
            db.commit(); db.close(); flash("Sezon zapisany."); return redirect("/pasza/receptury")
        r=db.execute("SELECT * FROM receptura WHERE id=? AND gospodarstwo_id=?",(rid,g)).fetchone(); db.close()
        if not r: return redirect("/pasza/receptury")
        SEZONY=[("caly_rok","Cały rok"),("wiosna","Wiosna (mar-maj)"),("lato","Lato (cze-sie)"),("jesien","Jesień (wrz-lis)"),("zima","Zima (gru-lut)")]
        MIES=[(i,n) for i,n in [(1,"Styczeń"),(2,"Luty"),(3,"Marzec"),(4,"Kwiecień"),(5,"Maj"),(6,"Czerwiec"),(7,"Lipiec"),(8,"Sierpień"),(9,"Wrzesień"),(10,"Październik"),(11,"Listopad"),(12,"Grudzień")]]
        s_opt="".join(f'<option value="{v}" {"selected" if (r.get("sezon_stosowania") or "caly_rok")==v else ""}>{l}</option>' for v,l in SEZONY)
        m_od="".join(f'<option value="{nr}" {"selected" if str(r.get("miesiac_od",""))==str(nr) else ""}>{n}</option>' for nr,n in MIES)
        m_do="".join(f'<option value="{nr}" {"selected" if str(r.get("miesiac_do",""))==str(nr) else ""}>{n}</option>' for nr,n in MIES)
        html=(f'<h1>Sezon: {r["nazwa"]}</h1><div class="card"><form method="POST">'
            f'<label>Sezon stosowania</label><select name="sezon_stosowania">{s_opt}</select>'
            f'<div class="g2"><div><label>Od miesiąca</label><select name="miesiac_od"><option value="">—</option>{m_od}</select></div>'
            f'<div><label>Do miesiąca</label><select name="miesiac_do"><option value="">—</option>{m_do}</select></div></div>'
            '<br><button class="btn bp">Zapisz</button><a href="/pasza/receptury" class="btn bo" style="margin-left:8px">Anuluj</a></form></div>')
        return R(html,"pasza")

    @app.route("/pasza/skladniki-roczne")
    @farm_required
    def pasza_skladniki_roczne():
        g=gid(); db=get_db()
        pdz=float(gs("pasza_dzienna_kg","6")); kg_rok=pdz*365
        recs=db.execute("SELECT * FROM receptura WHERE gospodarstwo_id=? ORDER BY aktywna DESC,nazwa",(g,)).fetchall()
        html_rek=""
        for r in recs:
            sklady=db.execute("SELECT rs.procent,sm.nazwa,sm.stan,sm.cena_aktualna FROM receptura_skladnik rs JOIN stan_magazynu sm ON rs.magazyn_id=sm.id WHERE rs.receptura_id=? ORDER BY rs.procent DESC",(r["id"],)).fetchall()
            if not sklady: continue
            wiersze=""
            for s in sklady:
                pct=float(s["procent"] or 0); kg_r=round(kg_rok*pct,1); kg_m=round(kg_r/12,1)
                cena=float(s["cena_aktualna"] or 0); koszt=round(kg_r*cena,0)
                stan=float(s["stan"] or 0); wyst=round(stan/(kg_rok*pct/365),0) if pct>0 and stan>0 else 0
                kol2="#A32D2D" if stan<kg_m else "#3B6D11"
                wiersze+=(f'<tr><td style="font-weight:500">{s["nazwa"]}</td>'
                    f'<td style="text-align:right">{round(pct*100,1)}%</td>'
                    f'<td style="text-align:right;font-weight:500">{kg_r} kg</td>'
                    f'<td style="text-align:right">{kg_m} kg</td>'
                    f'<td style="text-align:right;color:{kol2}">{round(stan,1)} kg</td>'
                    f'<td style="text-align:right">{int(wyst)+" dni" if wyst>0 else "—"}</td>'
                    f'<td style="text-align:right;color:#5f5e5a">{int(koszt)+" zł" if koszt>0 else "—"}</td></tr>')
            html_rek+=(f'<div class="card"><div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">'
                f'<b>{r["nazwa"]}</b>{"<span class=\'badge b-green\'>Aktywna</span>" if r["aktywna"] else ""}'
                f'<a href="/pasza/receptura/{r["id"]}/sezon-form" class="btn bo bsm" style="margin-left:auto">Sezon</a></div>'
                f'<p style="font-size:12px;color:#888;margin-bottom:8px">Przy {pdz} kg/dzień → <b>{round(kg_rok,0)} kg/rok</b></p>'
                f'<div style="overflow-x:auto"><table style="font-size:13px"><thead><tr>'
                f'<th>Składnik</th><th style="text-align:right">%</th><th style="text-align:right">Rocznie</th>'
                f'<th style="text-align:right">Miesięcznie</th><th style="text-align:right">W magazynie</th>'
                f'<th style="text-align:right">Wystarczy</th><th style="text-align:right">Koszt/rok</th>'
                f'</tr></thead><tbody>{wiersze}</tbody></table></div></div>')
        db.close()
        html=('<h1>Zapotrzebowanie roczne</h1>'+(html_rek or '<div class="card"><p style="color:#888">Brak receptur z składnikami.</p></div>')
            +'<a href="/pasza/receptury" class="btn bo bsm">← Receptury</a>')
        return R(html,"pasza")

    @app.route("/pasza/analityka")
    @farm_required
    def pasza_analityka_page():
        g=gid(); db=get_db()
        rec=db.execute("SELECT * FROM receptura WHERE gospodarstwo_id=? AND aktywna=1 LIMIT 1",(g,)).fetchone()
        if not rec:
            db.close()
            return R('<h1>Analityka paszy</h1><div class="card"><p style="color:#888">Brak aktywnej receptury. <a href="/pasza/receptury" style="color:#534AB7">Dodaj i aktywuj recepturę</a>.</p></div>',"ana")
        sklady=db.execute("""SELECT rs.procent,sm.nazwa,
            COALESCE(sb.bialko_pct,0) as bialko,COALESCE(sb.energia_me,0) as energia,
            COALESCE(sb.wapn_g_kg,0) as wapn,COALESCE(sb.fosfor_g_kg,0) as fosfor,
            COALESCE(sb.lizyna_g_kg,0) as lizyna,COALESCE(sb.metionina_g_kg,0) as met,
            COALESCE(sb.cena_pln_t,0) as cena_t
            FROM receptura_skladnik rs JOIN stan_magazynu sm ON rs.magazyn_id=sm.id
            LEFT JOIN skladniki_baza sb ON LOWER(TRIM(sb.nazwa))=LOWER(TRIM(sm.nazwa))
            WHERE rs.receptura_id=?""",(rec["id"],)).fetchall()
        db.close()
        wyniki={"bialko":0,"energia":0,"wapn":0,"fosfor":0,"lizyna":0,"met":0,"koszt":0}
        for s in sklady:
            p=float(s["procent"] or 0)
            wyniki["bialko"]  +=s["bialko"]*p
            wyniki["energia"] +=s["energia"]*p
            wyniki["wapn"]    +=s["wapn"]*p*10
            wyniki["fosfor"]  +=s["fosfor"]*p*10
            wyniki["lizyna"]  +=s["lizyna"]*p*10
            wyniki["met"]     +=s["met"]*p*10
            wyniki["koszt"]   +=s["cena_t"]*p
        N=_NORMY
        def _bar(val,mn,mx=None,unit=""):
            if not val: return f'<span style="color:#888;font-size:12px">Brak danych</span>'
            mx2=mx or mn*1.5
            pct=min(100,max(0,(val-mn*0.7)/(mx2*1.3-mn*0.7)*100))
            kol="#3B6D11" if mn<=val<=(mx or val*1.5) else "#A32D2D"
            return (f'<div style="display:flex;align-items:center;gap:8px;margin:3px 0">'
                    f'<div style="width:100px;background:#e0ddd4;border-radius:4px;height:8px">'
                    f'<div style="width:{pct:.0f}%;background:{kol};height:100%;border-radius:4px"></div></div>'
                    f'<span style="font-size:13px;color:{kol};font-weight:500">{val:.1f}{unit}</span>'
                    f'<span style="font-size:11px;color:#888">({mn:.0f}–{mx or "?"})</span></div>')
        reks=[]
        if wyniki["bialko"]<N["b_min"]: reks.append(("🔴","Białko za niskie","Zwiększ groch lub łubin (+2%)"))
        elif wyniki["bialko"]>N["b_max"]: reks.append(("🟡","Białko za wysokie","Zmniejsz białkowe na rzecz kukurydzy"))
        if wyniki["wapn"]<N["ca_min"]: reks.append(("🔴","Wapń za niski — miękkie skorupki!","Zwiększ kredę pastewną"))
        if wyniki["energia"]<N["e_min"]: reks.append(("🟡","Energia za niska","Zwiększ kukurydzę lub dodaj tłuszcz"))
        if wyniki["lizyna"]<N["liz_min"]: reks.append(("🟡","Lizyna za mała","Dodaj drożdże browarniane (+0.2%)"))
        if not reks: reks.append(("✅","Receptura w normach","Składniki w prawidłowych proporcjach"))
        r_html="".join(
            f'<div style="border-left:3px solid {"#A32D2D" if ico=="🔴" else "#BA7517" if ico=="🟡" else "#3B6D11"};'
            f'padding:8px 12px;border-radius:0 8px 8px 0;margin-bottom:8px;background:#fafaf8">'
            f'<div style="font-weight:500;font-size:13px">{ico} {problem}</div>'
            f'<div style="font-size:13px;color:#5f5e5a;margin-top:3px">{rozw}</div></div>'
            for ico,problem,rozw in reks)
        html=(f'<h1>Analityka paszy — {rec["nazwa"]}</h1><div class="g2">'
            '<div class="card"><b>Wartości odżywcze</b><div style="margin-top:10px">'
            f'<p style="font-size:12px;color:#5f5e5a">Białko surowe (%)</p>'+_bar(wyniki["bialko"],N["b_min"],N["b_max"],"%")
            +f'<p style="font-size:12px;color:#5f5e5a;margin-top:6px">Energia ME (kcal/kg)</p>'+_bar(wyniki["energia"],N["e_min"],N["e_max"])
            +f'<p style="font-size:12px;color:#5f5e5a;margin-top:6px">Wapń (g/kg)</p>'+_bar(wyniki["wapn"],N["ca_min"],N["ca_max"]," g/kg")
            +f'<p style="font-size:12px;color:#5f5e5a;margin-top:6px">Fosfor (g/kg)</p>'+_bar(wyniki["fosfor"],N["p_min"],N["p_min"]*1.5," g/kg")
            +f'<p style="font-size:12px;color:#5f5e5a;margin-top:6px">Lizyna (g/kg)</p>'+_bar(wyniki["lizyna"],N["liz_min"],N["liz_min"]*1.5," g/kg")
            +f'<div style="margin-top:12px;font-size:13px;color:#5f5e5a">Koszt: <b>{round(wyniki["koszt"],0)} PLN/T</b></div></div></div>'
            f'<div class="card"><b>Rekomendacje</b><div style="margin-top:10px">{r_html}</div></div></div>'
            '<div style="display:flex;gap:8px;margin-top:8px">'
            '<a href="/pasza/skladniki-baza" class="btn bo bsm">Baza składników</a>'
            '<a href="/pasza/receptury" class="btn bo bsm">← Receptury</a></div>')
        return R(html,"ana")

    @app.route("/pasza/skladniki-baza")
    @farm_required
    def pasza_skladniki_baza():
        db=get_db(); rows=db.execute("SELECT * FROM skladniki_baza ORDER BY kategoria,nazwa").fetchall(); db.close()
        kat_map={"zboze":"Zboża","bialkowe":"Białkowe","mineralne":"Mineralne","premiks":"Premiksy","naturalny_dodatek":"Naturalne dodatki","inne":"Inne"}
        bkat=None; w=""
        for s in rows:
            if s["kategoria"]!=bkat:
                bkat=s["kategoria"]
                w+=('<tr><td colspan=8 style="background:#f5f5f0;font-weight:500;font-size:12px;color:#534AB7;padding:8px">'+kat_map.get(bkat,bkat or "Inne")+'</td></tr>')
            w+=('<tr>'
                '<td style="font-weight:500">'+s["nazwa"]+'</td>'
                '<td>'+str(round(s["cena_pln_t"],0))+' PLN/T</td>'
                '<td>'+str(round(s["bialko_pct"],1))+'%</td>'
                '<td>'+str(round(s["energia_me"],0))+'</td>'
                '<td>'+str(round(s["wapn_g_kg"],1))+'</td>'
                '<td>'+str(round(s["fosfor_g_kg"],1))+'</td>'
                '<td style="font-size:11px;color:#888">'+((s["uwagi"] or "")[:35])+'</td>'
                '<td class="nowrap">'
                '<a href="/pasza/skladnik-baza/'+str(s["id"])+'/edytuj" class="btn bo bsm">Edytuj</a></td></tr>')
        html=('<h1>Baza składników paszy</h1>'
            '<a href="/pasza/skladnik-baza/dodaj" class="btn bp bsm" style="margin-bottom:12px">+ Dodaj składnik</a>'
            '<div class="card" style="overflow-x:auto"><table><thead><tr>'
            '<th>Składnik</th><th>Cena PLN/T</th><th>Białko%</th><th>ME kcal/kg</th>'
            '<th>Ca g/kg</th><th>P g/kg</th><th>Uwagi</th><th></th></tr></thead>'
            f'<tbody>{w}</tbody></table></div>')
        return R(html,"ana")

    @app.route("/pasza/skladnik-baza/dodaj", methods=["GET","POST"])
    @app.route("/pasza/skladnik-baza/<int:sid>/edytuj", methods=["GET","POST"])
    @farm_required
    def pasza_skladnik_baza_form(sid=None):
        db=get_db()
        if request.method=="POST":
            f=request.form
            vals=(f["nazwa"],f.get("kategoria","inne"),
                  float(f.get("cena_pln_t",0) or 0),
                  float(f.get("bialko_pct",0) or 0),float(f.get("energia_me",0) or 0),
                  float(f.get("tluszcz_pct",0) or 0),float(f.get("wlokno_pct",0) or 0),
                  float(f.get("wapn_g_kg",0) or 0),float(f.get("fosfor_g_kg",0) or 0),
                  float(f.get("lizyna_g_kg",0) or 0),float(f.get("metionina_g_kg",0) or 0),
                  f.get("uwagi",""))
            if sid:
                db.execute("UPDATE skladniki_baza SET nazwa=?,kategoria=?,cena_pln_t=?,bialko_pct=?,energia_me=?,tluszcz_pct=?,wlokno_pct=?,wapn_g_kg=?,fosfor_g_kg=?,lizyna_g_kg=?,metionina_g_kg=?,uwagi=? WHERE id=?",(*vals,sid))
            else:
                db.execute("INSERT INTO skladniki_baza(nazwa,kategoria,cena_pln_t,bialko_pct,energia_me,tluszcz_pct,wlokno_pct,wapn_g_kg,fosfor_g_kg,lizyna_g_kg,metionina_g_kg,uwagi) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",vals)
            db.commit(); db.close(); flash("Składnik zapisany."); return redirect("/pasza/skladniki-baza")
        s=dict(db.execute("SELECT * FROM skladniki_baza WHERE id=?",(sid,)).fetchone()) if sid else {}
        db.close()
        kat_opt="".join('<option value="'+k+'" '+("selected" if s.get("kategoria")==k else "")+'>'+l+'</option>'
            for k,l in [("zboze","Zboże"),("bialkowe","Białkowe"),("mineralne","Mineralne"),("premiks","Premiks"),("naturalny_dodatek","Naturalny dodatek"),("inne","Inne")])
        def fi(label,name,step="0.01"):
            return '<div><label>'+label+'</label><input name="'+name+'" type="number" step="'+step+'" value="'+str(s.get(name,"") or "")+'"></div>'
        html=('<h1>'+("Edytuj składnik" if sid else "Nowy składnik")+'</h1><div class="card"><form method="POST">'
            '<label>Nazwa</label><input name="nazwa" required value="'+s.get("nazwa","")+'">'
            '<div class="g2"><div><label>Kategoria</label><select name="kategoria">'+kat_opt+'</select></div>'
            +fi("Cena PLN/T","cena_pln_t","1")+'</div>'
            '<h2>Wartości odżywcze (na 1 kg)</h2>'
            '<div class="g3">'+fi("Białko (%)","bialko_pct")+fi("Energia ME (kcal/kg)","energia_me","1")+fi("Tłuszcz (%)","tluszcz_pct")+'</div>'
            '<div class="g3">'+fi("Włókno (%)","wlokno_pct")+fi("Wapń Ca (g/kg)","wapn_g_kg")+fi("Fosfor P (g/kg)","fosfor_g_kg")+'</div>'
            '<div class="g2">'+fi("Lizyna (g/kg)","lizyna_g_kg")+fi("Metionina (g/kg)","metionina_g_kg")+'</div>'
            '<label>Uwagi</label><textarea name="uwagi" rows="2">'+s.get("uwagi","")+'</textarea>'
            '<br><button class="btn bp">Zapisz</button><a href="/pasza/skladniki-baza" class="btn bo" style="margin-left:8px">Anuluj</a>'
            '</form></div>')
        return R(html,"ana")


    # ─── MAGAZYN ─────────────────────────────────────────────────────────────
    @app.route("/magazyn")
    @farm_required
    def magazyn():
        g=gid(); db=get_db()
        mag=db.execute("SELECT COALESCE(SUM(jaja_zebrane),0) as p, COALESCE(SUM(jaja_sprzedane),0) as s FROM produkcja WHERE gospodarstwo_id=?",(g,)).fetchone()
        stan=max(0,mag["p"]-mag["s"])
        rez=db.execute("SELECT z.*,k.nazwa as kn FROM zamowienia z LEFT JOIN klienci k ON z.klient_id=k.id WHERE z.gospodarstwo_id=? AND z.status IN ('nowe','potwierdzone') ORDER BY z.data_dostawy",(g,)).fetchall()
        hist=db.execute("SELECT data,jaja_zebrane,jaja_sprzedane FROM produkcja WHERE gospodarstwo_id=? ORDER BY data DESC LIMIT 30",(g,)).fetchall()
        db.close(); zar=sum(r["ilosc"] for r in rez)
        w_rez="".join(f'<tr><td>{r["data_dostawy"]}</td><td>{r["kn"] or "—"}</td>'
            f'<td style="font-weight:500">{r["ilosc"]} szt.</td>'
            f'<td>{round(r["ilosc"]*(r["cena_za_szt"] or 0),2)} zł</td>'
            f'<td><a href="/zamowienia/{r["id"]}/status/dostarczone" class="btn bg bsm">Dostarcz</a></td></tr>' for r in rez)
        w_hist="".join(f'<tr><td>{r["data"]}</td><td>{r["jaja_zebrane"]}</td><td>{r["jaja_sprzedane"]}</td><td>{max(0,r["jaja_zebrane"]-r["jaja_sprzedane"])}</td></tr>' for r in hist)
        html=('<h1>Magazyn jaj</h1>'
            '<div class="g3" style="margin-bottom:12px">'
            f'<div class="card stat"><div class="v" style="color:{"#3B6D11" if stan>0 else "#888"}">{stan}</div><div class="l">Stan magazynu</div></div>'
            f'<div class="card stat"><div class="v" style="color:#BA7517">{zar}</div><div class="l">Zarezerwowane</div></div>'
            f'<div class="card stat"><div class="v" style="color:{"#3B6D11" if stan-zar>=0 else "#A32D2D"}">{max(0,stan-zar)}</div><div class="l">Dostępne</div></div></div>'
            +(f'<div class="card"><b>Zaplanowane dostawy</b><div style="overflow-x:auto"><table style="margin-top:8px"><thead><tr><th>Data</th><th>Klient</th><th>Ilość</th><th>Wartość</th><th></th></tr></thead><tbody>{w_rez}</tbody></table></div></div>' if rez else "")
            +'<div class="card" style="overflow-x:auto"><b>Historia 30 dni</b><table style="margin-top:8px"><thead><tr><th>Data</th><th>Zebrane</th><th>Sprzedane</th><th>Zostało</th></tr></thead>'
            f'<tbody>{w_hist or "<tr><td colspan=4 style=\'color:#888;padding:12px\'>Brak</td></tr>"}</tbody></table></div>')
        return R(html,"mag")

    # ─── USTAWIENIA + KIOSK + IMPORT + ADMIN ─────────────────────────────────
    @app.route("/ustawienia", methods=["GET","POST"])
    @farm_required
    def ustawienia():
        g=gid()
        if request.method=="POST":
            for k in ["pasza_dzienna_kg","cena_jajka","cena_wody_litra","cena_kwh","etykieta_producent","etykieta_adres"]:
                v=request.form.get(k)
                if v is not None: save_setting(k,v.strip(),g)
            flash("Ustawienia zapisane."); return redirect("/ustawienia")
        def _v(k,d): return gs(k,d)
        html=('<h1>Ustawienia</h1><form method="POST">'
            '<div class="card"><b>Produkcja</b><div class="g2" style="margin-top:10px">'
            f'<div><label>Dzienne zużycie paszy (kg)</label><input name="pasza_dzienna_kg" type="number" step="0.1" value="{_v("pasza_dzienna_kg","6")}"></div>'
            f'<div><label>Domyślna cena jajka (zł)</label><input name="cena_jajka" type="number" step="0.01" value="{_v("cena_jajka","1.20")}"></div></div></div>'
            '<div class="card"><b>Ceny mediów</b><div class="g2" style="margin-top:10px">'
            f'<div><label>Cena wody (zł/litr)</label><input name="cena_wody_litra" type="number" step="0.0001" value="{_v("cena_wody_litra","0.005")}"></div>'
            f'<div><label>Cena prądu (zł/kWh)</label><input name="cena_kwh" type="number" step="0.01" value="{_v("cena_kwh","0.80")}"></div></div></div>'
            '<div class="card"><b>Etykiety jaj</b><div class="g2" style="margin-top:10px">'
            f'<div><label>Producent</label><input name="etykieta_producent" value="{_v("etykieta_producent","Ferma Jaj")}"></div>'
            f'<div><label>Adres</label><input name="etykieta_adres" value="{_v("etykieta_adres","")}"></div></div></div>'
            '<button class="btn bp">Zapisz ustawienia</button></form>'
            '<div class="card" style="margin-top:12px"><b>Skróty</b>'
            '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px">'
            '<a href="/import/xlsx" class="btn bo bsm">Import Chicken.xlsx</a>'
            '<a href="/pasza/skladniki-baza" class="btn bo bsm">Baza składników</a></div></div>')
        return R(html,"ust")

    @app.route("/import/xlsx", methods=["GET","POST"])
    @farm_required
    def import_xlsx_route():
        g=gid(); msg_html=""
        if request.method=="POST":
            if "plik" not in request.files: flash("Brak pliku."); return redirect("/import/xlsx")
            plik=request.files["plik"]
            if not plik.filename.endswith(".xlsx"): flash("Tylko .xlsx"); return redirect("/import/xlsx")
            tmp=f"/tmp/ferma_imp_{g}.xlsx"; plik.save(tmp)
            w=_do_import(tmp,g,request.form.get("typ","produkcja"))
            if "error" in w: flash("Błąd: "+w["error"])
            else:
                czesci=[]
                if w.get("produkcja"): czesci.append(f"Produkcja: {w['produkcja']} dni")
                if w.get("sprzedaz"):  czesci.append(f"Sprzedaż: {w['sprzedaz']} transakcji")
                if w.get("koszty"):    czesci.append(f"Koszty: {w['koszty']} wpisów")
                if w.get("receptury"): czesci.append(f"Receptury: {w['receptury']}")
                flash("Import OK — "+(", ".join(czesci) if czesci else "brak danych"))
                if w.get("bledy"):
                    msg_html='<div class="al alw"><b>Pominięte:</b><br>'+"<br>".join(w["bledy"][:5])+"</div>"
        html=(msg_html+'<h1>Import danych z Excel</h1>'
            '<div class="card"><form method="POST" enctype="multipart/form-data">'
            '<label>Plik Excel (.xlsx)</label><input type="file" name="plik" accept=".xlsx" required>'
            '<label>Co importować</label><select name="typ">'
            '<option value="produkcja">Produkcja + sprzedaż + koszty (JAJKA, CHICKEN, Koszta)</option>'
            '<option value="receptury">Receptury paszowe (Paszav2, Paszav3, Pasza Zimowa)</option>'
            '</select><br><button class="btn bp" style="margin-top:12px">Importuj</button></form></div>'
            '<div class="card"><b>Obsługiwane arkusze z Chicken.xlsx</b>'
            '<ul style="font-size:13px;color:#5f5e5a;margin:8px 0;list-style:disc;margin-left:18px;line-height:2">'
            '<li><b>JAJKA</b> — data, jaja, sprzedaż po 1,2zł i 1,0zł, zarobek</li>'
            '<li><b>Koszta</b> — koszty miesięczne wg kategorii</li>'
            '<li><b>Paszav2 / Paszav3 / Pasza Zimowa</b> — receptury z proporcjami</li>'
            '</ul></div>')
        return R(html,"ust")

    def _do_import(filepath,g,typ):
        try: import pandas as pd
        except: return {"error":"pip install pandas openpyxl"}
        if not os.path.exists(filepath): return {"error":"Plik nie istnieje"}
        try: xl=pd.read_excel(filepath,sheet_name=None)
        except Exception as e: return {"error":str(e)}
        wyniki={"produkcja":0,"sprzedaz":0,"koszty":0,"receptury":0,"bledy":[]}
        db=get_db()
        if typ=="produkcja":
            if "JAJKA" in xl:
                df=xl["JAJKA"].dropna(subset=["Data"])
                for _,row in df.iterrows():
                    try:
                        if pd.isna(row.get("Data")): continue
                        d=pd.to_datetime(row["Data"]).strftime("%Y-%m-%d")
                        jaja_raw=row.get("Ilość Jajek")
                        jaja=int(float(jaja_raw)) if jaja_raw is not None and not pd.isna(jaja_raw) else 0
                        s12_raw=row.get("Sprzedane Jajka po 1,2"); s10_raw=row.get("Sprzedane Jajka po 1,0")
                        s12=float(s12_raw) if s12_raw is not None and not pd.isna(s12_raw) else 0.0
                        s10=float(s10_raw) if s10_raw is not None and not pd.isna(s10_raw) else 0.0
                        sprzed=int(s12+s10)
                        zarobek_raw=row.get("Zarobek"); zarobek=float(zarobek_raw) if zarobek_raw is not None and not pd.isna(zarobek_raw) else 0.0
                        cena=round(zarobek/sprzed,2) if sprzed>0 else 0
                        ex=db.execute("SELECT id,jaja_sprzedane FROM produkcja WHERE gospodarstwo_id=? AND data=?",(g,d)).fetchone()
                        if not ex:
                            db.execute("INSERT INTO produkcja(gospodarstwo_id,data,jaja_zebrane,jaja_sprzedane,cena_sprzedazy,pasza_wydana_kg,uwagi) VALUES(?,?,?,?,?,0,'import JAJKA')",(g,d,jaja,sprzed,cena))
                            wyniki["produkcja"]+=1
                            if sprzed>0: wyniki["sprzedaz"]+=1
                        elif (ex["jaja_sprzedane"] or 0)==0 and sprzed>0:
                            db.execute("UPDATE produkcja SET jaja_sprzedane=?,cena_sprzedazy=? WHERE id=?",(sprzed,cena,ex["id"]))
                            wyniki["sprzedaz"]+=1
                    except Exception as e: wyniki["bledy"].append(f"JAJKA: {str(e)[:60]}")
            if "Koszta" in xl:
                df=xl["Koszta"]; hr=None
                for i,row in df.iterrows():
                    if any("zwierz" in str(v).lower() for v in row if not pd.isna(v)): hr=i; break
                if hr is not None:
                    df2=df.iloc[hr:].copy(); df2.columns=[str(v) for v in df2.iloc[0]]; df2=df2.iloc[1:].reset_index(drop=True)
                    mm={"styczeń":1,"luty":2,"marzec":3,"kwiecień":4,"maj":5,"czerwiec":6,"czewiec":6,"lipiec":7,"sierpień":8,"wrzesień":9,"październik":10,"listopad":11,"grudzień":12}
                    rb=None
                    for _,row in df2.iterrows():
                        try:
                            if not pd.isna(row.iloc[1]) and str(row.iloc[1]).strip().isdigit(): rb=int(row.iloc[1])
                            mn=str(row.iloc[2]).strip().lower() if not pd.isna(row.iloc[2]) else ""
                            m_nr=mm.get(mn)
                            if not m_nr or not rb: continue
                            dw=f"{rb}-{m_nr:02d}-01"
                            ki={"Zwierzęta":("Weterynarz",3),"Witaminy":("Witaminy/suplementy",4),"Kreda Pastewna":("Zboże/pasza",5),"Kukurydza":("Zboże/pasza",6),"Pszenica":("Zboże/pasza",7),"Owies":("Zboże/pasza",8),"Jęczmień":("Zboże/pasza",9),"Sorgo":("Zboże/pasza",10)}
                            for naz,(kat,idx) in ki.items():
                                if idx<len(row):
                                    v=row.iloc[idx]
                                    if not pd.isna(v) and float(v or 0)>0:
                                        db.execute("INSERT INTO wydatki(gospodarstwo_id,data,kategoria,nazwa,ilosc,jednostka,cena_jednostkowa,wartosc_total,uwagi) VALUES(?,?,?,?,1,'import',?,?,'import Koszta')",(g,dw,kat,naz,float(v),float(v)))
                                        wyniki["koszty"]+=1
                        except Exception as e: wyniki["bledy"].append(f"Koszta: {str(e)[:60]}")
        elif typ=="receptury":
            import pandas as pd
            ARK={"Paszav2":"Z Soją","Paszav3":"Bez Soi","Pasza Zimowa":"Zimowa"}
            for ark,dom in ARK.items():
                if ark not in xl: continue
                df=xl[ark]
                try:
                    sek=[]
                    for i,row in df.iterrows():
                        c2=str(row.iloc[2]).strip() if len(row)>2 and not pd.isna(row.iloc[2]) else ""
                        if c2 in ["Z Soją","Bez Soji","Bez Soi","V1","Groch wysoko białkowy","Zimowa"]: sek.append((i,c2))
                    if not sek: sek=[(0,dom)]
                    for si,(start,sn) in enumerate(sek):
                        end=sek[si+1][0] if si+1<len(sek) else len(df)
                        sdf=df.iloc[start+2:end]
                        ex2=db.execute("SELECT id FROM receptura WHERE gospodarstwo_id=? AND nazwa=?",(g,sn)).fetchone()
                        rid=ex2["id"] if ex2 else db.execute("INSERT INTO receptura(gospodarstwo_id,nazwa,sezon,aktywna) VALUES(?,?,?,0)",(g,sn,"caly_rok")).lastrowid
                        for _,row in sdf.iterrows():
                            try:
                                skl=str(row.iloc[0]).strip()
                                if not skl or pd.isna(row.iloc[0]) or skl in["nan","Składnik"]: continue
                                pct=float(row.iloc[3] or 0) if len(row)>3 and not pd.isna(row.iloc[3]) else 0
                                if pct<=0: continue
                                mag=db.execute("SELECT id FROM stan_magazynu WHERE gospodarstwo_id=? AND nazwa=?",(g,skl)).fetchone()
                                mid=mag["id"] if mag else db.execute("INSERT INTO stan_magazynu(gospodarstwo_id,kategoria,nazwa,jednostka,stan) VALUES(?,?,?,?,0)",(g,"Zboże/pasza",skl,"kg")).lastrowid
                                if not db.execute("SELECT id FROM receptura_skladnik WHERE receptura_id=? AND magazyn_id=?",(rid,mid)).fetchone():
                                    db.execute("INSERT INTO receptura_skladnik(receptura_id,magazyn_id,procent) VALUES(?,?,?)",(rid,mid,pct))
                            except Exception as e: wyniki["bledy"].append(f"{ark}: {str(e)[:50]}")
                        wyniki["receptury"]+=1
                except Exception as e: wyniki["bledy"].append(f"{ark}: {str(e)[:80]}")
        db.commit(); db.close(); return wyniki

    @app.route("/kiosk")
    @farm_required
    def kiosk():
        g=gid(); db=get_db()
        dzis=db.execute("SELECT * FROM produkcja WHERE gospodarstwo_id=? AND data=date('now')",(g,)).fetchone()
        kur=db.execute("SELECT COALESCE(SUM(liczba),0) as s FROM stado WHERE gospodarstwo_id=? AND aktywne=1 AND gatunek='nioski'",(g,)).fetchone()["s"] or 15
        db.close(); pdz=float(gs("pasza_dzienna_kg","6"))
        niesn=round((dzis["jaja_zebrane"]/kur*100) if dzis and kur else 0,1)
        return ('<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Kiosk</title><style>'
            'body{background:#1a1a2e;color:#e0ddd4;font-family:system-ui;margin:0;padding:20px}'
            '.big{font-size:80px;font-weight:700;color:#7F77DD;line-height:1}'
            '.lbl{font-size:16px;color:#888;margin-top:4px}'
            '.card{background:#16213e;border-radius:16px;padding:24px;text-align:center}'
            '.g2{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}'
            'input{background:#0f3460;color:#e0ddd4;border:1px solid #534AB7;border-radius:10px;padding:14px;font-size:22px;width:100%;text-align:center;box-sizing:border-box}'
            '.btn{display:block;width:100%;padding:20px;font-size:22px;font-weight:700;background:#534AB7;color:#fff;border:none;border-radius:10px;cursor:pointer;margin-top:12px}'
            '</style></head><body>'
            f'<h1 style="text-align:center;color:#7F77DD;margin-bottom:20px">🐓 {date.today().isoformat()}</h1>'
            '<div class="g2">'
            f'<div class="card"><div class="big">{dzis["jaja_zebrane"] if dzis else 0}</div><div class="lbl">Jaja zebrane dziś</div></div>'
            f'<div class="card"><div class="big" style="color:{"#3B6D11" if niesn>=70 else "#A32D2D"}">{niesn}%</div><div class="lbl">Nieśność</div></div></div>'
            '<div class="card"><form method="POST" action="/produkcja/dodaj">'
            f'<input type="hidden" name="data" value="{date.today().isoformat()}">'
            '<p style="color:#888;font-size:14px;margin-bottom:8px">Zebrane jaja</p>'
            f'<input name="jaja_zebrane" type="number" min="0" value="{dzis["jaja_zebrane"] if dzis else ""}" placeholder="wpisz ilość">'
            f'<input name="pasza_wydana_kg" type="hidden" value="{dzis["pasza_wydana_kg"] if dzis else pdz}">'
            '<button class="btn">💾 Zapisz</button></form>'
            '<a href="/" style="display:block;text-align:center;color:#888;margin-top:16px;font-size:14px">← Pełny panel</a></div>'
            '</body></html>')

    @app.route("/admin/farm-assign", methods=["GET","POST"])
    @login_required
    @superadmin_required
    def admin_farm_assign():
        db=get_db()
        if request.method=="POST":
            action=request.form.get("action","add"); uid=request.form.get("uid"); fid=request.form.get("farm_id"); rola=request.form.get("rola","member")
            if action=="add" and uid and fid:
                try:
                    db.execute("INSERT OR REPLACE INTO uzytkownicy_gospodarstwa(uzytkownik_id,gospodarstwo_id,rola) VALUES(?,?,?)",(int(uid),int(fid),rola))
                    db.commit(); flash("Przypisano.")
                except Exception as e: flash("Błąd: "+str(e))
            elif action=="remove" and uid and fid:
                db.execute("DELETE FROM uzytkownicy_gospodarstwa WHERE uzytkownik_id=? AND gospodarstwo_id=?",(int(uid),int(fid)))
                db.commit(); flash("Usunięto.")
            db.close(); return redirect("/admin/farm-assign")
        users=db.execute("SELECT id,login,email,rola FROM uzytkownicy ORDER BY login").fetchall()
        farms=db.execute("SELECT id,nazwa FROM gospodarstwa WHERE aktywne=1 ORDER BY nazwa").fetchall()
        assign=db.execute("""SELECT ug.*,u.login,g.nazwa as fn FROM uzytkownicy_gospodarstwa ug
            JOIN uzytkownicy u ON ug.uzytkownik_id=u.id
            JOIN gospodarstwa g ON ug.gospodarstwo_id=g.id ORDER BY u.login,g.nazwa""").fetchall()
        db.close()
        u_opt="".join(f'<option value="{u["id"]}">{u["login"]} ({u["email"] or ""}) — {u["rola"]}</option>' for u in users)
        f_opt="".join(f'<option value="{f["id"]}">{f["nazwa"]}</option>' for f in farms)
        r_opt="".join(f'<option value="{v}">{l}</option>' for v,l in [("owner","owner — właściciel"),("member","member — pracownik"),("viewer","viewer — tylko odczyt")])
        w="".join(f'<tr><td style="font-weight:500">{a["login"]}</td><td>{a["fn"]}</td>'
            f'<td><span class="badge b-purple">{a["rola"]}</span></td>'
            f'<td><form method="POST" style="display:inline"><input type="hidden" name="action" value="remove">'
            f'<input type="hidden" name="uid" value="{a["uzytkownik_id"]}"><input type="hidden" name="farm_id" value="{a["gospodarstwo_id"]}">'
            f'<button class="btn br bsm" onclick="return confirm(\'Usunąć?\')">Usuń</button></form></td></tr>' for a in assign)
        html=('<h1>Przypisywanie farm do użytkowników</h1>'
            '<p style="font-size:13px;color:#5f5e5a;margin-bottom:12px">Jeden użytkownik może mieć dostęp do wielu farm z różnymi rolami.</p>'
            '<div class="card"><b>Dodaj przypisanie</b><form method="POST" style="margin-top:10px">'
            '<input type="hidden" name="action" value="add"><div class="g3">'
            f'<div><label>Użytkownik</label><select name="uid">{u_opt}</select></div>'
            f'<div><label>Farma</label><select name="farm_id">{f_opt}</select></div>'
            f'<div><label>Rola</label><select name="rola">{r_opt}</select></div>'
            '</div><br><button class="btn bp">Przypisz</button></form></div>'
            '<div class="card" style="overflow-x:auto"><b>Aktualne przypisania</b>'
            '<table style="margin-top:8px"><thead><tr><th>Użytkownik</th><th>Farma</th><th>Rola</th><th></th></tr></thead>'
            f'<tbody>{w or "<tr><td colspan=4 style=\'color:#888;text-align:center;padding:16px\'>Brak</td></tr>"}</tbody></table></div>'
            '<a href="/admin" class="btn bo bsm" style="margin-top:8px">← Admin</a>')
        return R(html,"admin")

    # ─── API ─────────────────────────────────────────────────────────────────
    @app.route("/api/wszystkie-skladniki")
    @farm_required
    def api_wszystkie_skladniki():
        g=gid(); db=get_db()
        zb=db.execute("SELECT nazwa,kategoria,cena_pln_t/1000.0 as cena FROM skladniki_baza WHERE aktywny=1 ORDER BY nazwa").fetchall()
        zm=db.execute("SELECT nazwa,kategoria,cena_aktualna as cena FROM stan_magazynu WHERE gospodarstwo_id=? ORDER BY nazwa",(g,)).fetchall()
        db.close()
        seen=set(); wynik=[]
        for r in list(zb)+list(zm):
            if r["nazwa"] not in seen:
                seen.add(r["nazwa"])
                wynik.append({"nazwa":r["nazwa"],"kategoria":r["kategoria"] or "","cena":round(float(r["cena"] or 0),3)})
        return jsonify(wynik)

    @app.route("/api/skladnik-info")
    @farm_required
    def api_skladnik_info():
        g=gid(); nazwa=request.args.get("nazwa",""); db=get_db()
        pdz=float(gs("pasza_dzienna_kg","6")); kg_rok=pdz*365
        rec=db.execute("SELECT id FROM receptura WHERE gospodarstwo_id=? AND aktywna=1 LIMIT 1",(g,)).fetchone()
        procent=0
        if rec:
            s=db.execute("SELECT rs.procent FROM receptura_skladnik rs JOIN stan_magazynu sm ON rs.magazyn_id=sm.id WHERE rs.receptura_id=? AND LOWER(sm.nazwa)=LOWER(?)",(rec["id"],nazwa)).fetchone()
            if s: procent=float(s["procent"] or 0)
        sb=db.execute("SELECT cena_pln_t,kategoria FROM skladniki_baza WHERE LOWER(nazwa)=LOWER(?)",(nazwa,)).fetchone()
        cena=0; kat="Zboże/pasza"
        if sb:
            cena=round(sb["cena_pln_t"]/1000,3)
            if sb["kategoria"] in("premiks","mineralne","naturalny_dodatek"): kat="Witaminy/suplementy"
        else:
            sm=db.execute("SELECT cena_aktualna FROM stan_magazynu WHERE gospodarstwo_id=? AND LOWER(nazwa)=LOWER(?)",(g,nazwa)).fetchone()
            if sm: cena=round(float(sm["cena_aktualna"] or 0),3)
        db.close(); kg_r=round(kg_rok*procent,1)
        return jsonify({"nazwa":nazwa,"cena":cena,"kategoria":kat,"procent":procent,
            "kg_na_rok":kg_r,"kg_na_miesiac":round(kg_r/12,1),
            "info":f"{procent*100:.1f}% receptury → {kg_r} kg/rok" if procent>0 else ""})

    @app.route("/pasza/predykcja")
    @farm_required
    def pasza_predykcja():
        g=gid(); db=get_db()
        pdz=float(gs("pasza_dzienna_kg","6"))
        avg=db.execute("SELECT AVG(pasza_wydana_kg) as a FROM produkcja WHERE gospodarstwo_id=? AND pasza_wydana_kg>0 AND data>=date('now','-30 days')",(g,)).fetchone()["a"] or pdz
        wyprod=db.execute("SELECT COALESCE(SUM(ilosc_kg),0) as s FROM mieszania WHERE gospodarstwo_id=?",(g,)).fetchone()["s"]
        wydana=db.execute("SELECT COALESCE(SUM(pasza_wydana_kg),0) as s FROM produkcja WHERE gospodarstwo_id=?",(g,)).fetchone()["s"]
        gotowa=max(0,wyprod-wydana); db.close()
        today=date.today(); dni=(date(today.year,12,31)-today).days
        potrzeba=round(avg*dni,1); brakuje=max(0,round(potrzeba-gotowa,1))
        kol="#A32D2D" if brakuje>0 else "#3B6D11"
        al=""
        if today.month in(7,8) and brakuje>0:
            al=f'<div class="al ald"><b>Sierpień — zamów składniki!</b> Brakuje <b>{brakuje} kg</b> do końca roku.</div>'
        _mn=["","Styczeń","Luty","Marzec","Kwiecień","Maj","Czerwiec","Lipiec","Sierpień","Wrzesień","Październik","Listopad","Grudzień"]
        def _d(i):
            s=max(date(today.year,i,1),today)
            e=date(today.year,i%12+1,1)-timedelta(days=1) if i<12 else date(today.year,12,31)
            return max(0,(e-s).days+1)
        w="".join(f'<tr><td>{_mn[i]}</td><td>{_d(i)} dni</td><td style="font-weight:500">{round(avg*_d(i),1)} kg</td></tr>'
            for i in range(today.month,13))
        html=(al+f'<h1>Predykcja paszy — do końca roku</h1>'
            '<div class="g3" style="margin-bottom:12px">'
            f'<div class="card stat"><div class="v">{round(gotowa,1)} kg</div><div class="l">Pasza gotowa</div></div>'
            f'<div class="card stat"><div class="v" style="color:{kol}">{brakuje if brakuje>0 else "Wystarczy"}</div>'
            f'<div class="l">{"Brakuje" if brakuje>0 else "Zapas OK"}</div></div>'
            f'<div class="card stat"><div class="v">{potrzeba} kg</div><div class="l">Potrzeba do 31.12</div><div class="s">przy {round(avg,1)} kg/dzień</div></div></div>'
            '<div class="card"><b>Harmonogram miesięczny</b>'
            '<div style="overflow-x:auto"><table style="margin-top:8px"><thead><tr><th>Miesiąc</th><th>Dni</th><th>Potrzeba</th></tr></thead>'
            f'<tbody>{w}</tbody></table></div></div>')
        return R(html,"pasza")



    # ─── USTAWIENIA FARMY ────────────────────────────────────────────────────
    @app.route("/ustawienia/farma", methods=["GET","POST"])
    @farm_required
    def ustawienia_farma():
        g = gid()
        if request.method == "POST":
            sekcja = request.form.get("sekcja","")
            if sekcja == "podstawowe":
                for k in ["pasza_dzienna_kg","cena_jajka","etykieta_producent","etykieta_adres"]:
                    v = request.form.get(k)
                    if v is not None: save_setting(k, v.strip(), g)
                flash("Ustawienia podstawowe zapisane.")
            elif sekcja == "media":
                for k in ["cena_wody_litra","cena_kwh"]:
                    v = request.form.get(k)
                    if v is not None: save_setting(k, v.strip(), g)
                flash("Ceny mediów zapisane.")
            elif sekcja == "supla":
                save_setting("supla_webhook_token", request.form.get("supla_token","").strip(), g)
                flash("Token Supla zapisany.")
            return redirect("/ustawienia/farma")

        def _v(k, d=""): return gs(k, d)
        host = request.host
        supla_token = _v("supla_webhook_token","")

        db = get_db()
        kanaly = db.execute("""
            SELECT uc.kanal, uc.opis, uc.urzadzenie_id,
                   u.nazwa as urz_nazwa,
                   ks.tryb, ks.supla_channel_id, ks.esphome_entity, ks.gpio_pin
            FROM urzadzenia_kanaly uc
            JOIN urzadzenia u ON uc.urzadzenie_id = u.id
            LEFT JOIN kanal_sterowanie ks
                ON ks.urzadzenie_id = uc.urzadzenie_id AND ks.kanal = uc.kanal
            WHERE u.gospodarstwo_id = ? AND u.aktywne = 1
            ORDER BY u.nazwa, uc.kanal""", (g,)).fetchall()
        supla_cfg = db.execute(
            "SELECT s.*,u.nazwa as urz_nazwa FROM supla_config s "
            "LEFT JOIN urzadzenia u ON s.powiazane_urzadzenie_id=u.id "
            "WHERE s.gospodarstwo_id=? ORDER BY s.nazwa", (g,)).fetchall()
        supla_log = db.execute(
            "SELECT * FROM supla_log WHERE gospodarstwo_id=? ORDER BY czas DESC LIMIT 10", (g,)).fetchall()
        db.close()

        # Sekcja podstawowe
        s_podst = (
            '<div class="card"><b>Podstawowe</b>'
            '<form method="POST" style="margin-top:10px">'
            '<input type="hidden" name="sekcja" value="podstawowe">'
            '<div class="g2">'
            '<div><label>Dzienne zużycie paszy (kg)</label>'
            '<input name="pasza_dzienna_kg" type="number" step="0.1" value="' + _v("pasza_dzienna_kg","6") + '"></div>'
            '<div><label>Domyślna cena jajka (zł)</label>'
            '<input name="cena_jajka" type="number" step="0.01" value="' + _v("cena_jajka","1.20") + '"></div>'
            '<div><label>Producent (etykieta)</label>'
            '<input name="etykieta_producent" value="' + _v("etykieta_producent","Ferma Jaj") + '"></div>'
            '<div><label>Adres (etykieta)</label>'
            '<input name="etykieta_adres" value="' + _v("etykieta_adres","") + '"></div>'
            '</div>'
            '<button class="btn bp bsm" style="margin-top:10px">Zapisz</button>'
            '</form></div>'
        )

        # Sekcja media
        s_media = (
            '<div class="card"><b>Ceny mediów</b>'
            '<form method="POST" style="margin-top:10px">'
            '<input type="hidden" name="sekcja" value="media">'
            '<div class="g2">'
            '<div><label>Cena wody (zł/litr)</label>'
            '<input name="cena_wody_litra" type="number" step="0.0001" value="' + _v("cena_wody_litra","0.005") + '"></div>'
            '<div><label>Cena prądu (zł/kWh)</label>'
            '<input name="cena_kwh" type="number" step="0.01" value="' + _v("cena_kwh","0.80") + '"></div>'
            '</div>'
            '<button class="btn bp bsm" style="margin-top:10px">Zapisz</button>'
            '</form></div>'
        )

        # Sekcja Supla
        w_supla = ""
        for c in supla_cfg:
            badge = 'b-green' if c["ostatni_stan"] else 'b-gray'
            stan_txt = 'ON' if c["ostatni_stan"] else 'OFF'
            w_supla += (
                '<tr>'
                '<td style="font-weight:500">' + c["nazwa"] + '</td>'
                '<td><code>' + str(c["channel_id"] or "—") + '</code></td>'
                '<td>' + (c["urz_nazwa"] or "—") + ' / ' + (c["powiazany_kanal"] or "—") + '</td>'
                '<td><span class="badge ' + badge + '">' + stan_txt + '</span></td>'
                '<td class="nowrap">'
                '<a href="/supla/' + str(c["id"]) + '/edytuj" class="btn bo bsm">Edytuj</a> '
                '<a href="/supla/' + str(c["id"]) + '/usun" class="btn br bsm" onclick="return confirm(\'Usunąć?\')">✕</a>'
                '</td></tr>'
            )
        w_log = ""
        for l in supla_log:
            badge = 'b-green' if l["stan"] else 'b-gray'
            w_log += (
                '<tr>'
                '<td style="font-size:11px">' + l["czas"][:16] + '</td>'
                '<td><code>' + str(l["channel_id"] or "") + '</code></td>'
                '<td>' + (l["action_raw"] or "") + '</td>'
                '<td><span class="badge ' + badge + '">' + ('ON' if l["stan"] else 'OFF') + '</span></td>'
                '</tr>'
            )
        log_html = ("")
        if supla_log:
            log_html = (
                '<details style="margin-top:10px">'
                '<summary style="cursor:pointer;font-size:13px;color:#534AB7">Log webhooków (' + str(len(supla_log)) + ')</summary>'
                '<table style="font-size:12px;margin-top:6px"><thead><tr><th>Czas</th><th>Channel</th><th>Akcja</th><th>Stan</th></tr></thead>'
                '<tbody>' + w_log + '</tbody></table></details>'
            )
        s_supla = (
            '<div class="card"><b>Supla — webhook</b>'
            '<div style="background:#EEEDFE;border-radius:8px;padding:10px 14px;margin:10px 0;font-size:13px">'
            'URL: <code style="background:#fff;padding:2px 8px;border-radius:4px">https://' + host + '/webhook/supla</code><br>'
            'Supla Cloud → Kanał → Akcje bezpośrednie → POST<br>'
            'Nagłówek: <code>X-Supla-Token: ' + (supla_token or "ustaw_poniżej") + '</code>'
            '</div>'
            '<form method="POST" style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap">'
            '<input type="hidden" name="sekcja" value="supla">'
            '<input name="supla_token" value="' + supla_token + '" placeholder="Token bezpieczeństwa (opcjonalny)" style="flex:1">'
            '<button class="btn bp bsm">Zapisz token</button></form>'
            '<a href="/supla/dodaj" class="btn bp bsm" style="margin-bottom:10px">+ Dodaj kanał Supla</a>'
            '<div style="overflow-x:auto"><table style="font-size:13px"><thead><tr>'
            '<th>Nazwa</th><th>Channel ID</th><th>Urządzenie/Kanał</th><th>Stan</th><th></th>'
            '</tr></thead><tbody>'
            + (w_supla or '<tr><td colspan=5 style="color:#888;text-align:center;padding:12px">Brak kanałów Supla</td></tr>')
            + '</tbody></table></div>'
            + log_html
            + '</div>'
        )

        # Sekcja GPIO
        kol_map = {"reczny":"b-gray","supla":"b-amber","gpio_rpi":"b-green","esphome":"b-blue","gpio+supla":"b-purple","esphome+supla":"b-purple"}
        ico_map = {"reczny":"🖱","supla":"⚡","gpio_rpi":"🔌","esphome":"📡","gpio+supla":"🔌⚡","esphome+supla":"📡⚡"}
        w_kanaly = ""
        for k in kanaly:
            tryb = k["tryb"] or "reczny"
            w_kanaly += (
                '<tr>'
                '<td>' + k["urz_nazwa"] + '</td>'
                '<td><code>' + k["kanal"] + '</code></td>'
                '<td style="color:#5f5e5a">' + (k["opis"] or "—") + '</td>'
                '<td><span class="badge ' + kol_map.get(tryb,"b-gray") + '">'
                + ico_map.get(tryb,"") + ' ' + tryb + '</span></td>'
                '<td><a href="/sterowanie/kanal/' + str(k["urzadzenie_id"]) + '/' + k["kanal"] + '" class="btn bo bsm">Zmień</a></td>'
                '</tr>'
            )
        kanaly_html = ""
        if w_kanaly:
            kanaly_html = (
                '<div style="overflow-x:auto"><table style="font-size:13px;margin-top:8px">'
                '<thead><tr><th>Urządzenie</th><th>Kanał</th><th>Opis</th><th>Tryb</th><th></th></tr></thead>'
                '<tbody>' + w_kanaly + '</tbody></table></div>'
            )
        else:
            kanaly_html = '<p style="color:#888;font-size:13px;margin-top:8px">Brak urządzeń. <a href="/urzadzenia/dodaj" style="color:#534AB7">Dodaj ESP32 lub RPi slave</a>.</p>'

        s_gpio = (
            '<div class="card">'
            '<div style="display:flex;justify-content:space-between;align-items:center">'
            '<b>GPIO / Sterowanie per kanał</b>'
            '<a href="/sterowanie" class="btn bo bsm">Pełny panel</a>'
            '</div>'
            '<p style="font-size:12px;color:#888;margin:6px 0">'
            'Tryby: ręczny / Supla / GPIO RPi / ESPHome / kombinacje.</p>'
            + kanaly_html
            + '<div style="display:flex;gap:8px;margin-top:10px;flex-wrap:wrap">'
            '<a href="/urzadzenia/dodaj" class="btn bp bsm">+ Dodaj urządzenie</a>'
            '<a href="/integracje/esphome" class="btn bo bsm">Konfiguracja ESPHome</a>'
            '</div></div>'
        )

        s_skroty = (
            '<div class="card"><b>Skróty</b>'
            '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px">'
            '<a href="/import/xlsx" class="btn bo bsm">Import Chicken.xlsx</a>'
            '<a href="/pasza/skladniki-baza" class="btn bo bsm">Baza składników</a>'
            '<a href="/gpio/pwm" class="btn bo bsm">LED PWM</a>'
            '<a href="/pojenie" class="btn bo bsm">Harmonogram pojenia</a>'
            '</div></div>'
        )

        html = '<h1>Ustawienia farmy</h1>' + s_podst + s_media + s_supla + s_gpio + s_skroty
        return R(html, "ust")



    # ─── API: lista składników do autocomplete w wydatkach ───────────────────
    @app.route("/api/zboze-lista")
    @farm_required
    def api_zboze_lista():
        g = gid()
        db = get_db()
        z_bazy = db.execute(
            "SELECT nazwa, kategoria, cena_pln_t/1000.0 as cena "
            "FROM skladniki_baza WHERE aktywny=1 ORDER BY nazwa"
        ).fetchall()
        z_mag = db.execute(
            "SELECT nazwa, kategoria, cena_aktualna as cena "
            "FROM stan_magazynu WHERE gospodarstwo_id=? ORDER BY nazwa", (g,)
        ).fetchall()
        db.close()
        seen = {}
        for r in list(z_bazy) + list(z_mag):
            if r["nazwa"] not in seen:
                seen[r["nazwa"]] = {
                    "nazwa": r["nazwa"],
                    "kategoria": r["kategoria"] or "",
                    "cena": round(float(r["cena"] or 0), 3)
                }
        return jsonify(sorted(seen.values(), key=lambda x: x["nazwa"]))

    # ─── EDYCJA składnika bazy ────────────────────────────────────────────────
    @app.route("/pasza/skladnik-baza/<int:sid>/edytuj", methods=["GET","POST"])
    @farm_required
    def pasza_skladnik_baza_edytuj(sid):
        db = get_db()
        if request.method == "POST":
            f = request.form
            db.execute("""UPDATE skladniki_baza SET
                nazwa=?, kategoria=?, cena_pln_t=?,
                bialko_pct=?, energia_me=?, tluszcz_pct=?, wlokno_pct=?,
                wapn_g_kg=?, fosfor_g_kg=?, lizyna_g_kg=?, metionina_g_kg=?, uwagi=?
                WHERE id=?""", (
                f["nazwa"], f.get("kategoria","inne"),
                float(f.get("cena_pln_t",0) or 0),
                float(f.get("bialko_pct",0) or 0),
                float(f.get("energia_me",0) or 0),
                float(f.get("tluszcz_pct",0) or 0),
                float(f.get("wlokno_pct",0) or 0),
                float(f.get("wapn_g_kg",0) or 0),
                float(f.get("fosfor_g_kg",0) or 0),
                float(f.get("lizyna_g_kg",0) or 0),
                float(f.get("metionina_g_kg",0) or 0),
                f.get("uwagi",""), sid
            ))
            db.commit(); db.close()
            flash("Składnik zaktualizowany.")
            return redirect("/pasza/skladniki-baza")
        s = dict(db.execute("SELECT * FROM skladniki_baza WHERE id=?", (sid,)).fetchone() or {})
        db.close()
        if not s: return redirect("/pasza/skladniki-baza")
        KAT = [("zboze","Zboże"),("bialkowe","Białkowe"),("mineralne","Mineralne"),
               ("premiks","Premiks"),("naturalny_dodatek","Naturalny dodatek"),("inne","Inne")]
        kat_opt = "".join(
            f'<option value="{k}" {"selected" if s.get("kategoria")==k else ""}>{l}</option>'
            for k,l in KAT
        )
        def fi(label, name, step="0.01"):
            return (f'<div><label>{label}</label>'
                    f'<input name="{name}" type="number" step="{step}" value="{s.get(name,"") or ""}"></div>')
        html = (
            f'<h1>Edytuj składnik: {s.get("nazwa","")}</h1>'
            '<div class="card"><form method="POST">'
            f'<label>Nazwa</label><input name="nazwa" required value="{s.get("nazwa","")}">'
            f'<div class="g2"><div><label>Kategoria</label><select name="kategoria">{kat_opt}</select></div>'
            + fi("Cena PLN/T","cena_pln_t","1") +
            '</div><h2>Wartości odżywcze (na 1 kg składnika)</h2>'
            '<div class="g3">'
            + fi("Białko (%)","bialko_pct")
            + fi("Energia ME (kcal/kg)","energia_me","1")
            + fi("Tłuszcz (%)","tluszcz_pct")
            + fi("Włókno (%)","wlokno_pct")
            + fi("Wapń Ca (g/kg)","wapn_g_kg")
            + fi("Fosfor P (g/kg)","fosfor_g_kg")
            + fi("Lizyna (g/kg)","lizyna_g_kg")
            + fi("Metionina (g/kg)","metionina_g_kg")
            + '</div>'
            f'<label>Uwagi</label><textarea name="uwagi" rows="2">{s.get("uwagi","")}</textarea>'
            '<br><button class="btn bp">Zapisz</button>'
            '<a href="/pasza/skladniki-baza" class="btn bo" style="margin-left:8px">Anuluj</a>'
            '</form></div>'
        )
        return R(html, "ana")

    @app.route("/pasza/skladnik-baza/dodaj", methods=["GET","POST"])
    @farm_required
    def pasza_skladnik_baza_dodaj():
        db = get_db()
        if request.method == "POST":
            f = request.form
            db.execute("""INSERT INTO skladniki_baza
                (nazwa,kategoria,cena_pln_t,bialko_pct,energia_me,tluszcz_pct,wlokno_pct,
                 wapn_g_kg,fosfor_g_kg,lizyna_g_kg,metionina_g_kg,uwagi)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""", (
                f["nazwa"], f.get("kategoria","inne"),
                float(f.get("cena_pln_t",0) or 0),
                float(f.get("bialko_pct",0) or 0), float(f.get("energia_me",0) or 0),
                float(f.get("tluszcz_pct",0) or 0), float(f.get("wlokno_pct",0) or 0),
                float(f.get("wapn_g_kg",0) or 0), float(f.get("fosfor_g_kg",0) or 0),
                float(f.get("lizyna_g_kg",0) or 0), float(f.get("metionina_g_kg",0) or 0),
                f.get("uwagi","")
            ))
            db.commit(); db.close()
            flash("Składnik dodany.")
            return redirect("/pasza/skladniki-baza")
        db.close()
        KAT = [("zboze","Zboże"),("bialkowe","Białkowe"),("mineralne","Mineralne"),
               ("premiks","Premiks"),("naturalny_dodatek","Naturalny dodatek"),("inne","Inne")]
        kat_opt = "".join(f'<option value="{k}">{l}</option>' for k,l in KAT)
        def fi(label, name, step="0.01"):
            return f'<div><label>{label}</label><input name="{name}" type="number" step="{step}" value="0"></div>'
        html = (
            '<h1>Nowy składnik bazy</h1>'
            '<div class="card"><form method="POST">'
            f'<label>Nazwa</label><input name="nazwa" required placeholder="np. Kukurydza (śrutowana)">'
            f'<div class="g2"><div><label>Kategoria</label><select name="kategoria">{kat_opt}</select></div>'
            + fi("Cena PLN/T","cena_pln_t","1") +
            '</div><h2>Wartości odżywcze (na 1 kg składnika)</h2>'
            '<div class="g3">'
            + fi("Białko (%)","bialko_pct")
            + fi("Energia ME (kcal/kg)","energia_me","1")
            + fi("Tłuszcz (%)","tluszcz_pct")
            + fi("Włókno (%)","wlokno_pct")
            + fi("Wapń Ca (g/kg)","wapn_g_kg")
            + fi("Fosfor P (g/kg)","fosfor_g_kg")
            + fi("Lizyna (g/kg)","lizyna_g_kg")
            + fi("Metionina (g/kg)","metionina_g_kg")
            + '</div>'
            '<label>Uwagi</label><textarea name="uwagi" rows="2"></textarea>'
            '<br><button class="btn bp">Dodaj</button>'
            '<a href="/pasza/skladniki-baza" class="btn bo" style="margin-left:8px">Anuluj</a>'
            '</form></div>'
        )
        return R(html, "ana")

    # ─── SPRZEDAŻ NIEZALEŻNA ──────────────────────────────────────────────────
    @app.route("/sprzedaz", methods=["GET","POST"])
    @farm_required
    def sprzedaz():
        g = gid()
        if request.method == "POST":
            db = get_db()
            d       = request.form.get("data", date.today().isoformat())
            ilosc   = int(request.form.get("ilosc", 0) or 0)
            cena    = float(request.form.get("cena_szt", 0) or 0)
            kid     = request.form.get("klient_id") or None
            zid     = request.form.get("zamowienie_id") or None
            typ     = request.form.get("typ_platnosci", "gotowka")
            uwagi   = request.form.get("uwagi", "")
            wartosc = round(ilosc * cena, 2)

            # Zaktualizuj produkcję na ten dzień
            ex = db.execute(
                "SELECT id, jaja_sprzedane, cena_sprzedazy FROM produkcja "
                "WHERE gospodarstwo_id=? AND data=?", (g, d)
            ).fetchone()
            if ex:
                nowa_ilosc = (ex["jaja_sprzedane"] or 0) + ilosc
                # Przelicz cenę ważoną
                stara_wart = (ex["jaja_sprzedane"] or 0) * (ex["cena_sprzedazy"] or 0)
                nowa_cena = round((stara_wart + wartosc) / nowa_ilosc, 4) if nowa_ilosc > 0 else cena
                db.execute(
                    "UPDATE produkcja SET jaja_sprzedane=?, cena_sprzedazy=?, "
                    "klient_id=COALESCE(klient_id,?), zamowienie_id=COALESCE(zamowienie_id,?) "
                    "WHERE id=?",
                    (nowa_ilosc, nowa_cena, kid, zid, ex["id"])
                )
            else:
                db.execute(
                    "INSERT INTO produkcja(gospodarstwo_id,data,jaja_zebrane,jaja_sprzedane,"
                    "cena_sprzedazy,pasza_wydana_kg,klient_id,zamowienie_id,typ_sprzedazy,uwagi) "
                    "VALUES(?,?,0,?,?,0,?,?,?,?)",
                    (g, d, ilosc, cena, kid, zid, typ, uwagi)
                )

            # Oznacz zamówienie jako dostarczone
            if zid and ilosc > 0:
                db.execute(
                    "UPDATE zamowienia SET status='dostarczone' WHERE id=? AND gospodarstwo_id=?",
                    (zid, g)
                )

            db.commit(); db.close()
            flash(f"Sprzedaż zapisana: {ilosc} szt. × {cena} zł = {wartosc} zł")
            return redirect("/sprzedaz")

        # GET — formularz + historia
        db = get_db()
        klienci = db.execute(
            "SELECT id, nazwa, telefon FROM klienci WHERE gospodarstwo_id=? ORDER BY nazwa", (g,)
        ).fetchall()
        zamow = db.execute(
            """SELECT z.id, z.data_dostawy, z.ilosc, k.nazwa as kn
               FROM zamowienia z LEFT JOIN klienci k ON z.klient_id=k.id
               WHERE z.gospodarstwo_id=? AND z.status IN ('nowe','potwierdzone')
               ORDER BY z.data_dostawy""", (g,)
        ).fetchall()
        historia = db.execute(
            """SELECT p.data, p.jaja_sprzedane, p.cena_sprzedazy,
               ROUND(p.jaja_sprzedane*p.cena_sprzedazy,2) as wartosc,
               k.nazwa as kn, COALESCE(p.typ_sprzedazy,"gotowka") as typ_sprzedazy, p.uwagi
               FROM produkcja p LEFT JOIN klienci k ON p.klient_id=k.id
               WHERE p.gospodarstwo_id=? AND p.jaja_sprzedane>0
               ORDER BY p.data DESC LIMIT 30""", (g,)
        ).fetchall()
        mag = db.execute(
            "SELECT COALESCE(SUM(jaja_zebrane),0) as p, COALESCE(SUM(jaja_sprzedane),0) as s "
            "FROM produkcja WHERE gospodarstwo_id=?", (g,)
        ).fetchone()
        stan_mag = max(0, mag["p"] - mag["s"])
        db.close()

        kl_opt = '<option value="">— anonimowa —</option>' + "".join(
            f'<option value="{k["id"]}">{k["nazwa"]}"'
            + (f' ({k["telefon"]})' if k["telefon"] else "")
            + '</option>'
            for k in klienci
        )
        zam_opt = '<option value="">— bez zamówienia —</option>' + "".join(
            f'<option value="{z["id"]}">{z["data_dostawy"]} · {z["kn"] or "?"} · {z["ilosc"]} szt.</option>'
            for z in zamow
        )
        typ_opt = "".join(
            f'<option value="{v}">{l}</option>'
            for v, l in [
                ("gotowka","Gotówka"),("przelew","Przelew"),
                ("z_salda","Z salda klienta"),("nastepnym_razem","Zapłata następnym razem")
            ]
        )

        w_hist = "".join(
            '<tr>'
            '<td>' + r["data"] + '</td>'
            '<td style="font-weight:500">' + str(r["jaja_sprzedane"]) + ' szt.</td>'
            '<td>' + str(r["cena_sprzedazy"]) + ' zł</td>'
            '<td style="color:#3B6D11;font-weight:500">' + str(r["wartosc"]) + ' zł</td>'
            '<td>' + (r["kn"] or "—") + '</td>'
            '<td style="font-size:11px;color:#888">' + (r["typ_sprzedazy"] or "") + '</td>'
            '<td style="font-size:11px;color:#888">' + (r["uwagi"] or "") + '</td>'
            '</tr>'
            for r in historia
        )

        html = (
            '<h1>Sprzedaż jaj</h1>'
            f'<div class="card stat" style="margin-bottom:12px;text-align:center">'
            f'<div class="v" style="color:{"#3B6D11" if stan_mag>0 else "#888"}">{stan_mag}</div>'
            f'<div class="l">Jaj dostępnych w magazynie</div></div>'

            '<div class="card"><b>Nowa sprzedaż</b>'
            '<form method="POST" id="sp-form" style="margin-top:10px">'
            f'<div class="g2">'
            f'<div><label>Data sprzedaży</label>'
            f'<input name="data" type="date" value="{date.today().isoformat()}"></div>'
            f'<div><label>Klient</label><select name="klient_id" id="kl-sel">{kl_opt}</select>'
            f'<a href="/klienci/dodaj" style="font-size:12px;color:#534AB7;display:block;margin-top:4px">+ nowy klient</a></div>'
            f'</div>'

            '<div class="g3">'
            '<div><label>Ilość (szt.)</label>'
            '<input name="ilosc" type="number" min="1" id="sp-il" oninput="cW()" required></div>'
            '<div><label>Cena/szt (zł)</label>'
            '<input name="cena_szt" type="number" step="0.01" id="sp-cena" oninput="cW()"></div>'
            '<div><label>Typ płatności</label>'
            f'<select name="typ_platnosci">{typ_opt}</select></div>'
            '</div>'

            '<div style="background:#f5f5f0;border-radius:8px;padding:8px 12px;font-size:14px;margin:8px 0">'
            'Wartość: <b id="sp-wrt">0.00 zł</b></div>'

            '<label>Realizacja zamówienia (opcjonalnie)</label>'
            f'<select name="zamowienie_id">{zam_opt}</select>'

            '<label>Uwagi</label>'
            '<input name="uwagi" placeholder="opcjonalnie">'

            '<br><button class="btn bg" style="width:100%;margin-top:12px;padding:14px;font-size:16px">'
            '💰 Zapisz sprzedaż</button>'
            '</form></div>'

            '<div class="card" style="overflow-x:auto"><b>Historia sprzedaży</b>'
            '<table style="margin-top:8px"><thead><tr>'
            '<th>Data</th><th>Ilość</th><th>Cena</th><th>Wartość</th>'
            '<th>Klient</th><th>Płatność</th><th>Uwagi</th>'
            '</tr></thead>'
            f'<tbody>{w_hist or "<tr><td colspan=7 style=\'color:#888;text-align:center;padding:16px\'>Brak sprzedaży</td></tr>"}</tbody>'
            '</table></div>'

            '<script>'
            'function cW(){'
            '  var i=parseFloat(document.getElementById("sp-il").value)||0;'
            '  var c=parseFloat(document.getElementById("sp-cena").value)||0;'
            '  document.getElementById("sp-wrt").textContent=(i*c).toFixed(2)+" zł";'
            '}'
            '</script>'
        )
        return R(html, "zam")


    return app
