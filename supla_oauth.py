# -*- coding: utf-8 -*-
"""
supla_oauth.py — Integracja Supla przez OAuth2 + REST API
Supla serwer: svr1.supla.org
"""
import urllib.request, urllib.parse, json, hashlib, os
from datetime import datetime, timedelta

SUPLA_SERVER   = "https://svr1.supla.org"
CLIENT_ID      = "170_g5ctya3ysfcoo0kk88o8wwws8o8c0sokkko40kkk8gg4s8k84"
CLIENT_SECRET  = "5nzputvepk4k0okc44cgcw48owkwosw8404co0c8s8ksgcok8c"
CALLBACK_URL   = "https://coop.brap.cc/webhook/supla"
SCOPE          = "account_r channels_r channels_ea"


def get_auth_url(state="ferma"):
    """Zwraca URL do autoryzacji OAuth — użytkownik klika i loguje się na Supla."""
    params = urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": CALLBACK_URL,
        "scope": SCOPE,
        "state": state,
    })
    return f"{SUPLA_SERVER}/oauth/v2/auth?{params}"


def exchange_code(code):
    """Wymienia kod autoryzacji na access_token + refresh_token."""
    data = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": CALLBACK_URL,
        "code": code,
    }).encode()
    req = urllib.request.Request(
        f"{SUPLA_SERVER}/oauth/v2/token",
        data=data, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    resp = urllib.request.urlopen(req, timeout=10)
    return json.loads(resp.read())


def refresh_token(refresh_tok):
    """Odświeża access_token używając refresh_token."""
    data = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": refresh_tok,
    }).encode()
    req = urllib.request.Request(
        f"{SUPLA_SERVER}/oauth/v2/token",
        data=data, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    resp = urllib.request.urlopen(req, timeout=10)
    return json.loads(resp.read())


def api_call(access_token, path, method="GET", body=None):
    """Wywołuje Supla REST API."""
    url = f"{SUPLA_SERVER}/api/v2.4.0{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
    )
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"error": e.code, "msg": e.read().decode()}


def get_channels(access_token):
    """Pobiera listę kanałów (przekaźniki, sensory)."""
    return api_call(access_token, "/channels?include=state,iodevice")


def set_channel_state(access_token, channel_id, state_on: bool):
    """Włącza lub wyłącza kanał (relay)."""
    action = "TURN_ON" if state_on else "TURN_OFF"
    return api_call(access_token, f"/channels/{channel_id}",
                    method="PATCH", body={"action": action})


def get_channel_state(access_token, channel_id):
    """Pobiera aktualny stan kanału."""
    return api_call(access_token, f"/channels/{channel_id}?include=state")


