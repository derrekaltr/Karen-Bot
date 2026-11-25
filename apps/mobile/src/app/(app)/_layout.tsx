import * as Notifications from "expo-notifications";
import { Stack, router } from "expo-router";
import { useEffect, useRef } from "react";
import { Platform } from "react-native";
import { caseIdFrom, registerForPush } from "@/lib/push";
import { colors, fonts } from "@/lib/theme";

export default function AppLayout() {
  usePushRegistration();
  useNotificationTaps();

  return (
    <Stack
      screenOptions={{
        headerShadowVisible: false,
        headerStyle: { backgroundColor: colors.white },
        headerTintColor: colors.ink900,
        headerTitleStyle: { fontFamily: fonts.display, fontSize: 17 },
        headerLargeTitleStyle: { fontFamily: fonts.display },
        headerBackButtonDisplayMode: "minimal",
        contentStyle: { backgroundColor: colors.white },
      }}
    >
      <Stack.Screen name="index" options={{ title: "Your cases" }} />
      <Stack.Screen name="cases/[id]" options={{ title: "Case" }} />
      <Stack.Screen
        name="scan"
        options={{ title: "Karen found money", presentation: "modal" }}
      />
    </Stack>
  );
}

/** Signed in + already allowed → (re)register the token. Never prompts. */
function usePushRegistration() {
  useEffect(() => {
    registerForPush({ prompt: false }).catch(() => {
      // Offline or API down: next launch retries.
    });
  }, []);
}

/**
 * Tapping a Karen notification opens its case — whether the app was
 * running or cold-started by the tap. Mounted only while signed in, so a
 * tap that launched the app before sign-in is handled right after it.
 */
function useNotificationTaps() {
  const handled = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (Platform.OS === "web") return; // no notification responses on web

    function open(response: Notifications.NotificationResponse | null) {
      if (!response) return;
      if (response.actionIdentifier !== Notifications.DEFAULT_ACTION_IDENTIFIER) return;
      const id = response.notification.request.identifier;
      if (handled.current.has(id)) return;
      handled.current.add(id);
      const caseId = caseIdFrom(response.notification);
      if (caseId !== null) {
        router.push({ pathname: "/cases/[id]", params: { id: caseId } });
      }
      void Notifications.clearLastNotificationResponseAsync();
    }

    // Cold start: the tap that launched the app.
    Notifications.getLastNotificationResponseAsync()
      .then(open)
      .catch(() => {});
    // Warm: taps while the app is running or backgrounded.
    const sub = Notifications.addNotificationResponseReceivedListener(open);
    return () => sub.remove();
  }, []);
}
