# Antwort an den MCP-Entwickler: zweite Runde (2026-11-15)

Zu deiner Antwort „Sammlungsstrukturen, zweite Runde“ vom 14.11. und deiner Rückinfo vom 15.11.
(S11 bis S13 sind in Arbeit: danke).

## Kurzfassung

Wir haben jede Aussage an deinem Quelltext geprüft, deinen Stand lokal gestartet (anonym, nur
lesend, gegen Staging) und den Chatbot angepasst, wo er mit dem neuen Stand falsch reagiert
hätte. Die Reihenfolge beim Deploy ist egal.

- **Nachgemessen:** Fachportal über `collection` („Physik“ löst sich auf), `scanCapped`,
  `totalIsLowerBound`, `contentsCut`, `skipLimitReached`, `truncated` mit `collectionTotal`, die
  Hinweiszeile vor dem Fremdtext.
- **Eine Beobachtung an Staging**, die du vor dem Deploy ansehen solltest (unten).
- **Zwei Stellen in deinem Stand**, an denen der Code nicht zu dem passt, was geschehen ist,
  und vier kleinere Wünsche (unten).

## Was wir angepasst haben

| Bei dir | Bei uns |
|---|---|
| Ablehnung des Repositorys als `forbidden` / `not_found` / `refused` mit `outcomeOpen: false` | Die Person liest „abgelehnt“ mit einem Grund. Vorher hätten wir neu vorgelegt und „die Freigabe war nicht mehr gültig“ geschrieben, bei jedem Ja wieder |
| `not_stored` mit `outcomeOpen: false` | Ablehnung mit dem Satz „angenommen, aber nichts gespeichert, meist fehlt das Recht“. Vorher haben wir neu vorgelegt |
| `not_in_collection`, `forbidden` in der Vorschau | eigene Sätze, deutsch und englisch |
| `wlo_create_collection` mit `recordExists` | eigener Satz für eine Sammlung |
| `text_unreadable` | eigener Satz („gleich noch einmal“), kurzer Cache |
| `siblingsUnread` | kurzer Cache |
| `internal_error` | bei den Themenseiten ein Ausfall; keine Wiederholung. Bei einem Plan-Werkzeug nach dem Ja „Ausgang offen“ |
| Grenz-Sätze („Hinweis: …“) hinter dem JSON-Umschlag | reisen jetzt durch unsere Kürzung zur KI |
| Fachportal über `collection` | unsere Beschreibung schickt die KI nicht mehr zur Kennung |
| `not_checked` am Manifest | „später noch einmal“ statt „abgewiesen“ |

## Wann wir neu vorlegen

Von selbst holen wir eine neue Vorschau nur noch, wenn der Schlüssel nicht (mehr) gilt:
`confirm_expired`, `confirm_mismatch` vor der Einlösung, `changed_since_preview`.

Alles andere, was du mit `outcomeOpen: false` beantwortest, zeigen wir als Ablehnung mit einem
Grund; die Person bittet dann selbst noch einmal. Das gilt auch für `not_checked`, `unreadable`
und `upstream_error`. Wir hatten für diese drei zuerst „neu vorlegen“ gebaut und sind in zwei
Schleifen gelaufen (siehe die nächsten zwei Punkte).

Mit `outcomeOpen: true` heißt es bei uns „bitte nachsehen“; bei einem Plan-Werkzeug bieten wir
„Plan fortsetzen“ an.

## Zwei Stellen, an denen der Code nicht passt

1. **Volltext: ein abgelehnter Upload heißt `upstream_error`.** `wlo_attach_fulltext` bildet
   den Code nach dem POST mit `failureCode` (`services/write/fulltext.ts`). Ein 400, 409, 413
   oder 422 wird so `upstream_error` mit `outcomeOpen: false`. Die Einzelwerkzeuge für
   Sammlungen nehmen dafür `refusalCode` (`forbidden`, `not_found`, `refused`). Bitte auch hier.
   Bis dahin lesen wir bei `upstream_error` den Status aus dem Text: 4xx außer 429 ist für uns
   „so nicht angenommen“, alles andere „ließ sich gerade nicht prüfen“.
2. **Herausnehmen: `not_checked` ist nicht immer vorübergehend.** Die Vorschau von
   `wlo_remove_from_collection` lässt eine Sammlung durch, in der sich das Material nicht finden
   ließ (`tools/curation-collections.ts`); nach dem Ja kommt `not_checked`
   (`services/write/collections.ts`). Das trifft den Ausfall, aber auch eine Sammlung mit mehr
   Einträgen, als `findReference` durchsucht. Im zweiten Fall hilft „noch einmal“ nie. Bitte
   die Suchgrenze schon in der Vorschau ablehnen oder mit eigenem Code melden. (Deine Liste
   nennt `not_checked` bei der Vorschau; im Quelltext entsteht es erst nach dem Ja.)

## Woran wir jetzt zusätzlich hängen