def register_supla_oauth_routes(app):
    from flask import request, redirect, session, flash, jsonify
    from db import get_db, save_setting, get_setting
    from auth import farm_required, login_required
    from app import R

    def gid(): return session.get("farm_id")
    def gs(k, d=""): return get_setting(k, d, gid())

    def _get_token(g):
        """Pobierz aktualny access_token, odśwież jeśli wygasł."""
        db = get_db()
        tok = db.execute(
            "SELECT wartosc FROM ustawienia WHERE klucz='supla_access_token' AND gospodarstwo_id=?", (g,)
        ).fetchone()
        ref = db.execute(
            "SELECT wartosc FROM ustawienia WHERE klucz='supla_refresh_token' AND gospodarstwo_id=?", (g,)
        ).fetchone()
        exp = db.execute(
            "SELECT wartosc FROM ustawienia WHERE klucz='supla_token_expires' AND gospodarstwo_id=?", (g,)
        ).fetchone()
        db.close()
        if not tok: return None

        # Sprawdź czy wygasł
        if exp:
            try:
                exp_dt = datetime.fromisoformat(exp["wartosc"])
                if datetime.now() >= exp_dt - timedelta(minutes=5):
                    # Odśwież
                    new_tok = refresh_token(ref["wartosc"])
                    _save_token(g, new_tok)
                    return new_tok.get("access_token")
            except Exception:
                pass

        return tok["wartosc"]

    def _save_token(g, tok_data):
        """Zapisz tokeny do bazy."""
        expires_in = int(tok_data.get("expires_in", 3600))
        exp_dt = (datetime.now() + timedelta(seconds=expires_in)).isoformat()
        save_setting("supla_access_token",  tok_data.get("access_token",""), g)
        save_setting("supla_refresh_token", tok_data.get("refresh_token",""), g)
        save_setting("supla_token_expires", exp_dt, g)

    # ── OAuth flow ────────────────────────────────────────────────────────────
    @app.route("/supla/oauth/start")
    @farm_required
    def supla_oauth_start():
        g = gid()
        state = hashlib.md5(f"{g}{os.urandom(8).hex()}".encode()).hexdigest()
        save_setting("supla_oauth_state", state, g)
        return redirect(get_auth_url(state=state))

    @app.route("/webhook/supla")
    @app.route("/webhook/supla", methods=["POST"])
    def supla_oauth_callback():
        """Obsługuje zarówno OAuth callback (GET) jak i webhook (POST)."""
        if request.method == "POST":
            # Webhook — obsłuż jak wcześniej
            return _handle_webhook()

        # GET — OAuth callback
        code  = request.args.get("code")
        state = request.args.get("state","")
        error = request.args.get("error")

        if error:
            flash(f"Supla odmówił autoryzacji: {error}")
            return redirect("/supla")

        if not code:
            # Może to test ping z Supla
            return "OK", 200

        # Znajdź farmę po state
        db = get_db()
        rows = db.execute(
            "SELECT gospodarstwo_id FROM ustawienia WHERE klucz='supla_oauth_state' AND wartosc=?", (state,)
        ).fetchall()
        db.close()

        if not rows:
            flash("Nieprawidłowy state OAuth. Spróbuj ponownie.")
            return redirect("/supla")

        g = rows[0]["gospodarstwo_id"]
        session["farm_id"] = g  # ustaw kontekst farmy

        try:
            tok_data = exchange_code(code)
            _save_token(g, tok_data)
            # Zapisz info o koncie
            channels = get_channels(tok_data["access_token"])
            if isinstance(channels, list):
                save_setting("supla_channels_count", str(len(channels)), g)
            flash(f"Połączono z Supla! Znaleziono {len(channels) if isinstance(channels, list) else '?'} kanałów.")
        except Exception as e:
            flash(f"Błąd połączenia z Supla: {str(e)}")

        return redirect("/supla")

    def _handle_webhook():
        """Obsługa przychodzącego webhooka POST (stan kanału)."""
        data = request.get_json(force=True, silent=True) or {}
        if not data:
            # form-encoded
            data = {k: v for k, v in request.form.items()}

        channel_id = data.get("channel_id") or data.get("channelId")
        try: channel_id = int(channel_id) if channel_id else None
        except: channel_id = None

        if channel_id is None:
            return jsonify({"ok": False, "msg": "no channel_id"}), 400

        action = str(data.get("action","")).upper()
        state_raw = data.get("state", data.get("hi", data.get("value")))
        if action in ("TURN_ON","ON","1"):   stan = True
        elif action in ("TURN_OFF","OFF","0"): stan = False
        elif state_raw is not None:
            stan = str(state_raw).lower() in ("1","true","on","hi")
        else:
            stan = None

        db = get_db()
        cfg = db.execute(
            "SELECT * FROM supla_config WHERE channel_id=? AND aktywny=1", (channel_id,)
        ).fetchone()
        db.execute(
            "INSERT INTO supla_log(czas,channel_id,action_raw,stan,payload,gospodarstwo_id) VALUES(?,?,?,?,?,?)",
            (datetime.now().isoformat(), channel_id, action, 1 if stan else 0,
             json.dumps(data), cfg["gospodarstwo_id"] if cfg else None)
        )
        db.commit()
        wynik = {"ok": True, "channel_id": channel_id, "stan": stan}
        if cfg and stan is not None and cfg["powiazane_urzadzenie_id"] and cfg["powiazany_kanal"]:
            from routes import _send_cmd_local
            ok2, msg2 = _send_cmd_local(cfg["powiazane_urzadzenie_id"], cfg["powiazany_kanal"],
                                         stan, cfg["gospodarstwo_id"])
            wynik.update({"slave_ok": ok2, "slave_msg": msg2})
        db.close()
        return jsonify(wynik)

    # ── Panel Supla ───────────────────────────────────────────────────────────
    @app.route("/supla")
    @farm_required
    def supla_panel():
        g = gid()
        access_token = _get_token(g)
        db = get_db()
        supla_cfg = db.execute(
            "SELECT s.*,u.nazwa as urz_nazwa FROM supla_config s "
            "LEFT JOIN urzadzenia u ON s.powiazane_urzadzenie_id=u.id "
            "WHERE s.gospodarstwo_id=? ORDER BY s.nazwa", (g,)
        ).fetchall()
        supla_log = db.execute(
            "SELECT * FROM supla_log WHERE gospodarstwo_id=? ORDER BY czas DESC LIMIT 15", (g,)
        ).fetchall()
        urzadz = db.execute(
            "SELECT id,nazwa FROM urzadzenia WHERE gospodarstwo_id=? AND aktywne=1", (g,)
        ).fetchall()
        db.close()

        # Pobierz kanały z Supla API jeśli zalogowany
        supla_channels = []
        conn_error = None
        if access_token:
            try:
                ch = get_channels(access_token)
                if isinstance(ch, list):
                    supla_channels = ch
                elif isinstance(ch, dict) and "error" in ch:
                    conn_error = ch.get("msg","Błąd API")
            except Exception as e:
                conn_error = str(e)

        host = request.host

        # Status połączenia
        if access_token:
            status_html = (
                '<div class="al alok">'
                '✓ Połączono z Supla Cloud'
                + (f' — {len(supla_channels)} kanałów' if supla_channels else '')
                + (f' | <span style="color:#A32D2D">{conn_error}</span>' if conn_error else '')
                + '<a href="/supla/disconnect" class="btn br bsm" style="margin-left:10px">Rozłącz</a>'
                '</div>'
            )
        else:
            status_html = (
                '<div class="al alw">'
                'Nie połączono z Supla Cloud. '
                '<a href="/supla/oauth/start" class="btn bp bsm">Połącz przez OAuth</a>'
                '</div>'
            )

        # Tabela kanałów z Supla
        ch_rows = ""
        for ch in supla_channels[:20]:
            fn = ch.get("function",{}).get("name","") or ch.get("type","")
            state = ch.get("state",{}) or {}
            on = state.get("on", state.get("hi", state.get("connected", False)))
            badge = 'b-green' if on else 'b-gray'
            ch_rows += (
                f'<tr>'
                f'<td><code>{ch.get("id","")}</code></td>'
                f'<td style="font-weight:500">{ch.get("caption") or ch.get("id","")}</td>'
                f'<td style="font-size:12px;color:#888">{fn}</td>'
                f'<td><span class="badge {badge}">{"ON" if on else "OFF"}</span></td>'
                f'<td>'
                f'<button class="btn bg bsm" onclick="sendSupla({ch.get("id")},true)">ON</button> '
                f'<button class="btn br bsm" onclick="sendSupla({ch.get("id")},false)">OFF</button>'
                f'</td>'
                f'</tr>'
            )

        # Tabela mapowania channel_id -> urządzenie slave
        u_opt = '<option value="">— brak —</option>' + "".join(
            f'<option value="{u["id"]}">{u["nazwa"]}</option>' for u in urzadz)
        k_opt = "".join(f'<option value="relay{i}">relay{i}</option>' for i in range(1,5))
        w_cfg = ""
        for c in supla_cfg:
            w_cfg += (
                f'<tr><td style="font-weight:500">{c["nazwa"]}</td>'
                f'<td><code>{c["channel_id"] or "—"}</code></td>'
                f'<td>{c["urz_nazwa"] or "—"} / {c["powiazany_kanal"] or "—"}</td>'
                f'<td><span class="badge {"b-green" if c["ostatni_stan"] else "b-gray"}">{"ON" if c["ostatni_stan"] else "OFF"}</span></td>'
                f'<td class="nowrap">'
                f'<a href="/supla/{c["id"]}/edytuj" class="btn bo bsm">Edytuj</a> '
                f'<a href="/supla/{c["id"]}/usun" class="btn br bsm" onclick="return confirm(\'Usunąć?\')">✕</a>'
                f'</td></tr>'
            )

        w_log = "".join(
            f'<tr><td style="font-size:11px">{l["czas"][:16]}</td>'
            f'<td><code>{l["channel_id"] or ""}</code></td>'
            f'<td>{l["action_raw"] or ""}</td>'
            f'<td><span class="badge {"b-green" if l["stan"] else "b-gray"}">{"ON" if l["stan"] else "OFF"}</span></td>'
            f'</tr>'
            for l in supla_log
        )

        html = (
            '<h1>Supla — integracja</h1>'
            + status_html

            # Kanały z Supla (jeśli połączony)
            + (f'<div class="card"><b>Kanały Supla</b>'
               f'<div style="overflow-x:auto"><table style="margin-top:8px font-size:13px"><thead><tr>'
               f'<th>ID</th><th>Nazwa</th><th>Typ</th><th>Stan</th><th>Steruj</th>'
               f'</tr></thead><tbody>{ch_rows}</tbody></table></div>'
               f'<a href="/supla" class="btn bo bsm" style="margin-top:8px" '
               f'onclick="location.reload();return false">Odśwież</a>'
               f'</div>'
               if supla_channels else '')

            # Mapowanie webhook -> slave
            + '<div class="card"><b>Mapowanie kanałów (webhook → urządzenie slave)</b>'
            + '<p style="font-size:12px;color:#888;margin:6px 0">'
            + f'Webhook URL: <code>https://{host}/webhook/supla</code></p>'
            + '<a href="/supla/dodaj" class="btn bp bsm" style="margin-bottom:10px">+ Dodaj mapowanie</a>'
            + '<div style="overflow-x:auto"><table style="font-size:13px"><thead><tr>'
            + '<th>Nazwa</th><th>Supla Channel ID</th><th>Urządzenie/Kanał</th><th>Stan</th><th></th>'
            + '</tr></thead><tbody>'
            + (w_cfg or '<tr><td colspan=5 style="color:#888;text-align:center;padding:12px">Brak mapowań</td></tr>')
            + '</tbody></table></div></div>'

            # Log
            + (f'<div class="card"><b>Log webhooków</b>'
               f'<table style="font-size:12px;margin-top:6px"><thead><tr>'
               f'<th>Czas</th><th>Channel</th><th>Akcja</th><th>Stan</th></tr></thead>'
               f'<tbody>{w_log}</tbody></table></div>'
               if supla_log else '')

            + '<script>'
            + 'function sendSupla(chId, state){'
            + '  fetch("/supla/cmd",{method:"POST",'
            + '    headers:{"Content-Type":"application/json"},'
            + '    body:JSON.stringify({channel_id:chId,state:state})})'
            + '  .then(r=>r.json()).then(d=>{'
            + '    if(d.ok)location.reload();'
            + '    else alert("Błąd: "+(d.msg||"nieznany"));'
            + '  });'
            + '}'
            + '</script>'
        )
        return R(html, "gpio")

    @app.route("/supla/cmd", methods=["POST"])
    @farm_required
    def supla_cmd():
        """Bezpośrednie sterowanie kanałem Supla przez API."""
        g = gid()
        data = request.get_json()
        channel_id = data.get("channel_id")
        state_on   = data.get("state", False)
        access_token = _get_token(g)
        if not access_token:
            return jsonify({"ok": False, "msg": "Brak tokenu — połącz z Supla"}), 401
        try:
            result = set_channel_state(access_token, channel_id, state_on)
            ok = "error" not in result
            return jsonify({"ok": ok, "result": result})
        except Exception as e:
            return jsonify({"ok": False, "msg": str(e)})

    @app.route("/supla/disconnect")
    @farm_required
    def supla_disconnect():
        g = gid()
        from db import get_db
        db = get_db()
        for k in ["supla_access_token","supla_refresh_token","supla_token_expires","supla_oauth_state"]:
            db.execute("DELETE FROM ustawienia WHERE klucz=? AND gospodarstwo_id=?", (k, g))
        db.commit(); db.close()
        flash("Rozłączono z Supla.")
        return redirect("/supla")

    return app
