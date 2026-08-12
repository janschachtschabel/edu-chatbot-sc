"""Safety stage 1 — the always-on, deterministic regex backstop.

Byte-parity port of ALT ``safety_service`` (regex asset lists + ``_regex_gate``).
This stage runs BEFORE pattern selection and without any LLM, so it is the
safety-critical hard floor: even if every LLM stage fails, the regex gate still
blocks crisis/threat/PII. The ALT lines are verbatim security assets — do not
reflow them (the escalation tests pin exact matches).

**C1-f2c added English counterparts — as a union, never as a switch.** Unlike
the watchdogs over our own output (``i18n/output_patterns``), this gate does not
know the language of what it reads and must not: a user with ``locale=de-DE``
can still type English, and a crisis must not depend on a language setting. The
new entries are therefore appended to the existing lists, so every language is
always armed and the German lines stay byte-identical. Two measured
consequences are pinned in ``tests/test_safety_regex_gate.py``: the English
mirror deliberately stops where the German one does (``hurt you`` is no threat
in either), and German compounding shields the teaching case
(„Suizidprävention") in a way English cannot.

The second line of defence is not equivalent everywhere: ``moderation`` is
multilingual, but ``moderation._moderation_target()`` returns ``None`` without
an OpenAI key — on ``b-api-academiccloud`` that leaves this gate as the only
floor.

``regex_gate`` is stage 1; ``INJECTION_PATTERNS`` / ``LEGAL_TRIGGER_PATTERNS`` are
public because the orchestrator (``service``) consumes them in later stages.
"""

from __future__ import annotations

import re

from boerdi.api.schemas import SafetyDecision

# ── Stage 1: Regex patterns ─────────────────────────────────────────
# Crisis = Nutzer richtet Gewalt/Suizid gegen SICH SELBST.  Ein reines
# "ich" weiter vorn im Satz reicht NICHT — "ich werde dich umbringen"
# wäre sonst eine Crisis statt einer Drohung gegen Dritte.  Darum muss
# das self-referentielle Pronomen (mich/mir/selbst) DIREKT am Gewaltverb
# hängen (max. 10 Zeichen Abstand).
_CRISIS_PATTERNS = [
    # Suizid-Keywords sind klar self-referential
    r"\b(suizid|suicid|selbstmord|selbstt[öo]tung)\b",
    # Selbstverletzung
    r"\b(selbstverletz|ritz mich|ritze mich|ritzen seit|tu mir weh)\b",
    # "umbringen / töten" mit engem Selbstbezug. 0-10 Zeichen Abstand —
    # "ich will mich umbringen" ✓, "ich werde dich finden und umbringen" ✗.
    # WICHTIG: `umbring\w*` statt `\bumbring\b` — sonst matcht "umbringen"
    # nicht, weil \b mitten im Wort steht.
    r"\b(mich|mir)\b[^.?!]{0,10}\bumbring\w*\b",
    r"\b(mich|mir)\b[^.?!]{0,10}\bt[öo]te\w*\b",
    r"\bumbring\w*\b[^.?!]{0,10}\b(mich|mir)\b",
    r"\bt[öo]te\w*\b[^.?!]{0,10}\b(mich|mir)\b",
    r"\bmich\s+selbst\b[^.?!]{0,10}\b(umbring\w*|t[öo]te\w*)\b",
    # "nicht mehr leben wollen" — klar Suizid
    r"\bnicht mehr leben\b",
    # Tabletten-/Überdosis-Euphemismen (fängt "wie viele tabletten muss
    # ich nehmen damit es reicht", "genug tabletten für immer", "überdosis")
    r"\b(tabletten|pillen)\b[^.?!]{0,40}\b(reich(en|t)|genug|f[üu]r immer|damit (es|ich))\b",
    r"\b(überdosis|ueberdosis|overdose)\b",
    # ── C1-f2c: englische Entsprechungen ────────────────────────────
    # Additiv und IMMER scharf, NICHT sprachabhängig — anders als die
    # Wächter über unserer eigenen Ausgabe (C1-f2b4). Das Gate kennt die
    # Sprache der Eingabe nicht und darf sie nicht kennen: wer
    # ``locale=de-DE`` gesetzt hat, kann trotzdem englisch tippen, und
    # eine Krise darf nicht an der Spracheinstellung scheitern.
    #
    # ``suicid\w*`` statt des bestehenden ``suicid``: dort steht es in
    # einer ``\b…\b``-Gruppe und konnte „suicide"/„suicidal" deshalb NIE
    # treffen — es sah abgedeckt aus und war es nicht.
    r"\b(suicid\w*|self[-\s]?harm\w*|selfharm\w*)\b",
    # „kill/hurt myself", beide Reihenfolgen — Spiegel der mich/mir-Zeilen.
    r"\b(kill|hurt|harm|cut|injure)\w*\b[^.?!]{0,10}\bmyself\b",
    r"\bmyself\b[^.?!]{0,10}\b(kill|hurt|harm|cut|injure)\w*\b",
    r"\bend\s+my\s+(own\s+)?life\b",
    r"\bend\s+it\s+all\b",
    # Spiegel von „nicht mehr leben wollen".
    r"\b(don'?t|do not|no longer)\s+want\s+to\s+live\b",
    r"\bwant\s+to\s+(die|stop\s+living)\b",
    # Spiegel der Tabletten-/Überdosis-Zeile.
    r"\b(pills|tablets)\b[^.?!]{0,40}\b(enough|forever|to\s+(make|end|stop))\b",
]

