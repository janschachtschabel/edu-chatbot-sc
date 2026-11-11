# Paket TW-3: Abläufe zuerst, genauere Wendung, Startknopf (2026-11-11)

Plan `plans/2026-11-11-themenbaum-ausloesen-und-wissen.md`, Entscheide E2, E4 und E5. Nach
Vorgabe N16 des Nutzers werden Abläufe grundsätzlich zuerst angeboten.

## Umsetzung

- **Vorrang in der Beschreibung** (`ablauf/vorschlag.py`): Jedes Ablauf-Werkzeug sagt jetzt
  „Passt er zur Bitte, geht er vor einzelnen Modulen oder Werkzeugen vor (er fragt nach, was das
  Ergebnis braucht); ohne ihn nur, wenn die Person das will“. Das gilt beim Vorschlagen und beim
  direkten Start.
- **Reihenfolge im Angebot** (`agent_tools.build_agent_tools`): Die Ablauf-Werkzeuge stehen gleich
  hinter den MCP-Werkzeugen und vor Wissen, Dokument und Modulen.
- **Wendungen** (`ausloeser.per_text`): Der längste passende Treffer gewinnt, bei gleicher Länge
  die Reihenfolge der Kennungen. Damit startet „Themenbaum aus meinen Dateien“ den genaueren
  Ablauf, auch wenn ein allgemeinerer „themenbaum zu“ kennt.
- **Startknopf am KI-Schritt:**
  - Neues Feld `agent.startknopf`, je Sprache, höchstens 60 Zeichen, Vorgabe `None`. Im Studio
    heißt es „Startknopf“ (de/en).
  - Der Zug, der in den Schritt führt, zeigt ihn als erste Schnellantwort, vor „Weiter im
    Ablauf“. Sein Text geht als gewöhnliche Nachricht der Person an die KI, die dann loslegt. Damit
    entfällt das Tippen, das der KI-Schritt bisher verlangte (A2b).
  - **Nie eine Direktaktion:** `|` wird `/`, und ein Label mit `__` am Anfang zählt nicht.

## Prüfung

- `test_tw3_ablaeufe_zuerst.py`: 7 Fälle, zuerst rot.
  - längste Wendung, gleich lang, Vorrang in der Beschreibung;
  - Reihenfolge im Angebot;
  - Startknopf: Sprache, Direktaktion und der echte Zug über `zug.starten`.
- ruff sauber.

## Review (unabhängig) und Behebung

2 MAJOR, 5 MINOR, 5 NIT, dazu ein Vorbefund.

- **MAJOR 1:** Der längere Schlusssatz schnitt `wann` mitten im Wort ab („ohne ei“).
  - Der Vorrang-Satz ist kürzer.
  - Ohne `nicht_wann` bekommt `wann` den ganzen Rest.
  - Gekürzt wird an der Wortgrenze mit „…“.
  - Test mit einem `wann` in Seed-Länge.
- **MAJOR 2:** Der Master-Skill schickte neue Gliederungen ausdrücklich an `ui_strukturentwurf`.
  - In `docs/skills/vorgehen-knapp.md` geht jetzt ein passender Ablauf vor, auch vor
    `ui_strukturentwurf`. Ohne Ablauf geht es nur, wenn keiner passt oder die Person das will.
  - Die Zuordnung „→ `ui_strukturentwurf`“ steht weiter wörtlich da, mit „wenn kein passender
    Ablauf angeboten ist“, so verlangt es der Wächter.
  - **Der Master-Skill-Knoten in WLO muss nachgezogen werden.** Der Chatbot lädt ihn von dort.
    Der Chat-Smoke zeigte, dass die KI mit dem alten Knoten eine freie Bitte noch direkt entwirft.
- **MINOR 3:** Die Warnung zu Wendungen sagt, was gilt: die längere Wendung, bei gleicher Länge
  die kleinste Kennung. Der Docstring von `ausloeser` ist nachgezogen.
- **MINOR 4:** Kommt „Weiter“ zu früh (der Teil fehlt noch) und hat die KI noch nichts getan,
  steht der Startknopf wieder da (`ki_schritt.zuege_bisher`). Der Studio-Hinweis nennt beide
  Fälle.
- **MINOR 5:** „Weiter im Ablauf“ übersteht jeden Deckel, über den eigenen Prüfer
  `ist_weiter_knopf`. `ist_wahl_knopf` bleibt, wie er ist: er zählt „Weiter“ bewusst nicht.
- **MINOR 6:** Im Muster-Weg stehen die Abläufe jetzt ebenfalls vor den UI-Modulen.
- **MINOR 7:** Ein Startknopf mit `|` oder `__` am Anfang ist ein Prüfbefund
  (`startknopf_zeichen`).
- **NITs:**
  - Tests für leere Wendungen, „a|b“ wird „a/b“, „Weiter“ unter dem Deckel und zu frühes
    „Weiter“;
  - Konstante `STARTKNOPF_ZEICHEN`;
  - Doku in `ablaeufe.md`.
- **Nicht geändert:**
  - Ein Startknopf-Label gleich `tour_reply` startet die Web-Tour. Das ist sehr unwahrscheinlich.
  - Der Cache der Werkzeugliste: Die Abläufe stehen jetzt früher, das ist hier vermerkt.
- **Vorbefund:** Die Stubs von `_loop` in `test_respond_agent` und `test_agent_prompt_preview`
  kannten `modul_vorgaben` nicht (TW-2). Sie sind nachgezogen.

## Grenzen

- Der Startknopf steht im Zug, der in den Schritt führt, und nach einem zu frühen „Weiter“. Nach einem Neuladen zeigt die
  Ablauf-Leiste den Lauf, nicht den Startknopf. Tippen geht weiter.
- Ob die KI den Vorrang befolgt, prüft der Chat-Smoke nach TW-4.
