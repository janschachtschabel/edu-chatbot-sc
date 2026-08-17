"""Der Musterkatalog als Werkzeug-Beschreibung (Hybrid-Modus, H2).

Die Muster-Engine lässt den **Klassifikator** ein Muster wählen und schickt
dessen Body als Prompt-Schicht mit. Der Hybrid dreht das um: der Katalog wird zur
Beschreibung eines Werkzeugs, das Modell zieht ein Muster, wenn es die Trefferlage
kennt — und kann mitten im Zug wechseln.

**Vier Muster stehen nicht zur Wahl, und das ist keine Sparsamkeit:**

* ``M01``/``M02`` werden vom Sicherheits-Gate *erzwungen*
  (``safety/service.py`` → ``SafetyDecision.enforced_pattern``). Stünden sie im
  Katalog, wäre die Krisen-Behandlung ein Angebot statt einer Zusage — ein Modell
  könnte sie abwählen.
* ``M03`` ist keine Antwortform, sondern Klärungs-Mechanik mit Versuchszähler und
  Zwangsumleitung (``domain/turn_frame.py``). Ohne Klassifikator gibt es im Hybrid
  ohnehin keine Pflichtslots, die es klären könnte.
* ``M15`` ist der Rückfall-Anker. Sein Gegenstück im Hybrid ist „das Modell ruft
  gar kein Muster" — dafür braucht es keinen Eintrag.

Die Sperre greift **zweimal**: die Kennungen fehlen im ``enum`` des Werkzeugs
*und* ``finde_muster`` weist sie zurück. Der zweite Riegel ist kein Zierrat —
Werkzeug-Argumente sind Modell-Ausgabe und damit unvertraute Eingabe; eine frei
erfundene Kennung darf nicht deshalb greifen, weil sie nicht angeboten wurde.

**Warum hier gerendert wird und nicht in ``classify_prompt_blocks``.** Dort steht
mit ``_render_patterns_hint_block`` fast derselbe Text — aber jenes Modul ist ein
1:1-Port und trägt die Zusage „byte-identisch zu ALT für dieselbe Config". Die
beiden Texte haben verschiedene Auftraggeber: der Klassifikator-Block ist
eingefroren, diese Beschreibung wird sich mit der Werkzeugwahl weiterentwickeln.
Ein gemeinsamer Renderer koppelte ein eingefrorenes an ein bewegliches Artefakt —
die nächste Verbesserung hier bräche dort die Parität. Was bewusst geteilt wird,
ist die *Konvention*: derselbe Aufbau und derselbe Fünfer-Deckel, damit die
Redaktion in beiden Texten dieselbe Pflege wiedererkennt.
"""

from __future__ import annotations

from typing import Final

from boerdi.domain.pattern_engine import PatternDef

#: Muster, die das Modell niemals selbst wählen darf (Begründung im Modulkopf).
NICHT_WAEHLBAR: Final = frozenset({"M01", "M02", "M03", "M15"})

#: Derselbe Deckel wie im Klassifikator-Block (``classify_prompt_blocks``): eine
#: versehentlich groß editierte Config darf die Werkzeugbeschreibung nicht sprengen.
_MAX_JE_LISTE: Final = 5

#: Länge, ab der eine als Zweck missbrauchte ``core_rule`` gekürzt wird.
_MAX_ZWECK_ZEICHEN: Final = 100


def waehlbare_muster(muster: list[PatternDef]) -> list[PatternDef]:
    """Die Muster, die dem Modell angeboten werden — in Bestandsreihenfolge."""
    return [m for m in muster if m.id not in NICHT_WAEHLBAR]


def finde_muster(muster_id: object, muster: list[PatternDef]) -> PatternDef | None:
    """Kennung → Muster, oder ``None``.

    Der zweite Riegel der Sperre: ``muster_id`` stammt aus einem Werkzeug-Aufruf
    und ist damit Modell-Ausgabe. Weder ein gesperrtes noch ein erfundenes Muster
    darf hier durchkommen, und ein Nicht-String erst recht nicht.
    """
    if not isinstance(muster_id, str):
        return None
    gesucht = muster_id.strip()
    if not gesucht or gesucht in NICHT_WAEHLBAR:
        return None
    for m in waehlbare_muster(muster):
        if m.id == gesucht:
            return m
    return None