- Bei den lesenden Werkzeugen mit JSON-Antwort (Suchen, Sammlungsinhalt, Themenseite,
  Baumliste) reichen wir der KI jede Zeile als deinen Satz weiter, die hinter dem JSON-Umschlag
  **am Zeilenanfang** mit „Hinweis: “ beginnt, auch kursiv (`_Hinweis: …_`). Höchstens fünf je
  Antwort, Ausfall-Sätze eingeschlossen. Die Mehrfachsuche ist ausgenommen.
- Eingerückte Zeilen zählen wir nicht. Dein Skill-Katalog an einer Sammlung schreibt
  `"  " + Titel + ": " + Beschreibung`; ein Skill namens „Hinweis“ sähe sonst wie dein Satz
  aus. Bitte halte fremde Titel hinter dem Umschlag eingerückt oder in Anführungszeichen.
- `reason: "text_unreadable"` an `get_wlo_content_text` und `siblingsUnread: true` an
  `get_related_content` lesen wir als Ausfall (kurzer Cache).
- Den Text einer Ablehnung zeigen wir der Person nicht, wenn er „HTTP nnn“ oder „failed: nnn“
  enthält (siehe Wunsch 1).

## Beobachtung an Staging

Jede Inhaltssuche meldet an deinem Stand gegen Staging derzeit `incomplete: true` mit „Die
Inhaltssuche hat nicht (vollständig) geantwortet“, auch bei gewöhnlichen Anfragen
(`search_wlo_content` „Optik“, mit und ohne Lizenzfilter; `search_wlo_all`). Vermutlich schlägt
dort eine der Varianten der Rangsuche immer fehl. Mit deinem Stand hieße das für uns: Jede Suche
bleibt nur Sekunden im Cache, und die KI liest jedes Mal, die Liste könne Treffer auslassen.
Bitte vor dem Deploy ansehen.

## Vier kleinere Wünsche

1. **Ein Feld statt eines Satzes für „das Repository hat abgelehnt“.** `forbidden`, `not_found`
   und `refused` tragen in `error.message` jetzt die Antwort des Repositorys („HTTP 400: …“ mit
   bis zu 200 Zeichen seines Fehlertexts), andere Meldungen den Namen eines internen Abrufs
   („getCollectionContents failed: 503 Service Unavailable“). Wir unterscheiden deine eigenen
   Sätze davon heute am Wortlaut. Ein Feld wie `error.upstreamStatus` wäre verlässlicher.
2. **Alle Hinweise gleich beginnen lassen.** Diese Zeilen beginnen nicht mit „Hinweis: “ und
   gehen in unserem gekürzten Weg verloren: die drei „ⓘ“-Zeilen zur Lizenz
   (`filter-criteria.ts`), „Nur N neue Treffer …, der Katalog hält mehr“ und „Volltext nicht
   abrufbar (Abruf fehlgeschlagen …)“ (`services/content-search.ts`), „Der Titel stimmt nur in
   abweichender Schreibweise überein“ (`tools/collection-arg.ts`). Kein Muss.
3. **403 beim Anlegen eines Inhalts als `forbidden`.** Bei `wlo_create_content` heißt ein 403
   des Repositorys `refused`; die Person liest bei uns dann „so nicht angenommen“ statt „fehlt
   das Recht“.
4. **Plan-Werkzeuge: `outcomeOpen` nach einem Unfall.** Ein `internal_error` oder
   `upstream_error` nach der Einlösung eines Plans trägt kein `outcomeOpen`, weil dort kein
   `keySpent` greift. Wir behandeln beides als offen. Ein ausdrückliches `outcomeOpen: true`
   wäre sauberer.

Zur Klarheit, kein Wunsch: Dein Satz „nach der Einlösung fehlt `retryAfter`“ gilt für den
`confirmToken`. Bei den Werkzeugen mit `batchToken` bleibt es stehen. Uns stört das nicht.

## Bewusst nicht angepasst

- `outcomeOpen` je Eintrag eines Plans lesen wir im Ablauf nicht; wir werten `failed` und
  `not_stored` als „sicher nicht geschehen“.
- `error.upload` lesen wir nicht; der Code genügt uns für den Satz.
- Deine eigenen Sätze zu `refused` zeigen wir der Person auf Deutsch wörtlich. Einige nennen
  Werkzeuge und Parameter („liefert wlo_list_suggestions“, „replace: true angeben“). Das bleibt
  vorerst so.
- Ob die KI die Hinweiszeile vor dem Fremdtext in einen Volltext oder ein Material übernimmt,
  prüfen wir im Chat, sobald dein Stand auf Staging läuft.

## Offen bei dir

- Der Deploy-Termin für Staging.
- S11 bis S13. Sobald dein Stand dazu fertig ist, messen wir lokal und bauen bei uns: den
  Themenbaum mit `order: "position"` und im Abgleich den Ort eines Ausfalls.
