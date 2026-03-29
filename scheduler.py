# -*- coding: utf-8 -*-
"""
scheduler.py — lokalny harmonogram sterowania, działa offline bez internetu.
Wątek sprawdza harmonogramy co minutę i wysyła komendy do ESP32/RPi lokalnie.
"""
import threading, time, json, math, urllib.request
from datetime import datetime, date, timedelta

_thread    = None
_stop_flag = threading.Event()


# ── Wschód / Zachód słońca ────────────────────────────────────────────────────
def sun_times(lat=52.23, lon=21.01, d=None):
    """Zwraca (wschód, zachód) jako HH:MM string lub (None, None)."""
    if d is None:
        d = date.today()
    n   = (datetime(d.year, d.month, d.day) - datetime(2000, 1, 1)).days + 0.5
    L   = (280.460 + 0.9856474 * n) % 360
    g   = math.radians((357.528 + 0.9856003 * n) % 360)
    lam = math.radians(L + 1.915 * math.sin(g) + 0.020 * math.sin(2*g))
    ep  = math.radians(23.439 - 0.0000004 * n)
    dec = math.asin(math.sin(ep) * math.sin(lam))
    ra  = math.atan2(math.cos(ep) * math.sin(lam), math.cos(lam))
    eo  = (L/360 - ra/(2*math.pi)) * 24 * 60
    lat_r = math.radians(lat)
    ch  = (math.sin(math.radians(-0.833)) - math.sin(lat_r)*math.sin(dec)) / (math.cos(lat_r)*math.cos(dec))
    if abs(ch) > 1:
        return None, None
    h_deg = math.degrees(math.acos(ch))
    transit = 720 - 4*lon - eo
    # Offset strefy czasowej Polska (UTC+1 zima, UTC+2 lato)
    is_dst = time.daylight and time.localtime().tm_isdst
    utc_off = 1 if not is_dst else 2
    def _m2t(m):
        tot = int(m + utc_off*60) % 1440
        return f"{tot//60:02d}:{tot%60:02d}"
    return _m2t(transit - h_deg*4), _m2t(transit + h_deg*4)


# ── Wysyłanie komendy ─────────────────────────────────────────────────────────
def _send(did, kanal, stan, g):
    from db import get_db
    # Supla - kanal zaczyna sie od 'supla_'
    if kanal and str(kanal).startswith('supla_'):
        return _send_supla(kanal, stan, g)
    db = get_db()
    dev = db.execute("SELECT * FROM urzadzenia WHERE id=? AND gospodarstwo_id=?", (did, g)).fetchone()
    if not dev:
        db.close(); return False
    typ = dev["typ"]
    if typ == "esphome":
        path = f"/api/switch/{kanal}/{'turn_on' if stan else 'turn_off'}"
        body = b""
    else:
        path = "/api/relay"
        body = json.dumps({"channel": kanal, "state": bool(stan)}).encode()
    hdrs = {"Content-Type": "application/json"}
    if dev["api_key"]:
        hdrs["X-API-Key"] = dev["api_key"]
    ok = False
    try:
        req = urllib.request.Request(
            f"http://{dev['ip']}:{dev['port']}{path}",
            data=body, method="POST", headers=hdrs)
        urllib.request.urlopen(req, timeout=4)
        ok = True
    except Exception:
        pass
    now = datetime.now().isoformat()
    if ok:
        db.execute("UPDATE urzadzenia_kanaly SET stan=? WHERE urzadzenie_id=? AND kanal=?",
                   (1 if stan else 0, did, kanal))
        db.execute("UPDATE urzadzenia SET ostatni_kontakt=?,status='online' WHERE id=?", (now, did))
    db.execute(
        "INSERT INTO gpio_log(gospodarstwo_id,czas,urzadzenie_id,kanal,stan,zrodlo) VALUES(?,?,?,?,?,'harmonogram')",
        (g, now, did, kanal, 1 if stan else 0))
    db.commit(); db.close()
    return ok


# ── Sprawdzanie harmonogramów ─────────────────────────────────────────────────
def _check():
    from db import get_db
    now      = datetime.now()
    now_hm   = now.strftime("%H:%M")
    now_dow  = now.weekday()   # 0=pon … 6=nie

    db = get_db()
    rows = db.execute("SELECT * FROM harmonogramy WHERE aktywny=1").fetchall()
    db.close()

    for h in rows:
        try:
            _process(h, now_hm, now_dow)
        except Exception:
            pass   # nigdy nie crashuj pętli


def _process(h, now_hm, now_dow):
    typ  = h["typ"]          # godzina | wschod | zachod | wschod_offset | zachod_offset
    dni  = json.loads(h["dni_tygodnia"] or "[]")
    if dni and now_dow not in dni:
        return

    # Oblicz efektywne czasy dla słońca
    czas_wl  = h["czas_wlaczenia"]
    czas_wyl = h["czas_wylaczenia"]

    if typ in ("wschod", "wschod_offset", "zachod", "zachod_offset"):
        lat = float(h["lat"] or 52.23)
        lon = float(h["lon"] or 21.01)
        sr, ss = sun_times(lat, lon)
        if not sr:
            return
        base = sr if "wschod" in typ else ss
        off  = int(h["offset_minut"] or 0)
        # baza ± offset
        bh, bm = map(int, base.split(":"))
        total  = bh*60 + bm + off
        total  = total % 1440
        czas_wl = f"{total//60:02d}:{total%60:02d}"
        # czas wyłączenia = wl + czas_trwania (jeśli > 0)
        if h["czas_trwania_s"] and int(h["czas_trwania_s"]) > 0:
            czas_wyl = None   # wyłączy timer po czasie
        # brak czas_wylaczenia = tylko ON

    did   = h["urzadzenie_id"]
    kanal = h["kanal"]
    g     = h["gospodarstwo_id"]

    if czas_wl and now_hm == czas_wl:
        _send(did, kanal, True, g)
        # auto-wyłącz przez wątek jeśli czas_trwania_s > 0
        sec = int(h["czas_trwania_s"] or 0)
        if sec > 0:
            def _off():
                time.sleep(sec)
                _send(did, kanal, False, g)
            threading.Thread(target=_off, daemon=True).start()
        # zapisz ostatnie wykonanie
        from db import get_db as _db
        db2 = _db()
        db2.execute("UPDATE harmonogramy SET ostatnie_wykonanie=? WHERE id=?",
                    (datetime.now().isoformat(), h["id"]))
        db2.commit(); db2.close()

    elif czas_wyl and now_hm == czas_wyl and not (h["czas_trwania_s"] and int(h["czas_trwania_s"]) > 0):
        _send(did, kanal, False, g)
        from db import get_db as _db
        db2 = _db()
        db2.execute("UPDATE harmonogramy SET ostatnie_wykonanie=? WHERE id=?",
                    (datetime.now().isoformat(), h["id"]))
        db2.commit(); db2.close()


# ── Pętla schedulera ─────────────────────────────────────────────────────────
def _loop():
    while not _stop_flag.is_set():
        _check()
        _stop_flag.wait(60)


def start():
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop_flag.clear()
    _thread = threading.Thread(target=_loop, daemon=True, name="ferma-sched")
    _thread.start()


def stop():
    _stop_flag.set()

def status():
    return {"running": bool(_thread and _thread.is_alive())}
