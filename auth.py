# -*- coding: utf-8 -*-
import hashlib, secrets, functools
from datetime import datetime
from flask import session, redirect, request, g
from db import get_db, get_setting

def _hash(password, salt=""):
    if not salt:
        salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return salt + ":" + h

def _verify(password, stored):
    try:
        salt, _ = stored.split(":", 1)
        return secrets.compare_digest(stored, _hash(password, salt))
    except Exception:
        return False

def init_auth():
    db = get_db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS uzytkownicy (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL UNIQUE,
        login TEXT NOT NULL UNIQUE,
        haslo_hash TEXT NOT NULL,
        rola TEXT DEFAULT 'user',
        aktywny INTEGER DEFAULT 1,
        data_rejestracji DATETIME DEFAULT CURRENT_TIMESTAMP,
        ostatnie_logowanie DATETIME
    );
    """)
    if not db.execute("SELECT id FROM uzytkownicy WHERE rola='superadmin'").fetchone():
        db.execute("INSERT INTO uzytkownicy(email,login,haslo_hash,rola) VALUES(?,?,?,?)",
                   ("admin@ferma.local","admin", _hash("ferma2024"), "superadmin"))
        db.commit()
    db.close()

def register_user(email, login, password):
    db = get_db()
    try:
        db.execute("INSERT INTO uzytkownicy(email,login,haslo_hash) VALUES(?,?,?)",
                   (email, login, _hash(password)))
        db.commit()
        uid = db.execute("SELECT id FROM uzytkownicy WHERE login=?", (login,)).fetchone()["id"]
        db.close()
        return uid, None
    except Exception as e:
        db.close()
        msg = "Email lub login już istnieje." if "UNIQUE" in str(e) else str(e)
        return None, msg

def login_user(login, password):
    db = get_db()
    u = db.execute("SELECT * FROM uzytkownicy WHERE (login=? OR email=?) AND aktywny=1",
                   (login, login)).fetchone()
    if u and _verify(password, u["haslo_hash"]):
        db.execute("UPDATE uzytkownicy SET ostatnie_logowanie=? WHERE id=?",
                   (datetime.now().isoformat(), u["id"]))
        db.commit(); db.close()
        return dict(u)
    db.close()
    return None

def get_user_farms(uid):
    db = get_db()
    farms = db.execute("""
        SELECT g.*, ug.rola as moja_rola FROM gospodarstwa g
        JOIN uzytkownicy_gospodarstwa ug ON g.id=ug.gospodarstwo_id
        WHERE ug.uzytkownik_id=? AND g.aktywne=1
        ORDER BY g.nazwa
    """, (uid,)).fetchall()
    db.close()
    return [dict(f) for f in farms]

def create_farm(uid, nazwa, opis=""):
    db = get_db()
    gid = db.execute("INSERT INTO gospodarstwa(nazwa,opis) VALUES(?,?)", (nazwa, opis)).lastrowid
    db.execute("INSERT INTO uzytkownicy_gospodarstwa(uzytkownik_id,gospodarstwo_id,rola) VALUES(?,?,'owner')",
               (uid, gid))
    db.commit(); db.close()
    return gid

def user_can_access_farm(uid, gid, min_rola="viewer"):
    db = get_db()
    row = db.execute("SELECT rola FROM uzytkownicy_gospodarstwa WHERE uzytkownik_id=? AND gospodarstwo_id=?",
                     (uid, gid)).fetchone()
    db.close()
    if not row: return False
    roles = ["viewer","member","owner"]
    return roles.index(row["rola"]) >= roles.index(min_rola) if min_rola in roles else True

def change_password(uid, new_password):
    db = get_db()
    db.execute("UPDATE uzytkownicy SET haslo_hash=? WHERE id=?", (_hash(new_password), uid))
    db.commit(); db.close()

def current_user():
    return session.get("user_id"), session.get("login"), session.get("rola","user")

def current_farm():
    return session.get("farm_id"), session.get("farm_name","")

def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            return redirect("/login?next=" + request.path)
        return f(*args, **kwargs)
    return decorated

def farm_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            return redirect("/login?next=" + request.path)
        if not session.get("farm_id"):
            return redirect("/wybierz-gospodarstwo")
        uid = session["user_id"]
        gid = session["farm_id"]
        if not user_can_access_farm(uid, gid):
            session.pop("farm_id", None)
            return redirect("/wybierz-gospodarstwo")
        return f(*args, **kwargs)
    return decorated

def superadmin_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if session.get("rola") != "superadmin":
            return redirect("/")
        return f(*args, **kwargs)
    return decorated
