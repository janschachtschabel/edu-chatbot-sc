# Paket 12 — Werksfassung und eigene Fassung je Bereich

Stand 2026-10-16. Auftrag (Nutzer): Muster und Konfiguration als feste Werksfassung aus dem Repository
**und** als eigene, anpassbare Fassung; je Bereich zwischen beiden umschalten. „Leicht zu nutzen und
performant.“ Dazu die Frage, ob Schnappschüsse zwischen selbst angelegten und dem Werkszustand aus dem
Repository klar unterscheiden — heute nicht (§1).

## 1 Ausgangslage

- **Werksfassung gibt es schon:** die Seeds liegen unveränderlich im Image (`/app/seeds`, aus demselben
  Commit wie der Code).
- **Nach dem ersten Import gibt es nur noch eine Fassung** — die in `config_areas`. Neue Werksfassungen
  kommen nie von selbst an (auch nicht bei unberührten Bereichen), man sieht nicht, was angepasst ist,
  und zurück geht nur alles auf einmal (`exact`) oder von Hand. Paket 11 L brauchte deshalb einen
  Handimport für fünf Bereiche.
- **Begriffe verwirren:** die Karte „Werkseinstellungen“ ist ein aus dem *Live-Stand* gesicherter Stand,
  nicht das Repository; das Repository heißt „Auslieferungsstand aus dem Abbild“. Schnappschüsse
  unterscheiden „von Hand“ und „automatisch vor einer Aktion“ nur am Namen.

## 2 Entscheidung: Bauweise

**Gewählt: Die Datenbank bleibt die gelebte Konfiguration; je Bereich merkt sie sich, auf welcher
Werksfassung er beruht.** Der Lesepfad im Chat bleibt unverändert (Prozess-Cache, NOTIFY) — keine
zusätzliche Arbeit je Zug.

Verworfen: Werksfassung zur Laufzeit aus dem Image lesen und nur Abweichungen in der Datenbank halten
(„Overlay“). Gleiches Ergebnis für die Nutzung, aber jeder Lesepfad, die Versions-/Konfliktlogik
(Paket 4, D1–D5), Verlauf, Sicherungen und der Import müssten zwei Quellen zusammenführen — viel Risiko
für keinen Mehrwert.

| Feld (neu, `config_areas`) | Bedeutung |
|---|---|
| `werk_hash` | Prüfsumme der Werksfassung, auf der der Bereich zuletzt stand (`NULL` = unbekannt / kein Werk) |
| `eigene_fassung` (`jsonb`) | stillgelegte eigene Fassung, solange die Werksfassung aktiv ist |

Dazu Tabelle `config_werk_entfernt(area)`: ein im Studio gelöschter Werksbereich kommt beim Abgleich
nicht wieder. Löschen trägt ein, Schreiben trägt aus (in derselben Transaktion).

**Status je Bereich** (berechnet, nicht gespeichert; `h()` = Prüfsumme über kanonisches JSON):

| Status | Bedingung |
|---|---|
| `werk` | `h(data) == h(seed)` |
| `werk-veraltet` | `h(data) == werk_hash != h(seed)` — unberührt, der Abgleich zieht nach |
| `eigen` | weicht ab, `werk_hash == h(seed)` |
| `eigen-neues-werk` | weicht ab, `werk_hash` ≠ `h(seed)` (oder unbekannt) — neue Werksfassung verfügbar |
| `nur-eigen` | kein Werksbereich |
| `werk-entfernt` | Werksbereich, im Studio gelöscht |

## 3 Abläufe

1. **Werksabgleich** (`seed_sync`, Modus `werk`; CLI `import-config --werksabgleich`; Studio-Knopf):
   fehlende Werksbereiche anlegen (außer entfernte), `werk-veraltet` auf die neue Werksfassung heben,
   eigene **nie** anfassen; Bereiche mit `werk_hash = NULL`, die der Werksfassung gleichen, bekommen den
   Hash (Erstzuordnung des Bestands). Der `migrate`-Dienst ruft ihn statt `--only-missing` auf → nach
   einem Deploy sind unberührte Bereiche aktuell, ohne Handgriff.
2. **„Werksfassung verwenden“** (je Bereich): `eigene_fassung := data`, `data := seed`,
   `werk_hash := h(seed)` — bedingt auf die gelesene Version (Konflikt → 409 wie überall).
3. **„Eigene Fassung verwenden“**: `data := eigene_fassung`, `eigene_fassung := NULL`.
4. **Vergleich**: Unterschied Werk ↔ gelebt als Zeilen (`difflib`, Standardbibliothek) über die
   Dateiform (Markdown/YAML), wie man sie im Studio sieht.
