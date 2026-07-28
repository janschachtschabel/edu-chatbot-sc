/**
 * Speech-Cluster (STT-Recorder + TTS-Playback) — extrahiert aus
 * ``chat.component.ts`` (Frontend-Split Welle 3, Schritt 8, 2026-07-09).
 *
 * Bewusst KEIN ``@Injectable``-Singleton, sondern plain class mit
 * Komponenten-Lebenszeit (Muster: ``MarkdownRenderer``): der gesamte
 * Zustand (MediaRecorder, Audio-Queue, Speaking-Token, Flags) gehört zu
 * genau EINER Chat-Instanz und stirbt mit ihr (``destroy()`` aus
 * ``ngOnDestroy``). Live-Zustand der ChatComponent kommt als
 * :class:`SpeechContext` mit deferred Arrows herein — Feld-Initializer-
 * sicher, kein eagerer ``this.``-Zugriff.
 *
 * Die UI-Flags (``isRecording``/``isSpeaking``/``autoSpeak``/
 * ``recordingSeconds``) leben HIER; die Komponente delegiert per Getter,
 * damit Template-Bindings (``[class.recording]="isRecording"``) und
 * Widget-Zugriffe (``chatRef?.isSpeaking``) unverändert funktionieren.
 *
 * ⚠️ UNGENETZT: jsdom kennt MediaRecorder/getUserMedia/HTMLAudioElement
 * nicht (siehe NICHT-gepinnt-Block in chat.component.spec.ts) — alle
 * Bodies daher strikt verbatim übernommen, KEINE Logik-Änderung. Der Port
 * deckt daher nur die Nicht-Browser-API-Pfade ab (Flag-Toggles, Guards,
 * Selektions-Filter, destroy); Audio/Recorder-Erfolgspfade bleiben wie in
 * ALT ungetestet (live via E2E 8-7).
 *
 * NEU: Imports umgehängt (``ChatMessage`` → ``../grouping/message-types``,
 * TTS-Text-Helfer → ``./tts-text``). Provider-Hinweis: das STT/TTS-Backend
 * ist nur bei ``b-api-openai`` aktiv; bei ``b-api-academiccloud`` sind die
 * Speech-Endpoints ehrlich deaktiviert (#122) — die Widget-Shell gated die
 * Mic/Speaker-Buttons entsprechend, dieser Service bleibt unverändert.
 */
import { ChatMessage } from '../grouping/message-types';
import { splitSentences, stripMarkdown } from './tts-text';

/** Live-Zustand/Seiteneffekte der ChatComponent, die der Speech-Cluster
 *  braucht — als deferred Arrows (Muster: ``MarkdownRenderContext``). */
export interface SpeechContext {
  /** ``ApiService.transcribe`` — STT-Backend (Whisper). */
  transcribe: (blob: Blob) => Promise<string>;
  /** ``ApiService.synthesize`` — TTS-Backend (OpenAI TTS). */
  synthesize: (text: string, signal?: AbortSignal) => Promise<Blob>;
  /** ``NgZone.run`` — Browser-Audio-/Timer-Events feuern außerhalb
   *  Angulars; ohne Zone-Reentry bleiben Indikatoren hängen. */
  runInZone: <T>(fn: () => T) => T;
  /** Erfolgs-Pfad der Transkription: Text ins Eingabefeld übernehmen
   *  und als Nachricht senden (``userInput`` + ``sendMessage()``). */
  onTranscript: (text: string) => void;
  /** Fehler-Bubble in den Chat stellen (``addBotMessage``-Kurzform). */
  addBotMessage: (content: string) => void;
  /** Live-Zugriff auf die Message-Liste — ``toggleAutoSpeak`` liest die
   *  letzte fertige Bot-Nachricht für die Sofort-Bestätigung. */
  messages: () => ChatMessage[];
}

export class SpeechService {
  // ── UI-Flags (Komponente delegiert per Getter) ──────────────────
  isRecording = false;
  isSpeaking = false;
  autoSpeak = false;
  recordingSeconds = 0;

  // ── Recorder-State ──────────────────────────────────────────────
  private mediaRecorder: MediaRecorder | null = null;
  private audioChunks: Blob[] = [];
  private recordingTimer: ReturnType<typeof setInterval> | null = null;
  private speechBusy = false; // guard against double-click

  // ── TTS-State ───────────────────────────────────────────────────
  private currentAudio: HTMLAudioElement | null = null;
  /** Monotonically increasing token for the active speakChunked call.
   *  Each new call bumps it; older callers compare against this on exit
   *  and skip resetting ``isSpeaking`` if they've been superseded. Stops
   *  the "spricht …" indicator from sticking when a sentence's audio
   *  ``onended`` fires unusually late or when speakChunked is overlapped
   *  by a new turn's auto-speak. */
  private speakingToken = 0;
  // Audio queue for sentence-chunked OpenAI TTS
  private audioQueue: Blob[] = [];
  private audioAbort: AbortController | null = null;

