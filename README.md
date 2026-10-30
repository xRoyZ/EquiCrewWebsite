# EquiCrew Website

Die neue Website der EquiCrew FlexCo (smarte Energie – fair verteilte KI; Produkt: das Heizsystem EquiCube) ersetzt die bisherige Wix-Seite. Sie besteht aus fünf deutschsprachigen Seiten – Start, Über uns, EquiCube, Kontakt und Impressum – sowie der Datenschutzerklärung. Das Kontaktformular (Vorname, Nachname, Email, Nachricht) schickt seine Eingaben an eine kleine Python-API, die die Nachricht per SMTP an office@equicrew.com versendet. Es gibt keine Datenbank, keine Cookies und keine Ressourcen von Drittanbietern.

## Tech-Stack

- **Website (`frontend/`)**: reines HTML, CSS und JavaScript ohne Build-Schritt; eine HTML-Datei pro Seite, gemeinsame Stylesheets und Skripte, Schriften werden selbst ausgeliefert. Für die Entwicklung gibt es einen kleinen Server, der nur die Node.js-Standardbibliothek nutzt (`frontend/dev_server.mjs`, ohne Abhängigkeiten).
- **API (`backend/`)**: Python 3.12+, FastAPI, Uvicorn, Pydantic mit pydantic-settings; Versand per SMTP.
- **Tests**: `node --test` für die Website, `pytest` für die API.

## Installation

Voraussetzungen: Python 3.12 oder neuer, Node.js 22 (Entwicklungsserver der Website und Website-Tests), Bash. Für die Website ist nichts zu installieren.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

## Entwicklung starten

Ein Befehl startet Website und API gemeinsam:

```bash
./dev.sh
```

- Website: http://localhost:8080/ (bitte genau diese Adresse öffnen, sie ist als CORS-Origin der API eingetragen)
- API: http://127.0.0.1:8000/api/health

`Strg+C` beendet beide Prozesse. Andere Ports: `WEB_PORT=3000 API_PORT=9000 ./dev.sh`. Ein anderer Python-Interpreter: `PYTHON=.venv/bin/python ./dev.sh`.

Damit das Kontaktformular wirklich Mails versendet, werden die SMTP-Variablen beim Start mitgegeben:

```bash
export SMTP_HOST=smtp.example.com
export SMTP_PORT=587
export SMTP_USERNAME=website@equicrew.com
export SMTP_PASSWORD='…'          # nie ins Repository schreiben
export SMTP_FROM=website@equicrew.com
./dev.sh
```

Ohne SMTP-Variablen startet die API trotzdem; `/api/health` antwortet mit 200 und das Formular zeigt eine Fehlermeldung mit Verweis auf office@equicrew.com (die API antwortet dann mit 503).

### Einzeln starten

```bash
# API (aus backend/); --no-access-log hält die IP-Adressen der Besucher aus den Logs
cd backend
CORS_ORIGIN=http://localhost:8080 uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log

# Website (in einem zweiten Terminal, aus dem Repository-Wurzelverzeichnis)
cd frontend
PORT=8080 API_BASE_URL=http://127.0.0.1:8000 node dev_server.mjs
```

Die Website besteht nur aus statischen Dateien in `frontend/`. In `RUN.json` ist sie als Dienst `web` beschrieben (Stack `web-static`, Art `static`): Gestartet wird sie aus `frontend/` mit `node dev_server.mjs`, der Port kommt aus `PORT`, die API-Adresse aus `API_BASE_URL`. Der Server liefert die Seiten aus (`/ueber-uns/` → `ueber-uns/index.html`) und beantwortet `/js/config.js` mit der API-Adresse aus `API_BASE_URL`; ist die Variable nicht gesetzt, wird die statische Datei mit `apiBase: ""` (gleiche Origin) ausgeliefert.

## Produktion

Es gibt keinen Build-Schritt. Der Inhalt von `frontend/` wird von einem beliebigen statischen Webserver ausgeliefert; `/js/config.js` enthält dort `apiBase: ""`, die Website ruft die API also unter derselben Origin auf (`/api/...` per Reverse-Proxy an die API weiterleiten). Die API läuft mit:

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log
```

Liegt die API hinter einem Reverse-Proxy, muss dessen Adresse in `TRUSTED_PROXIES` stehen, damit das Rate-Limit die echte Client-IP aus `X-Forwarded-For` verwendet.

## Umgebungsvariablen

### API (`backend/`)

| Variable | Pflicht für Mailversand | Standard | Bedeutung |
|---|---|---|---|
| `SMTP_HOST` | ja | – | Hostname des SMTP-Servers |
| `SMTP_PORT` | nein | `587` | Port des SMTP-Servers |
| `SMTP_USERNAME` | ja, wenn der Server eine Anmeldung verlangt | – | SMTP-Benutzername |
| `SMTP_PASSWORD` | ja, wenn der Server eine Anmeldung verlangt | – | SMTP-Passwort; nur als Umgebungsvariable, nie im Repository |
| `SMTP_FROM` | ja | – | Absenderadresse der Kontaktmails |
| `CONTACT_TO` | nein | `office@equicrew.com` | Empfänger der Kontaktmails |
| `CORS_ORIGIN` | nein | `http://localhost:8080` | die eine Website-Origin, die die API aufrufen darf (keine Wildcard) |
| `TRUSTED_PROXIES` | nein | leer | kommagetrennte Adressen vertrauenswürdiger Reverse-Proxys |
| `PORT` | nein | – | Port der API, wenn sie über die Startbeschreibung `RUN.json` gestartet wird |

