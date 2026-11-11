# Fix: Seitenliste im Studio bricht Titel Buchstabe für Buchstabe um (2026-11-10)

## Befund

Gemeldet vom Nutzer nach dem Update auf `9bbce3c`, mit Screenshot der Seite „Abläufe“: In der
Dokumentliste standen die Titel buchstabenweise untereinander („Kur ze Füh run g“), und die Liste
lief waagerecht über.

## Ursache

`studio-entry-list` (`schema-form/entry-list.component.scss`) setzt Titel und Kennzeile
nebeneinander in eine Flex-Zeile. Die Kennzeile hatte `flex: none` und schrumpfte nie. Bei
Abläufen ist sie lang („kennung · aus · Knopf, Seite, Wendung“, seit AS-0) und nahm fast die
ganze Breite. Der Titel durfte wegen `overflow-wrap: anywhere` überall umbrechen, also blieb ihm
die Breite eines Buchstabens.

## Behebung

- **`.ol-entry`:** `flex-wrap: wrap`. Eine lange Kennzeile rutscht unter den Titel, eine kurze
  (etwa `gruss`) bleibt daneben.
- **`.ol-title`:** `flex: 1 1 8rem`. Das ist die Mindestbreite, bevor die Zeile umbricht.
- **`.ol-note`:** `flex: 0 1 auto` und `overflow-wrap: anywhere`. Länger als die ganze Zeile
  bricht sie selbst um, ohne Überlauf.

Die Liste dient allen Liste│Editor-Seiten (Gruppen wie Abläufe und Objektlisten), alle haben den
Fix.

## Prüfung

Gemessen in Chromium per Playwright, mit der Liste 18 rem breit und denselben Einträgen:

| | Breite der Titel | Zeilen je Titel | waagerechter Überlauf |
|---|---|---|---|
| vorher | 14–15 px | 13–26 | ja |
| nachher | 229–270 px | 1 | nein |

Studio 2144 grün; `lint`, `check:tokens`, `check:radii`, `check:contrast` und `check:a11y`
sauber.

## Deploy

Nur das Studio ändert sich: Image neu bauen und im Browser hart neu laden. Keine Migration.
