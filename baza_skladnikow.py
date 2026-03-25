# -*- coding: utf-8 -*-
"""
Baza składników paszy — zaimportowana z Chicken.xlsx
Zawiera 26 składników z Twoich receptur + wartości odżywcze (mikro/makro)
Źródło: tabele Paszav2, Arkusz10 z Chicken.xlsx
"""

# ─── SKŁADNIKI — baza z Twojego arkusza ──────────────────────────────────────
# Każdy składnik: nazwa, kategoria, cena PLN/T, wartości odżywcze
# Wartości odżywcze na kg składnika: białko%, energia ME kcal/kg, tłuszcz%, włókno%,
# wapń g/kg, fosfor g/kg, lizyna g/kg, metionina g/kg

SKLADNIKI_DOMYSLNE = [
    # ── ZBOŻA ──────────────────────────────────────────────────────────────────
    {
        "nazwa": "Kukurydza (śrutowana)",
        "kategoria": "zboze",
        "cena_pln_t": 1000,
        "jednostka": "kg",
        "bialko_pct": 8.5,
        "energia_me": 3370,
        "tluszcz_pct": 3.8,
        "wlokno_pct": 2.2,
        "wapn_g_kg": 0.3,
        "fosfor_g_kg": 2.8,
        "lizyna_g_kg": 2.2,
        "metionina_g_kg": 1.8,
        "uwagi": "Główne źródło energii, wysoka strawność"
    },
    {
        "nazwa": "Pszenica (śrutowana)",
        "kategoria": "zboze",
        "cena_pln_t": 800,
        "jednostka": "kg",
        "bialko_pct": 12.0,
        "energia_me": 3090,
        "tluszcz_pct": 1.8,
        "wlokno_pct": 2.5,
        "wapn_g_kg": 0.6,
        "fosfor_g_kg": 3.5,
        "lizyna_g_kg": 3.3,
        "metionina_g_kg": 2.0,
        "uwagi": "Dobre źródło białka i energii"
    },
    {
        "nazwa": "Pszenżyto (śrutowane)",
        "kategoria": "zboze",
        "cena_pln_t": 800,
        "jednostka": "kg",
        "bialko_pct": 11.5,
        "energia_me": 3030,
        "tluszcz_pct": 1.5,
        "wlokno_pct": 2.8,
        "wapn_g_kg": 0.5,
        "fosfor_g_kg": 3.2,
        "lizyna_g_kg": 3.0,
        "metionina_g_kg": 1.9,
        "uwagi": "Zamiennik pszenicy"
    },
    {
        "nazwa": "Owies (śrutowany)",
        "kategoria": "zboze",
        "cena_pln_t": 900,
        "jednostka": "kg",
        "bialko_pct": 11.0,
        "energia_me": 2770,
        "tluszcz_pct": 4.5,
        "wlokno_pct": 10.0,
        "wapn_g_kg": 1.0,
        "fosfor_g_kg": 3.4,
        "lizyna_g_kg": 3.9,
        "metionina_g_kg": 1.7,
        "uwagi": "Wysoka zawartość włókna, dobre dla jelit"
    },
    {
        "nazwa": "Jęczmień (śrutowany)",
        "kategoria": "zboze",
        "cena_pln_t": 900,
        "jednostka": "kg",
        "bialko_pct": 11.5,
        "energia_me": 2830,
        "tluszcz_pct": 2.1,
        "wlokno_pct": 4.5,
        "wapn_g_kg": 0.7,
        "fosfor_g_kg": 3.9,
        "lizyna_g_kg": 3.6,
        "metionina_g_kg": 1.7,
        "uwagi": "Dobry zamiennik pszenicy"
    },
    {
        "nazwa": "Sorgo",
        "kategoria": "zboze",
        "cena_pln_t": 950,
        "jednostka": "kg",
        "bialko_pct": 10.0,
        "energia_me": 3240,
        "tluszcz_pct": 3.0,
        "wlokno_pct": 2.5,
        "wapn_g_kg": 0.4,
        "fosfor_g_kg": 2.9,
        "lizyna_g_kg": 2.1,
        "metionina_g_kg": 1.5,
        "uwagi": "Dobra alternatywa kukurydzy latem"
    },
    # ── BIAŁKOWE ────────────────────────────────────────────────────────────────
    {
        "nazwa": "Groch (śrutowany)",
        "kategoria": "bialkowe",
        "cena_pln_t": 1080,
        "jednostka": "kg",
        "bialko_pct": 22.0,
        "energia_me": 2760,
        "tluszcz_pct": 1.4,
        "wlokno_pct": 5.5,
        "wapn_g_kg": 1.4,
        "fosfor_g_kg": 4.1,
        "lizyna_g_kg": 15.6,
        "metionina_g_kg": 2.0,
        "uwagi": "Krajowe źródło białka, bez GMO"
    },
    {
        "nazwa": "Słonecznik (śrutowany)",
        "kategoria": "bialkowe",
        "cena_pln_t": 2000,
        "jednostka": "kg",
        "bialko_pct": 28.0,
        "energia_me": 2210,
        "tluszcz_pct": 9.0,
        "wlokno_pct": 18.0,
        "wapn_g_kg": 3.5,
        "fosfor_g_kg": 9.0,
        "lizyna_g_kg": 9.6,
        "metionina_g_kg": 5.8,
        "uwagi": "Dobre źródło białka i tłuszczu"
    },
    {
        "nazwa": "Łubin słodki (śrutowany)",
        "kategoria": "bialkowe",
        "cena_pln_t": 2000,
        "jednostka": "kg",
        "bialko_pct": 34.0,
        "energia_me": 2670,
        "tluszcz_pct": 5.0,
        "wlokno_pct": 14.0,
        "wapn_g_kg": 2.7,
        "fosfor_g_kg": 4.0,
        "lizyna_g_kg": 16.0,
        "metionina_g_kg": 2.2,
        "uwagi": "Krajowa soja bez GMO"
    },
    {
        "nazwa": "Soja (śrutowana)",
        "kategoria": "bialkowe",
        "cena_pln_t": 1600,
        "jednostka": "kg",
        "bialko_pct": 44.0,
        "energia_me": 2990,
        "tluszcz_pct": 2.8,
        "wlokno_pct": 3.5,
        "wapn_g_kg": 3.2,
        "fosfor_g_kg": 6.5,
        "lizyna_g_kg": 27.0,
        "metionina_g_kg": 6.0,
        "uwagi": "Najlepsze źródło białka, ale GMO"
    },
    {
        "nazwa": "Lucerna (susz)",
        "kategoria": "bialkowe",
        "cena_pln_t": 3599,
        "jednostka": "kg",
        "bialko_pct": 17.0,
        "energia_me": 1670,
        "tluszcz_pct": 2.5,
        "wlokno_pct": 28.0,
        "wapn_g_kg": 14.0,
        "fosfor_g_kg": 2.5,
        "lizyna_g_kg": 7.0,
        "metionina_g_kg": 2.5,
        "uwagi": "Błonnik, wapń, pigmenty żółtka"
    },
    # ── MINERALNE ───────────────────────────────────────────────────────────────
    {
        "nazwa": "Kreda Pastewna Gruba",
        "kategoria": "mineralne",
        "cena_pln_t": 600,
        "jednostka": "kg",
        "bialko_pct": 0.0,
        "energia_me": 0,
        "tluszcz_pct": 0.0,
        "wlokno_pct": 0.0,
        "wapn_g_kg": 370.0,
        "fosfor_g_kg": 0.3,
        "lizyna_g_kg": 0.0,
        "metionina_g_kg": 0.0,
        "uwagi": "Główne źródło wapnia — gruba frakcja dla skorupek"
    },
    {
        "nazwa": "Kreda Pastewna Drobna",
        "kategoria": "mineralne",
        "cena_pln_t": 600,
        "jednostka": "kg",
        "bialko_pct": 0.0,
        "energia_me": 0,
        "tluszcz_pct": 0.0,
        "wlokno_pct": 0.0,
        "wapn_g_kg": 370.0,
        "fosfor_g_kg": 0.3,
        "lizyna_g_kg": 0.0,
        "metionina_g_kg": 0.0,
        "uwagi": "Drobna frakcja — lepsza wchłanialność"
    },
    # ── PREMIKSY ────────────────────────────────────────────────────────────────
    {
        "nazwa": "Dolmix DN RE",
        "kategoria": "premiks",
        "cena_pln_t": 6000,
        "jednostka": "kg",
        "bialko_pct": 5.0,
        "energia_me": 0,
        "tluszcz_pct": 0.0,
        "wlokno_pct": 0.0,
        "wapn_g_kg": 100.0,
        "fosfor_g_kg": 50.0,
        "lizyna_g_kg": 0.0,
        "metionina_g_kg": 0.0,
        "uwagi": "Premiks witaminowo-mineralny dla niosek, zawiera wit. D3, E, B12"
    },
    {
        "nazwa": "Dolmix NoKaniball",
        "kategoria": "premiks",
        "cena_pln_t": 6000,
        "jednostka": "kg",
        "bialko_pct": 0.0,
        "energia_me": 0,
        "tluszcz_pct": 0.0,
        "wlokno_pct": 0.0,
        "wapn_g_kg": 0.0,
        "fosfor_g_kg": 0.0,
        "lizyna_g_kg": 0.0,
        "metionina_g_kg": 0.0,
        "uwagi": "Zapobiega kanibalizmowi — sole gorzkie"
    },
    # ── NATURALNE DODATKI ────────────────────────────────────────────────────────
    {
        "nazwa": "Czosnek (proszek)",
        "kategoria": "naturalny_dodatek",
        "cena_pln_t": 21490,
        "jednostka": "kg",
        "bialko_pct": 16.0,
        "energia_me": 3320,
        "tluszcz_pct": 0.6,
        "wlokno_pct": 7.0,
        "wapn_g_kg": 2.0,
        "fosfor_g_kg": 4.0,
        "lizyna_g_kg": 0.0,
        "metionina_g_kg": 0.0,
        "uwagi": "Antybiotyk naturalny, odporność, smak jajek"
    },
    {
        "nazwa": "Imbir (proszek)",
        "kategoria": "naturalny_dodatek",
        "cena_pln_t": 30000,
        "jednostka": "kg",
        "bialko_pct": 9.0,
        "energia_me": 3470,
        "tluszcz_pct": 4.2,
        "wlokno_pct": 14.0,
        "wapn_g_kg": 1.0,
        "fosfor_g_kg": 1.8,
        "lizyna_g_kg": 0.0,
        "metionina_g_kg": 0.0,
        "uwagi": "Poprawia trawienie, odporność"
    },
    {
        "nazwa": "Kurkuma (mielona)",
        "kategoria": "naturalny_dodatek",
        "cena_pln_t": 20500,
        "jednostka": "kg",
        "bialko_pct": 9.0,
        "energia_me": 3540,
        "tluszcz_pct": 10.0,
        "wlokno_pct": 7.0,
        "wapn_g_kg": 1.8,
        "fosfor_g_kg": 2.7,
        "lizyna_g_kg": 0.0,
        "metionina_g_kg": 0.0,
        "uwagi": "Pigmentuje żółtka, działanie przeciwzapalne"
    },
    {
        "nazwa": "Tymianek (susz)",
        "kategoria": "naturalny_dodatek",
        "cena_pln_t": 28790,
        "jednostka": "kg",
        "bialko_pct": 9.0,
        "energia_me": 2760,
        "tluszcz_pct": 4.0,
        "wlokno_pct": 18.0,
        "wapn_g_kg": 12.0,
        "fosfor_g_kg": 2.0,
        "lizyna_g_kg": 0.0,
        "metionina_g_kg": 0.0,
        "uwagi": "Antybiotyk naturalny, aromat jajek"
    },
    {
        "nazwa": "Oregano (susz)",
        "kategoria": "naturalny_dodatek",
        "cena_pln_t": 23790,
        "jednostka": "kg",
        "bialko_pct": 9.0,
        "energia_me": 2690,
        "tluszcz_pct": 4.3,
        "wlokno_pct": 23.0,
        "wapn_g_kg": 16.0,
        "fosfor_g_kg": 2.0,
        "lizyna_g_kg": 0.0,
        "metionina_g_kg": 0.0,
        "uwagi": "Silne działanie przeciwbakteryjne"
    },
    {
        "nazwa": "Koper (susz)",
        "kategoria": "naturalny_dodatek",
        "cena_pln_t": 25790,
        "jednostka": "kg",
        "bialko_pct": 14.0,
        "energia_me": 2700,
        "tluszcz_pct": 3.5,
        "wlokno_pct": 22.0,
        "wapn_g_kg": 21.0,
        "fosfor_g_kg": 3.0,
        "lizyna_g_kg": 0.0,
        "metionina_g_kg": 0.0,
        "uwagi": "Wysoka zawartość wapnia, aromat"
    },
    {
        "nazwa": "Drożdże browarniane/paszowe",
        "kategoria": "naturalny_dodatek",
        "cena_pln_t": 3599,
        "jednostka": "kg",
        "bialko_pct": 45.0,
        "energia_me": 2450,
        "tluszcz_pct": 1.0,
        "wlokno_pct": 3.0,
        "wapn_g_kg": 0.8,
        "fosfor_g_kg": 14.0,
        "lizyna_g_kg": 30.0,
        "metionina_g_kg": 5.5,
        "uwagi": "Wit. z grupy B, probiotyki, poprawa piór"
    },
    {
        "nazwa": "Siemię Lniane",
        "kategoria": "naturalny_dodatek",
        "cena_pln_t": 4000,
        "jednostka": "kg",
        "bialko_pct": 24.0,
        "energia_me": 4840,
        "tluszcz_pct": 35.0,
        "wlokno_pct": 8.0,
        "wapn_g_kg": 2.0,
        "fosfor_g_kg": 5.0,
        "lizyna_g_kg": 8.5,
        "metionina_g_kg": 3.3,
        "uwagi": "Omega-3, zdrowe żółtka, błyszczące pióra"
    },
    {
        "nazwa": "Susz z pokrzywy",
        "kategoria": "naturalny_dodatek",
        "cena_pln_t": 5000,
        "jednostka": "kg",
        "bialko_pct": 20.0,
        "energia_me": 1800,
        "tluszcz_pct": 3.0,
        "wlokno_pct": 30.0,
        "wapn_g_kg": 25.0,
        "fosfor_g_kg": 3.0,
        "lizyna_g_kg": 0.0,
        "metionina_g_kg": 0.0,
        "uwagi": "Pigmenty żółtka, wapń, żelazo, wit. K"
    },
]

