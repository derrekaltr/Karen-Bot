import * as SecureStore from "expo-secure-store";
import { useEffect, useState } from "react";
import { View } from "react-native";
import { Banner, Button, Card, T } from "@/components/ui";
import { permissionState, registerForPush } from "@/lib/push";
import { colors } from "@/lib/theme";

const DISMISSED_KEY = "push-optin-dismissed-v1";

/**
 * Ask for notifications in context — once the customer has a case Karen is
 * working, not at launch — so the iOS prompt arrives with a reason. Shown
 * only while permission is undetermined; "Not now" is remembered.
 */
export function NotificationOptIn({ visible }: { visible: boolean }) {
  const [state, setState] = useState<"hidden" | "ask" | "busy" | "error">("hidden");

  useEffect(() => {
    if (!visible) return;
    let cancelled = false;
    (async () => {
      const [permission, dismissed] = await Promise.all([
        permissionState(),
        SecureStore.getItemAsync(DISMISSED_KEY).catch(() => null),
      ]);
      if (!cancelled && permission === "undetermined" && dismissed !== "1") {
        setState("ask");
      }
    })().catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [visible]);

  if (!visible || state === "hidden") return null;

  async function enable() {
    setState("busy");
    try {
      await registerForPush({ prompt: true });
      setState("hidden"); // granted or declined, iOS has had its say
    } catch {
      setState("error");
    }
  }

  function dismiss() {
    void SecureStore.setItemAsync(DISMISSED_KEY, "1").catch(() => {});
    setState("hidden");
  }

  return (
    <Card tone="face" style={{ marginBottom: 8 }}>
      <T variant="title">Get a ping when Karen needs you</T>
      <T variant="small" color={colors.ink600} style={{ marginTop: 6 }}>
        Companies make offers on their own schedule. Karen will tell you the
        moment one needs your call — and never accepts anything binding
        without you.
      </T>
      {state === "error" && (
        <View style={{ marginTop: 10 }}>
          <Banner>Couldn&apos;t turn on notifications — try again.</Banner>
        </View>
      )}
      <View style={{ marginTop: 14, gap: 10 }}>
        <Button loading={state === "busy"} onPress={() => void enable()}>
          Turn on notifications
        </Button>
        <Button variant="secondary" disabled={state === "busy"} onPress={dismiss}>
          Not now
        </Button>
      </View>
    </Card>
  );
}
