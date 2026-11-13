# Fix: soupsieve 2.9 → 4.1 (2026-11-13)

Die CI-Prüfung `licenses-backend` (Schritt `pip-audit`) schlug auf PR #60 fehl. Für `soupsieve 2.9`
waren zwei Lücken neu veröffentlicht worden (CVE-2026-126192, behoben ab 2.10.0;
CVE-2026-126190, behoben ab 4.0.0). Der Code der Pakete R1–R4 war nicht die Ursache. Ein neuer Lauf
auf `main` wäre genauso rot geworden.

- `uv lock --upgrade-package soupsieve` hebt nur dieses eine Paket an, auf 4.1. Es ist transitiv
  über `beautifulsoup4` 4.15.0, das unverändert bleibt.
- Geprüft:
  - `pip-audit` wie in der CI: keine bekannten Lücken;
  - Lizenzprüfung grün;
  - 158 Tests rund um Dokumente, Umwandlung und Strukturentwurf grün.
- Deploy: Das Image neu bauen genügt.
