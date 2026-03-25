# -*- coding: utf-8 -*-
"""
missing_routes.py — wszystkie brakujące route'y które dają 404:
- /integracje/esphome + download config
- /pojenie + /pojenie/dodaj + toggle + uruchom  
- /gpio (główna przekaźniki)
- /ustawienia
- /magazyn
Dodaj w app.py: from missing_routes import register_missing; register_missing(app)
"""
from flask import request, redirect, flash, session, jsonify, send_file
from datetime import datetime, date, timedelta
import io, threading

def register_missing(app):
    from db import get_db, get_setting, save_setting
    from auth import farm_required, login_required
    from app import R

    def gid(): return session.get("farm_id")
    def gs(k, d=""): return get_setting(k, d, gid())

    # ══════════════════════════════════════════════════════════════════════
    # ESPHOME
    # ══════════════════════════════════════════════════════════════════════
    ESPHOME_YAML = """esphome:
  name: kurnik-a
  friendly_name: Kurnik A

esp32:
  board: esp32dev
  framework:
    type: arduino

wifi:
  ssid: !secret wifi_ssid
  password: !secret wifi_password

web_server:
  port: 80

api:
  password: !secret api_password

ota:
  password: !secret ota_password

logger:

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

output:
  - platform: ledc
    pin: GPIO5
    id: led_pwm

light:
  - platform: monochromatic
    name: "LED Kurnik"
    output: led_pwm
    id: led_kurnik

one_wire:
  - platform: gpio
    pin: GPIO4

sensor:
  - platform: dallas_temp
    name: "Temperatura"
    address: 0x0000000000000000
  - platform: wifi_signal
    name: "WiFi"
    update_interval: 60s
"""

    ZEROTIER_INFO = """# ZeroTier / Tailscale dla urządzeń w innej sieci

## Tailscale (najprostsze)
Na każdym urządzeniu (RPi/serwer):
  curl -fsSL https://tailscale.com/install.sh | sh
  sudo tailscale up
Zatwierdź w panelu tailscale.com
Wpisz adres Tailscale IP urządzenia zamiast lokalnego IP.

## ZeroTier
  curl -s https://install.zerotier.com | sudo bash
  sudo zerotier-cli join NETWORK_ID

## ESP32
ESP32 nie obsługuje ZeroTier/Tailscale.
Rozwiązania:
1. cloudflared tunnel per ESP32 (najłatwiejsze)
2. RPi jako gateway WiFi dla ESP32
"""

    @app.route("/integracje/esphome")
    @farm_required
    def esphome_page():
        html = (
            '<h1>ESPHome — integracja</h1>'
            '<div class="card" style="border-left:3px solid #534AB7;border-radius:0 12px 12px 0">'
            '<b>Jak podłączyć ESPHome do Ferma Jaj</b>'
            '<ol style="font-size:13px;color:#5f5e5a;margin:10px 0;list-style:decimal;margin-left:18px;line-height:2.2">'
            '<li>Pobierz szablon YAML → wgraj przez <code>esphome run kurnik_a.yaml</code></li>'
            '<li>Edytuj SSID, hasło WiFi i api_password w pliku</li>'
            '<li>Panel → Sterowanie → Urządzenia → <b>Dodaj urządzenie</b></li>'
            '<li>Typ: <b>ESPHome</b>, wpisz IP i ten sam api_password</li>'
            '<li>System komunikuje się przez natywne REST API ESPHome (/api/switch/relay1/turn_on itd.)</li>'
            '</ol>'
            '<a href="/integracje/esphome/config" class="btn bp bsm">Pobierz kurnik_a.yaml</a>'
            '</div>'
            '<div class="card"><b>Szablon konfiguracji</b>'
            '<pre style="background:#f5f5f0;border-radius:8px;padding:14px;font-size:11px;'
            'overflow-x:auto;border:1px solid #e0ddd4;white-space:pre">'
            + ESPHOME_YAML.replace('<','&lt;').replace('>','&gt;')
            + '</pre></div>'
            '<div class="card"><b>Urządzenia w innej sieci — ZeroTier / Tailscale</b>'
            '<pre style="background:#f5f5f0;border-radius:8px;padding:14px;font-size:12px;'
            'border:1px solid #e0ddd4;white-space:pre-wrap">'
            + ZEROTIER_INFO
            + '</pre></div>'
            '<div class="card"><b>Dostępne encje w ESPHome</b>'
            '<p style="font-size:13px;color:#5f5e5a;margin-top:8px">'
            'Po wgraniu firmware ESPHome udostępnia REST API:<br>'
            '<code>GET /api/states</code> — wszystkie stany<br>'
            '<code>POST /api/switch/relay1/turn_on</code> — włącz relay1<br>'
            '<code>POST /api/switch/relay1/turn_off</code> — wyłącz relay1<br>'
            '<code>POST /api/light/led_kurnik/turn_on</code> + JSON <code>{"brightness":128}</code> — ściemniacz LED'
            '</p></div>'
        )
        return R(html, "gpio")

    @app.route("/integracje/esphome/config")
    @farm_required
    def esphome_config_download():
        return send_file(
            io.BytesIO(ESPHOME_YAML.encode()),
            mimetype="text/yaml",
            as_attachment=True,
            download_name="kurnik_a.yaml"
        )

    # ══════════════════════════════════════════════════════════════════════
    # POJENIE
    # ══════════════════════════════════════════════════════════════════════
    @app.route("/pojenie")
    @farm_required
    def pojenie():
        g = gid()
        db = get_db()
        rows = db.execute(
            "SELECT h.*, u.nazwa as urz_nazwa FROM harmonogram_pojenia h "
            "LEFT JOIN urzadzenia u ON h.urzadzenie_id=u.id "
            "WHERE h.gospodarstwo_id=? ORDER BY h.czas_otwarcia",
            (g,)
        ).fetchall()
        db.close()

        w = "".join(
            '<tr>'
            '<td style="font-weight:500">' + r["nazwa"] + '</td>'
            '<td>' + (r["urz_nazwa"] or "—") + '</td>'
            '<td><code>' + (r["kanal"] or "—") + '</code></td>'
            '<td>' + (r["czas_otwarcia"] or "—") + '</td>'
            '<td>' + str(r["czas_trwania_s"]) + ' s</td>'
            '<td>co ' + str(r["powtarzaj_co_h"]) + ' h</td>'
            '<td><span class="badge ' + ('b-green' if r["aktywny"] else 'b-gray') + '">'
            + ('aktywne' if r["aktywny"] else 'wyłączone') + '</span></td>'
            '<td class="nowrap">'
            '<a href="/pojenie/' + str(r["id"]) + '/uruchom" class="btn bg bsm">▶ Uruchom</a> '
            '<a href="/pojenie/' + str(r["id"]) + '/toggle" class="btn bo bsm">'
            + ('Wyłącz' if r["aktywny"] else 'Włącz') + '</a>'
            '</td></tr>'
            for r in rows
        )
        html = (
            '<h1>Pojenie — harmonogram</h1>'
            '<a href="/pojenie/dodaj" class="btn bp bsm" style="margin-bottom:12px">+ Dodaj harmonogram</a>'
            '<div class="card" style="overflow-x:auto"><table>'
            '<thead><tr><th>Nazwa</th><th>Urządzenie</th><th>Kanał</th>'
            '<th>Godzina</th><th>Czas</th><th>Cykl</th><th>Status</th><th></th></tr></thead>'
            '<tbody>' + (w or '<tr><td colspan=8 style="color:#888;text-align:center;padding:20px">'
                          'Brak harmonogramów — dodaj poniżej</td></tr>') + '</tbody></table></div>'
            '<div class="card"><b>Jak to działa</b>'
            '<p style="font-size:13px;color:#5f5e5a;margin-top:8px">'
            'Przycisk <b>Uruchom</b> — natychmiastowe otwarcie zaworu na ustawiony czas (s), potem automatyczne zamknięcie.<br>'
            'Harmonogram działa gdy serwer jest uruchomiony. '
            'Dla automatycznego pojenia w ustalonych godzinach skonfiguruj harmonogram w ESPHome lub Supla.'
            '</p></div>'
        )
        return R(html, "gpio")

    @app.route("/pojenie/dodaj", methods=["GET","POST"])
    @farm_required
    def pojenie_dodaj():
        g = gid()
        if request.method == "POST":
            db = get_db()
            db.execute(
                "INSERT INTO harmonogram_pojenia(gospodarstwo_id,nazwa,urzadzenie_id,"
                "kanal,czas_otwarcia,czas_trwania_s,powtarzaj_co_h,aktywny) VALUES(?,?,?,?,?,?,?,1)",
                (g, request.form["nazwa"],
                 request.form.get("urzadzenie_id") or None,
                 request.form.get("kanal","relay2"),
                 request.form.get("czas_otwarcia","08:00"),
                 int(request.form.get("czas_trwania_s",30)),
                 int(request.form.get("powtarzaj_co_h",4)))
            )
            db.commit(); db.close()
            flash("Harmonogram pojenia dodany.")
            return redirect("/pojenie")

        db = get_db()
        urzadzenia = db.execute(
            "SELECT id,nazwa FROM urzadzenia WHERE gospodarstwo_id=? AND aktywne=1", (g,)
        ).fetchall()
        db.close()
        u_opt = '<option value="">— brak —</option>' + "".join(
            f'<option value="{u["id"]}">{u["nazwa"]}</option>' for u in urzadzenia
        )
        k_opt = "".join(
            f'<option value="relay{i}">relay{i}</option>' for i in range(1,5)
        )
        html = (
            '<h1>Nowy harmonogram pojenia</h1><div class="card"><form method="POST">'
            '<label>Nazwa</label><input name="nazwa" required placeholder="np. Pojenie poranne">'
            '<div class="g2">'
            '<div><label>Urządzenie (ESP32/RPi)</label><select name="urzadzenie_id">' + u_opt + '</select></div>'
            '<div><label>Kanał (relay z zaworem wody)</label><select name="kanal">' + k_opt + '</select></div>'
            '</div>'
            '<div class="g3">'
            '<div><label>Godzina otwarcia</label><input name="czas_otwarcia" type="time" value="08:00"></div>'
            '<div><label>Czas trwania (sekundy)</label><input name="czas_trwania_s" type="number" value="30" min="5" max="300"></div>'
            '<div><label>Powtarzaj co (godziny)</label><input name="powtarzaj_co_h" type="number" value="4" min="1" max="24"></div>'
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
        db.execute(
            "UPDATE harmonogram_pojenia SET aktywny=1-aktywny WHERE id=? AND gospodarstwo_id=?",
            (hid, g)
        )
        db.commit(); db.close()
        flash("Status zmieniony.")
        return redirect("/pojenie")

    @app.route("/pojenie/<int:hid>/uruchom")
    @farm_required
    def pojenie_uruchom(hid):
        g = gid()
        db = get_db()
        h = db.execute(
            "SELECT * FROM harmonogram_pojenia WHERE id=? AND gospodarstwo_id=?", (hid, g)
        ).fetchone()
        db.close()
        if not h:
            flash("Nie znaleziono harmonogramu.")
            return redirect("/pojenie")
        if not h["urzadzenie_id"] or not h["kanal"]:
            flash("Skonfiguruj urządzenie i kanał przed uruchomieniem.")
            return redirect("/pojenie")

        from devices import send_command
        ok, msg = send_command(h["urzadzenie_id"], h["kanal"], True, g)
        if ok:
            flash(f"Pojenie uruchomione na {h['czas_trwania_s']} sekund.")
            sek = h["czas_trwania_s"]
            did = h["urzadzenie_id"]
            kanal = h["kanal"]
            def auto_close():
                import time as t; t.sleep(sek)
                try:
                    send_command(did, kanal, False, g)
                except Exception:
                    pass
            threading.Thread(target=auto_close, daemon=True).start()
        else:
            flash("Błąd komunikacji: " + str(msg))
        return redirect("/pojenie")

    # ══════════════════════════════════════════════════════════════════════
    # GPIO — główna strona przekaźników
    # ══════════════════════════════════════════════════════════════════════
    @app.route("/gpio")
    @farm_required
    def gpio_main():
        g = gid()
        db = get_db()
        urzadzenia = db.execute(
            "SELECT u.*, GROUP_CONCAT(c.id||'|'||c.kanal||'|'||c.opis||'|'||c.stan, ';;') as kanaly "
            "FROM urzadzenia u "
            "LEFT JOIN urzadzenia_kanaly c ON u.id=c.urzadzenie_id "
            "WHERE u.gospodarstwo_id=? AND u.aktywne=1 GROUP BY u.id",
            (g,)
        ).fetchall()
        db.close()

        urz_html = ""
        for u in urzadzenia:
            ch_html = ""
            if u["kanaly"]:
                for ch_str in u["kanaly"].split(";;"):
                    parts = ch_str.split("|")
                    if len(parts) < 4: continue
                    cid, kanal, opis, stan = parts[0], parts[1], parts[2], parts[3]
                    on = stan == "1"
                    ch_html += (
                        f'<div class="relay-card {"relay-on" if on else ""}" '
                        f'onclick="togRelay({u["id"]},\'{kanal}\',{"false" if on else "true"})" '
                        f'style="cursor:pointer">'
                        f'<div class="tog {"on" if on else ""}"></div>'
                        f'<div style="font-size:12px;margin-top:6px;font-weight:500">{kanal}</div>'
                        f'<div style="font-size:11px;color:#888">{opis or ""}</div>'
                        f'<div style="font-size:11px;color:{"#3B6D11" if on else "#aaa"}">'
                        f'{"ON" if on else "OFF"}</div></div>'
                    )
            badge_kol = "b-green" if u["status"]=="online" else "b-red"
            urz_html += (
                f'<div class="card">'
                f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">'
                f'<b>{u["nazwa"]}</b>'
                f'<span class="badge b-blue">{u["typ"].upper()}</span>'
                f'<span class="badge {badge_kol}">{u["status"]}</span>'
                f'<code style="font-size:11px;color:#888">{u["ip"]}:{u["port"]}</code>'
                f'<a href="/urzadzenia/{u["id"]}/ping" class="btn bo bsm" style="margin-left:auto">Ping</a>'
                f'<a href="/urzadzenia/{u["id"]}" class="btn bo bsm">Panel</a>'
                f'</div>'
                f'<div class="g4">{ch_html}</div>'
                f'</div>'
            )

        html = (
            '<h1>GPIO — przekaźniki</h1>'
            '<div style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap">'
            '<a href="/urzadzenia/dodaj" class="btn bp bsm">+ Dodaj urządzenie</a>'
            '<a href="/gpio/pwm" class="btn bo bsm">LED PWM</a>'
            '<a href="/pojenie" class="btn bo bsm">Pojenie</a>'
            '<a href="/integracje/esphome" class="btn bo bsm">ESPHome</a>'
            '<a href="/supla" class="btn bo bsm">Supla</a>'
            '</div>'
            + (urz_html or
               '<div class="card"><p style="color:#888;text-align:center;padding:20px">'
               'Brak aktywnych urządzeń. <a href="/urzadzenia/dodaj" style="color:#534AB7">Dodaj ESP32 lub RPi slave</a>.</p></div>')
            + '<script>'
            'function togRelay(did,ch,st){'
            'fetch("/urzadzenia/cmd",{method:"POST",'
            'headers:{"Content-Type":"application/json"},'
            'body:JSON.stringify({urzadzenie_id:did,kanal:ch,stan:st})})'
            '.then(r=>r.json()).then(()=>location.reload());}'
            '</script>'
        )
        return R(html, "gpio")

    # ══════════════════════════════════════════════════════════════════════
    # USTAWIENIA
    # ══════════════════════════════════════════════════════════════════════
    @app.route("/ustawienia", methods=["GET","POST"])
    @farm_required
    def ustawienia():
        g = gid()
        if request.method == "POST":
            for k in ["pasza_dzienna_kg","cena_jajka","cena_wody_litra",
                      "cena_kwh","liczba_kur","etykieta_producent","etykieta_adres"]:
                v = request.form.get(k)
                if v is not None:
                    save_setting(k, v.strip(), g)
            flash("Ustawienia zapisane.")
            return redirect("/ustawienia")

        vals = {k: gs(k, d) for k,d in [
            ("pasza_dzienna_kg","6"), ("cena_jajka","1.20"),
            ("cena_wody_litra","0.005"), ("cena_kwh","0.80"),
            ("liczba_kur","15"), ("etykieta_producent","Ferma Jaj"),
            ("etykieta_adres",""),
        ]}

        def field(label, name, typ="text", step=""):
            v = vals.get(name,"")
            s = f' step="{step}"' if step else ""
            t = f' type="{typ}"' if typ != "text" else ""
            return f'<div><label>{label}</label><input name="{name}" value="{v}"{t}{s}></div>'

        html = (
            '<h1>Ustawienia gospodarstwa</h1>'
            '<form method="POST">'
            '<div class="card"><b>Produkcja</b>'
            '<div class="g3" style="margin-top:10px">'
            + field("Liczba kur niosek","liczba_kur","number")
            + field("Dzienne zużycie paszy (kg)","pasza_dzienna_kg","number","0.1")
            + field("Domyślna cena jajka (zł)","cena_jajka","number","0.01")
            + '</div></div>'
            '<div class="card"><b>Ceny mediów</b>'
            '<div class="g3" style="margin-top:10px">'
            + field("Cena wody (zł/litr)","cena_wody_litra","number","0.0001")
            + field("Cena prądu (zł/kWh)","cena_kwh","number","0.01")
            + '</div></div>'
            '<div class="card"><b>Etykiety</b>'
            '<div class="g2" style="margin-top:10px">'
            + field("Producent na etykiecie","etykieta_producent")
            + field("Adres na etykiecie","etykieta_adres")
            + '</div></div>'
            '<button class="btn bp" style="margin-top:4px">Zapisz ustawienia</button>'
            '</form>'
            '<div class="card" style="margin-top:12px"><b>Skróty</b>'
            '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px">'
            '<a href="/import/xlsx" class="btn bo bsm">Import Chicken.xlsx</a>'
            '<a href="/admin/farm-assign" class="btn bo bsm">Przypisz farmy</a>'
            '<a href="/pasza/skladniki-baza" class="btn bo bsm">Baza składników</a>'
            '<a href="/backup/sheets" class="btn bo bsm">Backup Google Sheets</a>'
            '</div></div>'
        )
        return R(html, "ust")

    # ══════════════════════════════════════════════════════════════════════
    # MAGAZYN JAJ
    # ══════════════════════════════════════════════════════════════════════
    @app.route("/magazyn")
    @farm_required
    def magazyn():
        g = gid()
        db = get_db()
        # Stan magazynu jaj
        total = db.execute(
            "SELECT COALESCE(SUM(jaja_zebrane),0) as z, COALESCE(SUM(jaja_sprzedane),0) as s "
            "FROM produkcja WHERE gospodarstwo_id=?", (g,)
        ).fetchone()
        stan = max(0, total["z"] - total["s"])

        # Rezerwacje z zamówień
        rezerwacje = db.execute(
            "SELECT z.*, k.nazwa as kn FROM zamowienia z "
            "LEFT JOIN klienci k ON z.klient_id=k.id "
            "WHERE z.gospodarstwo_id=? AND z.status IN ('nowe','potwierdzone') "
            "ORDER BY z.data_dostawy", (g,)
        ).fetchall()
        zarezerwowane = sum(r["ilosc"] for r in rezerwacje)

        # Ostatnie 30 dni produkcja
        hist = db.execute(
            "SELECT data, jaja_zebrane, jaja_sprzedane FROM produkcja "
            "WHERE gospodarstwo_id=? ORDER BY data DESC LIMIT 30", (g,)
        ).fetchall()
        db.close()

        w_rez = "".join(
            '<tr>'
            '<td>' + r["data_dostawy"] + '</td>'
            '<td>' + (r["kn"] or "—") + '</td>'
            '<td style="font-weight:500">' + str(r["ilosc"]) + ' szt.</td>'
            '<td>' + str(round(r["ilosc"]*(r["cena_za_szt"] or 0),2)) + ' zł</td>'
            '<td><a href="/zamowienia/' + str(r["id"]) + '/status/dostarczone" class="btn bg bsm">Dostarcz</a></td>'
            '</tr>'
            for r in rezerwacje
        )
        w_hist = "".join(
            '<tr><td>' + r["data"] + '</td>'
            '<td>' + str(r["jaja_zebrane"]) + '</td>'
            '<td>' + str(r["jaja_sprzedane"]) + '</td>'
            '<td>' + str(max(0, r["jaja_zebrane"]-r["jaja_sprzedane"])) + '</td></tr>'
            for r in hist
        )

        html = (
            '<h1>Magazyn jaj</h1>'
            '<div class="g3" style="margin-bottom:12px">'
            '<div class="card stat"><div class="v" style="color:' + ('#3B6D11' if stan > 0 else '#888') + '">' + str(stan) + '</div><div class="l">Stan magazynu</div><div class="s">szt.</div></div>'
            '<div class="card stat"><div class="v" style="color:#BA7517">' + str(zarezerwowane) + '</div><div class="l">Zarezerwowane</div><div class="s">w zamówieniach</div></div>'
            '<div class="card stat"><div class="v" style="color:' + ('#3B6D11' if stan-zarezerwowane >= 0 else '#A32D2D') + '">' + str(max(0,stan-zarezerwowane)) + '</div><div class="l">Dostępne</div><div class="s">po odliczeniu rezerwacji</div></div>'
            '</div>'
            + ('<div class="card"><b>Zaplanowane dostawy</b>'
               '<div style="overflow-x:auto"><table style="margin-top:8px">'
               '<thead><tr><th>Data</th><th>Klient</th><th>Ilość</th><th>Wartość</th><th></th></tr></thead>'
               '<tbody>' + w_rez + '</tbody></table></div></div>' if rezerwacje else '')
            + '<div class="card" style="overflow-x:auto"><b>Historia 30 dni</b>'
            '<table style="margin-top:8px"><thead><tr><th>Data</th><th>Zebrane</th><th>Sprzedane</th><th>Zostało</th></tr></thead>'
            '<tbody>' + (w_hist or '<tr><td colspan=4 style="color:#888;padding:12px">Brak danych</td></tr>') + '</tbody></table></div>'
        )
        return R(html, "mag")

    return app
