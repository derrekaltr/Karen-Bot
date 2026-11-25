import {
  TERMINAL_STATUSES,
  formatAmount,
  humanize,
  listCases,
  type Case,
  type CaseStatus,
} from "@karenbot/api-client";
import { Image } from "expo-image";
import { Link, Stack, router } from "expo-router";
import { useCallback, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  RefreshControl,
  SectionList,
  StyleSheet,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Banner, Button, Card, StatusBadge, T } from "@/components/ui";
import { useAppAuth } from "@/lib/auth";
import { errorMessage, useFocusedPolling } from "@/lib/hooks";
import { colors } from "@/lib/theme";

/** Statuses where the case is waiting on the customer, not on Karen. */
const NEEDS_YOU: ReadonlySet<CaseStatus> = new Set([
  "AWAITING_INFORMATION",
  "AWAITING_AUTHORIZATION",
  "READY_TO_CONTACT",
  "AWAITING_CUSTOMER_APPROVAL",
  "VERIFYING_RECOVERY",
]);

const NEEDS_YOU_HINT: Partial<Record<CaseStatus, string>> = {
  AWAITING_INFORMATION: "Karen has questions for you",
  AWAITING_AUTHORIZATION: "Sign so Karen can act for you",
  READY_TO_CONTACT: "Say the word and Karen goes",
  AWAITING_CUSTOMER_APPROVAL: "An offer needs your call",
  VERIFYING_RECOVERY: "Did the money land?",
};

const REFRESH_INTERVAL_MS = 15_000;

interface Section {
  title: string;
  data: Case[];
}

export default function CasesScreen() {
  const insets = useSafeAreaInsets();
  const { signOut, mode } = useAppAuth();
  const [cases, setCases] = useState<Case[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      setCases(await listCases());
      setError(null);
    } catch (err) {
      setError(errorMessage(err, "Could not load your cases."));
    }
  }, []);

  // Refreshes on focus (e.g. coming back from a case) and every 15s.
  useFocusedPolling(() => void load(), REFRESH_INTERVAL_MS, true);

  async function onRefresh() {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }

  const sections = useMemo<Section[]>(() => {
    if (cases === null) return [];
    const needsYou = cases.filter((c) => NEEDS_YOU.has(c.status));
    const done = cases.filter((c) => TERMINAL_STATUSES.has(c.status));
    const working = cases.filter(
      (c) => !NEEDS_YOU.has(c.status) && !TERMINAL_STATUSES.has(c.status),
    );
    return [
      { title: "Needs you", data: needsYou },
      { title: "Karen's on it", data: working },
      { title: "Closed", data: done },
    ].filter((s) => s.data.length > 0);
  }, [cases]);

  function confirmSignOut() {
    Alert.alert(
      mode === "dev" ? "Leave demo mode?" : "Sign out?",
      "Karen keeps working on your open cases while you're signed out.",
      [
        { text: "Cancel", style: "cancel" },
        { text: "Sign out", style: "destructive", onPress: () => void signOut() },
      ],
    );
  }

  return (
    <View style={styles.screen}>
      <Stack.Screen
        options={{
          headerRight: () => (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Account"
              hitSlop={12}
              onPress={confirmSignOut}
            >
              <T variant="caption" color={colors.accent600}>
                {mode === "dev" ? "Demo" : "Account"}
              </T>
            </Pressable>
          ),
        }}
      />

      {cases === null && error === null ? (
        <View style={styles.centered}>
          <ActivityIndicator color={colors.accent500} />
        </View>
      ) : (
        <SectionList
          sections={sections}
          keyExtractor={(c) => c.id}
          contentContainerStyle={[
            styles.list,
            { paddingBottom: insets.bottom + 110 },
          ]}
          stickySectionHeadersEnabled={false}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => void onRefresh()}
              tintColor={colors.accent500}
            />
          }
          ListHeaderComponent={
            error !== null ? (
              <View style={{ marginBottom: 16 }}>
                <Banner>{`Could not load your cases: ${error}`}</Banner>
              </View>
            ) : undefined
          }
          renderSectionHeader={({ section }) => (
            <T variant="title" style={styles.sectionTitle}>
              {section.title}
            </T>
          )}
          renderItem={({ item }) => <CaseRow item={item} />}
          ItemSeparatorComponent={() => <View style={{ height: 14 }} />}
          ListEmptyComponent={cases !== null ? <EmptyState /> : undefined}
        />
      )}

      <View style={[styles.footer, { paddingBottom: insets.bottom + 12 }]}>
        <Button onPress={() => router.push("/scan")}>
          Scan my inbox for money
        </Button>
      </View>
    </View>
  );
}

function CaseRow({ item }: { item: Case }) {
  const amount = formatAmount(item.requested_amount, item.currency);
  const hint = NEEDS_YOU_HINT[item.status];
  return (
    <Link href={{ pathname: "/cases/[id]", params: { id: item.id } }} asChild>
      <Pressable
        accessibilityRole="button"
        style={({ pressed }) => pressed && { opacity: 0.85 }}
      >
        <Card tone={hint ? "bob" : "white"}>
          <T variant="bodyBold" numberOfLines={1}>
            {item.company_name ?? "Unknown company"}
          </T>
          <T variant="small" color={colors.ink600} numberOfLines={1}>
            {humanize(item.category)}
          </T>
          <View style={styles.rowBottom}>
            <T variant="title">{amount ?? "Amount TBD"}</T>
            <StatusBadge status={item.status} />
          </View>
          {hint !== undefined && (
            <T variant="caption" color={colors.accent700} style={{ marginTop: 10 }}>
              {hint} →
            </T>
          )}
        </Card>
      </Pressable>
    </Link>
  );
}

function EmptyState() {
  return (
    <View style={styles.empty}>
      <Image
        source={require("../../../assets/images/karen.png")}
        style={{ width: 96, height: 97 }}
        accessible={false}
      />
      <T variant="title" style={{ marginTop: 18, textAlign: "center" }}>
        No cases yet
      </T>
      <T
        variant="small"
        color={colors.ink600}
        style={{ marginTop: 6, textAlign: "center", maxWidth: 300 }}
      >
        Let Karen scan your inbox for refunds, credits, and double charges
        you&apos;re owed. Every email, escalation, and refund she chases
        shows up here.
      </T>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.white },
  centered: { flex: 1, alignItems: "center", justifyContent: "center" },
  list: { padding: 16 },
  sectionTitle: { marginTop: 16, marginBottom: 12 },
  rowBottom: {
    marginTop: 14,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
  },
  empty: { alignItems: "center", paddingTop: 64, paddingHorizontal: 24 },
  footer: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    paddingHorizontal: 16,
    paddingTop: 12,
    backgroundColor: colors.white,
    borderTopWidth: 2,
    borderTopColor: colors.ink900,
  },
});
