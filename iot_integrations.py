# -*- coding: utf-8 -*-
"""
Integracje IoT:
- ESPHome przez natywne REST API
- Supla przez webhook
- ZeroTier — instrukcja konfiguracji (sieć VPN)
- 3x PWM LED ściemniacz
"""
import urllib.request, json, threading, time
from datetime import datetime
from db import get_db

# ─── ESPHOME ─────────────────────────────────────────────────────────────────
class ESPHomeClient:
    """
    Komunikacja z ESPHome przez natywne HTTP API.
    ESPHome udostępnia endpointy REST od v2022.x
    """
    def __init__(self, host, api_password="", port=80):
        self.base = f"http://{host}:{port}"
        self.headers = {"Content-Type": "application/json"}
        if api_password:
            self.headers["X-ESPHome-Password"] = api_password

    def _get(self, path, timeout=5):
        try:
            req  = urllib.request.Request(self.base + path, headers=self.headers)
            resp = urllib.request.urlopen(req, timeout=timeout)
            return json.loads(resp.read()), None
        except Exception as e:
            return None, str(e)

    def _post(self, path, body=None, timeout=5):
        try:
            data = json.dumps(body).encode() if body else b""
            req  = urllib.request.Request(self.base + path, data=data,
                                          method="POST", headers=self.headers)
            resp = urllib.request.urlopen(req, timeout=timeout)
            return True, None
        except Exception as e:
            return False, str(e)

    def get_states(self):
        """Pobierz stany wszystkich encji."""
        return self._get("/api/states")

    def get_info(self):
        """Podstawowe info o urządzeniu."""
        return self._get("/")

    def switch_on(self, entity_id):
        return self._post(f"/api/switch/{entity_id}/turn_on")

    def switch_off(self, entity_id):
        return self._post(f"/api/switch/{entity_id}/turn_off")

    def set_light_brightness(self, entity_id, brightness_pct):
        """brightness_pct: 0-100"""
        b = max(0, min(255, int(brightness_pct * 255 / 100)))
        return self._post(f"/api/light/{entity_id}/turn_on", {"brightness": b})

    def get_sensor(self, entity_id):
        data, err = self._get(f"/api/sensor/{entity_id}")
        if data:
            return data.get("state"), None
        return None, err


def esphome_send_command(urzadzenie_id, kanal, stan, gid):
    """Wysyła polecenie do urządzenia ESPHome."""
    db = get_db()
    dev = db.execute(
        "SELECT * FROM urzadzenia WHERE id=? AND gospodarstwo_id=?",
        (urzadzenie_id, gid)
    ).fetchone()
    if not dev:
        db.close(); return False, "Brak urządzenia"

    client = ESPHomeClient(dev["ip"], dev["api_key"] or "", dev["port"] or 80)
    if stan:
        ok, err = client.switch_on(kanal)
    else:
        ok, err = client.switch_off(kanal)

    now = datetime.now().isoformat()
    if ok:
        db.execute("UPDATE urzadzenia_kanaly SET stan=? WHERE urzadzenie_id=? AND kanal=?",
                   (1 if stan else 0, urzadzenie_id, kanal))
        db.execute("UPDATE urzadzenia SET ostatni_kontakt=?,status='online' WHERE id=?",
                   (now, urzadzenie_id))
    else:
        db.execute("UPDATE urzadzenia SET status='offline' WHERE id=?", (urzadzenie_id,))

    db.execute("INSERT INTO gpio_log(gospodarstwo_id,czas,urzadzenie_id,kanal,stan,zrodlo) VALUES(?,?,?,?,?,?)",
               (gid, now, urzadzenie_id, kanal, 1 if stan else 0, "esphome"))
    db.commit(); db.close()
    return ok, err or "OK"

def esphome_get_sensors(urzadzenie_id, gid):
    """Pobierz wszystkie odczyty sensorów z ESPHome."""
    db = get_db()
    dev = db.execute(
        "SELECT * FROM urzadzenia WHERE id=? AND gospodarstwo_id=?",
        (urzadzenie_id, gid)
    ).fetchone()
    db.close()
    if not dev or dev["typ"] != "esphome":
        return None, "Nie ESPHome"
    client = ESPHomeClient(dev["ip"], dev["api_key"] or "", dev["port"] or 80)
    return client.get_states()


# ─── SUPLA WEBHOOK ───────────────────────────────────────────────────────────
def supla_send_command(config_id, stan):
    """
    Wyślij polecenie przez Supla Cloud API.
    Supla używa OAuth2 — potrzebny token dostępu z panelu Supla.
    """
    db = get_db()
    cfg = db.execute("SELECT * FROM supla_config WHERE id=?", (config_id,)).fetchone()
    if not cfg:
        db.close(); return False, "Brak konfiguracji Supla"

    # Supla Cloud API v2.x
    url  = f"{cfg['server_url']}/api/v2.4.0/channels/{cfg['channel_id']}"
    body = json.dumps({"action": "TURN_ON" if stan else "TURN_OFF"}).encode()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {cfg['token']}"
    }
    try:
        req  = urllib.request.Request(url, data=body, method="PATCH", headers=headers)
        resp = urllib.request.urlopen(req, timeout=5)
        db.close()
        return resp.status < 300, None
    except Exception as e:
        db.close()
        return False, str(e)