def _zweck(m: PatternDef) -> str:
    """``short_purpose``, ersatzweise die gekürzte ``core_rule``.

    Dieselbe Rückfallregel wie im Klassifikator-Block: ein Muster ohne gepflegten
    Zweck soll nicht namenlos im Katalog stehen.
    """
    zweck = (m.short_purpose or "").strip().replace("\n", " ")
    if zweck:
        return zweck
    zweck = (m.core_rule or "").strip().replace("\n", " ")
    if len(zweck) > _MAX_ZWECK_ZEICHEN:
        zweck = zweck[: _MAX_ZWECK_ZEICHEN - 3] + "…"
    return zweck


def _eintrag(m: PatternDef) -> list[str]:
    """Ein Muster als Katalogeintrag."""
    zeilen = [f"### {m.id} — {m.label}"]
    if zweck := _zweck(m):
        zeilen.append(f"_Zweck:_ {zweck}")

    if m.when_to_use:
        zeilen.append("**Einsetzen wenn:**")
        zeilen.extend(f"  - {it}" for it in m.when_to_use[:_MAX_JE_LISTE])

    if m.when_not_to_use:
        zeilen.append("**NICHT einsetzen wenn:**")
        zeilen.extend(f"  - {it}" for it in m.when_not_to_use[:_MAX_JE_LISTE])

    if m.trigger_phrases:
        phrasen = " · ".join(f"„{t}\"" for t in m.trigger_phrases[:_MAX_JE_LISTE])
        zeilen.append(f"**Typische Formulierungen:** {phrasen}")

    if m.discriminators:
        zeilen.append("**Abgrenzung:**")
        for d in m.discriminators[:_MAX_JE_LISTE]:
            zeile = f"  - vs **{d.get('vs', '')}**: {d.get('rule', '')}"
            if beispiel := d.get("example", ""):
                zeile += f" _Beispiel:_ {beispiel}"
            zeilen.append(zeile)

    return zeilen


def katalog_text(muster: list[PatternDef]) -> str:
    """Der Katalog der wählbaren Muster als Fließtext.

    Leerer Bestand → leerer String, damit der Aufrufer das Werkzeug weglassen
    kann, statt eine Beschreibung ohne Inhalt anzubieten.
    """
    bloecke = ["\n".join(_eintrag(m)) for m in waehlbare_muster(muster)]
    return "\n\n".join(bloecke)


def katalog_kurz(muster: list[PatternDef]) -> str:
    """Eine Zeile je Muster — die Fassung für einen Lauf, der schon wählte (H8-2).

    Gemessen am Bestand: der volle Katalog ist **25 251 von 31 742 Zeichen** des
    Werkzeugsatzes, nachdem ein Muster gewählt wurde — und er geht in jeder
    weiteren Runde mit, obwohl die Frage „welches Vorgehen passt zu dieser
    Anfrage" längst beantwortet ist. Die offene Frage lautet dann nur noch
    „muss ich wechseln", und dafür genügen Kennung, Etikett und Zweck.

    Was ausdrücklich wegfällt: ``when_to_use``/``when_not_to_use``,
    ``trigger_phrases``, ``discriminators``. Sie ordnen eine *Nutzer-Äußerung*
    einem Muster zu — die Information, die einem Lauf mitten in der Arbeit
    ohnehin nicht fehlt: er kennt die Lage aus seinen eigenen
    Werkzeug-Ergebnissen und nicht mehr aus Formulierungs-Beispielen.

    Die Sperrliste gilt hier genauso; beide Fassungen gehen durch
    ``waehlbare_muster``.
    """
    zeilen = []
    for m in waehlbare_muster(muster):
        zeile = f"- {m.id} — {m.label}"
        if zweck := _zweck(m):
            zeile += f": {zweck}"
        zeilen.append(zeile)
    return "\n".join(zeilen)
