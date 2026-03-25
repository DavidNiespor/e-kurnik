# -*- coding: utf-8 -*-
"""
supla_handler.py — integracja z Supla przez webhook
Supla wysyła HTTP POST gdy zmienia się stan kanału (przełącznik, czujnik).
Ferma rejestruje i wykonuje akcje po stronie GPIO / urządzeń slave.

Konfiguracja w Supla Cloud:
  Kanał → Akcje bezpośrednie → Wyślij żądanie HTTP
  URL:    https://twoja-domena.pl/webhook/supla
  Metoda: POST
  Nagłówek: X-Supla-Token: TWOJ_TOKEN  (ustaw w panelu Ustawienia)
  Treść: {"channel_id": {{channel_id}}, "state": {{value}}, "action": "{{action}}"}
"""
import json, hashlib, hmac
from datetime import datetime
from flask import Flask, request, jsonify
from db import get_db, get_setting


# ─── GŁÓWNY HANDLER WEBHOOKA ──────────────────────────────────────────────────

def handle_supla_webhook(data: dict, token_header: str) -> dict:
    """
    Przetwarza przychodzący webhook z Supla.
    Zwraca {"ok": bool, "action": str, "msg": str}
    """
    db = get_db()

    # 1. Znajdź konfigurację Supla pasującą do channel_id
    channel_id = data.get("channel_id") or data.get("channel", {}).get("id")
    action_raw = data.get("action","").upper()
    state_raw  = data.get("state")

    if channel_id is None:
        db.close()
        return {"ok": False, "msg": "Brak channel_id w payload"}

    cfg = db.execute(
        "SELECT * FROM supla_config WHERE channel_id=? AND aktywny=1", (channel_id,)
    ).fetchone()

    if not cfg:
        db.close()
        return {"ok": False, "msg": f"Brak konfiguracji dla channel_id={channel_id}"}

    # 2. Weryfikacja tokenu (jeśli skonfigurowany)
    supla_token = get_setting("supla_webhook_token","")
    if supla_token and token_header != supla_token:
        db.close()
        return {"ok": False, "msg": "Nieprawidłowy token"}

    gid = cfg["gospodarstwo_id"]

    # 3. Ustal stan ON/OFF
    if action_raw in ("TURN_ON","ON","1","HIGH"):
        stan = True
    elif action_raw in ("TURN_OFF","OFF","0","LOW"):
        stan = False
    elif state_raw is not None:
        stan = bool(state_raw) if not isinstance(state_raw, str) else state_raw.lower() in ("1","true","on","high")
    else:
        stan = None

    # 4. Zaloguj zdarzenie
    db.execute(
        "INSERT INTO supla_log(czas,channel_id,action_raw,stan,payload,gospodarstwo_id) VALUES(?,?,?,?,?,?)",
        (datetime.now().isoformat(), channel_id, action_raw,
         1 if stan else 0, json.dumps(data), gid)
    )

    wynik = {"ok": True, "action": action_raw, "stan": stan, "channel_id": channel_id}

    # 5. Wykonaj akcję — wyślij polecenie do powiązanego urządzenia slave
    if stan is not None:
        urz_id = cfg.get("powiazane_urzadzenie_id")
        kanal  = cfg.get("powiazany_kanal")

        if urz_id and kanal:
            try:
                from devices import send_command
                ok, msg = send_command(urz_id, kanal, stan, gid)
                wynik["slave_ok"]  = ok
                wynik["slave_msg"] = msg
            except Exception as e:
                wynik["slave_ok"]  = False
                wynik["slave_msg"] = str(e)

        # 6. Zaktualizuj stan w bazie
        db.execute(
            "UPDATE supla_config SET ostatni_stan=? WHERE id=?",
            (1 if stan else 0, cfg["id"])
        )

    db.commit()
    db.close()
    return wynik


def init_supla_tables(db):
    """Utwórz tabele dla Supla."""
    db.executescript("""
    CREATE TABLE IF NOT EXISTS supla_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gospodarstwo_id INTEGER REFERENCES gospodarstwa(id) ON DELETE CASCADE,
        nazwa TEXT NOT NULL,
        server_url TEXT DEFAULT 'https://svr1.supla.org',
        token TEXT,
        channel_id INTEGER,
        typ TEXT DEFAULT 'webhook',
        aktywny INTEGER DEFAULT 1,
        powiazane_urzadzenie_id INTEGER REFERENCES urzadzenia(id),
        powiazany_kanal TEXT,
        ostatni_stan INTEGER DEFAULT 0,
        ostatni_kontakt DATETIME
    );
    CREATE TABLE IF NOT EXISTS supla_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        czas DATETIME NOT NULL,
        channel_id INTEGER,
        action_raw TEXT,
        stan INTEGER,
        payload TEXT,
        gospodarstwo_id INTEGER REFERENCES gospodarstwa(id)
    );
    """)
    db.commit()