def supla_webhook_receive(data):
    """
    Odbierz webhook od Supla (np. zmiana stanu przycisku).
    Wywołaj z route /webhook/supla
    """
    # Supla wysyła JSON: {"channel":{"id":123,"state":{"on":true}}}
    try:
        ch_id = data.get("channel",{}).get("id")
        state = data.get("channel",{}).get("state",{}).get("on", False)
        db = get_db()
        cfg = db.execute("SELECT * FROM supla_config WHERE channel_id=? AND aktywny=1", (ch_id,)).fetchone()
        if cfg:
            # Zaktualizuj stan urządzenia powiązanego
            db.execute(
                "UPDATE urzadzenia_kanaly SET stan=? WHERE urzadzenie_id IN "
                "(SELECT id FROM urzadzenia WHERE gospodarstwo_id=?) AND kanal=?",
                (1 if state else 0, cfg["gospodarstwo_id"], "supla_"+str(ch_id))
            )
            db.commit()
        db.close()
        return True
    except Exception:
        return False


# ─── PWM LED (RPi GPIO) ───────────────────────────────────────────────────────
_pwm_objects = {}  # pin -> PWM object

GPIO_AVAILABLE = False
try:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO_AVAILABLE = True
except Exception:
    pass

def pwm_set_brightness(pin, brightness_pct, frequency=1000):
    """Ustaw jasność LED na pinie GPIO przez PWM. brightness_pct: 0-100"""
    brightness_pct = max(0, min(100, brightness_pct))
    if not GPIO_AVAILABLE:
        _pwm_objects[pin] = brightness_pct  # symulacja
        return True
    try:
        if pin not in _pwm_objects or not hasattr(_pwm_objects[pin], 'ChangeDutyCycle'):
            GPIO.setup(pin, GPIO.OUT)
            _pwm_objects[pin] = GPIO.PWM(pin, frequency)
            _pwm_objects[pin].start(brightness_pct)
        else:
            _pwm_objects[pin].ChangeDutyCycle(brightness_pct)
        return True
    except Exception:
        return False

def pwm_off(pin):
    pwm_set_brightness(pin, 0)

def init_pwm_from_db(gospodarstwo_id):
    """Załaduj ustawienia PWM LED z bazy i zastosuj."""
    db = get_db()
    leds = db.execute(
        "SELECT * FROM pwm_led WHERE gospodarstwo_id=? AND aktywny=1", (gospodarstwo_id,)
    ).fetchall()
    db.close()
    for led in leds:
        pwm_set_brightness(led["pin_bcm"], led["jasnosc_pct"])

def get_pwm_brightness(pin):
    """Pobierz aktualną jasność (symulacja lub rzeczywista)."""
    if pin in _pwm_objects:
        if isinstance(_pwm_objects[pin], (int, float)):
            return int(_pwm_objects[pin])
    return 0


# ─── ZEROTIER — instrukcja i konfiguracja ────────────────────────────────────
ZEROTIER_INSTRUCTIONS = """
# ZeroTier — VPN dla urządzeń wykonawczych (inna sieć)

## Kiedy używać
Gdy ESP32/RPi slave jest w innej sieci niż serwer główny
(np. serwer na VPS, urządzenie w sieci domowej)

## Instalacja na serwerze/RPi głównym
```bash
curl -s https://install.zerotier.com | sudo bash
sudo zerotier-cli join TWOJ_NETWORK_ID
sudo zerotier-cli status
```

## Instalacja na RPi slave
```bash
curl -s https://install.zerotier.com | sudo bash
sudo zerotier-cli join TWOJ_NETWORK_ID
```

## Instalacja na ESP32 (bez oficjalnego klienta)
ESP32 nie obsługuje ZeroTier natywnie.
Rozwiązanie: zamiast tego użyj:
1. cloudflared tunnel (per urządzenie) — najłatwiejsze
2. Wireguard na RPi jako gateway dla ESP32
3. Tailscale (prostszy niż ZeroTier)

## Tailscale — łatwiejsza alternatywa
```bash
# Na każdym urządzeniu Linux/RPi:
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
# Potem w panelu tailscale.com zatwierdź urządzenia
```

## Konfiguracja w panelu Ferma
Wpisz adres ZeroTier/Tailscale IP urządzenia zamiast lokalnego IP.
Wszystko inne działa tak samo.
"""

ESPHOME_CONFIG_TEMPLATE = """
# ESPHome — przykładowa konfiguracja dla kurnika
# Zapisz jako kurnik_a.yaml i wgraj przez ESPHome CLI lub Dashboard

esphome:
  name: kurnik-a
  friendly_name: Kurnik A

esp32:
  board: esp32dev
  framework:
    type: arduino

wifi:
  ssid: !secret wifi_ssid
  password: !secret wifi_password

# Włącz natywne API REST (wymagane przez Ferma Jaj)
web_server:
  port: 80

api:
  password: !secret api_password

ota:
  password: !secret ota_password

logger:

# Przekaźniki
switch:
  - platform: gpio
    pin: GPIO16
    name: "Relay 1 — Światło"
    id: relay1
    restore_mode: ALWAYS_OFF
  - platform: gpio
    pin: GPIO17
    name: "Relay 2 — Woda"
    id: relay2
    restore_mode: ALWAYS_OFF
  - platform: gpio
    pin: GPIO18
    name: "Relay 3 — Pasza"
    id: relay3
    restore_mode: ALWAYS_OFF
  - platform: gpio
    pin: GPIO19
    name: "Relay 4 — Wentylacja"
    id: relay4
    restore_mode: ALWAYS_OFF

# PWM LED (opcjonalnie)
output:
  - platform: ledc
    pin: GPIO5
    id: led_output
light:
  - platform: monochromatic
    name: "LED Kurnik"
    output: led_output
    id: led_kurnik

# DS18B20 temperatura
one_wire:
  - platform: gpio
    pin: GPIO4

sensor:
  - platform: dallas_temp
    name: "Temperatura Kurnik"
    address: 0x0000000000000000  # zastąp adresem czujnika
  - platform: wifi_signal
    name: "WiFi Signal"
    update_interval: 60s
"""