# Threat = Nutzer droht Gewalt/Tötung gegen Dritte.  Eigener enforced
# Pattern (M02) und HIGH-Risk, aber KEINE Suizid-Empathie.
# Vorsicht: `\bumbring\b` matcht NICHT in "umbringen"! Deshalb `umbring\w*`.
_THREAT_PATTERNS = [
    # "Ich werde dich/euch/ihn/sie umbringen/töten …"
    r"\b(werde|will|gonna)\b[^.?!]{0,30}\b(dich|euch|ihn|sie|ihr|you|him|her|them)\b[^.?!]{0,40}\b(umbring\w*|t[öo]te\w*|abstech\w*|erschieß\w*|erschiess\w*|kill\w*|murder\w*)\b",
    # "… umbringen, dich", umgekehrte Reihenfolge
    r"\b(umbring\w*|t[öo]te\w*|abstech\w*|erschieß\w*|erschiess\w*|kill\w*|murder\w*)\b[^.?!]{0,40}\b(dich|euch|ihn|sie|ihr|you|him|her|them)\b",
    # "Ich finde dich und …"
    r"\bich\s+finde\s+dich\b[^.?!]{0,40}\b(umbring\w*|t[öo]te\w*|fertig)\b",
    # C1-f2c: die zwei Zeilen oben führen bereits ``you|him|her|them`` und
    # ``kill|murder`` — es fehlten nur die übrigen englischen Gewaltverben.
    # Als eigene Einträge, damit die ALT-Zeilen unverändert bleiben.
    #
    # **Bewusst NICHT dabei: ``hurt``.** Auf Deutsch ist „ich werde dich
    # verletzen" gemessen KEINE Drohung (``low``) — nur die harten Verben
    # sind es. Der Spiegel zieht dieselbe Grenze; sonst kippte jede
    # Unterrichtsfrage („how does bullying hurt you?") in eine Abfuhr.
    r"\b(will|gonna|going\s+to)\b[^.?!]{0,30}\b(you|him|her|them)\b[^.?!]{0,40}\b(stab|shoot|strangle|behead)\w*\b",
    r"\b(stab|shoot|strangle|behead)\w*\b[^.?!]{0,40}\b(you|him|her|them)\b",
]