def register_supla_routes(app):
    """Rejestruje route'y Supla w aplikacji Flask."""
    from auth import farm_required, login_required, superadmin_required, current_user
    from db import get_db, get_setting, save_setting
    from app import R

    def gid(): 
        from flask import session
        return session.get("farm_id")

    # ── WEBHOOK odbiornik ──────────────────────────────────────────────────
    @app.route("/webhook/supla", methods=["POST"])
    def supla_webhook():
        data  = request.get_json(force=True, silent=True) or {}
        token = request.headers.get("X-Supla-Token","")
        wynik = handle_supla_webhook(data, token)
        status = 200 if wynik["ok"] else 400
        return jsonify(wynik), status

    # ── PANEL konfiguracji Supla ───────────────────────────────────────────
    @app.route("/supla")
    @farm_required
    def supla_panel():
        g = gid()
        db = get_db()
        configs = db.execute(
            "SELECT s.*, u.nazwa as urz_nazwa FROM supla_config s "
            "LEFT JOIN urzadzenia u ON s.powiazane_urzadzenie_id=u.id "
            "WHERE s.gospodarstwo_id=? ORDER BY s.nazwa", (g,)
        ).fetchall()
        logi = db.execute(
            "SELECT * FROM supla_log WHERE gospodarstwo_id=? ORDER BY czas DESC LIMIT 20", (g,)
        ).fetchall()
        supla_token = get_setting("supla_webhook_token","")
        db.close()

        w = "".join(
            '<tr>'
            '<td style="font-weight:500">' + c["nazwa"] + '</td>'
            '<td><code>' + str(c["channel_id"] or "—") + '</code></td>'
            '<td>' + (c["urz_nazwa"] or "—") + ' / ' + (c["powiazany_kanal"] or "—") + '</td>'
            '<td><span class="badge ' + ('b-green' if c["ostatni_stan"] else 'b-gray') + '">' + ('ON' if c["ostatni_stan"] else 'OFF') + '</span></td>'
            '<td><span class="badge ' + ('b-green' if c["aktywny"] else 'b-gray') + '">' + ('aktywna' if c["aktywny"] else 'wyłączona') + '</span></td>'
            '<td class="nowrap">'
            '<a href="/supla/' + str(c["id"]) + '/edytuj" class="btn bo bsm">Edytuj</a> '
            '<a href="/supla/' + str(c["id"]) + '/usun" class="btn br bsm" onclick="return confirm(\'Usunąć?\')">✕</a>'
            '</td></tr>'
            for c in configs
        )

        w_log = "".join(
            '<tr>'
            '<td style="font-size:11px">' + l["czas"][:16] + '</td>'
            '<td><code>' + str(l["channel_id"] or "") + '</code></td>'
            '<td>' + (l["action_raw"] or "") + '</td>'
            '<td><span class="badge ' + ('b-green' if l["stan"] else 'b-gray') + '">' + ('ON' if l["stan"] else 'OFF') + '</span></td>'
            '</tr>'
            for l in logi
        )

        host = request.host
        html = (
            '<h1>Supla — integracja webhook</h1>'
            '<div class="card" style="border-left:3px solid #534AB7;border-radius:0 12px 12px 0">'
            '<b>URL webhooka do wpisania w Supla Cloud</b>'
            '<p style="margin-top:8px;font-size:13px">'
            '<code style="background:#EEEDFE;padding:4px 10px;border-radius:6px;font-size:14px">'
            'https://' + host + '/webhook/supla</code></p>'
            '<p style="font-size:12px;color:#5f5e5a;margin-top:8px">'
            'Supla Cloud → Kanał → Akcje bezpośrednie → Wyślij żądanie HTTP<br>'
            'Metoda: POST &nbsp;|&nbsp; Nagłówek: <code>X-Supla-Token: ' + (supla_token or "ustaw_poniżej") + '</code><br>'
            'Treść (JSON): <code>{"channel_id": {{channel_id}}, "action": "{{action}}", "state": {{value}}}</code>'
            '</p></div>'
            '<div class="card"><b>Token zabezpieczający webhook</b>'
            '<form method="POST" action="/supla/token" style="display:flex;gap:8px;margin-top:8px;flex-wrap:wrap">'
            '<input name="token" value="' + supla_token + '" placeholder="Wpisz losowy ciąg znaków" style="flex:1">'
            '<button class="btn bp bsm">Zapisz token</button>'
            '</form>'
            '<p style="font-size:12px;color:#888;margin-top:6px">Ten sam token wpisz w Supla jako nagłówek X-Supla-Token</p>'
            '</div>'
            '<a href="/supla/dodaj" class="btn bp bsm" style="margin-bottom:12px">+ Dodaj kanał Supla</a>'
            '<div class="card" style="overflow-x:auto"><b>Skonfigurowane kanały</b>'
            '<table style="margin-top:8px"><thead><tr><th>Nazwa</th><th>Channel ID</th><th>Urządzenie/Kanał</th><th>Stan</th><th>Status</th><th></th></tr></thead>'
            '<tbody>' + (w or '<tr><td colspan=6 style="color:#888;text-align:center;padding:16px">Brak konfiguracji — dodaj kanał Supla</td></tr>') + '</tbody></table></div>'
            '<div class="card" style="overflow-x:auto"><b>Log webhooków (ostatnie 20)</b>'
            '<table style="margin-top:8px"><thead><tr><th>Czas</th><th>Channel</th><th>Akcja</th><th>Stan</th></tr></thead>'
            '<tbody>' + (w_log or '<tr><td colspan=4 style="color:#888;padding:10px">Brak zdarzeń</td></tr>') + '</tbody></table></div>'
        )
        return R(html, "gpio")

    @app.route("/supla/token", methods=["POST"])
    @farm_required
    def supla_token():
        g = gid()
        token = request.form.get("token","").strip()
        save_setting("supla_webhook_token", token, g)
        flash("Token webhook zapisany.")
        return redirect("/supla")

    @app.route("/supla/dodaj", methods=["GET","POST"])
    @farm_required
    def supla_dodaj():
        g = gid()
        if request.method == "POST":
            db = get_db()
            db.execute("""INSERT INTO supla_config
                (gospodarstwo_id,nazwa,server_url,token,channel_id,
                 powiazane_urzadzenie_id,powiazany_kanal,aktywny)
                VALUES(?,?,?,?,?,?,?,1)""",
                (g, request.form["nazwa"],
                 request.form.get("server_url","https://svr1.supla.org"),
                 request.form.get("token",""),
                 int(request.form.get("channel_id",0) or 0),
                 request.form.get("urzadzenie_id") or None,
                 request.form.get("kanal","") or None))
            db.commit(); db.close()
            flash("Kanał Supla dodany.")
            return redirect("/supla")

        db = get_db()
        urzadzenia = db.execute(
            "SELECT id,nazwa FROM urzadzenia WHERE gospodarstwo_id=? AND aktywne=1", (g,)
        ).fetchall()
        kanaly_std = ["relay1","relay2","relay3","relay4"]
        db.close()

        u_opt = '<option value="">— brak (tylko log) —</option>' + "".join(
            '<option value="' + str(u["id"]) + '">' + u["nazwa"] + '</option>'
            for u in urzadzenia
        )
        k_opt = "".join('<option value="' + k + '">' + k + '</option>' for k in kanaly_std)

        html = (
            '<h1>Nowy kanał Supla</h1><div class="card"><form method="POST">'
            '<label>Nazwa (opis do czego służy)</label>'
            '<input name="nazwa" required placeholder="np. Światło kurnik, Zawór wody">'
            '<label>Channel ID z Supla</label>'
            '<input name="channel_id" type="number" required placeholder="ID kanału z panelu Supla">'
            '<p style="font-size:12px;color:#888;margin-top:2px">'
            'Supla Cloud → Lokalizacje → kliknij kanał → ID widoczne w URL lub szczegółach</p>'
            '<div class="g2">'
            '<div><label>Powiąż z urządzeniem slave (opcjonalnie)</label>'
            '<select name="urzadzenie_id">' + u_opt + '</select></div>'
            '<div><label>Kanał urządzenia</label>'
            '<select name="kanal">' + k_opt + '</select></div>'
            '</div>'
            '<p style="font-size:12px;color:#888;margin-top:4px">'
            'Gdy Supla wyśle webhook → Ferma przekaże polecenie ON/OFF do wybranego urządzenia slave</p>'
            '<br><button class="btn bp">Dodaj</button>'
            '<a href="/supla" class="btn bo" style="margin-left:8px">Anuluj</a>'
            '</form></div>'
            '<div class="card"><b>Jak skonfigurować w Supla Cloud</b>'
            '<ol style="font-size:13px;color:#5f5e5a;margin:8px 0;list-style:decimal;margin-left:18px;line-height:2">'
            '<li>Zaloguj się na cloud.supla.org</li>'
            '<li>Wybierz kanał (przełącznik, czujnik, przycisk)</li>'
            '<li>Kliknij <b>Akcje bezpośrednie</b> → <b>Wyślij żądanie HTTP</b></li>'
            '<li>URL: <code>https://twoja-domena.pl/webhook/supla</code></li>'
            '<li>Metoda: POST, Content-Type: application/json</li>'
            '<li>Nagłówek: <code>X-Supla-Token: TWOJ_TOKEN</code></li>'
            '<li>Treść: <code>{"channel_id": {{channel_id}}, "action": "{{action}}", "state": {{value}}}</code></li>'
            '</ol></div>'
        )
        return R(html, "gpio")

    @app.route("/supla/<int:sid>/edytuj", methods=["GET","POST"])
    @farm_required
    def supla_edytuj(sid):
        g = gid()
        db = get_db()
        if request.method == "POST":
            db.execute("""UPDATE supla_config SET nazwa=?,channel_id=?,
                powiazane_urzadzenie_id=?,powiazany_kanal=?,aktywny=? WHERE id=? AND gospodarstwo_id=?""",
                (request.form["nazwa"],
                 int(request.form.get("channel_id",0) or 0),
                 request.form.get("urzadzenie_id") or None,
                 request.form.get("kanal","") or None,
                 1 if request.form.get("aktywny") else 0,
                 sid, g))
            db.commit(); db.close()
            flash("Zaktualizowano.")
            return redirect("/supla")
        c = db.execute("SELECT * FROM supla_config WHERE id=? AND gospodarstwo_id=?", (sid,g)).fetchone()
        urzadzenia = db.execute("SELECT id,nazwa FROM urzadzenia WHERE gospodarstwo_id=? AND aktywne=1", (g,)).fetchall()
        db.close()
        if not c: return redirect("/supla")

        u_opt = '<option value="">— brak —</option>' + "".join(
            '<option value="' + str(u["id"]) + '" ' + ('selected' if c["powiazane_urzadzenie_id"]==u["id"] else '') + '>' + u["nazwa"] + '</option>'
            for u in urzadzenia
        )
        k_opt = "".join(
            '<option value="' + k + '" ' + ('selected' if c["powiazany_kanal"]==k else '') + '>' + k + '</option>'
            for k in ["relay1","relay2","relay3","relay4"]
        )
        html = (
            '<h1>Edytuj kanał Supla</h1><div class="card"><form method="POST">'
            '<label>Nazwa</label><input name="nazwa" required value="' + c["nazwa"] + '">'
            '<label>Channel ID</label><input name="channel_id" type="number" value="' + str(c["channel_id"] or "") + '">'
            '<div class="g2">'
            '<div><label>Urządzenie slave</label><select name="urzadzenie_id">' + u_opt + '</select></div>'
            '<div><label>Kanał</label><select name="kanal">' + k_opt + '</select></div>'
            '</div>'
            '<label style="display:flex;align-items:center;gap:8px;margin-top:10px">'
            '<input type="checkbox" name="aktywny" ' + ('checked' if c["aktywny"] else '') + '> Aktywna'
            '</label>'
            '<br><button class="btn bp">Zapisz</button>'
            '<a href="/supla" class="btn bo" style="margin-left:8px">Anuluj</a>'
            '</form></div>'
        )
        return R(html, "gpio")

    @app.route("/supla/<int:sid>/usun")
    @farm_required
    def supla_usun(sid):
        g = gid()
        db = get_db()
        db.execute("DELETE FROM supla_config WHERE id=? AND gospodarstwo_id=?", (sid,g))
        db.commit(); db.close()
        flash("Kanał usunięty.")
        return redirect("/supla")

    # ── init tabel przy starcie ────────────────────────────────────────────

    return app
