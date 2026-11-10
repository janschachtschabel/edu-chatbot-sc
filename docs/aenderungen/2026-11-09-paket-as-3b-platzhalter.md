# Paket AS-3b: Platzhalter in Texten (2026-11-09)

Plan: [`plans/2026-11-09-ablaeufe-im-studio.md`](../plans/2026-11-09-ablaeufe-im-studio.md), D3 und §5d.

## Was sich ändert

- **Platzhalter `{teil.<name>}` und `{teil.<name>.<pfad>}`** gibt es in `text` (Nachricht, Modul,
  KI-Schritt, Auftrag, Ende) und in `freigabe`. Der Treiber setzt beim Ausgeben die Werte aus den
  Teilen des Laufs ein, auch aus Teilen, die im selben Zug entstanden sind (etwa ein Freitext).
- **Wie ein Wert zu Text wird:**
  - Ein Objekt mit `titel` zeigt den Titel. Andere Objekte und Listen stehen als kompaktes JSON da.
    Zahlen und Text bleiben, wie sie sind; ja/nein steht als „ja“/„nein“.
  - Er ist einzeilig und auf höchstens 200 sichtbare Zeichen gekürzt.
  - Er hat keine Markdown-Wirkung, denn ein Teil kann von der Person stammen (Freitext) und baute
    sonst Links oder Überschriften in die Antwort. Escapt wird jedes ASCII-Satzzeichen außer `$`.
    Steuer- und Bidi-Zeichen fallen weg.
  - Fehlt ein Wert (Teil oder Stelle im Pfad), steht „—“.
- **`{start.<feld>}`** ist für die Startdaten von AS-4 reserviert. Bis dahin ist er ein Befund und
  bleibt im Text stehen. Was nicht wie ein Platzhalter aussieht, etwa `{nicht}`, bleibt unverändert.
- **Prüfung** meldet:
  - eine kaputte Form (Name oder Pfad);
  - `start.` (noch nicht verfügbar);
  - einen Teil, den kein Schritt auf einem Weg *vor* diesem Schritt schreibt, und einen, den gar
    keiner schreibt. Bekannt sind `schreibt`, die Ausgabe
    eines KI-Schritts, Freitext und was das Manifest eines Moduls schreiben darf
    (`vorgang.schreibt`), auch beim Modul-Auslöser.
  - Platzhalter in Beschriftungen von Schnellantworten. Dort wirken sie nicht, weil die Chips ohne
    die Teile entstehen. Das ist eine bewusste Abweichung vom Plan, der sie dort auch vorsah.
- **Simulation:** Sie setzt mit ein, denn sie nutzt den echten Treiber. Jedes Testergebnis enthält die ausgegebenen Texte (`texte`, gekürzt), und das Studio zeigt sie je Testfall an.
- **Studio:** Die Hinweise an „Text“ und „Freigabe“ nennen die Platzhalter, auf Deutsch und Englisch.
  Die Studio-Übersetzung ersetzt nur `{wort}` ohne Punkt, `{teil.name}` bleibt im Hinweis also
  sichtbar.

## Wo

- `backend/src/boerdi/services/ablauf/platzhalter.py` (neu): `finden`, `entschaerft`, `einsetzen`.
- `services/ablauf/treiber.py`: Einsetzen bei Text, Freigabe und Auftragstext.
- `services/ablauf/pruefung.py`: `_geschriebene_teile`, `_platzhalter`; dazu `pruefung_texte.py`.
- Studio: `i18n/catalogue/fields-ablaeufe.ts`.

## Tests

- `backend/tests/test_ablauf_platzhalter.py` deckt ab:
  - Einsetzen mit Pfad;
  - fehlende Werte;
  - Markdown, Kürzen, Objekte und Listen;
  - fremde Klammern;
  - die Prüfung (bekannte Teile aus Schritt, Modul und Freitext, kaputte Form, `start`, unbekannter Teil, Beschriftung);
  - den Treiber mit Teilen aus demselben Zug.
- Ergebnis vor dem Review: Backend 969 gezielte Tests grün (Ablauf, Preflight, Chat, Verträge, Seed). Die Studio-Texttests sind grün.

## Betrieb

Keine Migration, keine neue Variable. Einzige Vertragsänderung ist das optionale Feld `texte` am
Ergebnis von `POST /api/config/ablauf-testen` (seit dem Review). Bestehende Texte mit `{…}` ändern sich nur,
wenn sie wie `{teil.x}` aussehen; der mitgelieferte Ablauf hat keine.

## Review (2026-11-09)

Ein frischer Reviewer fand 1 hoch, 5 klein und 4 Kleinigkeiten. Jeder Befund wurde am Quelltext nachgeprüft:

| Befund | Behebung |
|---|---|
| Hoch: Nackte Adressen und E-Mail-Adressen wurden trotz Entschärfung Links (GFM-Autolink im Widget). Dazu kamen Icon-Sentinels und Blockformen am Zeilenanfang. | Jedes ASCII-Satzzeichen außer `$` wird escapt, so dass `https\:\/\/` kein Link mehr wird. Tests decken Adresse, `www`, E-Mail, Icon und `$` ab. |
| UI-Module in einem KI-Schritt (`ui_upload` schreibt `structure`) fehlten unter den bekannten Teilen. | Die Prüfung liest jetzt auch die Manifeste der Module in `agent.werkzeuge` (Test). |
| „Den kein Schritt *davor* schreibt“ war nicht umgesetzt. | `_teile_davor` rechnet je Schritt die Teile, die auf einem Weg davor entstehen. Ein Teil, der erst später entsteht, ist ein eigener Befund (Test). Teile, die schon vor dem Start im Vorgang liegen, gehen bis AS-4 („Startteil“) nur über `$teil`. Das ist bewusst so. |
| Die Simulation gab die Texte nicht zurück. | `TestErgebnis.texte` und Feld `texte` am Endpunkt. Das Studio zeigt sie je Testfall aufklappbar und ohne Escapes (Tests). |
| Eingesetzte Werte landen in der gespeicherten Antwort und damit im Verlauf, den die KI im nächsten Zug sieht. | Das ist ein bewusst getragenes Risiko. Die Redaktion wählt die Platzhalter, der Wert ist auf 200 Zeichen begrenzt, ohne Markdown, ohne Steuerzeichen. Die Antwort beim Neuladen soll dasselbe zeigen wie vorher; deshalb wird nicht nur in der Ausgabe eingesetzt. |
| Tests für Teile aus demselben Zug, Freigabe-Satz und Auftragstext fehlten. | Drei Treiber-Tests: Werkzeug, Freitext, Freigabe und Auftrag. |
| Kleinigkeiten | `{teil.x.}` ist ungültig. Fast-Platzhalter wie `{Teil.x}` oder `{teil.a b}` sind ein Befund. `schreibt` zählt nur an Werkzeug und Auftrag, die Ausgabe nur am KI-Schritt. Steuer- und Bidi-Zeichen fallen weg. Die Sprachausgabe (`stripMarkdown`) löst die Escapes auf (`ohneMarkdownEscapes`, Bibliothek `ui`). |

Prüfung nach dem Review: Backend 936 gezielte Tests grün (ohne die damals noch rote AS-3c-Testdatei). Studio 170/170, `ui`-Sprachausgabe grün; eslint sauber.
Hinweis zum Betrieb: Die Bibliothek `ui` hat sich geändert (Sprachausgabe), deshalb das Image neu bauen (Widget, Studio, Backend).