5. **Werksbereich wiederherstellen** (`werk-entfernt`): Eintrag austragen, Werksfassung schreiben.

Jede Umschaltung schreibt eine Verlaufszeile (`updated_by` = `werkfassung` / `eigene-fassung`).

## 4 Studio

- Neue Karte **„Werk und eigene Fassung“** (unter Sicherung, ganz oben): Liste aller Bereiche mit
  Kennzeichen (Text + Form, nicht nur Farbe), Filter „alle / angepasst / neue Werksfassung“, je Zeile
  die passenden Knöpfe, Vergleich aufklappbar. Oben ein Satz, was „Werk“ bedeutet, und der Knopf
  „Werksabgleich“.
- **Begriffe:** „Auslieferungsstand aus dem Abbild“ → **„Werksfassung aus dem Repository“**;
  „Werkseinstellungen“ (aus dem Live-Stand gesichert) → **„Eigener Grundstand“** mit Satz, dass er
  nicht aus dem Repository kommt.
- **Schnappschüsse:** Spalte `art` (`hand` / `auto`); die Liste zeigt „von Hand“ bzw. „automatisch“.

## 5 Was sich nicht ändert

Lesepfad im Chat, Konflikt- und Versionslogik, NOTIFY, Verlauf, Sicherungen (sie enthalten die gelebten
Daten; stillgelegte eigene Fassungen nicht — dokumentiert in `deploy/README.md` „Werk und eigene
Fassung beim Umzug“, INSTALL.md und auf der Studio-Karte), `--exact` (setzt alles auf Werk, legt
vorher einen Schnappschuss an).

## 6 Aufgaben (Test zuerst)

| Nr. | Aufgabe | Nachweis |
|---|---|---|
| W1 | Migration 0011: `werk_hash`, `eigene_fassung`, `config_werk_entfernt`, `config_snapshots.art` | `alembic upgrade/downgrade` gegen Test-DB |
| W2 | `services/werkfassung.py`: Prüfsumme, Status (rein) | Einheitstests je Status |
| W3 | Store: Entfernt-Eintrag bei Löschen, Austrag bei Schreiben; Lesen der Fassungs-Spalten | DB-Tests |
| W4 | Werksabgleich (Modus `werk`), CLI-Schalter, Compose-Befehl | DB-Tests, Trockenlauf |
| W5 | API: Liste, Umschalten (beide Richtungen), Vergleich, Wiederherstellen; OpenAPI | Endpunkt-Tests |
| W6 | Studio-Karte + Begriffe + Schnappschuss-Art, i18n de/en | vitest, eslint, Kontrast |
| W7 | Doku (INSTALL, deploy/README, Befundliste), Memory | — |

Prüfung am Ende: volle Backend-Suite, Studio-Suite, Verträge; Review durch frischen Prüfer.

## 7 Log

- 2026-10-16, W1–W7 gebaut, alles Test zuerst:
  - **W1** Migration 0011 (`werk_hash`, `eigene_fassung`, `eigene_basis`, `config_werk_entfernt`,
    `config_snapshots.art`), Hin- und Rückweg geprüft.
  - **W2** `services/werkfassung.py`: Status, Planung des Abgleichs, Umschaltregeln.
  - **W3** Store: bedingtes Umschalten in einem UPDATE, `werk_schreiben`, Löschvermerk.
  - **W4** `seed_sync.werksabgleich`, CLI `--werksabgleich`, `migrate`-Befehl samt Deploy-Wächter.
    Der echte Seed besteht Import plus Abgleich mit Prüfsumme je Bereich.
  - **W5** API `/api/config/fassungen` (Liste, Werksabgleich, Umschalten, Vergleich), Vertrag und
    Zusätze dokumentiert.
  - **W6** Studio-Karte; Begriffe „Eigener Grundstand“ und „Werksfassung aus dem Repository“;
    Schnappschüsse „von Hand“/„automatisch“.
  - **W7** Doku.
