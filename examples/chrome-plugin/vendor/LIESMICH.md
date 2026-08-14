# Dieser Ordner ist absichtlich leer

Hier gehört `boerdi-widget.js` hinein — das gebaute Widget-Bündel des Backends.

Es liegt **nicht** im Repositorium, weil es ein Bau-Erzeugnis ist und sich mit
jedem Frontend-Stand ändert. Holt es euch:

```bash
node scripts/fetch-widget.mjs http://localhost:8000
```

## Warum es überhaupt lokal liegen muss

Manifest V3 verbietet nachgeladenen Code. Auf einer Erweiterungs-Seite gilt
`script-src 'self'`; ein `<script src="https://backend/widget/…">` wird von
Chrome gesperrt, auch bei einer entpackt geladenen Erweiterung.

Das ist keine Eigenheit dieses Beispiels — **jede** Chrome-Erweiterung, die das
Widget in einer eigenen Seite (Seitenleiste, Popup, Options-Seite) zeigt, muss
das Bündel mitliefern und bei einem Backend-Update neu holen.

Anders liegt der Fall nur, wenn ihr das Widget in die **Gastseite** einhängt
statt in eine Erweiterungs-Seite: dort gilt die CSP der Gastseite, und der
Skript-Tag darf auf euer Backend zeigen. Siehe
`docs/browser-plugin-einbindung.md`, §1.

## Nur aus einer Quelle, der ihr vertraut

Was hier landet, läuft danach mit den Rechten der Erweiterung — samt jeder
Seiten-Erlaubnis, die ihr ihr gebt. Eine Prüfsumme gibt es nicht (es wird keine
veröffentlicht), also ist die Herkunft die ganze Sicherheit. Über `http://` auf
einem fremden Host kann jeder dazwischen den Code austauschen; `fetch-widget.mjs`
sagt es, verweigert aber nichts — gegen `localhost` ist `http` der Normalfall.

Statt zu holen könnt ihr auch selbst bauen: `cd ../../frontend && npm run
build:widget`, dann `frontend/dist/widget/browser/main.js` hierher kopieren. Das
ist zugleich der einzige Weg, ein Attribut auszuprobieren, das im deployten
Backend noch nicht steckt.