  constructor(private readonly ctx: SpeechContext) {}

  // ── Recorder (STT) ──────────────────────────────────────────────
  async toggleRecording() {
    if (this.speechBusy) return; // guard
    if (this.isRecording) {
      this.stopRecording();
    } else {
      this.speechBusy = true;
      // Set UI immediately BEFORE async mic request
      this.isRecording = true;
      this.recordingSeconds = 0;
      try {
        await this.startRecording();
      } catch {
        // 8-6/zoneless: diese Rücknahme passiert NACH einem `await` (typischer
        // Fall: der Nutzer verweigert den Mikrofon-Zugriff), also außerhalb des
        // Klick-Turns. Ohne `runInZone` plant nichts eine Prüfung — der
        // Mikro-Button bliebe im Aufnahme-Zustand und das Eingabefeld gesperrt.
        // In ALT übernahm das zone.js.
        this.ctx.runInZone(() => { this.isRecording = false; });
      }
      this.speechBusy = false;
    }
  }

  private async startRecording() {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    this.mediaRecorder = new MediaRecorder(stream);
    this.audioChunks = [];

    this.mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) this.audioChunks.push(e.data);
    };

    this.mediaRecorder.onstop = () => {
      const blob = new Blob(this.audioChunks, { type: 'audio/webm' });
      stream.getTracks().forEach(t => t.stop());

      this.ctx.runInZone(async () => {
        this.isRecording = false;
        this.stopRecordingTimer();

        try {
          const text = await this.ctx.transcribe(blob);
          if (text) {
            this.ctx.onTranscript(text);
          }
        } catch (err) {
          console.error('Transcription error:', err);
          this.ctx.addBotMessage('Spracheingabe konnte nicht verarbeitet werden. Bitte tippe deine Nachricht.');
        }
      });
    };

    this.mediaRecorder.start();
    // Start timer (isRecording already set in toggleRecording)
    this.recordingTimer = setInterval(() => {
      this.ctx.runInZone(() => { this.recordingSeconds++; });
    }, 1000);
  }

  private stopRecording() {
    this.stopRecordingTimer();
    if (this.mediaRecorder && this.mediaRecorder.state === 'recording') {
      this.mediaRecorder.stop(); // triggers onstop → sets isRecording=false in zone
    } else {
      this.isRecording = false;
    }
  }

  private stopRecordingTimer() {
    if (this.recordingTimer) {
      clearInterval(this.recordingTimer);
      this.recordingTimer = null;
    }
    this.recordingSeconds = 0;
  }

  // ── TTS ─────────────────────────────────────────────────────────
  /**
   * Manual toggle (speaker button on a message): click while speaking stops;
   * click while idle starts TTS.
   */
  speakText(text: string) {
    if (this.isSpeaking) {
      this.stopSpeaking();
      return;
    }
    const plain = stripMarkdown(text);
    this.isSpeaking = true;
    this.speakChunked(plain);
  }

  /**
   * Auto-speak entry point: always plays the given text. If a prior
   * TTS playback is still running, it is aborted first so the new
   * response is spoken immediately. Used when `autoSpeak` is on and
   * a new bot response arrives (the user may have interrupted the
   * previous response by sending the next message).
   */
  autoSpeakText(text: string) {
    if (this.isSpeaking) {
      this.stopSpeaking();
    }
    const plain = stripMarkdown(text);
    if (!plain) return;
    this.isSpeaking = true;
    this.speakChunked(plain);
  }

  /**
   * Split text into sentences, fetch OpenAI TTS for each, and play them
   * in sequence — pre-fetching the next sentence while the current one plays.
   * Falls back to browser speechSynthesis if the backend TTS fails.
   */
  private async speakChunked(text: string) {
    // Identify this run so any later overlap (a new auto-speak fired
    // while we were still playing the previous one) can suppress our
    // ``isSpeaking = false`` reset and avoid clobbering its own state.
    const myToken = ++this.speakingToken;
    const finish = () => {
      // Always run inside Angular's zone so the widget header re-renders
      // when the binding ``chatRef?.isSpeaking`` flips. Browser audio
      // events fire outside NgZone, so a plain assignment can leave the
      // ``spricht …`` indicator stuck on screen.
      if (this.speakingToken === myToken) {
        this.ctx.runInZone(() => { this.isSpeaking = false; });
      }
    };

    const sentences = splitSentences(text);
    if (!sentences.length) { finish(); return; }

    this.audioQueue = [];
    this.audioAbort = new AbortController();
    const signal = this.audioAbort.signal;

    try {
      // Pre-fetch first sentence
      let nextFetch: Promise<Blob | null> = this.fetchTTS(sentences[0], signal);

      for (let i = 0; i < sentences.length; i++) {
        if (signal.aborted) break;

        // Await current sentence audio
        const blob = await nextFetch;
        if (signal.aborted || !blob) break;

        // Start pre-fetching next sentence while current one plays
        if (i + 1 < sentences.length) {
          nextFetch = this.fetchTTS(sentences[i + 1], signal);
        }

        // Play current sentence
        await this.playBlob(blob, signal);
      }
    } finally {
      // Always reset (token-guarded so we don't fight an overlapping run).
      // Without the finally, an early ``break`` from ``signal.aborted`` —
      // or any unexpected exception — would leave isSpeaking stuck true.
      finish();
    }
  }

  private async fetchTTS(text: string, signal: AbortSignal): Promise<Blob | null> {
    try {
      return await this.ctx.synthesize(text, signal);
    } catch {
      return null;
    }
  }

  private playBlob(blob: Blob, signal: AbortSignal): Promise<void> {
    return new Promise((resolve) => {
      if (signal.aborted) { resolve(); return; }

      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      this.currentAudio = audio;

      // Watchdog: in rare browser bugs ``onended``/``onerror`` may never
      // fire (e.g. lost focus, autoplay throttle). Without this guard the
      // outer speakChunked Promise hangs and ``isSpeaking`` stays true
      // until the next user turn. Cap at ~max(audio.duration, 90s) plus
      // a 5s safety margin; if the metadata isn't loaded yet, a flat 90s
      // is the upper bound — much longer than any single TTS sentence.
      let watchdog: ReturnType<typeof setTimeout> | null = null;
      const armWatchdog = () => {
        const dur = isFinite(audio.duration) && audio.duration > 0
          ? Math.ceil(audio.duration * 1000) + 5000
          : 90_000;
        watchdog = setTimeout(() => { cleanup(); resolve(); }, dur);
      };

      const cleanup = () => {
        if (watchdog != null) { clearTimeout(watchdog); watchdog = null; }
        URL.revokeObjectURL(url);
        this.currentAudio = null;
      };

      audio.onended = () => { cleanup(); resolve(); };
      audio.onerror = () => { cleanup(); resolve(); };
      audio.onloadedmetadata = () => { armWatchdog(); };

      // Listen for abort to stop mid-playback
      const onAbort = () => { audio.pause(); cleanup(); resolve(); };
      signal.addEventListener('abort', onAbort, { once: true });

      audio.play().catch(() => { cleanup(); resolve(); });
      // Arm a coarse watchdog up-front in case loadedmetadata never fires
      // (network issue, malformed blob). Will be replaced by the precise
      // duration-based one once metadata loads.
      if (watchdog == null) {
        watchdog = setTimeout(() => { cleanup(); resolve(); }, 90_000);
      }
    });
  }

  private stopSpeaking() {
    // Abort any in-flight TTS fetches and queued playback
    if (this.audioAbort) {
      this.audioAbort.abort();
      this.audioAbort = null;
    }
    if (this.currentAudio) {
      this.currentAudio.pause();
      this.currentAudio = null;
    }
    this.audioQueue = [];
    // Bump the token so any old speakChunked still unwinding can't undo
    // this hard stop in its ``finally`` cleanup.
    this.speakingToken++;
    this.isSpeaking = false;
  }

  toggleAutoSpeak() {
    this.autoSpeak = !this.autoSpeak;
    // When enabling, immediately speak the last bot message so the user
    // gets audio confirmation that it works.
    if (this.autoSpeak) {
      const msgs = this.ctx.messages();
      for (let i = msgs.length - 1; i >= 0; i--) {
        const m = msgs[i];
        if (m.sender === 'bot' && m.content && !m.isLoading) {
          this.autoSpeakText(m.content);
          break;
        }
      }
    } else {
      // When disabling, stop any currently playing audio
      this.stopSpeaking();
    }
  }

  /** Teardown aus ``ChatComponent.ngOnDestroy`` (B9, 2026-06-10):
   *  laufende Aufnahme/TTS beim Zerstören stoppen — sonst bleibt das
   *  Mikrofon aktiv (Privacy!), der Recording-Timer tickt weiter und
   *  eine laufende Sprachausgabe spielt ins Leere. */
  destroy(): void {
    try { this.stopRecording(); } catch { /* ignore */ }
    try {
      (this.mediaRecorder as any)?.stream?.getTracks?.()
        ?.forEach((t: MediaStreamTrack) => t.stop());
    } catch { /* ignore */ }
    try { this.stopSpeaking(); } catch { /* ignore */ }
  }
}
