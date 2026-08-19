# Personas

<!-- ERZEUGT von backend/scripts/export_dimensions.py aus backend/seeds/ — nicht von Hand ändern; Änderungen gehören in den Seed bzw. ins Studio. -->

## P-AND — Andere / Unbekannt

### Kopfdaten

- **element**: persona
- **id**: P-AND
- **label**: Andere / Unbekannt
- **description**: Default-Persona ohne klare Marker — offen, neutral, weder duzen noch siezen.
- **tone**: locker
- **length_bias**: 0.0
- **formality**: neutral
- **card_text_mode**: minimal
- **override**: False

### Marker und Listen

- **anti_markers**:
  - **phrase**: mein Kind|mein Sohn|meine Tochter
  - **redirect_to**: P-ELT
  - **rationale**: Eltern-Pronomen

  - **phrase**: meine Klasse|Stundenentwurf
  - **redirect_to**: P-LEH
  - **rationale**: Lehrkraft-Sprache

  - **phrase**: verstehe nicht|für meine Klausur
  - **redirect_to**: P-LER
  - **rationale**: Lerner-Defizit-Indikator

  - **phrase**: ich kuratiere|Artikel|Pressemitteilung
  - **redirect_to**: P-RED
  - **rationale**: Redaktions-/Presse-Bezug

  - **phrase**: Wahlkreis|Schulamt|KPI|Schulberatung
  - **redirect_to**: P-ENT
  - **rationale**: Verwaltungs-/Politik-Sprache

  - **phrase**: ich bin (Lehrer:in|Schüler:in|Mutter|Vater|Redakteur:in|Politikerin)
  - **rationale**: Jede explizite Selbst-ID bricht P-AND

- **discriminators**:
  - **vs**: P-LEH
  - **rule**: P-LEH ist KEIN Default — ohne eindeutige Lehrkraft-Signale lieber P-AND

  - **vs**: P-ENT
  - **rule**: "Bildungspolitik" als Topic allein → P-AND, nicht P-ENT

- **goals**:
  - Vage Anfrage strukturieren
  - Plausible Persona herausfinden
  - Bei Unsicherheit offen-neutral bleiben
- **rules**:
  - Bei vager Anfrage: 3 Optionen + sanfte Persona-Frage
  - Bei expliziter Selbst-ID ("Ich bin Lehrerin"): turn_type = "correction" setzen, dann umklassifizieren
- **typical_intents**:
  - I01
  - I02
  - I03

### Anweisung

# P-AND — Andere / Unbekannt

Default-Persona ohne klare Marker. Offen, neutral (weder duzen noch
siezen bis Klärung).

Sobald ein eindeutiger Marker einer anderen Persona fällt, ist es
NICHT mehr P-AND. Bei expliziter Selbst-ID umklassifizieren mit
`turn_type = "correction"`.

## P-ELT — Eltern

### Kopfdaten

- **element**: persona
- **id**: P-ELT
- **label**: Eltern
- **description**: Eltern eines schulpflichtigen Kindes — warmer Ton, einfache Sprache.
- **tone**: warm
- **length_bias**: 0.2
- **formality**: wie_user
- **card_text_mode**: explanation
- **override**: False

### Marker und Listen

- **positive_markers**:
  - mein Kind
  - mein Sohn
  - meine Tochter
  - meine Kinder
  - für meinen [Alter]-Jährigen
  - Nachhilfe
  - Nachhilfe für mein Kind
  - Hausaufgaben meines Kindes
  - für zu Hause
  - ich bin Mutter
  - ich bin Vater
- **anti_markers**:
  - **phrase**: meine Klasse
  - **redirect_to**: P-LEH
  - **rationale**: Lehrkraft-Sprache (Besitz einer ganzen Klasse)

  - **phrase**: Statistiken
  - **rationale**: Allein kein Eltern-Signal — Statistik-Frage ist Intent, keine Persona

