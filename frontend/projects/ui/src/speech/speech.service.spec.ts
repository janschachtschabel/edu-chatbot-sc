import { afterEach, describe, expect, it, vi, type Mock } from 'vitest';

import { ChatMessage } from '../grouping/message-types';
import { DE } from '../i18n/de';
import { createTranslator } from '../i18n/dictionary';
import { SpeechContext, SpeechService } from './speech.service';

/**
 * Charakterisierung des SpeechService — Verbatim-Port aus ALT (dort bewusst
 * UNGETESTET, weil jsdom MediaRecorder/getUserMedia/HTMLAudioElement fehlt).
 * Diese Spec deckt daher NUR die Nicht-Browser-API-Pfade ab: autoSpeak-
 * Toggle inkl. sender/isLoading-Selektionsfilter, Stop-Guards, Empty-Text-
 * Frühausstieg, mic-loser toggleRecording-Catch, destroy-No-Throw. Die
 * Audio-Playback- / Recorder-Erfolgspfade bleiben ungetestet (live via 8-7).
 *
 * Trick für die Selektions-Tests: `synthesize` wird SYNCHRON in
 * `speakChunked` → `fetchTTS` aufgerufen (vor dem ersten await), sodass der
 * Aufruf sichtbar ist, bevor `toggleAutoSpeak` zurückkehrt. Die Reject-
 * Antwort lässt `fetchTTS` `null` liefern → speakChunked bricht VOR `playBlob`
 * ab (kein `new Audio`).
 *
 * C1-b4: die eine übersetzte Zeile dieses Moduls (`error.transcription`) liegt
 * in `mediaRecorder.onstop` und ist aus demselben Grund nicht erreichbar —
 * jsdom kennt keinen MediaRecorder. Sie bleibt ungetestet wie der ganze
 * Recorder-Pfad; belegt ist nur, dass der Übersetzer im Kontext ankommt.
 */
type SynthMock = Mock<(text: string, signal?: AbortSignal) => Promise<Blob>>;

function makeCtx(over: Partial<Omit<SpeechContext, 'synthesize'>> = {}): {
  ctx: SpeechContext;
  synthesize: SynthMock;
  transcript: string[];
  bot: string[];
} {
  const transcript: string[] = [];
  const bot: string[] = [];
  const synthesize: SynthMock = vi.fn((_t: string, _s?: AbortSignal): Promise<Blob> => Promise.reject(new Error('no-tts')));
  const ctx: SpeechContext = {
    transcribe: over.transcribe ?? (async () => ''),
    synthesize,
    runInZone: over.runInZone ?? ((fn) => fn()),
    onTranscript: over.onTranscript ?? ((t) => transcript.push(t)),
    addBotMessage: over.addBotMessage ?? ((c) => bot.push(c)),
    messages: over.messages ?? (() => []),
    t: over.t ?? createTranslator(DE, DE),
  };
  return { ctx, synthesize, transcript, bot };
}

const flush = () => new Promise((r) => setTimeout(r));

