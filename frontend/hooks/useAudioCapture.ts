'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import {
  AudioCaptureProvider,
  AudioCaptureStatus,
  AudioSourceType,
} from '@/services/audioCapture';

export interface UseAudioCaptureOptions {
  onChunk?: (source: AudioSourceType, chunk: ArrayBuffer) => void;
}

export function useAudioCapture(options: UseAudioCaptureOptions = {}) {
  const [micStatus, setMicStatus] = useState<AudioCaptureStatus>('idle');
  const [tabStatus, setTabStatus] = useState<AudioCaptureStatus>('idle');

  const [micLevel, setMicLevel] = useState(0);
  const [tabLevel, setTabLevel] = useState(0);

  const [micError, setMicError] = useState<string | null>(null);
  const [tabError, setTabError] = useState<string | null>(null);

  const [availableDevices, setAvailableDevices] = useState<MediaDeviceInfo[]>([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState<string>('');

  const providerRef = useRef<AudioCaptureProvider | null>(null);

  // Initialize AudioCaptureProvider once
  useEffect(() => {
    const provider = new AudioCaptureProvider({
      onChunk: (source, chunk) => {
        options.onChunk?.(source, chunk);
      },
      onLevel: (source, level) => {
        if (source === 'mic') {
          setMicLevel(level);
        } else {
          setTabLevel(level);
        }
      },
      onTrackEnded: (source) => {
        if (source === 'mic') {
          setMicStatus('ended');
          setMicLevel(0);
        } else {
          setTabStatus('ended');
          setTabLevel(0);
        }
      },
      onError: (source, error) => {
        const msg = error.message;
        if (source === 'mic') {
          setMicStatus(error.name === 'NotAllowedError' ? 'denied' : 'error');
          setMicError(msg);
          setMicLevel(0);
        } else {
          setTabStatus(error.name === 'NotAllowedError' ? 'denied' : 'error');
          setTabError(msg);
          setTabLevel(0);
        }
      },
    });

    providerRef.current = provider;

    // Load available audio devices
    provider.getAudioInputDevices().then((devices) => {
      setAvailableDevices(devices);
      if (devices.length > 0) {
        setSelectedDeviceId(devices[0].deviceId);
      }
    });

    // Listen for device changes (e.g. mic plugged/unplugged)
    const handleDeviceChange = () => {
      provider.getAudioInputDevices().then((devices) => {
        setAvailableDevices(devices);
      });
    };

    if (navigator.mediaDevices && navigator.mediaDevices.addEventListener) {
      navigator.mediaDevices.addEventListener('devicechange', handleDeviceChange);
    }

    return () => {
      provider.stopAll();
      if (navigator.mediaDevices && navigator.mediaDevices.removeEventListener) {
        navigator.mediaDevices.removeEventListener('devicechange', handleDeviceChange);
      }
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const startMic = useCallback(async () => {
    if (!providerRef.current) return;
    setMicStatus('requesting');
    setMicError(null);
    try {
      await providerRef.current.startMic(selectedDeviceId || undefined);
      setMicStatus('recording');
    } catch {
      // Error handled by callback
    }
  }, [selectedDeviceId]);

  const stopMic = useCallback(() => {
    providerRef.current?.stopMic();
    setMicStatus('idle');
    setMicLevel(0);
  }, []);

  const startTab = useCallback(async () => {
    if (!providerRef.current) return;
    setTabStatus('requesting');
    setTabError(null);
    try {
      await providerRef.current.startTab();
      setTabStatus('recording');
    } catch {
      // Error handled by callback
    }
  }, []);

  const stopTab = useCallback(() => {
    providerRef.current?.stopTab();
    setTabStatus('idle');
    setTabLevel(0);
  }, []);

  const stopAll = useCallback(() => {
    providerRef.current?.stopAll();
    setMicStatus('idle');
    setTabStatus('idle');
    setMicLevel(0);
    setTabLevel(0);
  }, []);

  return {
    micStatus,
    tabStatus,
    micLevel,
    tabLevel,
    micError,
    tabError,
    availableDevices,
    selectedDeviceId,
    setSelectedDeviceId,
    startMic,
    stopMic,
    startTab,
    stopTab,
    stopAll,
  };
}
