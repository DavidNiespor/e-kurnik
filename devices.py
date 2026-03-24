# -*- coding: utf-8 -*-
"""
Komunikacja z urządzeniami slave: ESP32 i RPi przez HTTP REST.
Każde urządzenie należy do konkretnego gospodarstwa.
"""
import urllib.request, json, threading, time
from datetime import datetime
from db import get_db

ESP32_FIRMWARE = '''
// Ferma Jaj — ESP32 slave firmware v4
// Arduino IDE: WiFi + WebServer + ArduinoJson

#include <WiFi.h>
#include <WebServer.h>
#include <ArduinoJson.h>

const char* SSID    = "TWOJA_SIEC";
const char* PASS    = "TWOJE_HASLO";
const char* API_KEY = "WPISZ_API_KEY_Z_PANELU";

const int RELAY_PINS[] = {16, 17, 18, 19};
const int N = 4;
bool relay_state[4] = {false,false,false,false};

WebServer server(80);

bool auth() {
  return server.header("X-API-Key") == String(API_KEY);
}

void handleStatus() {
  if (!auth()) { server.send(403,"application/json","{\\"error\\":\\"unauthorized\\"}"); return; }
  StaticJsonDocument<256> doc;
  JsonObject ch = doc.createNestedObject("channels");
  for (int i=0;i<N;i++) ch["relay"+String(i+1)] = relay_state[i];
  doc["uptime"] = millis()/1000;
  doc["ip"] = WiFi.localIP().toString();
  String out; serializeJson(doc,out);
  server.send(200,"application/json",out);
}

void handleRelay() {
  if (!auth()) { server.send(403,"application/json","{\\"error\\":\\"unauthorized\\"}"); return; }
  StaticJsonDocument<128> doc;
  deserializeJson(doc, server.arg("plain"));
  String ch = doc["channel"].as<String>();
  bool state = doc["state"].as<bool>();
  int idx = ch.substring(5).toInt()-1;
  if (idx>=0 && idx<N) {
    relay_state[idx] = state;
    digitalWrite(RELAY_PINS[idx], state ? LOW : HIGH);
    server.send(200,"application/json","{\\"ok\\":true}");
  } else {
    server.send(400,"application/json","{\\"error\\":\\"invalid\\"}");
  }
}

void setup() {
  for (int i=0;i<N;i++) { pinMode(RELAY_PINS[i],OUTPUT); digitalWrite(RELAY_PINS[i],HIGH); }
  WiFi.begin(SSID,PASS);
  while (WiFi.status()!=WL_CONNECTED) delay(500);
  server.on("/api/status", HTTP_GET, handleStatus);
  server.on("/api/relay", HTTP_POST, handleRelay);
  server.collectHeaders("X-API-Key");
  server.begin();
}

void loop() { server.handleClient(); }
'''

def _req(ip, port, path, method="GET", body=None, api_key="", timeout=5):
    url  = f"http://{ip}:{port}{path}"
    data = json.dumps(body).encode() if body else None
    hdrs = {"Content-Type":"application/json"}
    if api_key: hdrs["X-API-Key"] = api_key
    try:
        req  = urllib.request.Request(url, data=data, method=method, headers=hdrs)
        resp = urllib.request.urlopen(req, timeout=timeout)
        return json.loads(resp.read()), None
    except Exception as e:
        return None, str(e)

def send_command(urzadzenie_id, kanal, stan, gid):
    db = get_db()
    dev = db.execute("SELECT * FROM urzadzenia WHERE id=? AND gospodarstwo_id=?",
                     (urzadzenie_id, gid)).fetchone()
    if not dev:
        db.close(); return False, "Brak urządzenia"
    path = "/api/relay" if dev["typ"]=="esp32" else "/api/gpio"
    body = {"channel": kanal, "state": bool(stan)}
    resp, err = _req(dev["ip"], dev["port"], path, "POST", body, dev["api_key"])
    ok  = resp is not None
    now = datetime.now().isoformat()
    if ok:
        db.execute("UPDATE urzadzenia_kanaly SET stan=? WHERE urzadzenie_id=? AND kanal=?",
                   (1 if stan else 0, urzadzenie_id, kanal))
        db.execute("UPDATE urzadzenia SET ostatni_kontakt=?,status='online' WHERE id=?", (now, urzadzenie_id))
    db.execute("INSERT INTO gpio_log(gospodarstwo_id,czas,urzadzenie_id,kanal,stan,zrodlo) VALUES(?,?,?,?,?,?)",
               (gid, now, urzadzenie_id, kanal, 1 if stan else 0, "reczny"))
    db.commit(); db.close()
    return ok, err or "OK"

def ping_device(urzadzenie_id, gid):
    db = get_db()
    dev = db.execute("SELECT * FROM urzadzenia WHERE id=? AND gospodarstwo_id=?",
                     (urzadzenie_id, gid)).fetchone()
    if not dev:
        db.close(); return False, "Brak urządzenia"
    resp, err = _req(dev["ip"], dev["port"], "/api/status", api_key=dev["api_key"])
    now = datetime.now().isoformat()
    if resp:
        db.execute("UPDATE urzadzenia SET ostatni_kontakt=?,status='online' WHERE id=?", (now, urzadzenie_id))
        if "channels" in resp:
            for ch, val in resp["channels"].items():
                db.execute("UPDATE urzadzenia_kanaly SET stan=? WHERE urzadzenie_id=? AND kanal=?",
                           (1 if val else 0, urzadzenie_id, ch))
    else:
        db.execute("UPDATE urzadzenia SET status='offline' WHERE id=?", (urzadzenie_id,))
    db.commit(); db.close()
    return bool(resp), err or "online"
