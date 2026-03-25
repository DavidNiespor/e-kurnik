# -*- coding: utf-8 -*-
"""
sterowanie.py — wybór trybu sterowania per kanał + admin multi-farm
Tryby: supla / gpio_rpi / esphome / gpio+supla / esphome+supla / reczny
Admin może być przypisany do wielu gospodarstw.
"""
from flask import request, redirect, flash, session, jsonify
from datetime import datetime
import json

def register_sterowanie(app):
    from db import get_db, get_setting, save_setting
    from auth import farm_required, login_required, superadmin_required
    from app import R

    def gid(): return session.get("farm_id")

    def _init():
        db = get_db()
        db.executescript("""
        -- Tryb sterowania per kanał urządzenia
        CREATE TABLE IF NOT EXISTS kanal_sterowanie (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gospodarstwo_id INTEGER NOT NULL REFERENCES gospodarstwa(id) ON DELETE CASCADE,
            urzadzenie_id   INTEGER REFERENCES urzadzenia(id) ON DELETE CASCADE,
            kanal           TEXT NOT NULL,
            opis            TEXT DEFAULT '',
            tryb            TEXT DEFAULT 'reczny',
            supla_channel_id INTEGER,
            esphome_entity  TEXT DEFAULT '',
            gpio_pin        INTEGER,
            aktywny         INTEGER DEFAULT 1,
            UNIQUE(urzadzenie_id, kanal)
        );
        """)
        # Dodaj kolumny do urzadzenia jeśli brak
        for col in ["tryb_sterowania TEXT DEFAULT 'http'"]:
            try:
                db.execute(f"ALTER TABLE urzadzenia ADD COLUMN {col}")
                db.commit()
            except Exception:
                pass
        db.commit()
        db.close()

    _init()

    TRYBY = [
        ("reczny",        "Ręczny (tylko panel)"),
        ("supla",         "Supla webhook"),
        ("gpio_rpi",      "GPIO RPi bezpośrednie"),
        ("esphome",       "ESPHome REST"),
        ("gpio+supla",    "GPIO RPi + Supla (równoległe)"),
        ("esphome+supla", "ESPHome + Supla (równoległe)"),
    ]

    # ══════════════════════════════════════════════════════════════════════
    # PANEL STEROWANIA — wybór trybu per kanał
    # ══════════════════════════════════════════════════════════════════════
    @app.route("/sterowanie")
    @farm_required
    def sterowanie():
        g = gid()
        db = get_db()
        # Pobierz wszystkie kanały ze wszystkich urządzeń
        kanaly = db.execute("""
            SELECT uc.*, u.nazwa as urz_nazwa, u.typ as urz_typ, u.ip,
                   ks.tryb, ks.supla_channel_id, ks.esphome_entity,
                   ks.gpio_pin, ks.opis as kanal_opis, ks.id as ks_id
            FROM urzadzenia_kanaly uc
            JOIN urzadzenia u ON uc.urzadzenie_id = u.id
            LEFT JOIN kanal_sterowanie ks
                ON ks.urzadzenie_id = uc.urzadzenie_id AND ks.kanal = uc.kanal
            WHERE u.gospodarstwo_id = ? AND u.aktywne = 1
            ORDER BY u.nazwa, uc.kanal
        """, (g,)).fetchall()
        db.close()

        tryb_kol = {
            "reczny":"b-gray","supla":"b-amber","gpio_rpi":"b-green",
            "esphome":"b-blue","gpio+supla":"b-purple","esphome+supla":"b-purple"
        }
        tryb_ico = {
            "reczny":"🖱","supla":"⚡","gpio_rpi":"🔌",
            "esphome":"📡","gpio+supla":"🔌⚡","esphome+supla":"📡⚡"
        }

        w = "".join(
            '<tr>'
            '<td style="font-weight:500">' + k["urz_nazwa"] + '</td>'
            '<td><code>' + k["kanal"] + '</code></td>'
            '<td style="color:#5f5e5a">' + (k["kanal_opis"] or k["opis"] or "—") + '</td>'
            '<td><span class="badge ' + tryb_kol.get(k["tryb"] or "reczny","b-gray") + '">'
            + tryb_ico.get(k["tryb"] or "reczny","") + ' ' + (k["tryb"] or "reczny") + '</span></td>'
            '<td style="font-size:11px;color:#888">' + _tryb_szczegol(k) + '</td>'
            '<td><a href="/sterowanie/kanal/' + str(k["urzadzenie_id"]) + '/' + k["kanal"] + '" class="btn bo bsm">Konfiguruj</a></td>'
            '</tr>'
            for k in kanaly
        )

        html = (
            '<h1>Sterowanie — tryby per kanał</h1>'
            '<div class="card" style="background:#EEEDFE;border-color:#AFA9EC">'
            '<b>Tryby sterowania</b>'
            '<div class="g3" style="margin-top:8px;font-size:13px">'
            + "".join(
                f'<div style="padding:4px 0"><span style="font-size:16px">{tryb_ico[v]}</span> '
                f'<b>{v}</b> — {l}</div>'
                for v,l in TRYBY
            )
            + '</div></div>'
            '<div class="card" style="overflow-x:auto"><table>'
            '<thead><tr><th>Urządzenie</th><th>Kanał</th><th>Opis</th><th>Tryb</th><th>Szczegóły</th><th></th></tr></thead>'
            '<tbody>' + (w or '<tr><td colspan=6 style="color:#888;text-align:center;padding:20px">'
                'Brak skonfigurowanych urządzeń. '
                '<a href="/urzadzenia/dodaj" style="color:#534AB7">Dodaj urządzenie</a>.</td></tr>') + '</tbody></table></div>'
        )
        return R(html, "gpio")

    def _tryb_szczegol(k):
        tryb = k["tryb"] or "reczny"
        if tryb == "supla" and k["supla_channel_id"]:
            return f"Supla ch: {k['supla_channel_id']}"
        if tryb == "esphome" and k["esphome_entity"]:
            return f"Entity: {k['esphome_entity']}"
        if tryb == "gpio_rpi" and k["gpio_pin"]:
            return f"GPIO pin: {k['gpio_pin']}"
        if tryb in ("gpio+supla","esphome+supla"):
            parts = []
            if k["gpio_pin"]: parts.append(f"GPIO {k['gpio_pin']}")
            if k["supla_channel_id"]: parts.append(f"Supla {k['supla_channel_id']}")
            if k["esphome_entity"]: parts.append(k["esphome_entity"])
            return " + ".join(parts)
        return ""

    @app.route("/sterowanie/kanal/<int:did>/<kanal>", methods=["GET","POST"])
    @farm_required
    def sterowanie_kanal(did, kanal):
        g = gid()
        db = get_db()
        if request.method == "POST":
            tryb          = request.form.get("tryb","reczny")
            supla_ch      = request.form.get("supla_channel_id") or None
            esphome_ent   = request.form.get("esphome_entity","").strip()
            gpio_pin      = request.form.get("gpio_pin") or None
            opis          = request.form.get("opis","").strip()
            ex = db.execute(
                "SELECT id FROM kanal_sterowanie WHERE urzadzenie_id=? AND kanal=?", (did,kanal)
            ).fetchone()
            if ex:
                db.execute(
                    "UPDATE kanal_sterowanie SET tryb=?,supla_channel_id=?,esphome_entity=?,"
                    "gpio_pin=?,opis=? WHERE id=?",
                    (tryb, supla_ch, esphome_ent, gpio_pin, opis, ex["id"])
                )
            else:
                db.execute(
                    "INSERT INTO kanal_sterowanie(gospodarstwo_id,urzadzenie_id,kanal,tryb,"
                    "supla_channel_id,esphome_entity,gpio_pin,opis) VALUES(?,?,?,?,?,?,?,?)",
                    (g, did, kanal, tryb, supla_ch, esphome_ent, gpio_pin, opis)
                )
            db.commit(); db.close()
            flash(f"Tryb sterowania kanału {kanal} zapisany: {tryb}")
            return redirect("/sterowanie")

        dev = db.execute("SELECT * FROM urzadzenia WHERE id=? AND gospodarstwo_id=?", (did,g)).fetchone()
        ks  = db.execute("SELECT * FROM kanal_sterowanie WHERE urzadzenie_id=? AND kanal=?", (did,kanal)).fetchone()
        supla_kanaly = db.execute("SELECT id,nazwa,channel_id FROM supla_config WHERE gospodarstwo_id=? AND aktywny=1", (g,)).fetchall()
        db.close()
        if not dev: return redirect("/sterowanie")

        v = dict(ks) if ks else {}
        tryb_cur = v.get("tryb","reczny")

        tryb_opt = "".join(
            f'<option value="{tv}" {"selected" if tryb_cur==tv else ""}>{tl}</option>'
            for tv,tl in TRYBY
        )
        supla_opt = '<option value="">— brak —</option>' + "".join(
            f'<option value="{s["channel_id"]}" '
            f'{"selected" if str(v.get("supla_channel_id",""))==str(s["channel_id"]) else ""}>'
            f'{s["nazwa"]} (ch: {s["channel_id"]})</option>'
            for s in supla_kanaly
        )

        html = (
            '<h1>Konfiguracja: ' + (dev["nazwa"] if dev else "") + ' / ' + kanal + '</h1>'
            '<div class="card"><form method="POST">'
            '<label>Opis kanału (co to steruje)</label>'
            '<input name="opis" value="' + v.get("opis","") + '" placeholder="np. Światło kurnik, Zawór wody">'
            '<label>Tryb sterowania</label>'
            '<select name="tryb" id="tryb-sel" onchange="showFields(this.value)">'
            + tryb_opt + '</select>'

            '<div id="f-supla" style="margin-top:10px">'
            '<div class="al alw" style="margin-bottom:8px"><b>Supla webhook</b> — '
            'skonfiguruj najpierw kanał Supla w <a href="/supla" style="color:#534AB7">panelu Supla</a>.</div>'
            '<label>Kanał Supla</label>'
            '<select name="supla_channel_id">' + supla_opt + '</select>'
            '</div>'

            '<div id="f-esphome" style="margin-top:10px">'
            '<div class="al alok" style="margin-bottom:8px"><b>ESPHome REST</b> — '
            'urządzenie musi mieć typ ESPHome i być dostępne pod adresem IP.</div>'
            '<label>Nazwa encji ESPHome (np. relay1, led_kurnik)</label>'
            '<input name="esphome_entity" value="' + v.get("esphome_entity","") + '" '
            'placeholder="relay1">'
            '</div>'

            '<div id="f-gpio" style="margin-top:10px">'
            '<div class="al alok" style="margin-bottom:8px"><b>GPIO RPi</b> — '
            'tylko gdy aplikacja działa bezpośrednio na RPi (nie w Dockerze na VPS).</div>'
            '<label>Numer pinu GPIO BCM</label>'
            '<input name="gpio_pin" type="number" value="' + str(v.get("gpio_pin","")) + '" '
            'placeholder="np. 17">'
            '</div>'

            '<br><button class="btn bp">Zapisz</button>'
            '<a href="/sterowanie" class="btn bo" style="margin-left:8px">Anuluj</a>'
            '</form></div>'

            '<script>'
            'function showFields(v){'
            '["supla","esphome","gpio"].forEach(function(id){'
            'document.getElementById("f-"+id).style.display="none";});'
            'if(v==="supla")document.getElementById("f-supla").style.display="block";'
            'else if(v==="esphome")document.getElementById("f-esphome").style.display="block";'
            'else if(v==="gpio_rpi")document.getElementById("f-gpio").style.display="block";'
            'else if(v==="gpio+supla"){'
            'document.getElementById("f-gpio").style.display="block";'
            'document.getElementById("f-supla").style.display="block";}'
            'else if(v==="esphome+supla"){'
            'document.getElementById("f-esphome").style.display="block";'
            'document.getElementById("f-supla").style.display="block";}'
            '}'
            'showFields("' + tryb_cur + '");'
            '</script>'
        )
        return R(html, "gpio")

    # ══════════════════════════════════════════════════════════════════════
    # KOMENDA Z UWZGLĘDNIENIEM TRYBU STEROWANIA
    # ══════════════════════════════════════════════════════════════════════
    @app.route("/sterowanie/cmd", methods=["POST"])
    @farm_required
    def sterowanie_cmd():
        """Wysyła polecenie z uwzględnieniem skonfigurowanego trybu sterowania."""
        g   = gid()
        data = request.get_json()
        did  = data.get("urzadzenie_id")
        kanal= data.get("kanal","")
        stan = data.get("stan", False)

        db   = get_db()
        ks   = db.execute(
            "SELECT * FROM kanal_sterowanie WHERE urzadzenie_id=? AND kanal=?", (did,kanal)
        ).fetchone()
        db.close()

        tryb = ks["tryb"] if ks else "reczny"
        wyniki = []

        if tryb in ("reczny","gpio_rpi","esphome","gpio+supla","esphome+supla","supla") or True:
            # Zawsze próbuj HTTP do slave'a jeśli urządzenie jest skonfigurowane
            from devices import send_command
            ok, msg = send_command(did, kanal, stan, g)
            wyniki.append({"zrodlo":"slave","ok":ok,"msg":msg})

        if tryb in ("supla","gpio+supla","esphome+supla") and ks and ks["supla_channel_id"]:
            # Wyślij też przez Supla API
            from supla_handler import supla_send_command
            supla_cfg = get_db().execute(
                "SELECT id FROM supla_config WHERE channel_id=? AND gospodarstwo_id=? AND aktywny=1",
                (ks["supla_channel_id"], g)
            ).fetchone()
            if supla_cfg:
                ok2, msg2 = supla_send_command(supla_cfg["id"], stan)
                wyniki.append({"zrodlo":"supla","ok":ok2,"msg":msg2})

        overall_ok = any(w["ok"] for w in wyniki)
        return jsonify({"ok":overall_ok,"wyniki":wyniki})

    # ══════════════════════════════════════════════════════════════════════
    # ADMIN — przypisywanie farm + wybór roli
    # ══════════════════════════════════════════════════════════════════════
    @app.route("/admin/farm-assign", methods=["GET","POST"])
    @login_required
    @superadmin_required
    def admin_farm_assign():
        db = get_db()
        if request.method == "POST":
            action  = request.form.get("action","add")
            uid     = request.form.get("uid")
            farm_id = request.form.get("farm_id")
            rola    = request.form.get("rola","member")

            if action == "add" and uid and farm_id:
                try:
                    db.execute(
                        "INSERT OR REPLACE INTO uzytkownicy_gospodarstwa"
                        "(uzytkownik_id,gospodarstwo_id,rola) VALUES(?,?,?)",
                        (int(uid), int(farm_id), rola)
                    )
                    db.commit()
                    flash("Przypisano.")
                except Exception as e:
                    flash("Błąd: " + str(e))
            elif action == "remove" and uid and farm_id:
                db.execute(
                    "DELETE FROM uzytkownicy_gospodarstwa WHERE uzytkownik_id=? AND gospodarstwo_id=?",
                    (int(uid), int(farm_id))
                )
                db.commit()
                flash("Usunięto przypisanie.")
            db.close()
            return redirect("/admin/farm-assign")

        users  = db.execute(
            "SELECT id,login,email,rola FROM uzytkownicy ORDER BY login"
        ).fetchall()
        farms  = db.execute(
            "SELECT id,nazwa FROM gospodarstwa WHERE aktywne=1 ORDER BY nazwa"
        ).fetchall()
        assign = db.execute("""
            SELECT ug.*, u.login, g.nazwa as farm_nazwa
            FROM uzytkownicy_gospodarstwa ug
            JOIN uzytkownicy u ON ug.uzytkownik_id=u.id
            JOIN gospodarstwa g ON ug.gospodarstwo_id=g.id
            ORDER BY u.login, g.nazwa
        """).fetchall()
        db.close()

        u_opt = "".join(
            f'<option value="{u["id"]}">{u["login"]} ({u["email"] or ""}) — {u["rola"]}</option>'
            for u in users
        )
        f_opt = "".join(
            f'<option value="{f["id"]}">{f["nazwa"]}</option>'
            for f in farms
        )
        r_opt = "".join(
            f'<option value="{v}">{l}</option>'
            for v,l in [("owner","owner — właściciel"),("member","member — pracownik"),("viewer","viewer — tylko odczyt")]
        )

        w = "".join(
            '<tr>'
            '<td style="font-weight:500">' + a["login"] + '</td>'
            '<td>' + a["farm_nazwa"] + '</td>'
            '<td><span class="badge b-purple">' + a["rola"] + '</span></td>'
            '<td>'
            '<form method="POST" style="display:inline">'
            '<input type="hidden" name="action" value="remove">'
            '<input type="hidden" name="uid" value="' + str(a["uzytkownik_id"]) + '">'
            '<input type="hidden" name="farm_id" value="' + str(a["gospodarstwo_id"]) + '">'
            '<button class="btn br bsm" onclick="return confirm(\'Usunąć?\')">Usuń</button>'
            '</form>'
            '</td></tr>'
            for a in assign
        )

        html = (
            '<h1>Przypisywanie farm do użytkowników</h1>'
            '<p style="font-size:13px;color:#5f5e5a;margin-bottom:12px">'
            'Jeden użytkownik może mieć dostęp do wielu farm z różnymi rolami. '
            'Superadmin widzi wszystkie farmy zawsze.</p>'
            '<div class="card"><b>Dodaj przypisanie</b>'
            '<form method="POST" style="margin-top:10px">'
            '<input type="hidden" name="action" value="add">'
            '<div class="g3">'
            '<div><label>Użytkownik</label><select name="uid">' + u_opt + '</select></div>'
            '<div><label>Farma / Gospodarstwo</label><select name="farm_id">' + f_opt + '</select></div>'
            '<div><label>Rola</label><select name="rola">' + r_opt + '</select></div>'
            '</div>'
            '<br><button class="btn bp">Przypisz</button>'
            '</form></div>'
            '<div class="card" style="overflow-x:auto"><b>Aktualne przypisania</b>'
            '<table style="margin-top:8px"><thead><tr><th>Użytkownik</th><th>Farma</th><th>Rola</th><th></th></tr></thead>'
            '<tbody>' + (w or '<tr><td colspan=4 style="color:#888;text-align:center;padding:16px">Brak przypisań</td></tr>') + '</tbody></table></div>'
            '<a href="/admin" class="btn bo bsm" style="margin-top:8px">← Panel admina</a>'
        )
        return R(html, "admin")

    return app