_PII_PATTERNS = [
    r"\b(passwort|password|kreditkart|sozialvers|geburtsdatum)\b.*\b(meine?|ist|lautet)\b",
    # C1-f2c: dieselbe Zeile mit englischen Kopula/Possessiv. ``password``
    # stand schon in der deutschen Zeile — nur „is" statt „ist" fehlte.
    r"\b(password|credit\s*card|social\s*security|date\s+of\s+birth)\b.*\b(my|is|are)\b",
]
# Heuristik-Trigger: wenn eines dieser Wörter auftaucht, soll der Legal-Classifier
# auch im "smart"-Mode laufen, selbst wenn das Risiko sonst noch low wäre.
LEGAL_TRIGGER_PATTERNS = [
    r"\b(hasse|hass|hassen|scheiß|verflucht|verfluche|drohe|drohung|drohst)\b",
    r"\b(umbring|umbringen|töten|toeten|abstech|erschieß|vergewaltig)\b",
    r"\b(schlag dich|schlage dich|hau dich|hau ihn|fertig mach)\b",
    r"\b(idiot|arschloch|hurensohn|wichser|missgeburt)\b",
    r"\b(nazi|jude|kanake|neger)\b",
    r"\b(hate|kill you|hurt you|threat|murder)\b",
]

# All patterns are matched against `message.lower()`, so the patterns
# themselves must be lowercase. Don't put uppercase tokens here.
INJECTION_PATTERNS = [
    # DE: allow 1-3 intermediate words between "ignoriere" and the noun so
    # phrases like "ignoriere alle vorherigen anweisungen" match.
    r"ignorier[et]?\s+(?:\w+\s+){1,3}(anweisungen|regeln|instruktionen|prompts?)",
    # EN: same — "ignore all previous instructions", "ignore your prior rules".
    r"ignore\s+(?:\w+\s+){1,3}(instructions|rules|prompts?)",
    r"system\s*prompt",
    # Persona-override — handles both "verhalte dich als/wie …" and
    # free-form "du bist jetzt <rolle/modus>". The old pattern required
    # "(as|wie|ein)" after "du bist jetzt …" which missed "du bist jetzt
    # dan mode" (no connector word).
    r"\b(verhalte dich|act as|you are now)\s+(as|wie|ein)\s+",
    r"\bdu bist jetzt\s+\w+",
    r"(reveal|zeig(e)?|gib aus)\s+(your|den|deinen)\s+(prompt|system|instructions)",
    # Known jailbreak modes — keep lowercase!
    r"\b(jailbreak|dan\s*mode|developer\s*mode|do\s*anything\s*now)\b",
    r"\bantworte\s+ohne\s+filter\b",
    r"<\|.*?\|>",
    r"```\s*system",
]


def regex_gate(message: str, signals: list[str]) -> SafetyDecision:
    """Stage 1: fast regex assessment.

    Three mutually exclusive hard-block paths:
      * Crisis — user endangers themselves → M01 (empathic)
      * Threat — user threatens others   → M02 (firm refusal)
      * PII   — user volunteers sensitive data → soft medium block

    Crisis takes priority over Threat when both would match (conservative
    side of the fence — never respond with hostility if there's any
    self-harm signal).
    """
    msg = (message or "").lower()
    decision = SafetyDecision()
    decision.stages_run.append("regex")

    for pat in _CRISIS_PATTERNS:
        if re.search(pat, msg):
            decision.risk_level = "high"
            decision.enforced_pattern = "M01"
            decision.blocked_tools = [
                "search_wlo_collections", "search_wlo_content",
                "get_collection_contents",
            ]
            decision.reasons.append("crisis_signal_detected")
            decision.legal_flags.append("jugendschutz")
            return decision

    for pat in _THREAT_PATTERNS:
        if re.search(pat, msg):
            decision.risk_level = "high"
            decision.enforced_pattern = "M02"
            decision.blocked_tools = [
                "search_wlo_collections", "search_wlo_content",
                "get_collection_contents",
            ]
            decision.reasons.append("threat_signal_detected")
            decision.legal_flags.append("strafrecht")
            return decision

    for pat in _PII_PATTERNS:
        if re.search(pat, msg):
            decision.risk_level = "medium"
            decision.blocked_tools.append("search_wlo_content")
            decision.reasons.append("pii_in_message")
            decision.legal_flags.append("datenschutz")
            break

    if "bedroht" in signals or "in_gefahr" in signals:
        decision.risk_level = "high"
        decision.reasons.append("danger_signal")

    return decision
