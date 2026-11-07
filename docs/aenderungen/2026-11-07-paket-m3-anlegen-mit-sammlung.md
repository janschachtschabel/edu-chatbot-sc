# Paket M3: Material anlegen und einsortieren in einer Bestätigung (2026-11-07)

Plan [`../plans/2026-11-07-mcp-vertrag.md`](../plans/2026-11-07-mcp-vertrag.md) (M3). Anlass ist der
gemeldete Fall „Wikipedia-Seite erschließen und in die Sammlung Optik legen“. Er brauchte zwei
Abnahmen (anlegen, dann einsortieren) und prüfte Dubletten nur über die Volltextsuche.

## Was sich ändert

- **`wlo_create_content` mit `addToCollectionId`:** Der neue Datensatz landet unter **derselben**
  Bestätigung in der Sammlung, ein `wlo_add_to_collection` hinterher entfällt. Die Werkzeugbeschreibung
  sagt das dem Modell. Gibt es zur Adresse schon einen Datensatz, bietet die Vorschau des Servers an,
  diesen aufzunehmen. Scheitert nur das Einsortieren, bleibt der Datensatz bestehen, und die Antwort sagt
  es.
- **Neues Lese-Werkzeug `find_content_by_url`:** Es prüft genau (auch bereinigt), ob es zu einer Adresse
  schon einen Datensatz gibt. Es liefert bis 20 Adressen je Aufruf und kappt mehr. Es steht im
  Server-Register (Studio) und in den Mustern M18 (Kuration) und M20 (Webseite erschließen).
- **Muster M20 („Webseite erschließen und ablegen“):**
  - Schritt 2 prüft zuerst die Adresse (`exact` = vorhanden, `normalized` = nachfragen), dann den Titel.
    Gibt es den Datensatz schon, wird er mit `wlo_add_to_collection` einsortiert.
  - Schritt 4 ruft `wlo_create_content` (mit `addToCollectionId`) auf. Die Vorschau des Servers IST der
    Vorschlag. Vorher gab es zwei „ja“ (Fließtext-Vorschlag, dann Vorschau), jetzt eines.
  - Der Ablageort muss vor der Vorschau feststehen.
- **Muster M18:** neue Zeile „Neues Material zu einer Adresse anlegen (und einsortieren)“.
- **Master-Skill** (`docs/skills/vorgehen.md`, `-kompakt`, `-knapp`), Abschnitt „Fremde Seite mit
  Sammlungsbezug“: Dublette per `find_content_by_url`, dann `wlo_create_content` mit `addToCollectionId`.
  Ein vorhandener Datensatz wird mit `wlo_add_to_collection` einsortiert.
- `find_content_by_url` kommt nie aus dem Werkzeug-Cache: direkt nach dem Anlegen muss die Prüfung
  frisch sein. Adressen über 2000 Zeichen fallen einzeln weg, denn der Server lehnte sonst den ganzen
  Aufruf ab.
- Die erzeugten Seiten unter `docs/dimensionen/` sind neu erzeugt (`scripts/export_dimensions.py`).

## Beim Deploy

- **Der MCP muss auf dem Stand vom 07.11.2026 laufen**, bevor dieses Backend kommt. Ein älterer Server kennt
  `find_content_by_url` nicht und übergeht `addToCollectionId`: dann entstünde der Datensatz ohne
  Einsortieren.
- **Master-Skill neu einspielen** (Text im WLO-Knoten ersetzen), sonst steuert im Agent-Modus noch die
  alte Reihenfolge.
- **Seeds geändert:** `03-patterns/m18-kuration.md`, `03-patterns/m20-erschliessen.md` und
  `05-knowledge/mcp-servers.yaml`. Übernehmen mit `boerdi import-config --werksabgleich`. Eigene
  Fassungen im Studio bleiben; die Werksfassung zeigt den neuen Stand.

## Review

Unabhängiges Review: 2 MAJOR, 8 MINOR, 1 NIT. Bestätigt wurde: `addToCollectionId` kommt bis zum
bestätigten Aufruf an, und der Weg des Servers „vorhandenen Datensatz aufnehmen“ läuft mit der
Abnahme aus M2.

Behoben:
- Ein Wächter-Test für die Vertrauensgrenze war rot (MAJOR).
- Der Master-Skill war nicht angepasst (MAJOR).
- Kein Cache für die Dublettenprüfung.
- Die Bedeutung von `exact`/`normalized` fehlte in Beschreibung und Muster.
- Überlange Adressen kippten den ganzen Aufruf.
- M20 brauchte zwei „ja“.
- Der Fall „vorhanden, soll einsortiert werden“ fehlte, die M18-Zeile war ungenau.
- Die `docs/dimensionen` waren veraltet.
- Die Deploy-Reihenfolge fehlte.
- Tests fehlten.

Offen (älter): `services/page_duplicate.py` (Dublettenprüfung beim Seitengruß) nutzt noch die Suche mit
eigenem Adressvergleich. Eine Umstellung auf `find_content_by_url` ist sinnvoll, steht aber in einem
eigenen Schritt.

## Tests

- `tests/test_mcp_vertrag_m3.py` (neu, 5): `addToCollectionId` reist mit (und ohne Wert nicht),
  `find_content_by_url` mit Kappung auf 20, Register und Muster kennen das Werkzeug, M20 legt mit einer
  Bestätigung an. Die Tests liefen vor dem Code rot.
- `tests/test_mcp_tool_defs.py`: die festgehaltene Reihenfolge der Werkzeugliste ergänzt.
- Aus dem Review (+3): überlange Adressen, kein Cache, und das Einlösen trägt `addToCollectionId` bis
  zum Server. Dazu `tests/test_untrusted_text.py`: Vertrauensgrenze eingeordnet.
