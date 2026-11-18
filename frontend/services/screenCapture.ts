/**
 * Permitted browser Screen Capture Engine using standard getDisplayMedia().
 *
 * - Always requests explicit user permission via the browser's screen-picker dialog.
 * - Never covert: callers display an active indicator + live miniature preview.
 * - Downscales frames to a clean JPEG (<= 1280px wide) and computes a lightweight
 *   32x18 grayscale diff score so Auto-Watch skips unchanged screens.
 */

export interface CapturedScreenFrame {
  blob: Blob;
  dataUrl: string;
  width: number;
  height: number;
  diffScore: number; // 0.0 (identical) to 1.0 (completely changed)
}

export interface ScreenCaptureCallbacks {
  onTrackEnded?: () => void;
  onError?: (message: string) => void;
}

const DIFF_W = 32;
const DIFF_H = 18;

export class ScreenCaptureProvider {
  private stream: MediaStream | null = null;
  private video: HTMLVideoElement | null = null;
  private captureCanvas: HTMLCanvasElement | null = null;
  private diffCanvas: HTMLCanvasElement | null = null;
  private lastGrayscale: Uint8Array | null = null;
  private callbacks: ScreenCaptureCallbacks;

  constructor(callbacks: ScreenCaptureCallbacks = {}) {
    this.callbacks = callbacks;
  }

  get isActive(): boolean {
    return Boolean(
      this.stream &&
        this.stream.getVideoTracks().some((t) => t.readyState === 'live')
    );
  }

  async start(): Promise<void> {
    if (this.isActive) return;

    if (typeof navigator === 'undefined' || !navigator.mediaDevices?.getDisplayMedia) {
      const msg = 'Screen sharing (getDisplayMedia) is not supported in this browser.';
      this.callbacks.onError?.(msg);
      throw new Error(msg);
    }

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getDisplayMedia({
        video: {
          frameRate: { ideal: 2, max: 5 },
        },
        audio: false,
      });
    } catch (err: unknown) {
      const name = err instanceof DOMException ? err.name : '';
      const msg =
        name === 'NotAllowedError'
          ? 'Screen sharing permission was cancelled or denied.'
          : err instanceof Error
          ? err.message
          : 'Failed to start screen capture.';
      this.callbacks.onError?.(msg);
      throw new Error(msg);
    }

    const videoTrack = stream.getVideoTracks()[0];
    if (!videoTrack) {
      stream.getTracks().forEach((t) => t.stop());
      const msg = 'No video track was shared.';
      this.callbacks.onError?.(msg);
      throw new Error(msg);
    }

    videoTrack.addEventListener('ended', () => {
      this.stop();
      this.callbacks.onTrackEnded?.();
    });

    const video = document.createElement('video');
    video.srcObject = stream;
    video.muted = true;
    video.playsInline = true;

    await new Promise<void>((resolve, reject) => {
      const onLoaded = () => {
        video.removeEventListener('loadedmetadata', onLoaded);
        video.play().then(() => resolve()).catch(reject);
      };
      video.addEventListener('loadedmetadata', onLoaded);
    });

    this.stream = stream;
    this.video = video;
    this.captureCanvas = document.createElement('canvas');
    this.diffCanvas = document.createElement('canvas');
    this.diffCanvas.width = DIFF_W;
    this.diffCanvas.height = DIFF_H;
    this.lastGrayscale = null;
  }

  /**
   * Capture a single JPEG frame from the active screen stream.
   * Returns a blob suitable for multipart upload, a thumbnail data URL, and a frame-diff score.
   */
  async captureFrame(
    maxWidth = 1280,
    quality = 0.78,
    commitDiffBaseline = true
  ): Promise<CapturedScreenFrame> {
    if (!this.isActive || !this.video || !this.captureCanvas || !this.diffCanvas) {
      throw new Error('Screen capture is not active.');
    }

    const vw = this.video.videoWidth;
    const vh = this.video.videoHeight;
    if (!vw || !vh) {
      throw new Error('Shared screen video frame is not ready yet.');
    }

    const scale = vw > maxWidth ? maxWidth / vw : 1;
    const targetW = Math.max(1, Math.round(vw * scale));
    const targetH = Math.max(1, Math.round(vh * scale));

    this.captureCanvas.width = targetW;
    this.captureCanvas.height = targetH;
    const ctx = this.captureCanvas.getContext('2d');
    if (!ctx) {
      throw new Error('Failed to initialize 2D capture canvas.');
    }
    ctx.drawImage(this.video, 0, 0, targetW, targetH);

    // Lightweight 32x18 grayscale diff against previous analyzed frame
    const diffCtx = this.diffCanvas.getContext('2d', { willReadFrequently: true });
    let diffScore = 1.0;
    let currentGray: Uint8Array | null = null;
    if (diffCtx) {
      diffCtx.drawImage(this.video, 0, 0, DIFF_W, DIFF_H);
      const pixels = diffCtx.getImageData(0, 0, DIFF_W, DIFF_H).data;
      currentGray = new Uint8Array(DIFF_W * DIFF_H);
      for (let i = 0, p = 0; i < currentGray.length; i++, p += 4) {
        currentGray[i] = (pixels[p] * 77 + pixels[p + 1] * 150 + pixels[p + 2] * 29) >> 8;
      }
      if (this.lastGrayscale) {
        let totalDiff = 0;
        for (let i = 0; i < currentGray.length; i++) {
          totalDiff += Math.abs(currentGray[i] - this.lastGrayscale[i]);
        }
        diffScore = totalDiff / (currentGray.length * 255);
      }
      if (commitDiffBaseline) {
        this.lastGrayscale = currentGray;
      }
    }

    const dataUrl = this.captureCanvas.toDataURL('image/jpeg', 0.55);
    const blob = await new Promise<Blob>((resolve, reject) => {
      this.captureCanvas!.toBlob(
        (b) => {
          if (b) resolve(b);
          else reject(new Error('Failed to encode screen capture JPEG.'));
        },
        'image/jpeg',
        quality
      );
    });

    return {
      blob,
      dataUrl,
      width: targetW,
      height: targetH,
      diffScore,
    };
  }

  /** Reset diff baseline so the next Auto-Watch tick always evaluates the current screen. */
  resetDiffBaseline(): void {
    this.lastGrayscale = null;
  }

  stop(): void {
    if (this.stream) {
      this.stream.getTracks().forEach((t) => t.stop());
      this.stream = null;
    }
    if (this.video) {
      this.video.srcObject = null;
      this.video = null;
    }
    this.captureCanvas = null;
    this.diffCanvas = null;
    this.lastGrayscale = null;
  }
}