- **discriminators**:
  - **vs**: P-LEH
  - **rule**: mein Kind (P-ELT) vs meine Klasse (P-LEH)
  - **example_a**: Arbeitsblatt für mein Kind → P-ELT
  - **example_b**: Arbeitsblatt für meine Klasse → P-LEH

  - **vs**: P-LER
  - **rule**: mein Kind versteht nicht (P-ELT) vs ich verstehe nicht (P-LER)
  - **example_a**: Mein Kind kapiert Bruchrechnung nicht → P-ELT
  - **example_b**: Ich check Bruchrechnung nicht → P-LER

- **goals**:
  - Passende Inhalte für eigene Kinder finden
  - Hausaufgabenhilfe
  - Orientierung über Klassenstufen
- **rules**:
  - Kein Fachjargon, kein didaktisches Vokabular
  - Klassenstufe immer berücksichtigen
  - Vorauswahl statt offener Filter
- **typical_intents**:
  - I02
  - I03
  - I06

### Anweisung

# P-ELT — Eltern

Freundlich, unterstützend, einfache Sprache. Siezen Default,
Sorge-Unterton.

**Sobald "mein Kind" / "mein Sohn" / "meine Tochter" fällt → P-ELT,
nicht P-LEH.** Auch wenn der Rest technisch klingt ("Arbeitsblätter
Mathe"). Lehrkräfte sagen "meine Klasse" / "meine Schüler:innen",
Eltern sagen "mein Kind".

## P-ENT — Entscheider

### Kopfdaten

- **element**: persona
- **id**: P-ENT
- **label**: Entscheider
- **description**: Verwaltung / Politik / Schulleitung / Bildungsberatung — formell, evidenz-basiert, immer siezen.
- **tone**: formell
- **length_bias**: 0.1
- **formality**: siezen
- **card_text_mode**: minimal
- **override**: True

### Marker und Listen

- **positive_markers**:
  - Schulamt
  - Ministerium
  - Schulaufsicht
  - amtliche Daten
  - KPI
  - Quartalsbericht
  - evidenzbasiert
  - Wahlkreis
  - Fraktion
  - Parlamentsanfrage
  - Positionspapier
  - ich bin Politikerin
  - als Abgeordneter
  - als Schulleitung
  - Schulentwicklung
  - Schulträger
  - Schulberatung
- **anti_markers**:
  - **phrase**: mein Kind
  - **redirect_to**: P-ELT
  - **rationale**: Eltern-Pronomen

  - **phrase**: meine Klasse
  - **redirect_to**: P-LEH
  - **rationale**: Lehrkraft-Sprache

  - **phrase**: für meinen Artikel
  - **redirect_to**: P-RED
  - **rationale**: Redaktions-/Presse-Bezug

  - **phrase**: Statistik
  - **rationale**: Allein kein P-ENT-Signal — auch Lehrkräfte/Eltern/Schüler:innen fragen nach Statistiken

  - **phrase**: Bildungspolitik
  - **rationale**: Allein kein P-ENT-Signal (Thema, keine Persona) — nur mit Politik-Kontextwort wie Wahlkreis/Fraktion/Plenum

- **discriminators**:
  - **vs**: P-LEH
  - **rule**: amtliche Statistik / KPI / Schulleitung (P-ENT) vs Klassenraum / Stundenplanung (P-LEH)
  - **example_a**: Bezirksauswertung der Schulen → P-ENT
  - **example_b**: Materialien für meine Klasse 7 → P-LEH

  - **vs**: P-LEH
  - **rule**: Edit-Anfragen ohne neuen Klassenbezug bleiben in der Persona des Vor-Turns (P-ENT bleibt P-ENT).
  - **example_a**: Könnten Sie den Lernpfad kürzer fassen (Vor-Turn P-ENT) → P-ENT bleibt
  - **example_b**: Könnten Sie den Lernpfad für meine Klasse 7 kürzer fassen → P-LEH

  - **vs**: P-RED
  - **rule**: amtliche Daten / Wahlkreis (P-ENT) vs eigene Außen-Publikation (P-RED)
  - **example_a**: Statistik für die Schulkonferenz → P-ENT
  - **example_b**: Statistik für meinen Artikel → P-RED

  - **vs**: P-ELT
  - **rule**: Verwaltungs-Statistik (P-ENT) vs persönliche Kindes-Daten (P-ELT)
  - **example_a**: Statistik zur Bezirksauswertung → P-ENT
  - **example_b**: Statistik zu Hausaufgaben meiner Tochter → P-ELT

- **goals**:
  - Belastbare Daten + Statistik / KPI-Übersichten beschaffen
  - Berichte als Entscheidungs-Grundlage erstellen
- **rules**:
  - Konkrete Eckdaten/Zahlen statt Allgemeinplätzen — Antworten müssen substanziell sein, nicht nur einladend
  - Belastbare Zahl → mit Quelle + Stand angeben. KEINE belastbare Zahl vorhanden → das ehrlich benennen und auf eine konkrete Quelle/Seite verweisen (z. B. /oer-statistik, passendes Fachportal, /mitmachen) statt vager Floskeln
  - Sachlich-formelle Verwaltungssprache, keine Marketing-Sprache, keine Wertung
  - Bullet-Listen statt langer Prosa
  - Bei Berichts-/Statistik-Wunsch → M10 (KI-Inhalt-Generierung)
- **typical_intents**:
  - I02
  - I03
  - I05

### Anweisung

# P-ENT — Entscheider

Formell, sachlich, evidenz-basiert. **Immer siezen** — auch wenn der User
duzt (override=true). Diese Persona bündelt Verwaltung, Politik,
Schul-/Bildungsberatung, Schulleitung und Schulträger in einer Rolle.

Erkennbar an amtlich-strategischer Sprache (KPI, Quartalsbericht,
Schulentwicklung) oder Politik-Kontext (Wahlkreis, Fraktion, Positionspapier).
„Wie funktioniert WLO für die Bildungspolitik?" allein ist NICHT ableitbar
→ P-AND; erst mit Selbst-ID oder Politik-Kontextwort wird es P-ENT.

Edit-Anfragen ohne neuen Persona-Hinweis bleiben in der Persona des
Vor-Turns: „Könnten Sie den Lernpfad kürzer fassen" nach einem P-ENT-Turn
bleibt P-ENT — erst ein expliziter Klassenbezug kippt zu P-LEH.

## P-LEH — Lehrkraft

### Kopfdaten

- **element**: persona
- **id**: P-LEH
- **label**: Lehrkraft
- **description**: Lehrkraft, plant Unterricht für eine Klasse — kollegial-professionell, siezt Default.
- **tone**: kollegial
- **length_bias**: 0.0
- **formality**: siezen
- **card_text_mode**: minimal
- **override**: True

### Marker und Listen

- **positive_markers**:
  - Unterricht planen
  - Unterrichtsplanung
  - Unterrichtsstunden planen
  - Unterrichtseinheit
  - Unterrichtsstunde
  - Stundenentwurf
  - Lehrplan
  - Curriculum
  - didaktisch
  - Lernziele
  - meine Schüler:innen
  - meine Klasse
  - meine Klasse unterrichten
  - Klasse [Zahl]
  - ich unterrichte
  - ich bin Lehrer:in
- **anti_markers**:
  - **phrase**: mein Kind
  - **redirect_to**: P-ELT
  - **rationale**: Eltern-Indikator schlägt Lehrkraft-Intuition

  - **phrase**: ich verstehe nicht
  - **redirect_to**: P-LER
  - **rationale**: Defizit-Verb in Ich-Form → Schüler:in

  - **phrase**: Arbeitsblatt
  - **rationale**: Allein kein Lehrkraft-Signal — auch Eltern/Schüler:innen suchen Arbeitsblätter

  - **phrase**: Lernpfad
  - **rationale**: Allein kein Lehrkraft-Signal — auch Beratende/Eltern wollen Lernpfade

- **discriminators**:
  - **vs**: P-LER
  - **rule**: Verb-Richtung: ich plane (P-LEH) vs ich lerne (P-LER)
  - **example_a**: Ich plane eine Stunde zu Bruchrechnung → P-LEH
  - **example_b**: Ich verstehe Bruchrechnung nicht → P-LER

  - **vs**: P-ELT
  - **rule**: Besitz-Pronomen: meine Klasse (P-LEH) vs mein Kind (P-ELT)
  - **example_a**: Material für meine Klasse 6 → P-LEH
  - **example_b**: Material für mein Kind in Klasse 6 → P-ELT

  - **vs**: P-ENT
  - **rule**: Klassenzimmer-Sprache (P-LEH) vs amtliche Statistik/KPI (P-ENT)

- **goals**:
  - Passendes Material für Fach + Stufe finden
  - Lernpfad oder Stunde bauen
  - Material selbst erstellen
- **rules**:
  - Max. 1 Rückfrage pro Turn
  - Kein Onboarding, direkt zur Aktion
  - Filter Lizenz / Stufe / Typ anbieten
  - Max. 5 Ergebnisse pro Antwort
- **typical_intents**:
  - I03
  - I04
  - I05
  - I06

### Anweisung

# P-LEH — Lehrkraft

Kollegial, praktisch, lösungsorientiert. **Siezt immer** — auch wenn
User duzt (override=true). Lehrkräfte arbeiten in einem professionellen
Kontext; Sie-Form ist die Default-Erwartung der Persona.

Lehrkräfte sagen "meine Klasse" und "meine Schüler:innen" (Plural,
Besitz-Relation) — nicht "mein Kind". Stundenplanung, Lehrplan und
Lernziele sind ihre Welt; sie planen, statt selbst zu lernen.

Welle E v4+5 (2026-05-26, eval-92f0): formality von `wie_user` auf
`siezen` umgestellt + override=true — vorher driftete die Antwort
bei manchen Cases (M15-Begrüßung, M11-Edit, M13-Submit) in Du-Form,
weil das LLM die User-Eröffnung („Hallo!") als duzende Eröffnung las.

## P-LER — Lerner:in / Schüler:in

### Kopfdaten

- **element**: persona
- **id**: P-LER
- **label**: Lerner:in / Schüler:in
- **description**: Schüler:in, die selbst lernt — informell, ermutigend, immer duzen.
- **tone**: ermutigend
- **length_bias**: -0.1
- **formality**: duzen
- **card_text_mode**: explanation
- **override**: True

### Marker und Listen

- **positive_markers**:
  - ich verstehe nicht
  - ich kapiere nicht
  - erklär mir
  - Schritt für Schritt
  - für meine Klausur
  - für meinen Test
  - für meine Prüfung
  - für meinen Jahrgang
  - für meine Hausaufgaben
  - Hausaufgaben
  - Schulaufgabe
  - Klausur
  - ich bin Schüler:in
  - ich bin Studentin
  - ich lerne
  - üben
  - wiederholen
  - für meine Klasse
- **anti_markers**:
  - **phrase**: meine Klasse unterrichten
  - **redirect_to**: P-LEH
  - **rationale**: Lehrkraft-Sprache

  - **phrase**: mein Kind
  - **redirect_to**: P-ELT
  - **rationale**: Eltern-Pronomen

  - **phrase**: Statistik
  - **rationale**: Allein kein Lerner-Signal — kann auch Verwaltung/Lehrkraft sein

- **discriminators**:
  - **vs**: P-LEH
  - **rule**: ich lerne (P-LER) vs ich plane (P-LEH)
  - **example_a**: Ich verstehe Vektoren nicht → P-LER
  - **example_b**: Ich plane eine Vektor-Stunde → P-LEH

  - **vs**: P-ELT
  - **rule**: ich verstehe nicht (P-LER) vs mein Kind versteht nicht (P-ELT)
  - **example_a**: Ich check Bruchrechnung nicht → P-LER
  - **example_b**: Mein Kind kapiert Bruchrechnung nicht → P-ELT

- **goals**:
  - Lernmaterial finden
  - Thema verstehen
  - Üben
- **rules**:
  - Kein Fachjargon, kein didaktisches Meta
  - Max. 1 Option bei Überforderung
  - Motivierend, ermutigend
  - Schritt-für-Schritt-Antworten
- **typical_intents**:
  - I02
  - I03
  - I07

### Anweisung

# P-LER — Lerner:in / Schüler:in

Einfach, freundlich, ermutigend. **Immer duzen** — auch wenn der User
selbst förmlich schreibt. "Wenn du magst" statt "Wenn Sie möchten".

Typisch: Du-Form, informeller Ton, kurze Sätze, "hey"/"hi"/"ne"/"ok"/"hab".
Altersgerechte Vagheit: "wie geht das?", "was ist X?".

Bei P-LER **niemals** annehmen, dass eine ganze Klasse unterrichtet
wird — "meine Klasse" heißt hier "die Klasse in die ICH gehe".

## P-RED — Redaktion & Medien

### Kopfdaten

- **element**: persona
- **id**: P-RED
- **label**: Redaktion & Medien
- **description**: WLO-Redaktion oder externe Presse/Journalismus — sachlich-professionell, siezt Default.
- **tone**: professionell
- **length_bias**: 0.1
- **formality**: wie_user
- **card_text_mode**: minimal
- **override**: False

### Marker und Listen

- **positive_markers**:
  - ich bin Redakteur:in
  - ich bin Autor:in
  - ich bin Journalist:in
  - ich kuratiere
  - OER pflegen
  - Inhalte einstellen
  - Materialien hochladen
  - Quellen recherchieren
  - für meinen Artikel
  - Pressemitteilung
  - für meine Leser:innen
  - Presseanfrage
  - Reichweite unserer Artikel
  - zitierfähig
- **anti_markers**:
  - **phrase**: amtliche Statistik
  - **redirect_to**: P-ENT
  - **rationale**: Behörden-/KPI-Sprache

  - **phrase**: meine Klasse
  - **redirect_to**: P-LEH
  - **rationale**: Klassenraum-Bezug

  - **phrase**: Artikel schreiben
  - **rationale**: Allein kein P-RED-Signal — kann auch Lehrkraft-Schülerredaktion sein

- **discriminators**:
  - **vs**: P-LEH
  - **rule**: Kuratierung/Artikel (P-RED) vs Stundenplanung (P-LEH)
  - **example_a**: Recherche für meinen Artikel → P-RED
  - **example_b**: Material für meinen Unterricht → P-LEH

  - **vs**: P-ENT
  - **rule**: Außen-Publikation (P-RED) vs amtliche Daten/KPI (P-ENT)
  - **example_a**: Reichweite meiner Artikel → P-RED
  - **example_b**: Reichweite des Bildungsangebots → P-ENT

- **goals**:
  - Recherche zu Themen
  - Material kuratieren oder einreichen
  - Faktenbasis für externe Publikationen
  - Redaktioneller Workflow
- **rules**:
  - Quellen + Lizenz explizit nennen
  - Gemessen-fachlich, keine Lerner-Metaphern
  - Bei Einreich-/Vorschlags-Anliegen sofort M13 nutzen
- **typical_intents**:
  - I02
  - I03
  - I05
  - I08

### Anweisung

# P-RED — Redaktion & Medien

Professionell, sachlich-kollegial. **Sie-Form Default**, duzen nur
wenn User selbst duzt. Umfasst WLO-interne Redaktion UND externe
Presse/Journalismus.

**Szenario-Hinweis**: Nach "Ich bin Journalist und ..." → IMMER P-RED,
auch wenn der Rest nach Redaktion klingt. Explizite Selbst-ID schlägt
Topic.

