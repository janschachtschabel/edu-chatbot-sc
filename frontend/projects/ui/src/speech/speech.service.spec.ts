import { describe, expect, it, vi, type Mock } from 'vitest';

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
