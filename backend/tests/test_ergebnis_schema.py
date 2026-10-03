"""Ergebnis-Schema eines Gastgebers prüfen (Paket 4, A3; externes Audit F11).

Das Schema reiste wörtlich in die Werkzeug-Parameter, geprüft wurde das
Ergebnis aber nirgends: ``score`` als Integer 0..5 nahm ``"bad"`` an. Der
Anbieter erzwingt die Form nur mit ``strict``, und das setzt dieses Projekt
bewusst nicht (es verlangte ``additionalProperties: false`` und alle Felder als
Pflicht).
"""

from __future__ import annotations

import time

from boerdi.domain.ergebnis_schema import argument_fehler, schema_fehler

_SCORE = {
    "type": "object",
    "properties": {"score": {"type": "integer", "minimum": 0, "maximum": 5}},
    "required": ["score"],
}
_PARAMETER = {
    "type": "object",
    "properties": {"text": {"type": "string"}, "result": _SCORE},
    "required": ["text", "result"],
}


class TestSchemaAmEingang:
    def test_ein_gueltiges_schema_passiert(self):
        assert schema_fehler(_SCORE) is None

    def test_ein_kaputtes_schema_wird_benannt(self):
        assert schema_fehler({"type": "intger"}) is not None

    def test_ein_lokaler_verweis_ist_erlaubt(self):
        schema = {"$defs": {"n": {"type": "integer"}},
                  "type": "object", "properties": {"a": {"$ref": "#/$defs/n"}}}
        assert schema_fehler(schema) is None

    def test_ein_entfernter_verweis_wird_abgewiesen(self):
        # Geladen wird nichts von außen: die Prüfung soll nie nachladen.
        schema = {"type": "object",
                  "properties": {"a": {"$ref": "https://example.org/s.json"}}}
        assert schema_fehler(schema) is not None


class TestArgumente:
    def test_passende_argumente_ergeben_nichts(self):
        assert argument_fehler(_PARAMETER, {"text": "ok", "result": {"score": 3}}) == []

    def test_ein_falscher_typ_nennt_den_pfad(self):
        fehler = argument_fehler(_PARAMETER, {"text": "ok", "result": {"score": "bad"}})
        assert len(fehler) == 1
        assert fehler[0].startswith("result.score:")

    def test_eine_grenze_zaehlt(self):
        assert argument_fehler(_PARAMETER, {"text": "ok", "result": {"score": 99}})

    def test_ein_fehlendes_pflichtfeld_zaehlt(self):
        assert argument_fehler(_PARAMETER, {"text": "ok"})

    def test_ohne_parameter_gibt_es_nichts_zu_pruefen(self):
        # Minimale Werkzeugdefinition ohne ``parameters`` (etwa in Tests).
        assert argument_fehler(None, {"text": "ok", "result": "beliebig"}) == []

    def test_die_meldungen_sind_gedeckelt(self):
        schema = {"type": "object",
                  "properties": {f"f{i}": {"type": "integer"} for i in range(20)}}
        fehler = argument_fehler(schema, {f"f{i}": "x" for i in range(20)})
        assert len(fehler) == 5


# ── Prüfer 2026-10-04: Das Schema kommt von außen ────────────────────────────
#
# Vorher holte jsonschema unbekannte Adressen per ``urlopen`` (SSRF), ein
# ``pattern`` des Gastgebers lief ungebremst gegen die Modell-Ausgabe (ReDoS),
# lokale Verweise zeigten auf die Werkzeug-Hülle (Absturz), und draft-07 galt
# als kaputt.

_SSRF = {"type": "object", "properties": {"a": {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "http://169.254.169.254/latest/meta-data/",
    "$ref": "#/x"}}}


def _als_ergebnis(schema):
    return {"type": "object", "properties": {"result": schema}, "required": ["result"]}