describe('SpeechService', () => {
  it('toggleAutoSpeak an: spricht die letzte fertige Bot-Nachricht (synthesize aufgerufen)', async () => {
    const msgs: ChatMessage[] = [
      { id: 'u1', sender: 'user', content: 'Frage', timestamp: new Date() },
      { id: 'b1', sender: 'bot', content: 'Antwort Satz.', timestamp: new Date() },
    ];
    const { ctx, synthesize } = makeCtx({ messages: () => msgs });
    const svc = new SpeechService(ctx);
    svc.toggleAutoSpeak();
    expect(svc.autoSpeak).toBe(true);
    expect(synthesize).toHaveBeenCalledTimes(1);
    expect(synthesize.mock.calls[0][0]).toBe('Antwort Satz.');
    await flush(); // Async-Unwind (Reject in fetchTTS geschluckt)
  });

  it('toggleAutoSpeak an: letzte Nachricht = user → kein synthesize (sender-Filter)', () => {
    const { ctx, synthesize } = makeCtx({ messages: () => [{ id: 'u1', sender: 'user', content: 'Frage', timestamp: new Date() }] });
    new SpeechService(ctx).toggleAutoSpeak();
    expect(synthesize).not.toHaveBeenCalled();
  });

  it('toggleAutoSpeak an: letzte Bot-Nachricht lädt noch → kein synthesize (isLoading-Filter)', () => {
    const { ctx, synthesize } = makeCtx({ messages: () => [{ id: 'b1', sender: 'bot', content: 'lädt', isLoading: true, timestamp: new Date() }] });
    new SpeechService(ctx).toggleAutoSpeak();
    expect(synthesize).not.toHaveBeenCalled();
  });

  it('toggleAutoSpeak aus: stoppt laufende Ausgabe (isSpeaking → false)', () => {
    const { ctx, synthesize } = makeCtx();
    const svc = new SpeechService(ctx);
    svc.autoSpeak = true;
    svc.isSpeaking = true;
    svc.toggleAutoSpeak();
    expect(svc.autoSpeak).toBe(false);
    expect(svc.isSpeaking).toBe(false);
    expect(synthesize).not.toHaveBeenCalled();
  });

  it('autoSpeakText(""): leerer Text → Frühausstieg, kein isSpeaking, kein synthesize', () => {
    const { ctx, synthesize } = makeCtx();
    const svc = new SpeechService(ctx);
    svc.autoSpeakText('');
    expect(svc.isSpeaking).toBe(false);
    expect(synthesize).not.toHaveBeenCalled();
  });

  it('speakText während Sprechen → Stop (isSpeaking false, kein synthesize)', () => {
    const { ctx, synthesize } = makeCtx();
    const svc = new SpeechService(ctx);
    svc.isSpeaking = true;
    svc.speakText('egal');
    expect(svc.isSpeaking).toBe(false);
    expect(synthesize).not.toHaveBeenCalled();
  });

  it('toggleRecording ohne Mikrofon (jsdom) → isRecording endet false (Guard/Catch)', async () => {
    const { ctx } = makeCtx();
    const svc = new SpeechService(ctx);
    await svc.toggleRecording();
    expect(svc.isRecording).toBe(false);
  });

  it('verweigertes Mikrofon meldet den Zustandswechsel an die UI (8-6, zoneless)', async () => {
    // `isRecording` ist ein plain Feld: die Rücknahme passiert NACH einem
    // `await` (getUserMedia rejected), also außerhalb des Klick-Turns. Ohne
    // `runInZone` plant im zoneless Betrieb nichts eine Prüfung — der
    // Mikro-Button bliebe im Aufnahme-Zustand und das Eingabefeld gesperrt.
    const zoneRuns: string[] = [];
    const { ctx } = makeCtx({
      runInZone: (fn) => { zoneRuns.push('run'); return fn(); },
    });
    const svc = new SpeechService(ctx);
    await svc.toggleRecording();
    expect(svc.isRecording).toBe(false);
    expect(zoneRuns.length).toBeGreaterThan(0);
  });

  it('destroy() wirft nicht (ohne aktive Aufnahme/Ausgabe)', () => {
    const { ctx } = makeCtx();
    const svc = new SpeechService(ctx);
    expect(() => svc.destroy()).not.toThrow();
  });
});

// ── Paket 18E: Spur in der Konsole — die Fehlerart, nie der Text ─────────────
const MARKE = 'KANARIE7Q';
const ausgabe = (spy: { mock: { calls: unknown[][] } }): string =>
  spy.mock.calls.flat().map(String).join(' ');

