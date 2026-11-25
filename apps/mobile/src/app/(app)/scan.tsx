import {
  createCase,
  formatAmount,
  humanize,
  scanInbox,
  type ClaimCandidate,
  type ScanSource,
} from "@karenbot/api-client";
import { router } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Banner, Button, Card, Pill, T } from "@/components/ui";
import { errorMessage } from "@/lib/hooks";
import { colors } from "@/lib/theme";

/** Same color story as the web dashboard: blonde = owed travel money,
 *  red = double-charged, blue = merchandise that never arrived. */
const KIND_COLORS: Record<string, { bg: string; fg: string }> = {
  unused_flight_credit: { bg: colors.bob100, fg: colors.ink900 },
  cancelled_flight: { bg: colors.bob100, fg: colors.ink900 },
  duplicate_charge: { bg: colors.accent100, fg: colors.accent700 },
  failed_delivery: { bg: colors.face100, fg: colors.ink600 },
};

/** Inbox sweep → claimable candidates → one tap to open a case. */
export default function ScanScreen() {
  const insets = useSafeAreaInsets();
  const [scanning, setScanning] = useState(true);
  const [source, setSource] = useState<ScanSource | null>(null);
  const [candidates, setCandidates] = useState<ClaimCandidate[]>([]);
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [startingRef, setStartingRef] = useState<string | null>(null);

  const scan = useCallback(async () => {
    setScanning(true);
    setError(null);
    try {
      const result = await scanInbox();
      setCandidates(result.candidates);
      setSource(result.source);
      setDismissed(new Set());
    } catch (err) {
      setError(errorMessage(err, "Could not scan your inbox — try again."));
    } finally {
      setScanning(false);
    }
  }, []);

  // The user opened this sheet by tapping "Scan my inbox" — start right away.
  useEffect(() => {
    void scan();
  }, [scan]);

  async function startCase(candidate: ClaimCandidate) {
    setStartingRef(candidate.reference);
    setError(null);
    try {
      const numeric =
        candidate.amount !== null && candidate.amount !== ""
          ? Number(candidate.amount)
          : null;
      const created = await createCase({
        company_name: candidate.company_name,
        category: candidate.suggested_category,
        description: `${candidate.title}. ${candidate.snippet}`,
        requested_amount:
          numeric !== null && !Number.isNaN(numeric) ? numeric : null,
        company_industry: candidate.company_industry,
      });
      // Close the sheet, then open the new case on the main stack.
      router.back();
      router.push({
        pathname: "/cases/[id]",
        params: { id: created.case.id },
      });
    } catch (err) {
      setError(
        `Could not start the case: ${errorMessage(err, "try again.")}`,
      );
      setStartingRef(null);
    }
  }

  const visible = candidates.filter((c) => !dismissed.has(c.reference));

  return (
    <ScrollView
      contentContainerStyle={[
        styles.container,
        { paddingBottom: insets.bottom + 24 },
      ]}
    >
      {scanning ? (
        <View style={styles.centered}>
          <ActivityIndicator size="large" color={colors.accent500} />
          <T variant="bodyBold" style={{ marginTop: 16 }}>
            Karen is reading your inbox…
          </T>
        </View>
      ) : (
        <>
          {error !== null && <Banner>{error}</Banner>}

          {source === "mock" && (
            <Banner tone="warn">
              Demo data — connect your email on karencollects.com to scan your
              real inbox.
            </Banner>
          )}

          {error === null && visible.length === 0 && (
            <Card tone="face">
              <T variant="bodyBold">Inbox looks clean</T>
              <T variant="small" color={colors.ink600} style={{ marginTop: 4 }}>
                Nothing worth chasing right now. Karen will be here when
                something goes sideways.
              </T>
            </Card>
          )}

          {visible.map((candidate) => {
            const amount = formatAmount(candidate.amount, "USD");
            const kind = KIND_COLORS[candidate.kind] ?? {
              bg: colors.face100,
              fg: colors.ink600,
            };
            return (
              <Card key={candidate.reference}>
                <View style={styles.cardTop}>
                  <Pill label={humanize(candidate.kind)} bg={kind.bg} fg={kind.fg} />
                  <Pressable
                    accessibilityRole="button"
                    accessibilityLabel={`Dismiss: ${candidate.title}`}
                    hitSlop={12}
                    onPress={() =>
                      setDismissed((prev) => new Set(prev).add(candidate.reference))
                    }
                  >
                    <T variant="bodyBold" color={colors.ink400}>
                      ✕
                    </T>
                  </Pressable>
                </View>
                <View style={styles.titleRow}>
                  <T variant="bodyBold" style={{ flex: 1 }}>
                    {candidate.title}
                  </T>
                  {amount !== null && <T variant="title">{amount}</T>}
                </View>
                <T variant="small" color={colors.ink600} style={{ marginTop: 4 }}>
                  {candidate.snippet}
                </T>
                <T variant="caption" color={colors.ink400} style={{ marginTop: 6 }}>
                  {candidate.company_name} — {humanize(candidate.suggested_category)}
                </T>
                <Button
                  style={{ marginTop: 14 }}
                  loading={startingRef === candidate.reference}
                  disabled={startingRef !== null}
                  onPress={() => void startCase(candidate)}
                >
                  Start a case
                </Button>
              </Card>
            );
          })}

          <Button variant="secondary" onPress={() => void scan()}>
            Scan again
          </Button>
        </>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { padding: 16, gap: 16 },
  centered: { alignItems: "center", paddingTop: 96 },
  cardTop: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  titleRow: {
    marginTop: 10,
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 12,
  },
});
