import {
  ApiError,
  TERMINAL_STATUSES,
  approveAction,
  attachEvidenceGroup,
  authorizeCase,
  completeIntake,
  confirmRecovery,
  denyAction,
  devTick,
  formatAmount,
  getCase,
  getHealth,
  humanize,
  initiateContact,
  listApprovals,
  listAudit,
  listCaseEvidence,
  listCommunications,
  removeCaseEvidence,
  revokeCase,
  scanCaseEvidence,
  type Approval,
  type AuditEvent,
  type Case,
  type CaseEvidenceItem,
  type CaseStatus,
  type Communication,
  type EvidenceGroup,
  type EvidenceScanResult,
  type Persona,
} from "@karenbot/api-client";
import * as Haptics from "expo-haptics";
import { Stack, useLocalSearchParams } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  RefreshControl,
  ScrollView,
  StyleSheet,
  TextInput,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import {
  ApprovalCard,
  AuditList,
  Collapsible,
  EvidenceGroupPicker,
  EvidenceList,
  PaperTrail,
  SimulatorPanel,
} from "@/components/case-sections";
import { Banner, Button, Card, Pill, StatusBadge, T } from "@/components/ui";
import { errorMessage, useFocusedPolling } from "@/lib/hooks";
import { colors, fonts } from "@/lib/theme";

const POLL_INTERVAL_MS = 3000;

/** Before eligibility is decided: gather proof, then ask Karen to assess. */
const INTAKE_STATUSES: ReadonlySet<CaseStatus> = new Set([
  "DISCOVERED",
  "AWAITING_INFORMATION",
  "ELIGIBILITY_REVIEW",
]);

interface CaseData {
  caseRecord: Case;
  communications: Communication[];
  approvals: Approval[];
  audit: AuditEvent[];
}

