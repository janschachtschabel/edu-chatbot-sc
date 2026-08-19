# Entities (Slots)

<!-- ERZEUGT von backend/scripts/export_dimensions.py aus backend/seeds/ — nicht von Hand ändern; Änderungen gehören in den Seed bzw. ins Studio. -->

Quelle: `backend/seeds/04-entities/entities.yaml`

## fach — Fach / Fachgebiet

- **type**: string
- **description**: Schulfach oder Fachgebiet (z.B. Mathematik, Deutsch, Biologie).
- **examples**:
  - Mathematik
  - Deutsch
  - Biologie
  - Informatik
  - Geschichte
- **positive_examples**:
  - **text**: Ich brauche Hilfe bei Mathe
  - **value**: Mathematik

  - **text**: Ich lerne Biologie
  - **value**: Biologie

  - **text**: Kannst du mir bei Deutsch helfen?
  - **value**: Deutsch

- **discriminators**:
  - **vs**: thema
  - **rule**: Schulfächer (Mathe, Deutsch, Biologie, Chemie, Physik, Englisch, Geschichte, Erdkunde, Geographie, Sport, Kunst, Musik, Informatik, Religion, Ethik, Politik, Wirtschaft, Sozialkunde) → IMMER `fach`, NIE `thema`.
  - **example_a**: Ich lerne Biologie → fach=Biologie, thema=''
  - **example_b**: Ich lerne Photosynthese → fach='', thema='Photosynthese'

## stufe — Bildungsstufe

- **type**: string
- **description**: Bildungsstufe gemäß dem WLO-Vokabular educationalContext (Elementarbereich, Grundschule, Sekundarstufe I, Sekundarstufe II, Berufliche Bildung, Hochschule, Erwachsenenbildung, Fortbildung, Förderschule). Nennt der Nutzer eine konkrete Klassenstufe ("Klasse 6", "6. Klasse", "11. Schuljahr"), MAPPE auf die passende Bildungsstufe: Klasse 1-4 = Grundschule, Klasse 5-10 = Sekundarstufe I, Klasse 11-13 = Sekundarstufe II. Filter auf Klassenstufen-Ebene gibt es auf WLO nicht — Inhalte sind nur mit educationalContext (Bildungsstufe) getaggt.
- **examples**:
  - Grundschule
  - Sekundarstufe I
  - Sekundarstufe II
  - Berufliche Bildung
  - Hochschule
  - Erwachsenenbildung
- **positive_examples**:
  - **text**: Klasse 6
  - **value**: Sekundarstufe I

  - **text**: Material für Klasse 2
  - **value**: Grundschule

  - **text**: Oberstufe 11. Schuljahr
  - **value**: Sekundarstufe II

## thema — Thema

- **type**: string
- **description**: Konkretes Thema oder Lerngegenstand INNERHALB eines Fachs (z.B. Bruchrechnung, Photosynthese, Lyrik der Romantik). `thema` ist ein eigenständiger Lerngegenstand, NICHT ein Satzfragment. Wenn kein klarer Lerngegenstand erkennbar ist, LASSE `thema` komplett LEER — dann fragt das System degradierend nach.
- **examples**:
  - Bruchrechnung
  - Photosynthese
  - Lyrik der Romantik
  - Klimawandel
  - Satz des Pythagoras
- **positive_examples**:
  - **text**: Erstelle ein Arbeitsblatt zur Photosynthese
  - **value**: Photosynthese

  - **text**: Quiz zu Bruchrechnung für Klasse 6
  - **value**: Bruchrechnung

  - **text**: Material zum Klimawandel
  - **value**: Klimawandel

  - **text**: Lerngeschichte über die Römer
  - **value**: die Römer

- **negative_examples**:
  - **text**: Kannst du mir das Arbeitsblatt runterladen?
  - **rationale**: Kein Lerninhalt genannt — Material-Typ, kein Thema.

  - **text**: Ich brauche Ideen für ein neues Arbeitsblatt
  - **rationale**: Nur Absicht, kein Thema.

  - **text**: Hey, ich hab ne Frage zu den Übungen für mein Kind
  - **rationale**: Vages Feedback, kein konkreter Lerngegenstand.

  - **text**: Gibt's ne Übersicht zu den aktuellen Statistiken?
  - **rationale**: Meta-Frage, kein Lerninhalt.

  - **text**: Hilf mir die Qualität des Arbeitsblatts zu bewerten
  - **rationale**: Review-Anfrage, kein Lerninhalt.

  - **text**: Erstelle mir ein neues Material
  - **rationale**: Kein Thema genannt — System degradiert auf Nachfrage.

  - **text**: Mach mir ein Quiz
  - **rationale**: Material-Typ klar, Thema fehlt.

  - **text**: Ich brauche Hilfe bei Mathe
  - **rationale**: Nur Fach (→ fach=Mathematik), kein Thema.

  - **text**: Ich suche Materialien
  - **rationale**: Keine Lerngegenstand-Nennung.

  - **text**: Ich will Infos
  - **rationale**: Kein Inhalt, kein Fach.

- **discriminators**:
  - **vs**: fach
  - **rule**: Eigenständige Lerngegenstände wie 'Bruchrechnung', 'Photosynthese', 'Mittelalter', 'Satz des Pythagoras' → `thema`. Schulfächer → `fach`.
  - **example_a**: Bruchrechnung → thema='Bruchrechnung'
  - **example_b**: Mathematik → fach='Mathematik'

## medientyp — Medientyp

- **type**: string
- **description**: Art des gesuchten Materials / Ressourcentyp (resourceType / Lernressourcentyp). Extrahiere diesen Slot IMMER wenn der Nutzer einen Inhaltstyp nennt — auch bei Pluralformen, Umschreibungen oder Adjektiven. Der Wert darf Klartext sein — das Backend löst ihn ins WLO-Vokabular auf.
- **examples**:
  - Video
  - Arbeitsblatt
  - Bild
  - Interaktives medium
  - Simulation
  - Quiz
  - Audio
  - Lernspiel
  - Podcast
  - Kurs
- **positive_examples**:
  - **text**: Zeig mir Videos zu Bruchrechnung
  - **value**: Video

  - **text**: Interaktive Übung zu Photosynthese
  - **value**: Interaktives medium

  - **text**: Arbeitsblätter für Klasse 5
  - **value**: Arbeitsblatt

  - **text**: Quiz zur Lyrik
  - **value**: Quiz

  - **text**: Podcast zum Klimawandel
  - **value**: Audio

  - **text**: Karte zum Mittelalter
  - **value**: Karte

  - **text**: Webseite zum Thema OER
  - **value**: Webseite

## lizenz — Lizenz

- **type**: string
- **description**: Gewünschte Lizenz (z.B. CC BY, CC BY-SA, CC0).
- **examples**:
  - CC BY
  - CC BY-SA
  - CC0
  - Alle OER