Die SMTP-Variablen, die EquiCrew setzen muss: **`SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`** (optional `CONTACT_TO`).

### Website (`frontend/dev_server.mjs`)

| Variable | Standard | Bedeutung |
|---|---|---|
| `PORT` | `8000` | Port des Entwicklungsservers (`dev.sh` setzt 8080) |
| `API_BASE_URL` | leer (gleiche Origin) | Origin der API, wird unter `/js/config.js` an die Seiten ausgeliefert |

## Bedienung

### Seiten

| Pfad | Seite |
|---|---|
| `/` | Start |
| `/ueber-uns/` | Über uns – die Crew und die drei Gründer |
| `/equicube/` | EquiCube – Produkt, Key Features, Vorteile |
| `/kontakt/` | Kontakt – Formular und Kontaktdaten |
| `/impressum/` | Impressum |
| `/datenschutz/` | Datenschutzerklärung |

Die Navigation im Kopfbereich führt zu allen fünf Hauptseiten, auf schmalen Bildschirmen über die Menü-Schaltfläche. Die Fußzeile verlinkt Kontakt, Impressum und Datenschutz.

### API-Endpunkte

Alle Fehlerantworten haben genau die Form `{"detail": "<Text>"}`; sie enthalten weder SMTP-Fehlerdetails noch Passwörter oder Besucherdaten. Eine Authentifizierung gibt es nicht.

**`GET /api/health`** – Lebenszeichen der API.

```json
{"status": "ok"}
```

**`POST /api/contact`** – sendet eine Kontaktnachricht an `CONTACT_TO`.

Body (JSON):

```json
{
  "vorname": "Maria",
  "nachname": "Muster",
  "email": "maria@example.com",
  "nachricht": "Ich interessiere mich für den EquiCube.",
  "website": ""
}
```

`nachricht` darf höchstens 5000 Zeichen lang sein. `website` ist ein im Formular verstecktes Honeypot-Feld: Ist es ausgefüllt, antwortet die API ebenfalls mit Erfolg, versendet aber nichts.

Antworten:

| Status | Body | Bedeutung |
|---|---|---|
| 200 | `{"status": "sent"}` | Nachricht versendet (oder Honeypot ausgefüllt) |
| 413 | `{"detail": "..."}` | Request-Body größer als 64 KB |
| 422 | `{"detail": "..."}` | ungültige Eingabe |
| 429 | `{"detail": "..."}` | zu viele Anfragen von dieser IP-Adresse (Standard: 5 in 10 Minuten) |
| 503 | `{"detail": "..."}` | SMTP nicht konfiguriert oder Versand fehlgeschlagen |

Beispiel:

```bash
curl -X POST http://127.0.0.1:8000/api/contact \
  -H 'Content-Type: application/json' \
  -d '{"vorname":"Maria","nachname":"Muster","email":"maria@example.com","nachricht":"Hallo!"}'
```

CORS: Nur `CORS_ORIGIN` erhält `Access-Control-Allow-Origin`, erlaubt sind `GET` und `POST` mit dem Header `Content-Type`, ohne Credentials. Anfragen mit fremdem `Origin` erhalten keinen CORS-Header.

## Tests

```bash
# Website (aus frontend/)
cd frontend
node --test tests/*.test.mjs

# API (aus backend/)
cd backend
PYTHONPATH=. python3 -m pytest
```

## Funktionen

- Fünf Seiten (Start, Über uns, EquiCube, Kontakt, Impressum) plus Datenschutzerklärung, jede als eigenes HTML-Dokument mit eigenem Titel und eigener Beschreibung
- Gemeinsamer Kopfbereich mit Navigation (Menü-Schaltfläche auf kleinen Bildschirmen) und gemeinsame Fußzeile mit Adresse, E-Mail und Telefon
- Kontaktformular mit Prüfung der Eingaben im Browser und Versand per SMTP an office@equicrew.com, Antwortadresse ist die des Besuchers
- Schutz der API: Honeypot-Feld, Rate-Limit pro IP-Adresse (nur im Arbeitsspeicher), Größenlimit für den Request-Body, CORS nur für die Website-Origin
- Datensparsam: keine Datenbank, keine Cookies, keine Drittanbieter-Ressourcen, keine Besucherdaten oder IP-Adressen in Logs
- Läuft ohne Build-Schritt auf jedem statischen Webserver; Animationen werden bei `prefers-reduced-motion` abgeschaltet