# ─── NORMY ŻYWIENIOWE DLA NIOSEK ─────────────────────────────────────────────
# Zalecane wartości dzienne / na 100g paszy (dla kur niosek w pełnej nieśności)
NORMY_NIOSEK = {
    "energia_me_min":    2700,   # kcal/kg paszy
    "energia_me_max":    2850,
    "bialko_min":        15.5,   # % w paszy
    "bialko_max":        18.0,
    "wapn_min":          38.0,   # g/kg paszy (3.8%)
    "wapn_max":          45.0,
    "fosfor_min":         3.5,   # g/kg paszy
    "fosfor_max":         4.5,
    "lizyna_min":         7.0,   # g/kg paszy
    "metionina_min":      3.0,   # g/kg paszy
    "tluszcz_min":        3.0,   # %
    "tluszcz_max":        6.0,
    "wlokno_max":        10.0,   # %
}

# ─── MIGRACJA DO BAZY DANYCH ──────────────────────────────────────────────────
def seed_skladniki(db, gospodarstwo_id=None):
    """Wstaw domyślne składniki do bazy jeśli tabela jest pusta."""
    count = db.execute("SELECT COUNT(*) as c FROM skladniki_baza").fetchone()["c"]
    if count > 0:
        return  # już wypełniona
    for s in SKLADNIKI_DOMYSLNE:
        db.execute("""INSERT INTO skladniki_baza(
            nazwa, kategoria, cena_pln_t, jednostka,
            bialko_pct, energia_me, tluszcz_pct, wlokno_pct,
            wapn_g_kg, fosfor_g_kg, lizyna_g_kg, metionina_g_kg, uwagi
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
            s["nazwa"], s["kategoria"], s["cena_pln_t"], s["jednostka"],
            s["bialko_pct"], s["energia_me"], s["tluszcz_pct"], s["wlokno_pct"],
            s["wapn_g_kg"], s["fosfor_g_kg"], s["lizyna_g_kg"], s["metionina_g_kg"],
            s.get("uwagi","")
        ))
    db.commit()

def init_skladniki_tables(db):
    """Utwórz tabele dla bazy składników i analizy receptur."""
    db.executescript("""
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
    CREATE TABLE IF NOT EXISTS receptura_analiza (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        receptura_id INTEGER REFERENCES receptura(id) ON DELETE CASCADE,
        data_analizy DATETIME DEFAULT CURRENT_TIMESTAMP,
        bialko_wynik REAL,
        energia_wynik REAL,
        wapn_wynik REAL,
        fosfor_wynik REAL,
        lizyna_wynik REAL,
        metionina_wynik REAL,
        tluszcz_wynik REAL,
        wlokno_wynik REAL,
        koszt_pln_t REAL,
        ocena_ogolna INTEGER,
        rekomendacje TEXT
    );
    CREATE TABLE IF NOT EXISTS pwm_led (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gospodarstwo_id INTEGER REFERENCES gospodarstwa(id),
        nazwa TEXT DEFAULT 'LED',
        pin_bcm INTEGER NOT NULL,
        jasnosc_pct INTEGER DEFAULT 80,
        aktywny INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS supla_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gospodarstwo_id INTEGER REFERENCES gospodarstwa(id),
        nazwa TEXT NOT NULL,
        server_url TEXT,
        token TEXT,
        channel_id INTEGER,
        typ TEXT DEFAULT 'webhook',
        aktywny INTEGER DEFAULT 1
    );
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
    db.commit()
