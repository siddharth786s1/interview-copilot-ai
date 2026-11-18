/**
 * AudioCaptureProvider — Browser Audio Capture Engine
 *
 * Captures two independent audio streams:
 * 1. Microphone (user speech) via getUserMedia
 * 2. Shared Tab/System audio (interviewer speech) via getDisplayMedia
 *
 * Features:
 * - Independent start/stop for mic and tab
 * - PCM chunk conversion (16kHz 16-bit mono) with source header byte (0x01: mic, 0x02: tab)
 * - Real-time RMS audio level calculation (0.0 to 1.0)
 * - Visible track-ended, permission denial, and device change handling
 */

export type AudioSourceType = 'mic' | 'tab';

export type AudioCaptureStatus =
  | 'idle'
  | 'requesting'
  | 'recording'
  | 'denied'
  | 'ended'
  | 'error';

export interface AudioCaptureCallbacks {
  onChunk?: (source: AudioSourceType, chunk: ArrayBuffer) => void;
  onLevel?: (source: AudioSourceType, level: number) => void;
  onTrackEnded?: (source: AudioSourceType) => void;
  onError?: (source: AudioSourceType, error: Error) => void;
}

export class TabAudioMissingError extends Error {
  constructor() {
    super(
      "No audio track was found. When selecting the browser tab, make sure the 'Also share tab audio' checkbox is enabled."
    );
    this.name = 'TabAudioMissingError';
  }
}

export class AudioCaptureProvider {
  private micStream: MediaStream | null = null;
  private tabStream: MediaStream | null = null;

  private micAudioContext: AudioContext | null = null;
  private tabAudioContext: AudioContext | null = null;

  private micProcessor: ScriptProcessorNode | null = null;
  private tabProcessor: ScriptProcessorNode | null = null;

  private callbacks: AudioCaptureCallbacks;

  constructor(callbacks: AudioCaptureCallbacks = {}) {
    this.callbacks = callbacks;
  }

  setCallbacks(callbacks: AudioCaptureCallbacks) {
    this.callbacks = { ...this.callbacks, ...callbacks };
  }