- Erstzuordnung: Bestand ohne Basis gilt als unberührt, wenn `updated_by` ein Import-Weg ist. So
  kommen die Paket-11-L-Bereiche ohne Handimport an. Der einfache Import schreibt seither
  `import-cli` und merkt die Basis nur aus dem Seed-Ordner (Review #3).
- Browser-Abnahme gegen die Wegwerf-DB `boerdi_p12_browser`, danach gelöscht. Gefunden: Der
  Vergleich zeigte Schein-Unterschiede, weil jsonb die Schlüssel umordnet; seither ordnet er nach
  der Werks-Folge, Test zuerst. Bedienung per Maus und Tastatur geprüft: Fokus auf den Gegenknopf,
  Status-Region, Wiederherstellen. Bei 375 px ist die Seite zu breit, das liegt an bestehenden
  Karten (Befundliste §5). Budget-Warnung des Studios bestand schon (+4,7 kB durch die Texte).
- Review (frischer Prüfer: 4 MAJOR, 8 MINOR, 1 NIT — alle bestätigt und behoben, Test zuerst):
  - **#1** Umschalten konnte eine Fassung verlieren.
    - Lösung: „eigen“ tauscht, „werk“ verweigert bei zwei eigenen (`fassung.zweiEigene`).
    - Lösung: Studio bietet dann nur den Tausch an.
  - **#2** Werksabgleich mit Wettlauf.
    - Lösung: bedingt schreiben (gelesene Version, Löschvermerk), Bericht `uebersprungen`.
  - **#3** `import` als dauerhafter Freibrief.
    - Lösung: `import-cli`, Basis nur aus dem Seed-Ordner.
  - **#4** Seed je Aufruf synchron gelesen (~360 ms).
    - Lösung: je Prozess zwischengespeichert, Lesen im Thread; danach 12 ms.
  - **#5** Wiederherstellen ohne Zeile unbedingt.
    - Lösung: anlegen nur, wenn er noch fehlt, sonst 409.
  - **#6** Kennungs-Kollision im Abgleich.
    - Lösung: überspringen, als `konflikt` melden.
  - **#7** Löschvermerk für jeden Bereich.
    - Lösung: nur für Bereiche mit Werksbasis.
  - **#8** Basis der stillgelegten Fassung.
    - Lösung: Spalte `eigene_basis`, reist mit.
  - **#9** Vergleich per Tastatur, Knöpfe ohne Bezug.
    - Lösung: `tabindex`/`role=region` am Vergleich, `aria-describedby` an den Knöpfen.
  - **#10** `werk-fehlt` nur unter „Alle“.
    - Lösung: zusätzlich unter „Angepasst“.
  - **#11** Konflikt-Wege und Begriffe.
    - Lösung: `conflict.via.*` ergänzt, „Auslieferungsstand“ → „Werksfassung“ in Studio und
      Schnappschuss-Etiketten, EN `factory.lead` berichtigt.
  - **#12** Doku.
    - Lösung: Schnellstart-Ausgabe, Umzugs-Hinweis, dieses Log.
  - **#13** zwei UPDATEs je Umschalten.
    - Lösung: ein UPDATE.
- Zweites Review (frischer Prüfer: 2 MAJOR, 6 MINOR, 3 NIT — alle bestätigt und behoben, Test
  zuerst):
  - **#1** Löschen nahm eine stillgelegte eigene Fassung mit; sie steht in keinem Schnappschuss.
    - Jetzt löscht der Store einen solchen Bereich nie.
    - Das Studio-Löschen antwortet 400 (`fassung.loeschenMitEigener`).
    - Exaktes Wiederherstellen und „Alles auf die Werksfassung“ lassen den Bereich stehen und
      melden ihn unter `behalten`.
  - **#2** Der Löschvermerk hing an der Basis, vor 0011 angepasste Werksbereiche kamen nach dem
    Löschen wieder.
    - Jetzt sagt der Aufrufer per Seed, ob es ein Werksbereich ist.
  - **#3** Der Bericht zählt Geschriebenes, nicht Geplantes.
  - **#4** Eine Anhebung allein über die Import-Kennung legt den alten Inhalt still; sie ist so
    umkehrbar.
  - **#5** „Als geprüft markieren“ (`ziel=geprueft`): die eigene Fassung bleibt, die aktuelle
    Werksfassung gilt als gesehen.
    - Sonst stünde Bestand ohne Basis für immer auf „neue Werksfassung“.
  - **#6** Die Meldung richtet sich nach dem, was geschah (veraltetes Werk: „aktualisiert“).
    `umschalten` wertet die Import-Kennung bewusst nicht aus (sichere Richtung: stilllegen).
  - **#7** „Fehlende nachziehen“ und `--only-missing` holen Gelöschtes nicht zurück, und der
    Seed-Status zählt es nicht als fehlend.
  - **#8** Betriebsdoku auf die neuen Begriffe und den Werksabgleich.
  - **#9** Kollisionstext neutral („nicht verwendbar“).
  - **#10** Der Vergleich zeigt auch die stillgelegte Fassung gegen das Werk.
  - **#11** Einheitlich „Werksfassung“; `factory.missing` heißt „Kein eigener Grundstand
    gesichert“.

