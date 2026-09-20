import { useState, useCallback, useRef, useEffect } from 'react';

export const useVoice = () => {
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isSupported, setIsSupported] = useState(false);
  const utteranceRef = useRef(null);

  useEffect(() => {
    if ('speechSynthesis' in window) {
      setIsSupported(true);
    }
  }, []);

  const speak = useCallback((text, options = {}) => {
    if (!isSupported) return;

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = options.rate || 0.9;
    utterance.pitch = options.pitch || 1;
    utterance.volume = options.volume || 1;
    utterance.lang = options.lang || 'en-US';

    utterance.onstart = () => setIsSpeaking(true);
    utterance.onend = () => setIsSpeaking(false);
    utterance.onerror = () => setIsSpeaking(false);

    utteranceRef.current = utterance;
    window.speechSynthesis.speak(utterance);
  }, [isSupported]);

  const stop = useCallback(() => {
    if (isSupported) {
      window.speechSynthesis.cancel();
      setIsSpeaking(false);
    }
  }, [isSupported]);

  return { speak, stop, isSpeaking, isSupported };
};

export const useVoiceGuidance = (enabled = true) => {
  const { speak, stop, isSpeaking, isSupported } = useVoice();
  const [guidanceEnabled, setGuidanceEnabled] = useState(enabled);

  const announce = useCallback((text) => {
    if (guidanceEnabled && isSupported) {
      speak(text);
    }
  }, [guidanceEnabled, isSupported, speak]);

  const toggleGuidance = useCallback(() => {
    setGuidanceEnabled(prev => !prev);
    if (!guidanceEnabled) {
      speak('Voice guidance enabled');
    }
  }, [guidanceEnabled, speak]);

  return { announce, toggleGuidance, guidanceEnabled, isSpeaking, isSupported, stop };
};