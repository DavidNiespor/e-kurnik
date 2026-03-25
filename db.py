# -*- coding: utf-8 -*-
import sqlite3, os

_data_dir = os.environ.get("FERMA_DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(_data_dir, "ferma.db")

def get_db():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    return db

def get_setting(key, default="", gid=None):
    db = get_db()
    if gid:
        row = db.execute("SELECT wartosc FROM ustawienia WHERE klucz=? AND gospodarstwo_id=?", (key, gid)).fetchone()
    else:
        row = db.execute("SELECT wartosc FROM ustawienia WHERE klucz=? AND gospodarstwo_id IS NULL", (key,)).fetchone()
    db.close()
    return row["wartosc"] if row else default

def save_setting(key, val, gid=None):
    db = get_db()
    if gid:
        db.execute("INSERT OR REPLACE INTO ustawienia(klucz,wartosc,gospodarstwo_id) VALUES(?,?,?)", (key, val, gid))
    else:
        db.execute("INSERT OR REPLACE INTO ustawienia(klucz,wartosc,gospodarstwo_id) VALUES(?,?,NULL)", (key, val))
    db.commit(); db.close()

def init_db():
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
    CREATE TABLE IF NOT EXISTS gospodarstwa (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nazwa TEXT NOT NULL,
        opis TEXT,
        lokalizacja_lat REAL DEFAULT 52.0,
        lokalizacja_lon REAL DEFAULT 20.0,
        strefa_czasowa TEXT DEFAULT 'Europe/Warsaw',
        data_utworzenia DATETIME DEFAULT CURRENT_TIMESTAMP,
        aktywne INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS uzytkownicy_gospodarstwa (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        uzytkownik_id INTEGER REFERENCES uzytkownicy(id) ON DELETE CASCADE,
        gospodarstwo_id INTEGER REFERENCES gospodarstwa(id) ON DELETE CASCADE,
        rola TEXT DEFAULT 'owner',
        UNIQUE(uzytkownik_id, gospodarstwo_id)
    );
    CREATE TABLE IF NOT EXISTS ustawienia (
        klucz TEXT NOT NULL,
        wartosc TEXT,
        gospodarstwo_id INTEGER REFERENCES gospodarstwa(id) ON DELETE CASCADE,
        UNIQUE (klucz, gospodarstwo_id)
    );
    CREATE TABLE IF NOT EXISTS stado (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gospodarstwo_id INTEGER NOT NULL REFERENCES gospodarstwa(id) ON DELETE CASCADE,
        nazwa TEXT NOT NULL,
        gatunek TEXT DEFAULT 'nioski',
        liczba INTEGER DEFAULT 0,
        data_dodania DATE,
        data_urodzenia DATE,
        rasa TEXT, uwagi TEXT, aktywne INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS stado_ubytki (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stado_id INTEGER REFERENCES stado(id),
        gospodarstwo_id INTEGER REFERENCES gospodarstwa(id),
        data DATE NOT NULL,
        ilosc INTEGER NOT NULL,
        powod TEXT, uwagi TEXT
    );
    CREATE TABLE IF NOT EXISTS produkcja (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gospodarstwo_id INTEGER NOT NULL REFERENCES gospodarstwa(id) ON DELETE CASCADE,
        data DATE NOT NULL,
        jaja_zebrane INTEGER DEFAULT 0,
        jaja_sprzedane INTEGER DEFAULT 0,
        cena_sprzedazy REAL DEFAULT 0,
        pasza_wydana_kg REAL DEFAULT 0,
        uwagi TEXT,
        UNIQUE(gospodarstwo_id, data)
    );
    CREATE TABLE IF NOT EXISTS klienci (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gospodarstwo_id INTEGER NOT NULL REFERENCES gospodarstwa(id) ON DELETE CASCADE,
        nazwa TEXT NOT NULL,
        telefon TEXT, email TEXT, adres TEXT, uwagi TEXT
    );
    CREATE TABLE IF NOT EXISTS zamowienia (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gospodarstwo_id INTEGER NOT NULL REFERENCES gospodarstwa(id) ON DELETE CASCADE,
        klient_id INTEGER REFERENCES klienci(id),
        data_zlozenia DATE NOT NULL,
        data_dostawy DATE NOT NULL,
        ilosc INTEGER NOT NULL,
        cena_za_szt REAL DEFAULT 0,
        status TEXT DEFAULT 'nowe',
        platnosc_typ TEXT DEFAULT 'gotowka',
        uwagi TEXT
    );
    CREATE TABLE IF NOT EXISTS konta_saldo (
        klient_id INTEGER PRIMARY KEY REFERENCES klienci(id) ON DELETE CASCADE,
        saldo_pln REAL DEFAULT 0,
        saldo_jaj INTEGER DEFAULT 0,
        ostatnia_zmiana DATETIME
    );
    CREATE TABLE IF NOT EXISTS konta_transakcje (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gospodarstwo_id INTEGER REFERENCES gospodarstwa(id),
        klient_id INTEGER REFERENCES klienci(id),
        data DATETIME NOT NULL,
        typ TEXT NOT NULL,
        kwota REAL DEFAULT 0,
        jaj INTEGER DEFAULT 0,
        opis TEXT,
        zamowienie_id INTEGER REFERENCES zamowienia(id),
        saldo_po REAL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS wydatki (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gospodarstwo_id INTEGER NOT NULL REFERENCES gospodarstwa(id) ON DELETE CASCADE,
        data DATE NOT NULL,
        kategoria TEXT NOT NULL,
        nazwa TEXT NOT NULL,
        ilosc REAL DEFAULT 0,
        jednostka TEXT DEFAULT 'szt',
        cena_jednostkowa REAL DEFAULT 0,
        wartosc_total REAL DEFAULT 0,
        dostawca TEXT, uwagi TEXT
    );
    CREATE TABLE IF NOT EXISTS stan_magazynu (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gospodarstwo_id INTEGER NOT NULL REFERENCES gospodarstwa(id) ON DELETE CASCADE,
        kategoria TEXT NOT NULL,
        nazwa TEXT NOT NULL,
        jednostka TEXT DEFAULT 'kg',
        stan REAL DEFAULT 0,
        min_zapas REAL DEFAULT 0,
        cena_aktualna REAL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS receptura (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gospodarstwo_id INTEGER NOT NULL REFERENCES gospodarstwa(id) ON DELETE CASCADE,
        nazwa TEXT NOT NULL,
        sezon TEXT DEFAULT 'caly_rok',
        aktywna INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS receptura_skladnik (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        receptura_id INTEGER REFERENCES receptura(id) ON DELETE CASCADE,
        magazyn_id INTEGER REFERENCES stan_magazynu(id),
        procent REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS mieszania (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gospodarstwo_id INTEGER NOT NULL REFERENCES gospodarstwa(id) ON DELETE CASCADE,
        data DATETIME NOT NULL,
        receptura_id INTEGER REFERENCES receptura(id),
        ilosc_kg REAL NOT NULL, uwagi TEXT
    );
    CREATE TABLE IF NOT EXISTS woda_dzien (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gospodarstwo_id INTEGER NOT NULL REFERENCES gospodarstwa(id) ON DELETE CASCADE,
        data DATE NOT NULL,
        litry_reczne REAL DEFAULT 0,
        uwagi TEXT,
        UNIQUE(gospodarstwo_id, data)
    );
    CREATE TABLE IF NOT EXISTS prad_odczyty (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gospodarstwo_id INTEGER NOT NULL REFERENCES gospodarstwa(id) ON DELETE CASCADE,
        data DATE NOT NULL,
        kwh REAL DEFAULT 0,
        koszt REAL DEFAULT 0,
        UNIQUE(gospodarstwo_id, data)
    );
    CREATE TABLE IF NOT EXISTS urzadzenia (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gospodarstwo_id INTEGER NOT NULL REFERENCES gospodarstwa(id) ON DELETE CASCADE,
        nazwa TEXT NOT NULL,
        typ TEXT DEFAULT 'esp32',
        ip TEXT NOT NULL,
        port INTEGER DEFAULT 80,
        api_key TEXT DEFAULT '',
        aktywne INTEGER DEFAULT 1,
        ostatni_kontakt DATETIME,
        status TEXT DEFAULT 'nieznany'
    );
    CREATE TABLE IF NOT EXISTS urzadzenia_kanaly (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        urzadzenie_id INTEGER REFERENCES urzadzenia(id) ON DELETE CASCADE,
        kanal TEXT NOT NULL,
        opis TEXT, stan INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS harmonogram (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gospodarstwo_id INTEGER NOT NULL REFERENCES gospodarstwa(id) ON DELETE CASCADE,
        nazwa TEXT NOT NULL,
        urzadzenie_id INTEGER REFERENCES urzadzenia(id),
        kanal TEXT,
        tryb TEXT DEFAULT 'czas',
        sezon TEXT DEFAULT 'caly_rok',
        czas_wl TEXT, czas_wyl TEXT,
        offset_wschod_min INTEGER DEFAULT 0,
        offset_zachod_min INTEGER DEFAULT 0,
        aktywny INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS kalendarz (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gospodarstwo_id INTEGER NOT NULL REFERENCES gospodarstwa(id) ON DELETE CASCADE,
        nazwa TEXT NOT NULL,
        typ TEXT DEFAULT 'cykliczne',
        data_pierwsza DATE NOT NULL,
        co_ile_dni INTEGER DEFAULT 0,
        powiadomienie_dni_przed INTEGER DEFAULT 3,
        ostatnie_wykonanie DATE,
        nastepne DATE,
        uwagi TEXT, aktywne INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS wyposazenie (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gospodarstwo_id INTEGER NOT NULL REFERENCES gospodarstwa(id) ON DELETE CASCADE,
        nazwa TEXT NOT NULL,
        kategoria TEXT DEFAULT 'inne',
        data_zakupu DATE,
        cena REAL DEFAULT 0,
        stan TEXT DEFAULT 'sprawne',
        nastepny_przeglad DATE,
        uwagi TEXT
    );
    CREATE TABLE IF NOT EXISTS gpio_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gospodarstwo_id INTEGER REFERENCES gospodarstwa(id),
        czas DATETIME NOT NULL,
        urzadzenie_id INTEGER REFERENCES urzadzenia(id),
        kanal TEXT, stan INTEGER, zrodlo TEXT DEFAULT 'reczny'
    );
    CREATE TABLE IF NOT EXISTS powiadomienia_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gospodarstwo_id INTEGER REFERENCES gospodarstwa(id),
        czas DATETIME NOT NULL,
        kanal TEXT NOT NULL,
        tresc TEXT, sukces INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS system_config (
        klucz TEXT PRIMARY KEY, wartosc TEXT
    );
    INSERT OR IGNORE INTO system_config VALUES ('app_version','4.0');
    INSERT OR IGNORE INTO system_config VALUES ('rejestracja_otwarta','1');

    -- ── SUPLA ──────────────────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS supla_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gospodarstwo_id INTEGER REFERENCES gospodarstwa(id) ON DELETE CASCADE,
        nazwa TEXT NOT NULL,
        server_url TEXT DEFAULT 'https://svr1.supla.org',
        token TEXT,
        channel_id INTEGER,
        typ TEXT DEFAULT 'webhook',
        aktywny INTEGER DEFAULT 1
    );
    -- ── PWM LED ────────────────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS pwm_led (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gospodarstwo_id INTEGER REFERENCES gospodarstwa(id),
        nazwa TEXT DEFAULT 'LED',
        pin_bcm INTEGER NOT NULL,
        jasnosc_pct INTEGER DEFAULT 80,
        aktywny INTEGER DEFAULT 1
    );
    -- ── CZYNNOŚCI DZIENNE ──────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS dzienne_czynnosci (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gospodarstwo_id INTEGER NOT NULL REFERENCES gospodarstwa(id) ON DELETE CASCADE,
        data DATE NOT NULL,
        czynnosci TEXT DEFAULT '[]',
        notatka TEXT,
        UNIQUE(gospodarstwo_id, data)
    );
    -- ── WODA RĘCZNA Z CENAMI ───────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS woda_reczna (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gospodarstwo_id INTEGER NOT NULL REFERENCES gospodarstwa(id) ON DELETE CASCADE,
        data DATE NOT NULL,
        litry REAL DEFAULT 0,
        cena_litra REAL DEFAULT 0,
        koszt REAL DEFAULT 0,
        uwagi TEXT,
        UNIQUE(gospodarstwo_id, data)
    );
    -- ── SPRZEDAŻ SZCZEGÓŁ ──────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS sprzedaz_szczegol (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gospodarstwo_id INTEGER NOT NULL REFERENCES gospodarstwa(id),
        data DATE NOT NULL,
        klient_id INTEGER REFERENCES klienci(id),
        zamowienie_id INTEGER REFERENCES zamowienia(id),
        ilosc INTEGER NOT NULL,
        cena_szt REAL DEFAULT 0,
        wartosc REAL DEFAULT 0,
        typ TEXT DEFAULT 'gotowka',
        uwagi TEXT
    );
    -- ── SKŁADNIKI BAZA ─────────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS skladniki_baza (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nazwa TEXT NOT NULL UNIQUE,
        kategoria TEXT DEFAULT 'inne',
        cena_pln_t REAL DEFAULT 0,
        jednostka TEXT DEFAULT 'kg',
        bialko_pct REAL DEFAULT 0,
        energia_me REAL DEFAULT 0,
        tluszcz_pct REAL DEFAULT 0,
        wlokno_pct REAL DEFAULT 0,
        wapn_g_kg REAL DEFAULT 0,
        fosfor_g_kg REAL DEFAULT 0,
        lizyna_g_kg REAL DEFAULT 0,
        metionina_g_kg REAL DEFAULT 0,
        uwagi TEXT,
        aktywny INTEGER DEFAULT 1,
        data_aktualizacji_ceny DATETIME
    );
    -- ── HARMONOGRAM POJENIA ────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS harmonogram_pojenia (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gospodarstwo_id INTEGER NOT NULL REFERENCES gospodarstwa(id),
        nazwa TEXT NOT NULL,
        urzadzenie_id INTEGER REFERENCES urzadzenia(id),
        kanal TEXT,
        czas_otwarcia TEXT,
        czas_zamkniecia TEXT,
        czas_trwania_s INTEGER DEFAULT 30,
        powtarzaj_co_h INTEGER DEFAULT 4,
        aktywny INTEGER DEFAULT 1
    );
    """)
    db.commit(); db.close()
