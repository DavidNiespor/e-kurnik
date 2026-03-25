# -*- coding: utf-8 -*-
"""
routes_v5.py — rozszerzenia do app.py:
- Analityka paszy + baza składników
- Kiosk dotykowy + dark mode
- 3x PWM LED
- ESPHome + Supla
- Import xlsx
- Pojenie harmonogram
- Edycja klientów i towarów
Dodaj do app.py: from routes_v5 import register_v5; register_v5(app)
"""
from flask import request, redirect, flash, session, jsonify, send_file
from markupsafe import Markup
from datetime import datetime, date, timedelta
import json, io, os

def register_v5(app):
    from db import get_db, get_setting, save_setting
    from app import R
    from auth import farm_required, login_required, current_user, current_farm
    from baza_skladnikow import (SKLADNIKI_DOMYSLNE, NORMY_NIOSEK,
                                  seed_skladniki, init_skladniki_tables)
    from pasza_analityka import (oblicz_recepture, generuj_rekomendacje,
                                  korelacja_pasza_niesnosc, porownaj_receptury)
    from iot_integrations import (esphome_send_command, esphome_get_sensors,
                                   supla_send_command, supla_webhook_receive,
                                   pwm_set_brightness, get_pwm_brightness,
                                   ZEROTIER_INSTRUCTIONS, ESPHOME_CONFIG_TEMPLATE,
                                   GPIO_AVAILABLE)

    def gid(): return session.get("farm_id")

    # ── Inicjalizacja tabel v5 ─────────────────────────────────────────────────
    with app.app_context():
        db = get_db()
        init_skladniki_tables(db)
        seed_skladniki(db)
        db.close()

    # ─── ANALITYKA PASZY ──────────────────────────────────────────────────────
    @app.route("/pasza/analityka")
    @farm_required
    def pasza_analityka_page():
        g = gid()
        db = get_db()
        receptury = db.execute(
            "SELECT * FROM receptura WHERE gospodarstwo_id=? ORDER BY aktywna DESC, nazwa",
            (g,)
        ).fetchall()
        db.close()

        korelacja = korelacja_pasza_niesnosc(g, 90)

        # Analiza aktywnej receptury
        aktywna = next((r for r in receptury if r["aktywna"]), None)
        wyniki  = oblicz_recepture(aktywna["id"]) if aktywna else None
        rekomendacje = generuj_rekomendacje(wyniki) if wyniki else []

        N = NORMY_NIOSEK

        def _pasek(val, mn, mx, jednostka=""):
            if not val: return ""
            pct = min(100, max(0, (val - mn*0.7) / (mx*1.3 - mn*0.7) * 100)) if mx else 50
            kolor = "#3B6D11" if mn <= val <= (mx or val*1.5) else "#A32D2D"
            return (
                f'<div style="display:flex;align-items:center;gap:8px;margin:2px 0">'
                f'<div style="width:120px;background:#e0ddd4;border-radius:4px;height:8px">'
                f'<div style="width:{pct:.0f}%;background:{kolor};height:100%;border-radius:4px"></div></div>'
                f'<span style="font-size:13px;color:{kolor};font-weight:500">{val:.1f}{jednostka}</span>'
                f'<span style="font-size:11px;color:#888">({mn:.0f}–{mx:.0f})</span>'
                f'</div>'
            )

        analiza_html = ""
        if wyniki:
            analiza_html = (
                '<div class="card"><b>Analiza aktywnej receptury: ' + (aktywna["nazwa"] if aktywna else "") + '</b>'
                '<div class="g2" style="margin-top:12px">'
                '<div>'
                '<div style="margin-bottom:8px"><span style="font-size:12px;color:#5f5e5a">Białko surowe</span>'
                + _pasek(wyniki["bialko_pct"], N["bialko_min"], N["bialko_max"], "%") + '</div>'
                '<div style="margin-bottom:8px"><span style="font-size:12px;color:#5f5e5a">Energia ME (kcal/kg)</span>'
                + _pasek(wyniki["energia_me"], N["energia_me_min"], N["energia_me_max"], "") + '</div>'
                '<div style="margin-bottom:8px"><span style="font-size:12px;color:#5f5e5a">Wapń (g/kg paszy)</span>'
                + _pasek(wyniki["wapn_g_kg"], N["wapn_min"], N["wapn_max"], " g/kg") + '</div>'
                '<div style="margin-bottom:8px"><span style="font-size:12px;color:#5f5e5a">Fosfor (g/kg paszy)</span>'
                + _pasek(wyniki["fosfor_g_kg"], N["fosfor_min"], N["fosfor_max"], " g/kg") + '</div>'
                '</div>'
                '<div>'
                '<div style="margin-bottom:8px"><span style="font-size:12px;color:#5f5e5a">Lizyna (g/kg paszy)</span>'
                + _pasek(wyniki["lizyna_g_kg"], N["lizyna_min"], N["lizyna_min"]*1.5, " g/kg") + '</div>'
                '<div style="margin-bottom:8px"><span style="font-size:12px;color:#5f5e5a">Metionina (g/kg paszy)</span>'
                + _pasek(wyniki["metionina_g_kg"], N["metionina_min"], N["metionina_min"]*1.5, " g/kg") + '</div>'
                '<div style="margin-bottom:8px"><span style="font-size:12px;color:#5f5e5a">Tłuszcz surowy</span>'
                + _pasek(wyniki["tluszcz_pct"], N["tluszcz_min"], N["tluszcz_max"], "%") + '</div>'
                '<div style="margin-bottom:8px"><span style="font-size:12px;color:#5f5e5a">Włókno surowe</span>'
                + _pasek(wyniki["wlokno_pct"], 2, N["wlokno_max"], "%") + '</div>'
                '</div>'
                '</div>'
                '<div style="margin-top:10px;font-size:13px;color:#5f5e5a">Szacowany koszt: <b>' + str(round(wyniki["koszt_pln_t"],0)) + ' PLN/T</b></div>'
                '</div>'
            )

        prio_kolor = {"krytyczny":"#A32D2D","wysoki":"#BA7517","sredni":"#534AB7","niski":"#3B6D11","brak":"#3B6D11"}
        prio_badge = {"krytyczny":"b-red","wysoki":"b-amber","sredni":"b-purple","niski":"b-green","brak":"b-green"}
        rek_html = "".join(
            '<div class="card" style="border-left:3px solid ' + prio_kolor.get(r.get("priorytet","niski"),"#888") + ';border-radius:0 12px 12px 0;margin-bottom:8px">'
            '<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">'
            '<span class="badge ' + prio_badge.get(r.get("priorytet","niski"),"b-gray") + '">' + r.get("priorytet","") + '</span>'
            '<b style="font-size:14px">' + r.get("parametr","") + '</b>'
            '</div>'
            '<p style="font-size:13px;color:#A32D2D;margin-bottom:4px">' + r.get("problem","") + '</p>'
            '<p style="font-size:13px;color:#5f5e5a;margin-bottom:4px">' + r.get("rozwiazanie","") + '</p>'
            '<p style="font-size:12px;color:#3B6D11"><b>Efekt:</b> ' + r.get("oczekiwany_efekt","") + '</p>'
            '</div>'
            for r in rekomendacje
        )

        # Korelacja trend
        trend_html = ""
        if not korelacja.get("brak_danych"):
            kolor_trend = "#3B6D11" if korelacja["trend"] == "rosnący" else "#A32D2D" if korelacja["trend"] == "malejący" else "#5f5e5a"
            trend_html = (
                '<div class="card"><b>Korelacja pasza → nieśność (ostatnie 90 dni)</b>'
                '<div class="g3" style="margin-top:10px">'
                '<div class="stat"><div class="v" style="color:' + kolor_trend + '">' + korelacja["trend"] + '</div><div class="l">Trend nieśności</div></div>'
                '<div class="stat"><div class="v">' + str(korelacja.get("avg_niesnosc","—")) + '%</div><div class="l">Średnia nieśność</div></div>'
                '<div class="stat"><div class="v">' + str(len(korelacja.get("zdarzenia",[]))) + '</div><div class="l">Zmian receptury</div></div>'
                '</div>'
                + ("".join(
                    '<div style="display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid #f0ede4;font-size:13px">'
                    '<span style="color:#888;min-width:80px">' + z["data"] + '</span>'
                    '<span>' + z["receptura"] + '</span>'
                    '<span style="margin-left:auto;color:' + ('#3B6D11' if z["delta"]>0 else '#A32D2D') + ';font-weight:500">'
                    + ('+' if z["delta"]>0 else '') + str(z["delta"]) + '% nieśności</span>'
                    '</div>'
                    for z in korelacja.get("zdarzenia",[])
                ) if korelacja.get("zdarzenia") else '<p style="color:#888;font-size:13px;margin-top:8px">Brak danych o zmianach receptury</p>')
                + '</div>'
            )

        html = (
            '<h1>Analityka paszy</h1>'
            + analiza_html
            + '<div class="card"><b>Rekomendacje</b><div style="margin-top:10px">' + rek_html + '</div></div>'
            + trend_html
            + '<div style="display:flex;gap:8px;margin-top:12px;flex-wrap:wrap">'
            '<a href="/pasza/skladniki-baza" class="btn bp bsm">Baza składników</a>'
            '<a href="/pasza/receptury" class="btn bo bsm">Receptury</a>'
            '</div>'
        )
        return R(html, "pasza")

    # ─── BAZA SKŁADNIKÓW ──────────────────────────────────────────────────────
    @app.route("/pasza/skladniki-baza")
    @farm_required
    def pasza_skladniki_baza():
        db = get_db()
        skladniki = db.execute(
            "SELECT * FROM skladniki_baza WHERE aktywny=1 ORDER BY kategoria, nazwa"
        ).fetchall()
        db.close()

        kat_map = {
            "zboze":"Zboża", "bialkowe":"Białkowe", "mineralne":"Mineralne",
            "premiks":"Premiksy", "naturalny_dodatek":"Naturalne dodatki"
        }
        biezaca_kat = None
        wiersze = ""
        for s in skladniki:
            if s["kategoria"] != biezaca_kat:
                biezaca_kat = s["kategoria"]
                wiersze += f'<tr><td colspan=9 style="background:#f5f5f0;font-weight:500;font-size:12px;color:#534AB7;padding:8px">{kat_map.get(biezaca_kat,biezaca_kat)}</td></tr>'
            wiersze += (
                '<tr>'
                '<td style="font-weight:500">' + s["nazwa"] + '</td>'
                '<td>' + str(round(s["cena_pln_t"],0)) + ' PLN/T</td>'
                '<td>' + str(round(s["bialko_pct"],1)) + '%</td>'
                '<td>' + str(round(s["energia_me"],0)) + '</td>'
                '<td>' + str(round(s["wapn_g_kg"],1)) + '</td>'
                '<td>' + str(round(s["fosfor_g_kg"],1)) + '</td>'
                '<td>' + str(round(s["lizyna_g_kg"],1)) + '</td>'
                '<td style="font-size:11px;color:#888">' + (s["uwagi"] or "")[:50] + '</td>'
                '<td><a href="/pasza/skladnik-baza/' + str(s["id"]) + '/edytuj" class="btn bo bsm">Edytuj</a></td>'
                '</tr>'
            )

        html = (
            '<h1>Baza składników paszy</h1>'
            '<div style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap">'
            '<a href="/pasza/skladnik-baza/dodaj" class="btn bp bsm">+ Dodaj składnik</a>'
            '<a href="/pasza/analityka" class="btn bo bsm">← Analityka</a>'
            '</div>'
            '<p style="font-size:13px;color:#5f5e5a;margin-bottom:12px">'
            'Baza zawiera ' + str(len(skladniki)) + ' składników z Twoich receptur. '
            'Wartości odżywcze są używane do analizy receptur i rekomendacji.</p>'
            '<div class="card" style="overflow-x:auto">'
            '<table><thead><tr>'
            '<th>Składnik</th><th>Cena</th><th>Białko</th><th>ME kcal/kg</th>'
            '<th>Ca g/kg</th><th>P g/kg</th><th>Liz g/kg</th><th>Uwagi</th><th></th>'
            '</tr></thead>'
            '<tbody>' + wiersze + '</tbody></table></div>'
        )
        return R(html, "pasza")

    @app.route("/pasza/skladnik-baza/dodaj", methods=["GET","POST"])
    @app.route("/pasza/skladnik-baza/<int:sid>/edytuj", methods=["GET","POST"])
    @farm_required
    def pasza_skladnik_baza_form(sid=None):
        db = get_db()
        if request.method == "POST":
            f = request.form
            vals = (f["nazwa"], f.get("kategoria","inne"), float(f.get("cena_pln_t",0) or 0),
                    float(f.get("bialko_pct",0) or 0), float(f.get("energia_me",0) or 0),
                    float(f.get("tluszcz_pct",0) or 0), float(f.get("wlokno_pct",0) or 0),
                    float(f.get("wapn_g_kg",0) or 0), float(f.get("fosfor_g_kg",0) or 0),
                    float(f.get("lizyna_g_kg",0) or 0), float(f.get("metionina_g_kg",0) or 0),
                    f.get("uwagi",""))
            if sid:
                db.execute("""UPDATE skladniki_baza SET nazwa=?,kategoria=?,cena_pln_t=?,
                    bialko_pct=?,energia_me=?,tluszcz_pct=?,wlokno_pct=?,
                    wapn_g_kg=?,fosfor_g_kg=?,lizyna_g_kg=?,metionina_g_kg=?,uwagi=?,
                    data_aktualizacji_ceny=datetime('now') WHERE id=?""", (*vals, sid))
            else:
                db.execute("""INSERT INTO skladniki_baza(nazwa,kategoria,cena_pln_t,
                    bialko_pct,energia_me,tluszcz_pct,wlokno_pct,
                    wapn_g_kg,fosfor_g_kg,lizyna_g_kg,metionina_g_kg,uwagi) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""", vals)
            db.commit(); db.close()
            flash("Składnik zapisany.")
            return redirect("/pasza/skladniki-baza")

        s = db.execute("SELECT * FROM skladniki_baza WHERE id=?", (sid,)).fetchone() if sid else None
        db.close()
        v = dict(s) if s else {}

        def field(label, name, type="number", step="0.01", placeholder=""):
            val = v.get(name,"")
            return (f'<div><label>{label}</label>'
                    f'<input name="{name}" type="{type}" step="{step}" value="{val}" placeholder="{placeholder}"></div>')

        kat_opt = "".join(
            f'<option value="{k}" {"selected" if v.get("kategoria")==k else ""}>{l}</option>'
            for k,l in [("zboze","Zboże"),("bialkowe","Białkowe"),("mineralne","Mineralne"),
                        ("premiks","Premiks"),("naturalny_dodatek","Naturalny dodatek"),("inne","Inne")]
        )

        html = (
            '<h1>' + ("Edytuj składnik" if sid else "Nowy składnik") + '</h1>'
            '<div class="card"><form method="POST">'
            '<label>Nazwa składnika</label><input name="nazwa" required value="' + v.get("nazwa","") + '">'
            '<div class="g2">'
            '<div><label>Kategoria</label><select name="kategoria">' + kat_opt + '</select></div>'
            '<div>' + field("Cena PLN/T", "cena_pln_t") + '</div>'
            '</div>'
            '<h2>Wartości odżywcze (na 1 kg składnika)</h2>'
            '<div class="g3">'
            + field("Białko surowe (%)", "bialko_pct")
            + field("Energia ME (kcal/kg)", "energia_me", step="1")
            + field("Tłuszcz surowy (%)", "tluszcz_pct")
            + '</div>'
            '<div class="g3">'
            + field("Włókno surowe (%)", "wlokno_pct")
            + field("Wapń Ca (g/kg)", "wapn_g_kg")
            + field("Fosfor P (g/kg)", "fosfor_g_kg")
            + '</div>'
            '<div class="g2">'
            + field("Lizyna (g/kg)", "lizyna_g_kg")
            + field("Metionina (g/kg)", "metionina_g_kg")
            + '</div>'
            '<label>Uwagi / działanie</label>'
            '<textarea name="uwagi" rows="2">' + v.get("uwagi","") + '</textarea>'
            '<br><button class="btn bp">Zapisz</button>'
            '<a href="/pasza/skladniki-baza" class="btn bo" style="margin-left:8px">Anuluj</a>'
            '</form></div>'
        )
        return R(html, "pasza")

    # ─── PWM LED ──────────────────────────────────────────────────────────────
    @app.route("/gpio/pwm")
    @farm_required
    def gpio_pwm_panel():
        g = gid()
        db = get_db()
        leds = db.execute("SELECT * FROM pwm_led WHERE gospodarstwo_id=? ORDER BY nazwa", (g,)).fetchall()
        db.close()

        led_html = "".join(
            '<div class="card">'
            '<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">'
            '<b style="min-width:80px">' + l["nazwa"] + '</b>'
            '<span style="font-size:12px;color:#888">GPIO BCM ' + str(l["pin_bcm"]) + '</span>'
            '<input type="range" min="0" max="100" value="' + str(l["jasnosc_pct"]) + '" '
            'style="flex:1" id="sl-' + str(l["id"]) + '" '
            'oninput="setPWM(' + str(l["id"]) + ',' + str(l["pin_bcm"]) + ',this.value)">'
            '<span id="val-' + str(l["id"]) + '" style="min-width:35px;font-weight:500">' + str(l["jasnosc_pct"]) + '%</span>'
            '<a href="/gpio/pwm/' + str(l["id"]) + '/off" class="btn br bsm">OFF</a>'
            '</div></div>'
            for l in leds
        )

        html = (
            '<h1>Ściemniacze LED (PWM)</h1>'
            '<a href="/gpio/pwm/dodaj" class="btn bp bsm" style="margin-bottom:12px">+ Dodaj LED</a>'
            + (led_html or '<div class="card"><p style="color:#888">Brak skonfigurowanych LED. Dodaj piny GPIO.</p></div>')
            + '<div class="card" style="background:#f5f5f0"><b>GPIO ' + ('AKTYWNE — RPi.GPIO' if GPIO_AVAILABLE else 'Tryb symulacji') + '</b></div>'
            '<script>'
            'function setPWM(id,pin,val){'
            'document.getElementById("val-"+id).textContent=val+"%";'
            'fetch("/gpio/pwm/set",{method:"POST",'
            'headers:{"Content-Type":"application/json"},'
            'body:JSON.stringify({led_id:id,pin:pin,brightness:parseInt(val)})});}'
            '</script>'
        )
        return R(html, "gpio")

    @app.route("/gpio/pwm/set", methods=["POST"])
    @farm_required
    def gpio_pwm_set():
        data = request.get_json()
        pin  = data.get("pin")
        br   = data.get("brightness", 0)
        led_id = data.get("led_id")
        ok = pwm_set_brightness(pin, br)
        if ok and led_id:
            db = get_db()
            db.execute("UPDATE pwm_led SET jasnosc_pct=? WHERE id=?", (br, led_id))
            db.commit(); db.close()
        return jsonify({"ok": ok, "brightness": br})

    @app.route("/gpio/pwm/dodaj", methods=["GET","POST"])
    @farm_required
    def gpio_pwm_dodaj():
        g = gid()
        if request.method == "POST":
            db = get_db()
            db.execute("INSERT INTO pwm_led(gospodarstwo_id,nazwa,pin_bcm,jasnosc_pct) VALUES(?,?,?,?)",
                (g, request.form.get("nazwa","LED"),
                 int(request.form.get("pin_bcm",18)),
                 int(request.form.get("jasnosc_pct",80))))
            db.commit(); db.close()
            flash("LED dodany.")
            return redirect("/gpio/pwm")
        html = (
            '<h1>Dodaj ściemniacz LED</h1><div class="card"><form method="POST">'
            '<label>Nazwa (np. Światło główne, LED gniazda)</label>'
            '<input name="nazwa" required placeholder="np. LED Kurnik">'
            '<div class="g2">'
            '<div><label>Pin GPIO BCM</label>'
            '<select name="pin_bcm">'
            + "".join(f'<option value="{p}">GPIO {p}</option>' for p in [12,13,18,19,21])
            + '</select></div>'
            '<div><label>Domyślna jasność (%)</label>'
            '<input name="jasnosc_pct" type="number" min="0" max="100" value="80"></div>'
            '</div>'
            '<p style="font-size:12px;color:#888;margin-top:8px">Piny PWM na RPi 4: GPIO 12, 13, 18, 19 (hardware PWM). GPIO 21 = software PWM.</p>'
            '<br><button class="btn bp">Dodaj</button>'
            '<a href="/gpio/pwm" class="btn bo" style="margin-left:8px">Anuluj</a>'
            '</form></div>'
        )
        return R(html, "gpio")

    @app.route("/gpio/pwm/<int:lid>/off")
    @farm_required
    def gpio_pwm_off(lid):
        db = get_db()
        led = db.execute("SELECT * FROM pwm_led WHERE id=?", (lid,)).fetchone()
        if led:
            pwm_set_brightness(led["pin_bcm"], 0)
            db.execute("UPDATE pwm_led SET jasnosc_pct=0 WHERE id=?", (lid,))
            db.commit()
        db.close()
        flash("LED wyłączony.")
        return redirect("/gpio/pwm")

    # ─── KIOSK DOTYKOWY ───────────────────────────────────────────────────────
    @app.route("/kiosk")
    @farm_required
    def kiosk():
        g = gid()
        db = get_db()
        kur = db.execute(
            "SELECT COALESCE(SUM(liczba),0) as s FROM stado WHERE gospodarstwo_id=? AND aktywne=1 AND gatunek='nioski'",
            (g,)
        ).fetchone()["s"] or 50
        prod_dzis = db.execute(
            "SELECT * FROM produkcja WHERE gospodarstwo_id=? AND data=date('now')", (g,)
        ).fetchone()
        dzis_mag = db.execute(
            "SELECT COALESCE(SUM(jaja_zebrane),0)-COALESCE(SUM(jaja_sprzedane),0) as s FROM produkcja WHERE gospodarstwo_id=?",
            (g,)
        ).fetchone()["s"]
        urzadzenia = db.execute(
            "SELECT u.*, GROUP_CONCAT(uc.kanal||':'||uc.stan) as kanaly FROM urzadzenia u "
            "LEFT JOIN urzadzenia_kanaly uc ON u.id=uc.urzadzenie_id "
            "WHERE u.gospodarstwo_id=? AND u.aktywne=1 GROUP BY u.id",
            (g,)
        ).fetchall()
        db.close()

        pdz = float(get_setting("pasza_dzienna_kg", "6", g))
        nies = round((prod_dzis["jaja_zebrane"] if prod_dzis else 0) / kur * 100, 0) if kur else 0

        # Urządzenia przyciski
        urz_buttons = ""
        for u in urzadzenia:
            if u["kanaly"]:
                for kv in u["kanaly"].split(","):
                    if ":" in kv:
                        kanal, stan = kv.split(":", 1)
                        on = stan == "1"
                        urz_buttons += (
                            '<button onclick="togKiosk(' + str(u["id"]) + ',\'' + kanal + '\',' + ('false' if on else 'true') + ')" '
                            'style="width:100%;padding:20px;font-size:18px;font-weight:500;border:2px solid '
                            + ('#3B6D11' if on else '#e0ddd4') + ';background:'
                            + ('#EAF3DE' if on else '#fff') + ';border-radius:12px;cursor:pointer;margin-bottom:10px">'
                            + kanal + ' — ' + u["nazwa"] + '<br>'
                            '<span style="font-size:13px;color:#888">' + ('ON' if on else 'OFF') + '</span>'
                            '</button>'
                        )

        from flask import render_template_string
        from markupsafe import Markup
        KIOSK_HTML = """<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>Ferma — Kiosk</title>
<style>
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
body{font-family:system-ui,sans-serif;background:#f5f5f0;color:#2c2c2a;padding:12px;font-size:16px;max-width:600px;margin:0 auto}
h1{font-size:22px;font-weight:600;margin-bottom:16px;color:#534AB7}
.stat-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:16px}
.stat-card{background:#fff;border:1px solid #e0ddd4;border-radius:16px;padding:16px;text-align:center}
.stat-v{font-size:36px;font-weight:600;line-height:1.1}
.stat-l{font-size:13px;color:#888;margin-top:4px}
.form-card{background:#fff;border:1px solid #e0ddd4;border-radius:16px;padding:16px;margin-bottom:16px}
label{display:block;font-size:14px;color:#5f5e5a;margin:12px 0 4px}
input[type=number]{width:100%;padding:14px;border:2px solid #e0ddd4;border-radius:10px;font-size:24px;font-weight:500;text-align:center;background:#f9f9f7}
input[type=number]:focus{border-color:#534AB7;outline:none;background:#fff}
.submit-btn{width:100%;padding:18px;background:#3B6D11;color:#fff;border:none;border-radius:14px;font-size:20px;font-weight:600;cursor:pointer;margin-top:12px}
.submit-btn:active{transform:scale(0.97)}
.devices{margin-bottom:16px}
a.back{display:inline-block;padding:8px 16px;background:#fff;border:1px solid #e0ddd4;border-radius:8px;text-decoration:none;color:#534AB7;font-size:14px;margin-bottom:12px}
</style>
</head>
<body>
<a href="/" class="back">← Panel główny</a>
<h1>Szybki wpis</h1>
<div class="stat-grid">
  <div class="stat-card">
    <div class="stat-v" style="color:#3B6D11">{{ dzis_mag }}</div>
    <div class="stat-l">Jaj w magazynie</div>
  </div>
  <div class="stat-card">
    <div class="stat-v" style="color:{{ '#3B6D11' if nies >= 75 else '#A32D2D' }}">{{ nies }}%</div>
    <div class="stat-l">Nieśność dziś</div>
  </div>
</div>
<div class="form-card">
  <form method="POST" action="/produkcja/dodaj">
    <input type="hidden" name="data" value="{{ dzis }}">
    <label>Zebrane jaja</label>
    <input type="number" name="jaja_zebrane" min="0" max="200" inputmode="numeric"
           value="{{ prod_dzis.jaja_zebrane if prod_dzis else '' }}" placeholder="0">
    <label>Sprzedane dziś</label>
    <input type="number" name="jaja_sprzedane" min="0" inputmode="numeric"
           value="{{ prod_dzis.jaja_sprzedane if prod_dzis else '0' }}" placeholder="0">
    <label>Pasza wydana (kg)</label>
    <input type="number" name="pasza_wydana_kg" min="0" step="0.1" inputmode="decimal"
           value="{{ prod_dzis.pasza_wydana_kg if prod_dzis else pdz }}" placeholder="{{ pdz }}">
    <input type="hidden" name="cena_sprzedazy" value="{{ prod_dzis.cena_sprzedazy if prod_dzis else 0 }}">
    <input type="hidden" name="uwagi" value="">
    <button type="submit" class="submit-btn">Zapisz wpis</button>
  </form>
</div>
<div class="devices">{{ urz_buttons }}</div>
<script>
function togKiosk(uid,ch,state){
  fetch('/urzadzenia/cmd',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({urzadzenie_id:uid,kanal:ch,stan:state})})
  .then(r=>r.json()).then(()=>location.reload());
}
</script>
</body></html>"""

        return render_template_string(KIOSK_HTML,
            dzis_mag=dzis_mag, nies=int(nies), kur=kur, pdz=pdz,
            prod_dzis=prod_dzis, dzis=date.today().isoformat(),
            urz_buttons=Markup(urz_buttons))

    # ─── IMPORT XLSX ──────────────────────────────────────────────────────────
    @app.route("/import/xlsx", methods=["GET","POST"])
    @farm_required
    def import_xlsx_page():
        g = gid()
        if request.method == "POST":
            if "plik" not in request.files:
                flash("Brak pliku.")
                return redirect("/import/xlsx")
            plik = request.files["plik"]
            if not plik.filename.endswith(".xlsx"):
                flash("Tylko pliki .xlsx")
                return redirect("/import/xlsx")
            # Zapisz tymczasowo
            tmp = "/tmp/ferma_import.xlsx"
            plik.save(tmp)
            db = get_db()
            from import_xlsx import import_chicken_xlsx, import_receptury_xlsx
            typ = request.form.get("typ","produkcja")
            if typ == "produkcja":
                wyniki = import_chicken_xlsx(tmp, g, db)
            else:
                wyniki = import_receptury_xlsx(tmp, g, db)
            db.close()
            if "error" in wyniki:
                flash("Błąd: " + wyniki["error"])
            else:
                msg = f"Import zakończony. Produkcja: {wyniki.get('produkcja',0)}, Koszty: {wyniki.get('koszty',0)}"
                if wyniki.get("receptury"): msg += f", Receptury: {wyniki['receptury']}"
                if wyniki.get("bledy"): msg += f" | Błędy: {len(wyniki['bledy'])}"
                flash(msg)
            return redirect("/import/xlsx")

        html = (
            '<h1>Import danych z Excel</h1>'
            '<div class="card">'
            '<p style="font-size:14px;color:#5f5e5a;margin-bottom:16px">'
            'Zaimportuj historię produkcji i kosztów z Twojego arkusza Chicken.xlsx. '
            'Dane zostaną dodane do bieżącego gospodarstwa bez nadpisywania istniejących.</p>'
            '<form method="POST" enctype="multipart/form-data">'
            '<label>Plik Excel (.xlsx)</label>'
            '<input type="file" name="plik" accept=".xlsx" required>'
            '<label>Co importować</label>'
            '<select name="typ">'
            '<option value="produkcja">Produkcja + koszty (arkusze JAJKA, Koszta)</option>'
            '<option value="receptury">Receptury paszowe (Paszav2, Paszav3, Pasza Zimowa)</option>'
            '</select>'
            '<br><button class="btn bp" style="margin-top:12px">Importuj</button>'
            '</form></div>'
            '<div class="card"><b>Obsługiwane arkusze</b>'
            '<ul style="font-size:13px;color:#5f5e5a;margin-top:8px;list-style:disc;margin-left:20px">'
            '<li><b>JAJKA</b> — historia dzienna: zebrane jaja, sprzedane, nieśność, zarobek</li>'
            '<li><b>Koszta</b> — koszty miesięczne: zwierzęta, witaminy, kreda, zboża</li>'
            '<li><b>Paszav2 / Paszav3 / Pasza Zimowa</b> — receptury z proporcjami składników</li>'
            '</ul></div>'
        )
        return R(html, "ust")

    # ─── SUPLA WEBHOOK ────────────────────────────────────────────────────────
    @app.route("/webhook/supla", methods=["POST"])
    def supla_webhook():
        data = request.get_json() or {}
        ok = supla_webhook_receive(data)
        return jsonify({"ok": ok})

    # ─── SUPLA KONFIGURACJA ───────────────────────────────────────────────────
    @app.route("/integracje/supla")
    @farm_required
    def supla_config_page():
        g = gid()
        db = get_db()
        configs = db.execute("SELECT * FROM supla_config WHERE gospodarstwo_id=? ORDER BY nazwa", (g,)).fetchall()
        db.close()
        w = "".join(
            '<tr><td>' + c["nazwa"] + '</td><td><code>' + (c["server_url"] or "") + '</code></td>'
            '<td>' + str(c["channel_id"] or "") + '</td>'
            '<td><span class="badge ' + ('b-green' if c["aktywny"] else 'b-gray') + '">' + ('aktywna' if c["aktywny"] else 'wyłączona') + '</span></td>'
            '<td><a href="/integracje/supla/' + str(c["id"]) + '/usun" class="btn br bsm">✕</a></td></tr>'
            for c in configs
        )
        html = (
            '<h1>Integracja Supla</h1>'
            '<div class="card"><b>Webhook URL do wpisania w Supla</b>'
            '<p style="font-size:13px;margin-top:6px"><code>https://twoja-domena.pl/webhook/supla</code></p>'
            '<p style="font-size:12px;color:#888;margin-top:4px">W Supla Cloud: Kanał → Akcje → Wyślij HTTP Request</p>'
            '</div>'
            '<a href="/integracje/supla/dodaj" class="btn bp bsm" style="margin-bottom:12px">+ Dodaj kanał Supla</a>'
            '<div class="card" style="overflow-x:auto"><table>'
            '<thead><tr><th>Nazwa</th><th>Serwer</th><th>Channel ID</th><th>Status</th><th></th></tr></thead>'
            '<tbody>' + (w or '<tr><td colspan=5 style="color:#888;text-align:center;padding:16px">Brak konfiguracji</td></tr>') + '</tbody></table></div>'
        )
        return R(html, "gpio")

    @app.route("/integracje/supla/dodaj", methods=["GET","POST"])
    @farm_required
    def supla_dodaj():
        g = gid()
        if request.method == "POST":
            db = get_db()
            db.execute("INSERT INTO supla_config(gospodarstwo_id,nazwa,server_url,token,channel_id) VALUES(?,?,?,?,?)",
                (g, request.form["nazwa"], request.form.get("server_url","https://svr1.supla.org"),
                 request.form.get("token",""), request.form.get("channel_id",0) or 0))
            db.commit(); db.close()
            flash("Kanał Supla dodany.")
            return redirect("/integracje/supla")
        html = (
            '<h1>Nowy kanał Supla</h1><div class="card"><form method="POST">'
            '<label>Nazwa</label><input name="nazwa" required placeholder="np. Przekaźnik światło">'
            '<label>Serwer Supla</label><input name="server_url" value="https://svr1.supla.org">'
            '<label>Token OAuth2</label><input name="token" placeholder="Bearer token z Supla Cloud">'
            '<label>Channel ID</label><input name="channel_id" type="number" placeholder="ID kanału z Supla">'
            '<br><button class="btn bp">Zapisz</button>'
            '<a href="/integracje/supla" class="btn bo" style="margin-left:8px">Anuluj</a>'
            '</form></div>'
        )
        return R(html, "gpio")

    # ─── ESPHOME ──────────────────────────────────────────────────────────────
    @app.route("/integracje/esphome")
    @farm_required
    def esphome_page():
        html = (
            '<h1>ESPHome — konfiguracja</h1>'
            '<div class="card"><b>Szablon konfiguracji ESPHome</b>'
            '<p style="font-size:13px;color:#5f5e5a;margin:8px 0">Wgraj przez: <code>esphome run kurnik_a.yaml</code></p>'
            '<a href="/integracje/esphome/config/download" class="btn bp bsm" style="margin-bottom:10px">Pobierz kurnik_a.yaml</a>'
            '<pre style="background:#f5f5f0;border-radius:8px;padding:14px;font-size:11px;overflow-x:auto;border:1px solid #e0ddd4;white-space:pre-wrap">'
            + ESPHOME_CONFIG_TEMPLATE.replace("<","&lt;").replace(">","&gt;")
            + '</pre></div>'
            '<div class="card"><b>ZeroTier / Tailscale (urządzenia w innej sieci)</b>'
            '<pre style="background:#f5f5f0;border-radius:8px;padding:14px;font-size:11px;overflow-x:auto;border:1px solid #e0ddd4;white-space:pre-wrap">'
            + ZEROTIER_INSTRUCTIONS.replace("<","&lt;").replace(">","&gt;")
            + '</pre></div>'
            '<div class="card"><b>Jak połączyć ESPHome z Ferma Jaj</b>'
            '<ol style="font-size:13px;color:#5f5e5a;margin:8px 0;list-style:decimal;margin-left:20px">'
            '<li>Wgraj firmware ESPHome na ESP32 (edytuj SSID, hasło, API key)</li>'
            '<li>W panelu Ferma → Urządzenia → Dodaj urządzenie → wybierz <b>ESPHome</b></li>'
            '<li>Wpisz IP urządzenia (z routera lub ZeroTier) i ten sam API key</li>'
            '<li>System automatycznie komunikuje się przez REST API ESPHome</li>'
            '</ol></div>'
        )
        return R(html, "gpio")

    @app.route("/integracje/esphome/config/download")
    @farm_required
    def esphome_config_download():
        return send_file(io.BytesIO(ESPHOME_CONFIG_TEMPLATE.encode()),
                         mimetype="text/yaml", as_attachment=True,
                         download_name="kurnik_a.yaml")

    # ─── POJENIE HARMONOGRAM ──────────────────────────────────────────────────
    @app.route("/pojenie")
    @farm_required
    def pojenie():
        g = gid()
        db = get_db()
        harmonogramy = db.execute(
            "SELECT h.*, u.nazwa as urz_nazwa FROM harmonogram_pojenia h "
            "LEFT JOIN urzadzenia u ON h.urzadzenie_id=u.id "
            "WHERE h.gospodarstwo_id=? ORDER BY h.czas_otwarcia",
            (g,)
        ).fetchall()
        db.close()
        w = "".join(
            '<tr>'
            '<td style="font-weight:500">' + h["nazwa"] + '</td>'
            '<td>' + (h["urz_nazwa"] or "—") + ' / ' + (h["kanal"] or "—") + '</td>'
            '<td>' + (h["czas_otwarcia"] or "—") + '</td>'
            '<td>' + str(h["czas_trwania_s"]) + ' s</td>'
            '<td>co ' + str(h["powtarzaj_co_h"]) + ' h</td>'
            '<td><span class="badge ' + ('b-green' if h["aktywny"] else 'b-gray') + '">' + ('aktywne' if h["aktywny"] else 'wyłączone') + '</span></td>'
            '<td class="nowrap">'
            '<a href="/pojenie/' + str(h["id"]) + '/toggle" class="btn bo bsm">' + ('Wyłącz' if h["aktywny"] else 'Włącz') + '</a> '
            '<a href="/pojenie/' + str(h["id"]) + '/uruchom" class="btn bg bsm">Uruchom</a>'
            '</td></tr>'
            for h in harmonogramy
        )
        html = (
            '<h1>Pojenie — harmonogram</h1>'
            '<a href="/pojenie/dodaj" class="btn bp bsm" style="margin-bottom:12px">+ Dodaj harmonogram</a>'
            '<div class="card" style="overflow-x:auto"><table>'
            '<thead><tr><th>Nazwa</th><th>Urządzenie/Kanał</th><th>Otwarcie</th><th>Czas</th><th>Cykl</th><th>Status</th><th></th></tr></thead>'
            '<tbody>' + (w or '<tr><td colspan=7 style="color:#888;text-align:center;padding:20px">Brak harmonogramów</td></tr>') + '</tbody></table></div>'
        )
        return R(html, "gpio")

    @app.route("/pojenie/dodaj", methods=["GET","POST"])
    @farm_required
    def pojenie_dodaj():
        g = gid()
        if request.method == "POST":
            db = get_db()
            db.execute("""INSERT INTO harmonogram_pojenia(gospodarstwo_id,nazwa,urzadzenie_id,kanal,
                czas_otwarcia,czas_zamkniecia,czas_trwania_s,powtarzaj_co_h,aktywny) VALUES(?,?,?,?,?,?,?,?,1)""",
                (g, request.form["nazwa"],
                 request.form.get("urzadzenie_id") or None,
                 request.form.get("kanal","relay2"),
                 request.form.get("czas_otwarcia","08:00"),
                 request.form.get("czas_zamkniecia",""),
                 int(request.form.get("czas_trwania_s",30)),
                 int(request.form.get("powtarzaj_co_h",4))))
            db.commit(); db.close()
            flash("Harmonogram pojenia dodany.")
            return redirect("/pojenie")
        db = get_db()
        urzadzenia = db.execute("SELECT id,nazwa FROM urzadzenia WHERE gospodarstwo_id=? AND aktywne=1", (g,)).fetchall()
        db.close()
        opt = "".join(f'<option value="{u["id"]}">{u["nazwa"]}</option>' for u in urzadzenia)
        html = (
            '<h1>Nowy harmonogram pojenia</h1><div class="card"><form method="POST">'
            '<label>Nazwa</label><input name="nazwa" required placeholder="np. Pojenie poranne">'
            '<div class="g2">'
            '<div><label>Urządzenie</label><select name="urzadzenie_id"><option value="">— wybierz —</option>' + opt + '</select></div>'
            '<div><label>Kanał (relay)</label><input name="kanal" value="relay2" placeholder="relay2"></div>'
            '</div>'
            '<div class="g3">'
            '<div><label>Godzina otwarcia</label><input name="czas_otwarcia" type="time" value="08:00"></div>'
            '<div><label>Czas trwania (s)</label><input name="czas_trwania_s" type="number" value="30" min="5" max="300"></div>'
            '<div><label>Powtarzaj co (h)</label><input name="powtarzaj_co_h" type="number" value="4" min="1" max="24"></div>'
            '</div>'
            '<br><button class="btn bp">Dodaj</button>'
            '<a href="/pojenie" class="btn bo" style="margin-left:8px">Anuluj</a>'
            '</form></div>'
        )
        return R(html, "gpio")

    @app.route("/pojenie/<int:hid>/toggle")
    @farm_required
    def pojenie_toggle(hid):
        g = gid()
        db = get_db()
        db.execute("UPDATE harmonogram_pojenia SET aktywny=1-aktywny WHERE id=? AND gospodarstwo_id=?", (hid,g))
        db.commit(); db.close()
        flash("Status zmieniony.")
        return redirect("/pojenie")

    @app.route("/pojenie/<int:hid>/uruchom")
    @farm_required
    def pojenie_uruchom(hid):
        g = gid()
        db = get_db()
        h = db.execute("SELECT * FROM harmonogram_pojenia WHERE id=? AND gospodarstwo_id=?", (hid,g)).fetchone()
        db.close()
        if h and h["urzadzenie_id"] and h["kanal"]:
            import time as tm
            from devices import send_command
            ok, msg = send_command(h["urzadzenie_id"], h["kanal"], True, g)
            if ok:
                flash(f"Pojenie uruchomione na {h['czas_trwania_s']} sekund.")
                def auto_close():
                    tm.sleep(h["czas_trwania_s"])
                    send_command(h["urzadzenie_id"], h["kanal"], False, g)
                import threading
                threading.Thread(target=auto_close, daemon=True).start()
            else:
                flash("Błąd: " + msg)
        else:
            flash("Skonfiguruj urządzenie i kanał.")
        return redirect("/pojenie")

    return app