describe('Paket 18E: Spur, wenn das Vorlesen scheitert', () => {
  afterEach(() => vi.restoreAllMocks());

  const msgs: ChatMessage[] = [
    { id: 'b1', sender: 'bot', content: 'Antwort Satz.', timestamp: new Date() },
  ];

  it('eine gescheiterte Synthese warnt mit der Fehlerart, nie mit dem Text', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const { ctx, synthesize } = makeCtx({ messages: () => msgs });
    synthesize.mockImplementation(() => Promise.reject(new Error(MARKE)));
    new SpeechService(ctx).toggleAutoSpeak();
    await flush();
    expect(warn).toHaveBeenCalledTimes(1);
    expect(ausgabe(warn)).toContain('Error');
    expect(ausgabe(warn)).not.toContain(MARKE);
  });

  it('ein Abbruch durch Stopp ist kein Fehler — keine Warnung', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    let ablehnen: (e: unknown) => void = () => {};
    const { ctx, synthesize } = makeCtx({ messages: () => msgs });
    synthesize.mockImplementation(() => new Promise<Blob>((_ok, nein) => { ablehnen = nein; }));
    const svc = new SpeechService(ctx);
    svc.toggleAutoSpeak();
    svc.toggleAutoSpeak(); // aus: bricht die laufende Synthese ab
    ablehnen(new DOMException('abgebrochen', 'AbortError'));
    await flush();
    expect(warn).not.toHaveBeenCalled();
  });
});

// ── Paket 19, Audit 2026-10-31 M-13 + N-38: Mikrofon ─────────────────────────
// jsdom kennt weder MediaRecorder noch getUserMedia — hier stehen kleine
// Attrappen, die nur das Verhalten tragen, auf das der Dienst baut: `stop()`
// liefert erst die Daten, dann `onstop`.
describe('Paket 19: Aufnahme verwerfen und verweigertes Mikrofon', () => {
  const spuren: Array<{ stop: () => void; gestoppt: boolean }> = [];

  class AttrappenRecorder {
    state: 'inactive' | 'recording' = 'inactive';
    ondataavailable: ((e: { data: Blob }) => void) | null = null;
    onstop: (() => void) | null = null;
    constructor(readonly stream: MediaStream) {}
    start() { this.state = 'recording'; }
    stop() {
      this.state = 'inactive';
      this.ondataavailable?.({ data: new Blob(['ton']) });
      this.onstop?.();
    }
  }

  function mitMikrofon(getUserMedia: () => Promise<MediaStream>) {
    vi.stubGlobal('MediaRecorder', AttrappenRecorder);
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true, value: { getUserMedia },
    });
  }

  function strom(): MediaStream {
    const spur = { gestoppt: false, stop() { this.gestoppt = true; } };
    spuren.push(spur);
    return { getTracks: () => [spur] } as unknown as MediaStream;
  }

  afterEach(() => {
    vi.unstubAllGlobals();
    delete (navigator as { mediaDevices?: unknown }).mediaDevices;
    spuren.length = 0;
    vi.restoreAllMocks();
  });

  it('Gegenprobe: normales Stoppen transkribiert und sendet', async () => {
    mitMikrofon(async () => strom());
    const transcribe = vi.fn(async () => 'Hallo');
    const { ctx, transcript } = makeCtx({ transcribe });
    const svc = new SpeechService(ctx);
    await svc.toggleRecording();
    expect(svc.isRecording).toBe(true);
    await svc.toggleRecording();
    await flush();
    expect(transcribe).toHaveBeenCalledTimes(1);
    expect(transcript).toEqual(['Hallo']);
  });

  it('verwerfen(): stoppt die Aufnahme, gibt das Mikrofon frei, transkribiert und sendet nichts (M-13)', async () => {
    mitMikrofon(async () => strom());
    const transcribe = vi.fn(async () => 'Geheim');
    const { ctx, transcript } = makeCtx({ transcribe });
    const svc = new SpeechService(ctx);
    await svc.toggleRecording();
    svc.verwerfen();
    await flush();
    expect(svc.isRecording).toBe(false);
    expect(spuren.every((s) => s.gestoppt)).toBe(true);
    expect(transcribe).not.toHaveBeenCalled();
    expect(transcript).toEqual([]);
  });

  it('destroy(): dieselbe Verwerfung — kein Hochladen nach dem Entfernen (M-13)', async () => {
    mitMikrofon(async () => strom());
    const transcribe = vi.fn(async () => 'Geheim');
    const { ctx, transcript } = makeCtx({ transcribe });
    const svc = new SpeechService(ctx);
    await svc.toggleRecording();
    svc.destroy();
    await flush();
    expect(spuren.every((s) => s.gestoppt)).toBe(true);
    expect(transcribe).not.toHaveBeenCalled();
    expect(transcript).toEqual([]);
  });

  it('nach dem Verwerfen nimmt die nächste Aufnahme wieder normal auf', async () => {
    mitMikrofon(async () => strom());
    const transcribe = vi.fn(async () => 'Zwei');
    const { ctx, transcript } = makeCtx({ transcribe });
    const svc = new SpeechService(ctx);
    await svc.toggleRecording();
    svc.verwerfen();
    await svc.toggleRecording();
    await svc.toggleRecording();
    await flush();
    expect(transcript).toEqual(['Zwei']);
  });

  it('verweigertes Mikrofon → Hinweisblase error.micDenied (N-38)', async () => {
    mitMikrofon(async () => { throw new DOMException('nein', 'NotAllowedError'); });
    const { ctx, bot } = makeCtx();
    const svc = new SpeechService(ctx);
    await svc.toggleRecording();
    expect(svc.isRecording).toBe(false);
    expect(bot).toEqual([DE['error.micDenied']]);
  });
});

