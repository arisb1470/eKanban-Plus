# eKanban-Plus

## Was der Prototyp kann

- lädt Rack-, Pricing- und Einzeltrommel-CSVs aus `data/raw`
- berechnet einen aktuellen Trommel-Snapshot
- schätzt Restreichweite, Leer-Datum und sicheren Bestellzeitpunkt
- schlägt Bündel vor, um Versand- und Mindestbestellkosten zu reduzieren
- beantwortet Rückfragen im Chat auf Basis deterministischer Tool-Ergebnisse

## Erwartete Struktur
data/raw/
├─ rack_kunde_a_regal_og.csv
├─ rack_kunde_b_kommissionierung.csv
├─ pricing_and_leadtimes.csv
└─ einzeltrommeln/
   └─ *.csv

## Starten mit

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run Dashboard.py

## Powershell

python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run Dashboard.py

## Login
Mit Kunde A oder Kunde B, Passowrt für beide: 12345