  /**
   * Enumerate available audio input devices (microphones)
   */
  async getAudioInputDevices(): Promise<MediaDeviceInfo[]> {
    if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) {
      return [];
    }
    const devices = await navigator.mediaDevices.enumerateDevices();
    return devices.filter((d) => d.kind === 'audioinput');
  }

  /**
   * Start microphone audio capture (User voice)
   */
  async startMic(deviceId?: string): Promise<MediaStream> {
    this.stopMic();

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      const err = new Error('Microphone audio capture is not supported in this browser.');
      this.callbacks.onError?.('mic', err);
      throw err;
    }

    try {
      const constraints: MediaStreamConstraints = {
        audio: {
          deviceId: deviceId ? { exact: deviceId } : undefined,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          sampleRate: 16000,
        },
        video: false,
      };

      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      this.micStream = stream;

      const audioTrack = stream.getAudioTracks()[0];
      if (audioTrack) {
        audioTrack.onended = () => {
          this.callbacks.onTrackEnded?.('mic');
          this.stopMic();
        };
      }

      this.setupAudioPipeline('mic', stream);
      return stream;
    } catch (err: unknown) {
      const error = err instanceof Error ? err : new Error(String(err));
      this.callbacks.onError?.('mic', error);
      throw error;
    }
  }

  /**
   * Start tab/system audio capture (Interviewer voice via Google Meet tab)
   */
  async startTab(): Promise<MediaStream> {
    this.stopTab();

    if (!navigator.mediaDevices || !navigator.mediaDevices.getDisplayMedia) {
      const err = new Error('Tab audio capture (getDisplayMedia) is not supported in this browser.');
      this.callbacks.onError?.('tab', err);
      throw err;
    }

    try {
      // getDisplayMedia requires video: true in almost all browsers
      const displayStream = await navigator.mediaDevices.getDisplayMedia({
        video: true,
        audio: true,
      });

      // Check if user selected "Share audio"
      const audioTracks = displayStream.getAudioTracks();
      if (!audioTracks || audioTracks.length === 0) {
        // Stop video immediately and throw error
        displayStream.getTracks().forEach((t) => t.stop());
        const err = new TabAudioMissingError();
        this.callbacks.onError?.('tab', err);
        throw err;
      }

      // Stop video track immediately — we only need audio!
      displayStream.getVideoTracks().forEach((t) => t.stop());

      // Create a clean audio-only MediaStream
      const audioStream = new MediaStream(audioTracks);
      this.tabStream = audioStream;

      const audioTrack = audioTracks[0];
      audioTrack.onended = () => {
        this.callbacks.onTrackEnded?.('tab');
        this.stopTab();
      };

      this.setupAudioPipeline('tab', audioStream);
      return audioStream;
    } catch (err: unknown) {
      const error = err instanceof Error ? err : new Error(String(err));
      this.callbacks.onError?.('tab', error);
      throw error;
    }
  }

  /**
   * Setup Web Audio pipeline: Analyser for RMS level + ScriptProcessor for 16kHz PCM chunks
   */
  private setupAudioPipeline(source: AudioSourceType, stream: MediaStream) {
    const AudioCtxClass = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    const ctx = new AudioCtxClass();

    if (source === 'mic') {
      this.micAudioContext = ctx;
    } else {
      this.tabAudioContext = ctx;
    }

    const sourceNode = ctx.createMediaStreamSource(stream);
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 512;
    sourceNode.connect(analyser);

    // Buffer size: 4096 samples at audioCtx sample rate (~85ms chunks)
    const processor = ctx.createScriptProcessor(4096, 1, 1);
    analyser.connect(processor);
    processor.connect(ctx.destination);

    if (source === 'mic') {
      this.micProcessor = processor;
    } else {
      this.tabProcessor = processor;
    }

    const timeData = new Uint8Array(analyser.frequencyBinCount);

    processor.onaudioprocess = (event) => {
      // 1. Calculate RMS volume level
      analyser.getByteTimeDomainData(timeData);
      let sum = 0;
      for (let i = 0; i < timeData.length; i++) {
        const val = (timeData[i] - 128) / 128;
        sum += val * val;
      }
      const rms = Math.sqrt(sum / timeData.length);
      // Normalize level roughly 0.0 to 1.0 with a curve for visual responsiveness
      const level = Math.min(1.0, rms * 4.0);
      this.callbacks.onLevel?.(source, level);

      // 2. Downsample input float32 buffer to 16kHz 16-bit PCM
      const inputBuffer = event.inputBuffer.getChannelData(0);
      const inputSampleRate = ctx.sampleRate;
      const targetSampleRate = 16000;

      const pcmData = this.resampleTo16BitPCM(inputBuffer, inputSampleRate, targetSampleRate);

      // 3. Prepend source header byte: 0x01 for mic, 0x02 for tab
      const headerByte = source === 'mic' ? 0x01 : 0x02;
      const payload = new Uint8Array(pcmData.byteLength + 1);
      payload[0] = headerByte;
      payload.set(new Uint8Array(pcmData), 1);

      this.callbacks.onChunk?.(source, payload.buffer);
    };
  }

  /**
   * Resamples float32 PCM to 16kHz 16-bit linear PCM ArrayBuffer
   */
  private resampleTo16BitPCM(
    inputBuffer: Float32Array,
    inputSampleRate: number,
    targetSampleRate: number
  ): ArrayBuffer {
    if (targetSampleRate === inputSampleRate) {
      const output = new Int16Array(inputBuffer.length);
      for (let i = 0; i < inputBuffer.length; i++) {
        const s = Math.max(-1, Math.min(1, inputBuffer[i]));
        output[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
      }
      return output.buffer;
    }

    const ratio = inputSampleRate / targetSampleRate;
    const outputLength = Math.round(inputBuffer.length / ratio);
    const output = new Int16Array(outputLength);

    for (let i = 0; i < outputLength; i++) {
      const srcIndex = Math.min(Math.round(i * ratio), inputBuffer.length - 1);
      const s = Math.max(-1, Math.min(1, inputBuffer[srcIndex]));
      output[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }
    return output.buffer;
  }

  stopMic() {
    if (this.micStream) {
      this.micStream.getTracks().forEach((t) => t.stop());
      this.micStream = null;
    }
    if (this.micProcessor) {
      this.micProcessor.disconnect();
      this.micProcessor = null;
    }
    if (this.micAudioContext && this.micAudioContext.state !== 'closed') {
      this.micAudioContext.close().catch(() => {});
      this.micAudioContext = null;
    }
    this.callbacks.onLevel?.('mic', 0);
  }

  stopTab() {
    if (this.tabStream) {
      this.tabStream.getTracks().forEach((t) => t.stop());
      this.tabStream = null;
    }
    if (this.tabProcessor) {
      this.tabProcessor.disconnect();
      this.tabProcessor = null;
    }
    if (this.tabAudioContext && this.tabAudioContext.state !== 'closed') {
      this.tabAudioContext.close().catch(() => {});
      this.tabAudioContext = null;
    }
    this.callbacks.onLevel?.('tab', 0);
  }

  stopAll() {
    this.stopMic();
    this.stopTab();
  }

  isMicActive(): boolean {
    return !!(this.micStream && this.micStream.active);
  }

  isTabActive(): boolean {
    return !!(this.tabStream && this.tabStream.active);
  }
}