// ── Review zu M-13: Prüfung nach der Transkription, Merker je Aufnahme ───────
describe('Paket 19 Review: Verwerfen auch während der Transkription', () => {
  class Rec {
    state: 'inactive' | 'recording' = 'inactive';
    ondataavailable: ((e: { data: Blob }) => void) | null = null;
    onstop: (() => void) | null = null;
    constructor(readonly stream: MediaStream) {}
    start() { this.state = 'recording'; }
    stop() { this.state = 'inactive'; this.ondataavailable?.({ data: new Blob(['t']) }); this.onstop?.(); }
  }
  const strom = () => ({ getTracks: () => [{ stop() { /* frei */ } }] }) as unknown as MediaStream;

  afterEach(() => {
    vi.unstubAllGlobals();
    delete (navigator as { mediaDevices?: unknown }).mediaDevices;
  });

  it('destroy() während transcribe läuft → das Transkript wird nicht gesendet', async () => {
    vi.stubGlobal('MediaRecorder', Rec);
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true, value: { getUserMedia: async () => strom() },
    });
    let fertig!: (t: string) => void;
    const transcribe = vi.fn(() => new Promise<string>((r) => { fertig = r; }));
    const { ctx, transcript } = makeCtx({ transcribe });
    const svc = new SpeechService(ctx);
    await svc.toggleRecording();
    await svc.toggleRecording();            // stoppt → transcribe läuft
    expect(transcribe).toHaveBeenCalledTimes(1);
    svc.destroy();
    fertig('Geheim');
    await flush();
    expect(transcript).toEqual([]);
  });

  it('der Verwerfen-Merker gilt nur für seine Aufnahme', async () => {
    vi.stubGlobal('MediaRecorder', Rec);
    let freigeben!: (s: MediaStream) => void;
    let aufruf = 0;
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: {
        getUserMedia: () => (++aufruf === 1
          ? new Promise<MediaStream>((r) => { freigeben = r; })
          : Promise.resolve(strom())),
      },
    });
    const transcribe = vi.fn(async () => 'Zwei');
    const { ctx, transcript } = makeCtx({ transcribe });
    const svc = new SpeechService(ctx);
    const erste = svc.toggleRecording();    // wartet auf die Freigabe
    svc.verwerfen();                        // verwirft die erste
    freigeben(strom());
    await erste;
    await svc.toggleRecording();            // zweite Aufnahme
    await svc.toggleRecording();
    await flush();
    expect(transcript).toEqual(['Zwei']);
  });
});