class TestVonAussen:
    def test_id_und_schema_unterhalb_der_wurzel_werden_abgewiesen(self):
        assert schema_fehler(_SSRF) is not None

    def test_die_pruefung_laedt_nie_nach(self, monkeypatch):
        # Auch ein Schema, das am Eingang vorbeikäme, holt nichts von außen.
        # Mitzählen statt werfen: ``referencing`` macht aus jeder Ausnahme beim
        # Nachladen ein ``Unresolvable``, das die Prüfung auffängt.
        abrufe: list[object] = []

        def mitschreiben(url, *_args, **_kwargs):
            abrufe.append(url)
            raise OSError("im Test gesperrt")

        monkeypatch.setattr("urllib.request.urlopen", mitschreiben)
        assert argument_fehler(_als_ergebnis(_SSRF), {"result": {"a": 1}})
        assert abrufe == []

    def test_anker_werden_abgewiesen(self):
        assert schema_fehler({"$defs": {"n": {"$anchor": "n"}}, "$ref": "#n"}) is not None

    def test_ein_verweis_ins_leere_wird_am_eingang_abgewiesen(self):
        assert schema_fehler({"properties": {"a": {"$ref": "#/$defs/fehlt"}}}) is not None

    def test_zu_tief_verschachtelt_wird_abgewiesen(self):
        schema: dict = {"type": "object"}
        for _ in range(100):
            schema = {"not": schema}
        assert schema_fehler(schema) is not None

    def test_lokale_verweise_zeigen_ins_gastgeber_schema(self):
        gast = {"type": "object", "$defs": {"Item": {"type": "string"}},
                "properties": {"i": {"$ref": "#/$defs/Item"}}}
        assert schema_fehler(gast) is None
        assert argument_fehler(_als_ergebnis(gast), {"result": {"i": "x"}}) == []
        fehler = argument_fehler(_als_ergebnis(gast), {"result": {"i": 1}})
        assert len(fehler) == 1
        assert fehler[0].startswith("result.i:")

    def test_ein_rekursives_schema_prueft_gegen_die_eigene_wurzel(self):
        knoten = {"type": "object", "required": ["name"],
                  "properties": {"name": {"type": "string"},
                                 "kinder": {"type": "array", "items": {"$ref": "#"}}}}
        gut = {"name": "a", "kinder": [{"name": "b"}]}
        assert argument_fehler(_als_ergebnis(knoten), {"result": gut}) == []
        assert argument_fehler(_als_ergebnis(knoten), {"result": {"name": "a", "kinder": [{}]}})

    def test_muster_blockieren_den_server_nicht(self):
        # Freie Gastgeber-Schemata bleiben erlaubt (P4-3); das Muster ist ein
        # Hinweis an das Modell, geprüft wird es nicht.
        gast = {"type": "object", "properties": {"x": {"type": "string", "pattern": "^(a+)+$"}}}
        assert schema_fehler(gast) is None
        start = time.perf_counter()
        argument_fehler(_als_ergebnis(gast), {"result": {"x": "a" * 40 + "!"}})
        assert time.perf_counter() - start < 1

    def test_muster_eigenschaften_machen_schluessel_nicht_zusaetzlich(self):
        gast = {"type": "object", "patternProperties": {"^(a+)+$": {"type": "integer"}},
                "additionalProperties": False}
        start = time.perf_counter()
        assert argument_fehler(_als_ergebnis(gast), {"result": {"a" * 40 + "!": 1}}) == []
        assert time.perf_counter() - start < 1

    def test_eine_eigenschaft_namens_pattern_bleibt_gepruft(self):
        gast = {"type": "object", "properties": {"pattern": {"type": "integer"}}}
        assert argument_fehler(_als_ergebnis(gast), {"result": {"pattern": "x"}})

    def test_der_dialekt_folgt_dem_schema(self):
        # draft-07 mit Tupel-``items`` und ``definitions``: vorher 422.
        alt = {"$schema": "http://json-schema.org/draft-07/schema#",
               "definitions": {"n": {"type": "integer"}},
               "type": "array", "items": [{"$ref": "#/definitions/n"}, {"type": "string"}]}
        assert schema_fehler(alt) is None
        assert argument_fehler(_als_ergebnis(alt), {"result": [1, "a"]}) == []
        assert argument_fehler(_als_ergebnis(alt), {"result": ["a", "a"]})