export default function CaseDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const caseId = id;
  const insets = useSafeAreaInsets();

  const [data, setData] = useState<CaseData | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [sandbox, setSandbox] = useState(false);
  const [signedName, setSignedName] = useState("");
  const [loaText, setLoaText] = useState<string | null>(null);
  const [evidence, setEvidence] = useState<CaseEvidenceItem[]>([]);
  const [evidenceScanning, setEvidenceScanning] = useState(false);
  const [scanResult, setScanResult] = useState<EvidenceScanResult | null>(null);
  const [persona, setPersona] = useState<Persona>("lowball_then_accept");
  const [ineligibleReasons, setIneligibleReasons] = useState<string[] | null>(
    null,
  );

  const refetch = useCallback(async () => {
    try {
      const [caseRecord, communications, approvals, audit] = await Promise.all([
        getCase(caseId),
        listCommunications(caseId),
        listApprovals(caseId),
        listAudit(caseId),
      ]);
      setData({ caseRecord, communications, approvals, audit });
      setLoadError(null);
    } catch (err) {
      setLoadError(errorMessage(err, "Could not load this case."));
    }
  }, [caseId]);

  const refetchEvidence = useCallback(async () => {
    try {
      setEvidence(await listCaseEvidence(caseId));
    } catch {
      // non-fatal — the section keeps the last known list
    }
  }, [caseId]);

  useEffect(() => {
    void refetch();
    void refetchEvidence();
    getHealth()
      .then((h) => setSandbox(h.sandbox))
      .catch(() => setSandbox(false));
  }, [refetch, refetchEvidence]);

  const status = data?.caseRecord.status;
  const isTerminal = status !== undefined && TERMINAL_STATUSES.has(status);

  // Live updates while Karen works the case; stops once it's closed.
  useFocusedPolling(
    () => void refetch(),
    POLL_INTERVAL_MS,
    status !== undefined && !isTerminal,
  );

  async function onRefresh() {
    setRefreshing(true);
    await Promise.all([refetch(), refetchEvidence()]);
    setRefreshing(false);
  }

  async function runAction(action: () => Promise<unknown>) {
    setActionError(null);
    setBusy(true);
    try {
      await action();
      void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      await refetch();
    } catch (err) {
      void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
      setActionError(errorMessage(err, "Action failed — try again."));
    } finally {
      setBusy(false);
    }
  }

  async function submitAuthorization() {
    const name = signedName.trim();
    if (name === "") {
      setActionError("Type your full name to sign.");
      return;
    }
    await runAction(async () => {
      const result = await authorizeCase(caseId, name);
      setLoaText(result.loa_text);
    });
  }

  async function checkEligibility() {
    await runAction(async () => {
      const result = await completeIntake(caseId);
      setIneligibleReasons(result.eligible ? null : result.reasons);
    });
  }

  async function sendKaren() {
    await runAction(async () => {
      const result = await initiateContact(caseId);
      if (result.decision === "deny") {
        throw new ApiError(
          422,
          `Karen can't make contact yet: ${result.reasons.join("; ")}`,
        );
      }
    });
  }

  async function scanForEvidence() {
    setEvidenceScanning(true);
    try {
      await runAction(async () => {
        setScanResult(await scanCaseEvidence(caseId));
        await refetchEvidence();
      });
    } finally {
      setEvidenceScanning(false);
    }
  }

  async function pickEvidenceGroup(group: EvidenceGroup) {
    await runAction(async () => {
      const attached = await attachEvidenceGroup(caseId, group.hits);
      setScanResult((prev) => ({
        source: prev?.source ?? "live",
        attached,
        total_matches: prev?.total_matches ?? attached.length,
        groups: [],
      }));
      await refetchEvidence();
    });
  }

  function confirmRevoke() {
    Alert.alert(
      "Stop Karen?",
      "This revokes her authorization. She'll cease all contact with the company.",
      [
        { text: "Keep going", style: "cancel" },
        {
          text: "Stop Karen",
          style: "destructive",
          onPress: () => void runAction(() => revokeCase(caseId)),
        },
      ],
    );
  }

  function confirmRemoveEvidence(item: CaseEvidenceItem) {
    Alert.alert("Remove this evidence?", item.summary.slice(0, 120), [
      { text: "Cancel", style: "cancel" },
      {
        text: "Remove",
        style: "destructive",
        onPress: () =>
          void runAction(async () => {
            await removeCaseEvidence(caseId, item.id);
            await refetchEvidence();
          }),
      },
    ]);
  }

  if (data === null) {
    return (
      <View style={styles.centered}>
        <Stack.Screen options={{ title: "Case" }} />
        {loadError !== null ? (
          <View style={{ padding: 16, gap: 12, alignSelf: "stretch" }}>
            <Banner>{`Could not load this case: ${loadError}`}</Banner>
            <Button variant="secondary" onPress={() => void refetch()}>
              Try again
            </Button>
          </View>
        ) : (
          <ActivityIndicator color={colors.accent500} />
        )}
      </View>
    );
  }

  const { caseRecord, communications, approvals, audit } = data;
  const amount = formatAmount(caseRecord.requested_amount, caseRecord.currency);
  const companyLabel = caseRecord.company_name ?? "the company";
  const isCancellation = caseRecord.category === "subscription_cancellation";

  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={[
        styles.container,
        { paddingBottom: insets.bottom + 32 },
      ]}
      keyboardShouldPersistTaps="handled"
      automaticallyAdjustKeyboardInsets
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={() => void onRefresh()}
          tintColor={colors.accent500}
        />
      }
    >
      <Stack.Screen options={{ title: caseRecord.company_name ?? "Case" }} />

      {/* Header */}
      <Card>
        <View style={styles.badges}>
          <StatusBadge status={caseRecord.status} />
          {caseRecord.contact_mode === "assist" && (
            <Pill label="Assist mode" bg={colors.face100} fg={colors.ink600} />
          )}
          {sandbox && <Pill label="Sandbox" bg={colors.bob100} fg={colors.ink900} />}
        </View>
        <T variant="display" style={{ marginTop: 12 }}>
          {amount ?? "Amount TBD"}
        </T>
        <T variant="body" color={colors.ink600}>
          {companyLabel} · {humanize(caseRecord.category)}
        </T>
        {caseRecord.eligibility_basis !== null && (
          <View style={styles.basis}>
            <T variant="caption" color={colors.accent700}>
              Eligibility basis: {caseRecord.eligibility_basis}
            </T>
          </View>
        )}
        {loadError !== null && (
          <T variant="small" color={colors.bob600} style={{ marginTop: 10 }}>
            Live updates interrupted: {loadError}
          </T>
        )}
      </Card>

      {sandbox && (
        <Banner tone="warn">
          Sandbox mode: no real emails are sent. Outbound messages go to a
          simulated company — use the simulator below to play out the
          negotiation.
        </Banner>
      )}

      {actionError !== null && <Banner>{actionError}</Banner>}

      {ineligibleReasons !== null && (
        <Banner>
          {`Karen checked ${companyLabel}'s policies and this one doesn't qualify${
            ineligibleReasons.length > 0 ? `: ${ineligibleReasons.join("; ")}` : "."
          }`}
        </Banner>
      )}

      {/* Intake: gather proof, then eligibility */}
      {INTAKE_STATUSES.has(caseRecord.status) && (
        <Card tone="accent">
          <T variant="title">Let&apos;s build your case</T>
          <T variant="small" color={colors.ink600} style={{ marginTop: 6 }}>
            Receipts, confirmations, and emails from {companyLabel} make
            Karen&apos;s demand airtight. She can pull them from your inbox.
            When you&apos;re done, she checks {companyLabel}&apos;s own
            policies to confirm they owe you.
          </T>
          <T variant="caption" style={{ marginTop: 12 }}>
            {evidence.length === 0
              ? "No evidence on file yet"
              : `${evidence.length} piece${evidence.length === 1 ? "" : "s"} of evidence on file`}
          </T>
          <View style={{ marginTop: 12, gap: 10 }}>
            <Button
              variant="secondary"
              loading={evidenceScanning}
              disabled={busy}
              onPress={() => void scanForEvidence()}
            >
              Scan my inbox for proof
            </Button>
            <Button
              disabled={busy || evidenceScanning}
              loading={busy && !evidenceScanning}
              onPress={() => void checkEligibility()}
            >
              That&apos;s everything — check my case
            </Button>
          </View>
        </Card>
      )}

      {/* Evidence scan result — next to the buttons that trigger it */}
      {scanResult !== null && scanResult.groups.length > 0 && (
        <EvidenceGroupPicker
          groups={scanResult.groups}
          busy={busy}
          onPick={(group) => void pickEvidenceGroup(group)}
        />
      )}
      {scanResult !== null && scanResult.groups.length === 0 && (
        <Banner tone="info">
          {scanResult.attached.length > 0
            ? `Attached ${scanResult.attached.length} new item${
                scanResult.attached.length === 1 ? "" : "s"
              } from your inbox.`
            : scanResult.total_matches > 0
              ? `Nothing new — ${scanResult.total_matches} matching item${
                  scanResult.total_matches === 1 ? "" : "s"
                } already attached.`
              : `No new matching emails found.${
                  scanResult.source === "mock"
                    ? " (Demo inbox — connect your real email to scan actual mail.)"
                    : ""
                }`}
        </Banner>
      )}

      {/* Authorization */}
      {caseRecord.status === "AWAITING_AUTHORIZATION" && (
        <Card tone="accent">
          <T variant="title">Karen needs your authorization</T>
          <T variant="small" color={colors.ink600} style={{ marginTop: 6 }}>
            Before Karen can go after {companyLabel} on your behalf, sign a
            Letter of Authorization by typing your full legal name. You can
            revoke it at any time.
          </T>
          <T variant="caption" style={{ marginTop: 14, marginBottom: 6 }}>
            Your full name
          </T>
          <TextInput
            value={signedName}
            onChangeText={setSignedName}
            placeholder="e.g. Dana Example"
            placeholderTextColor={colors.ink400}
            autoCapitalize="words"
            autoComplete="name"
            textContentType="name"
            returnKeyType="done"
            onSubmitEditing={() => void submitAuthorization()}
            style={styles.input}
            accessibilityLabel="Type your full name to sign"
          />
          <Button
            style={{ marginTop: 12 }}
            loading={busy}
            onPress={() => void submitAuthorization()}
          >
            Authorize KarenBot
          </Button>
        </Card>
      )}

      {loaText !== null && (
        <Collapsible title="Your signed Letter of Authorization">
          <T variant="small" selectable style={{ fontFamily: fonts.regular }}>
            {loaText}
          </T>
        </Collapsible>
      )}

      {/* Ready to contact */}
      {caseRecord.status === "READY_TO_CONTACT" && (
        <Card tone="accent">
          <T variant="title">Karen is ready</T>
          <T variant="small" color={colors.ink600} style={{ marginTop: 6 }}>
            Authorization signed. Say the word and Karen makes first contact
            with {companyLabel}.
          </T>
          <Button
            style={{ marginTop: 14 }}
            loading={busy}
            onPress={() => void sendKaren()}
          >
            {caseRecord.contact_mode === "assist"
              ? "Have Karen draft it"
              : "Send Karen after them"}
          </Button>
        </Card>
      )}

      {/* Approvals */}
      {approvals.length > 0 && (
        <Card tone="bob">
          <T variant="title">Karen needs your approval</T>
          <View style={{ marginTop: 12, gap: 12 }}>
            {approvals.map((approval) => (
              <ApprovalCard
                key={approval.id}
                approval={approval}
                isCancellation={isCancellation}
                busy={busy}
                onApprove={() => void runAction(() => approveAction(approval.id))}
                onDeny={() => void runAction(() => denyAction(approval.id))}
              />
            ))}
          </View>
        </Card>
      )}

      {/* Recovery confirmation */}
      {caseRecord.status === "VERIFYING_RECOVERY" && (
        <Card tone="face">
          <T variant="title">
            {isCancellation ? "Did the billing stop?" : "Did the money land?"}
          </T>
          <T variant="small" color={colors.ink600} style={{ marginTop: 6 }}>
            Karen closes the case once you confirm.
          </T>
          <Button
            style={{ marginTop: 14 }}
            loading={busy}
            onPress={() => void runAction(() => confirmRecovery(caseId))}
          >
            {isCancellation ? "Confirmed — the billing stopped" : "I received the money"}
          </Button>
        </Card>
      )}

      <PaperTrail communications={communications} companyLabel={companyLabel} />

      <Collapsible title={`Evidence on file (${evidence.length})`}>
        <EvidenceList
          items={evidence}
          busy={busy}
          onRemove={confirmRemoveEvidence}
        />
        {!isTerminal && (
          <Button
            variant="secondary"
            style={{ marginTop: 14 }}
            loading={evidenceScanning}
            disabled={busy}
            onPress={() => void scanForEvidence()}
          >
            Scan inbox for evidence
          </Button>
        )}
      </Collapsible>

      {sandbox && !isTerminal && (
        <SimulatorPanel
          persona={persona}
          onPersona={setPersona}
          busy={busy}
          onSimulate={() => void runAction(() => devTick({ persona, ticks: 1 }))}
        />
      )}

      <Collapsible title={`Audit trail (${audit.length})`}>
        <AuditList events={audit} />
      </Collapsible>

      {!isTerminal && (
        <Button variant="danger" disabled={busy} onPress={confirmRevoke}>
          Stop Karen / revoke authorization
        </Button>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.white },
  container: { padding: 16, gap: 16 },
  centered: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.white,
  },
  badges: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  basis: {
    marginTop: 12,
    alignSelf: "flex-start",
    borderWidth: 1.5,
    borderColor: colors.ink900,
    borderRadius: 10,
    backgroundColor: colors.accent50,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  input: {
    minHeight: 48,
    borderWidth: 2,
    borderColor: colors.ink900,
    borderRadius: 12,
    backgroundColor: colors.white,
    paddingHorizontal: 14,
    fontFamily: fonts.regular,
    fontSize: 16,
    color: colors.ink900,
  },
});
