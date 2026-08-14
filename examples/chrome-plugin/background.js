/**
 * Der Dienst-Worker. Er tut genau eine Sache: den Klick auf das Symbol in der
 * Werkzeugleiste öffnet die Seitenleiste.
 *
 * `setPanelBehavior` genügt dafür — es gibt keinen Grund, `sidePanel.open()`
 * je Klick selbst zu rufen, und der Aufruf wäre an eine Nutzergeste gebunden,
 * die ein aufgewachter Worker nicht mehr sicher hat.
 */
chrome.runtime.onInstalled.addListener(() => {
  chrome.sidePanel
    .setPanelBehavior({ openPanelOnActionClick: true })
    .catch((err) => console.error('Seitenleisten-Verhalten nicht gesetzt:', err));
});
