"""Paket 13 (A3): Fingerabdruck der Konfiguration und der Golden-Abläufe eines Laufs.

Zwei Läufe sind nur vergleichbar, wenn man sieht, ob zwischen ihnen die Konfiguration oder
die Testfälle sich änderten — und welche Bereiche. Der Abdruck hängt nicht an der
Schlüssel-Reihenfolge (jsonb ordnet selbst), aber an jedem geänderten Wert.
"""

from __future__ import annotations

from boerdi.services.eval import fingerprint as fp


def _zeile(area: str, data: dict, version: int = 1, werk_hash: str | None = None,
           updated_by: str = "studio") -> dict:
    return {"area": area, "data": data, "version": version, "updated_by": updated_by,
            "werk_hash": werk_hash, "hat_eigene_fassung": False}


def test_reihenfolge_der_schluessel_aendert_den_abdruck_nicht() -> None:
    a = fp.konfig_fingerprint([_zeile("01-base/x", {"a": 1, "b": 2})], werk={})
    b = fp.konfig_fingerprint([_zeile("01-base/x", {"b": 2, "a": 1})], werk={})
    assert a["hash"] == b["hash"]


def test_ein_geaenderter_wert_aendert_bereich_und_gesamt() -> None:
    a = fp.konfig_fingerprint([_zeile("01-base/x", {"a": 1}), _zeile("01-base/y", {"c": 3})],
                              werk={})
    b = fp.konfig_fingerprint([_zeile("01-base/x", {"a": 2}), _zeile("01-base/y", {"c": 3})],
                              werk={})
    assert a["hash"] != b["hash"]
    assert a["bereiche"]["01-base/x"]["hash"] != b["bereiche"]["01-base/x"]["hash"]
    assert a["bereiche"]["01-base/y"] == b["bereiche"]["01-base/y"]


def test_stand_gegen_die_werksfassung() -> None:
    werk = {"01-base/x": {"a": 1}, "01-base/y": {"c": 3}}
    zeilen = [_zeile("01-base/x", {"a": 1}, version=4),
              _zeile("01-base/y", {"c": 9}, version=2),
              _zeile("01-base/z", {"neu": True})]
    abdruck = fp.konfig_fingerprint(zeilen, werk=werk)
    assert abdruck["bereiche"]["01-base/x"] == {
        "version": 4, "hash": fp.kurz({"a": 1}), "stand": "werk"}
    assert abdruck["bereiche"]["01-base/y"]["stand"] == "eigen-neues-werk"
    assert abdruck["bereiche"]["01-base/z"]["stand"] == "nur-eigen"


def test_ohne_werk_bleibt_der_stand_leer() -> None:
    abdruck = fp.konfig_fingerprint([_zeile("01-base/x", {"a": 1})], werk=None)
    assert abdruck["bereiche"]["01-base/x"]["stand"] == ""


def test_gold_flows_hash_haengt_am_inhalt() -> None:
    flows = [{"id": "GV-1", "turns": [{"message": "hallo"}]}]
    gleich = [{"turns": [{"message": "hallo"}], "id": "GV-1"}]
    anders = [{"id": "GV-1", "turns": [{"message": "hallo!"}]}]
    assert fp.gold_flows_hash(flows) == fp.gold_flows_hash(gleich)
    assert fp.gold_flows_hash(flows) != fp.gold_flows_hash(anders)
    assert len(fp.gold_flows_hash(flows)) == 12
