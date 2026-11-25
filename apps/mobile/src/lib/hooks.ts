import { useFocusEffect } from "expo-router";
import { useCallback, useEffect, useRef, useState } from "react";
import { AppState } from "react-native";
import { ApiError } from "@karenbot/api-client";

/** Human-readable message from anything a fetch can throw. */
export function errorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError) return err.detail;
  if (err instanceof TypeError) {
    // React Native's fetch throws TypeError("Network request failed").
    return "Can't reach KarenBot right now — check your connection.";
  }
  if (err instanceof Error) return err.message;
  return fallback;
}

/**
 * Re-run `tick` every `intervalMs` while the screen is focused and the app
 * is in the foreground — and immediately when either comes back.
 * Pass `enabled: false` to stop (e.g. once a case reaches a terminal state).
 */
export function useFocusedPolling(
  tick: () => void,
  intervalMs: number,
  enabled: boolean,
): void {
  const tickRef = useRef(tick);
  tickRef.current = tick;
  const [appActive, setAppActive] = useState(AppState.currentState === "active");

  useEffect(() => {
    const sub = AppState.addEventListener("change", (state) => {
      setAppActive(state === "active");
    });
    return () => sub.remove();
  }, []);

  useFocusEffect(
    useCallback(() => {
      if (!enabled || !appActive) return;
      tickRef.current();
      const timer = setInterval(() => tickRef.current(), intervalMs);
      return () => clearInterval(timer);
    }, [enabled, appActive, intervalMs]),
  );
}
