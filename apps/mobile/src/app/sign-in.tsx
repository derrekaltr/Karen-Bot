import { Image } from "expo-image";
import { useState } from "react";
import { ScrollView, StyleSheet, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Banner, Button, T } from "@/components/ui";
import { useAppAuth } from "@/lib/auth";
import { API_URL } from "@/lib/config";
import { errorMessage } from "@/lib/hooks";
import { colors } from "@/lib/theme";

export default function SignInScreen() {
  const { mode, signIn } = useAppAuth();
  const [busy, setBusy] = useState<"sign-in" | "sign-up" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function start(flow: "sign-in" | "sign-up") {
    setBusy(flow);
    setError(null);
    try {
      await signIn(flow);
      // On success the root guard swaps this screen for the app.
    } catch (err) {
      setError(errorMessage(err, "Sign-in didn't go through — try again."));
    } finally {
      setBusy(null);
    }
  }

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={styles.container}>
        <View style={styles.hero}>
          <Image
            source={require("../../assets/images/karen.png")}
            style={styles.mascot}
            contentFit="contain"
            accessibilityIgnoresInvertColors
            accessible={false}
          />
          <T variant="display" style={styles.center}>
            Stop fighting customer service.
          </T>
          <T variant="body" color={colors.ink600} style={[styles.center, { marginTop: 10 }]}>
            Tell Karen what happened. She contacts the company, negotiates,
            follows up for weeks, and gets your money back.
          </T>
        </View>

        <View style={styles.actions}>
          {error !== null && <Banner>{error}</Banner>}

          {mode === "misconfigured" ? (
            <Banner>
              This build is missing its sign-in configuration
              (EXPO_PUBLIC_CLERK_PUBLISHABLE_KEY).
            </Banner>
          ) : mode === "dev" ? (
            <>
              <Button
                loading={busy !== null}
                onPress={() => void start("sign-in")}
              >
                Continue as demo user
              </Button>
              <T variant="small" color={colors.ink400} style={styles.center}>
                Dev mode — no Clerk key set. Using the seeded demo account
                against {API_URL}.
              </T>
            </>
          ) : (
            <>
              <Button
                loading={busy === "sign-up"}
                disabled={busy !== null}
                onPress={() => void start("sign-up")}
              >
                Get started
              </Button>
              <Button
                variant="secondary"
                loading={busy === "sign-in"}
                disabled={busy !== null}
                onPress={() => void start("sign-in")}
              >
                I already have an account
              </Button>
            </>
          )}

          <T variant="small" color={colors.ink400} style={styles.center}>
            KarenBot is not a law firm and does not provide legal advice.
          </T>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.face100 },
  container: {
    flexGrow: 1,
    justifyContent: "space-between",
    padding: 24,
    gap: 32,
  },
  hero: { alignItems: "center", paddingTop: 32 },
  mascot: { width: 150, height: 152, marginBottom: 24 },
  center: { textAlign: "center" },
  actions: { gap: 14 },
});
