/**
 * Building blocks for the case detail screen. Kept presentational: the
 * screen owns data + actions and passes callbacks down.
 */
import {
  PERSONAS,
  humanize,
  type Approval,
  type AuditEvent,
  type CaseEvidenceItem,
  type Communication,
  type EvidenceGroup,
  type Persona,
} from "@karenbot/api-client";
import * as Clipboard from "expo-clipboard";
import * as Haptics from "expo-haptics";
import { useState, type ReactNode } from "react";
import { Pressable, ScrollView, StyleSheet, View } from "react-native";
import { Button, Card, Pill, T } from "@/components/ui";
import { colors, fonts } from "@/lib/theme";

const BODY_TRUNCATE_LENGTH = 400;

function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

// ---------------------------------------------------------------------------
// Collapsible
// ---------------------------------------------------------------------------

export function Collapsible({
  title,
  children,
  initiallyOpen = false,
}: {
  title: string;
  children: ReactNode;
  initiallyOpen?: boolean;
}) {
  const [open, setOpen] = useState(initiallyOpen);
  return (
    <View style={styles.collapsible}>
      <Pressable
        accessibilityRole="button"
        accessibilityState={{ expanded: open }}
        onPress={() => setOpen((v) => !v)}
        style={styles.collapsibleHeader}
      >
        <T variant="bodyBold" style={{ flex: 1 }}>
          {title}
        </T>
        <T variant="bodyBold" color={colors.ink400}>
          {open ? "−" : "+"}
        </T>
      </Pressable>
      {open && <View style={styles.collapsibleBody}>{children}</View>}
    </View>
  );
}

// ---------------------------------------------------------------------------
// Approvals
// ---------------------------------------------------------------------------

/** Fields not worth showing a customer: internal ids and the action tag. */
function isDisplayField(key: string): boolean {
  return key !== "action" && key !== "purpose" && !key.endsWith("_id") && !key.endsWith("_ids");
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export function ApprovalCard({
  approval,
  isCancellation,
  busy,
  onApprove,
  onDeny,
}: {
  approval: Approval;
  isCancellation: boolean;
  busy: boolean;
  onApprove: () => void;
  onDeny: () => void;
}) {
  const purpose = approval.proposed_action.purpose;
  const fields = Object.entries(approval.proposed_action).filter(([key]) =>
    isDisplayField(key),
  );
  return (
    <View style={styles.approval}>
      <T variant="bodyBold">{humanize(approval.action_type)}</T>
      {typeof purpose === "string" && purpose !== "" && (
        <T variant="body" style={{ marginTop: 6 }}>
          {/^[a-z_]+$/.test(purpose) ? humanize(purpose) : purpose}
        </T>
      )}
      {fields.length > 0 && (
        <View style={{ marginTop: 10, gap: 4 }}>
          {fields.map(([key, value]) => (
            <T key={key} variant="small">
              <T variant="small" color={colors.ink600} style={{ fontFamily: fonts.semibold }}>
                {humanize(key)}:{" "}
              </T>
              {formatValue(value)}
            </T>
          ))}
        </View>
      )}
      {approval.policy_reasons.length > 0 && (
        <T variant="small" color={colors.ink600} style={{ marginTop: 10 }}>
          Why approval is needed:{" "}
          {approval.policy_reasons
            .map((r) => humanize(r.split(":")[0] ?? r))
            .join("; ")}
        </T>
      )}
      <View style={{ marginTop: 14, gap: 10 }}>
        <Button disabled={busy} onPress={onApprove}>
          {approval.action_type === "accept_offer" ? "Take the offer" : "Approve"}
        </Button>
        <Button variant="danger" disabled={busy} onPress={onDeny}>
          {isCancellation ? "No deal — keep canceling" : "Decline — keep pushing"}
        </Button>
      </View>
    </View>
  );
}

// ---------------------------------------------------------------------------
// Paper trail
// ---------------------------------------------------------------------------

function ExpandableBody({ body }: { body: string }) {
  const [expanded, setExpanded] = useState(false);
  const long = body.length > BODY_TRUNCATE_LENGTH;
  return (
    <>
      <T variant="small" selectable>
        {long && !expanded ? `${body.slice(0, BODY_TRUNCATE_LENGTH)}…` : body}
      </T>
      {long && (
        <Pressable
          accessibilityRole="button"
          hitSlop={8}
          onPress={() => setExpanded((v) => !v)}
          style={{ marginTop: 6 }}
        >
          <T variant="caption" color={colors.accent600}>
            {expanded ? "Show less" : "Show more"}
          </T>
        </Pressable>
      )}
    </>
  );
}

function DraftForCustomer({ comm }: { comm: Communication }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    const text =
      comm.subject !== null && comm.subject !== ""
        ? `${comm.subject}\n\n${comm.body}`
        : comm.body;
    await Clipboard.setStringAsync(text);
    void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }
  return (
    <View style={styles.draft}>
      <View style={styles.draftHeader}>
        <T variant="bodyBold" color={colors.accent700}>
          Draft for you to send
        </T>
        <Pressable
          accessibilityRole="button"
          onPress={() => void copy()}
          style={styles.copyButton}
        >
          <T variant="caption" color={colors.accent700}>
            {copied ? "Copied!" : "Copy"}
          </T>
        </Pressable>
      </View>
      {typeof comm.classification.guidance === "string" && (
        <T variant="small" color={colors.ink600} style={{ marginTop: 4 }}>
          {comm.classification.guidance}
        </T>
      )}
      {comm.subject !== null && comm.subject !== "" && (
        <T variant="bodyBold" style={{ marginTop: 10 }}>
          {comm.subject}
        </T>
      )}
      <View style={{ marginTop: 4 }}>
        <ExpandableBody body={comm.body} />
      </View>
    </View>
  );
}

export function PaperTrail({
  communications,
  companyLabel,
}: {
  communications: Communication[];
  companyLabel: string;
}) {
  return (
    <Card style={{ padding: 0 }}>
      <View style={styles.trailHeader}>
        <T variant="title">The paper trail</T>
      </View>
      {communications.length === 0 ? (
        <T variant="small" color={colors.ink400} style={{ padding: 18 }}>
          No messages yet — Karen hasn&apos;t made contact.
        </T>
      ) : (
        <View style={{ padding: 14, gap: 16 }}>
          {communications.map((comm) => {
            if (comm.classification.draft_for_customer === true) {
              return <DraftForCustomer key={comm.id} comm={comm} />;
            }
            const fromKaren =
              comm.direction === "outbound" && comm.counterparty === "company";
            const label = fromKaren
              ? `Karen → ${companyLabel}`
              : comm.direction === "inbound"
                ? companyLabel
                : "Karen → you";
            const timestamp = comm.sent_at ?? comm.received_at ?? comm.created_at;
            return (
              <View
                key={comm.id}
                style={{ alignItems: fromKaren ? "flex-end" : "flex-start" }}
              >
                <T variant="caption" color={colors.ink400} style={{ marginBottom: 4 }}>
                  {label} · {formatTimestamp(timestamp)}
                </T>
                <View
                  style={[
                    styles.bubble,
                    fromKaren ? styles.bubbleKaren : styles.bubbleThem,
                  ]}
                >
                  {comm.subject !== null && comm.subject !== "" && (
                    <T variant="bodyBold" style={{ marginBottom: 4 }}>
                      {comm.subject}
                    </T>
                  )}
                  <ExpandableBody body={comm.body} />
                </View>
              </View>
            );
          })}
        </View>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Evidence
// ---------------------------------------------------------------------------

export function EvidenceGroupPicker({
  groups,
  busy,
  onPick,
}: {
  groups: EvidenceGroup[];
  busy: boolean;
  onPick: (group: EvidenceGroup) => void;
}) {
  return (
    <Card tone="accent">
      <T variant="title">Which trip or order is this case about?</T>
      <T variant="small" color={colors.ink600} style={{ marginTop: 4 }}>
        Karen found emails from more than one. She never mixes different
        situations into one case.
      </T>
      <View style={{ marginTop: 12, gap: 10 }}>
        {groups.map((group) => (
          <Pressable
            key={group.key}
            accessibilityRole="button"
            disabled={busy}
            onPress={() => onPick(group)}
            style={({ pressed }) => [
              styles.groupOption,
              pressed && { backgroundColor: colors.face100 },
              busy && { opacity: 0.6 },
            ]}
          >
            <T variant="bodyBold">{group.label}</T>
            {group.hits.slice(0, 2).map((hit) => (
              <T key={hit.reference} variant="small" color={colors.ink600} numberOfLines={1}>
                {hit.summary}
              </T>
            ))}
          </Pressable>
        ))}
      </View>
    </Card>
  );
}

export function EvidenceList({
  items,
  busy,
  onRemove,
}: {
  items: CaseEvidenceItem[];
  busy: boolean;
  onRemove: (item: CaseEvidenceItem) => void;
}) {
  if (items.length === 0) {
    return (
      <T variant="small" color={colors.ink400}>
        No evidence on file yet.
      </T>
    );
  }
  return (
    <View style={{ gap: 12 }}>
      {items.map((item) => (
        <View key={item.id} style={styles.evidenceRow}>
          <View style={{ flex: 1, gap: 4 }}>
            <Pill label={humanize(item.evidence_type)} bg={colors.face100} fg={colors.ink600} />
            <T variant="small">{item.summary}</T>
          </View>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={`Remove evidence: ${item.summary.slice(0, 60)}`}
            disabled={busy}
            hitSlop={10}
            onPress={() => onRemove(item)}
          >
            <T variant="bodyBold" color={colors.ink400}>
              ✕
            </T>
          </Pressable>
        </View>
      ))}
    </View>
  );
}

// ---------------------------------------------------------------------------
// Audit trail
// ---------------------------------------------------------------------------

export function AuditList({ events }: { events: AuditEvent[] }) {
  if (events.length === 0) {
    return (
      <T variant="small" color={colors.ink400}>
        No events yet.
      </T>
    );
  }
  return (
    <View style={{ gap: 10 }}>
      {events.map((event, index) => (
        <View key={index} style={{ gap: 2 }}>
          <T variant="caption" color={colors.ink400}>
            {formatTimestamp(event.timestamp)} · {event.actor_type}
          </T>
          <T variant="small" style={{ fontFamily: fonts.medium }}>
            {event.event_type}
          </T>
        </View>
      ))}
    </View>
  );
}

// ---------------------------------------------------------------------------
// Sandbox simulator (dev API only)
// ---------------------------------------------------------------------------

export function SimulatorPanel({
  persona,
  onPersona,
  busy,
  onSimulate,
}: {
  persona: Persona;
  onPersona: (p: Persona) => void;
  busy: boolean;
  onSimulate: () => void;
}) {
  return (
    <View style={styles.simulator}>
      <T variant="caption" color={colors.ink400}>
        SIMULATOR (SANDBOX ONLY)
      </T>
      <T variant="small" style={{ marginTop: 8 }}>
        Company persona
      </T>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={{ gap: 8, paddingVertical: 8 }}
      >
        {PERSONAS.map((p) => {
          const selected = p === persona;
          return (
            <Pressable
              key={p}
              accessibilityRole="button"
              accessibilityState={{ selected }}
              onPress={() => onPersona(p)}
              style={[styles.chip, selected && styles.chipSelected]}
            >
              <T variant="caption" color={selected ? colors.white : colors.ink900}>
                {humanize(p)}
              </T>
            </Pressable>
          );
        })}
      </ScrollView>
      <Button variant="secondary" disabled={busy} onPress={onSimulate}>
        Simulate company response
      </Button>
    </View>
  );
}

const styles = StyleSheet.create({
  collapsible: {
    borderWidth: 2,
    borderColor: colors.ink900,
    borderRadius: 12,
    backgroundColor: colors.white,
  },
  collapsibleHeader: {
    minHeight: 52,
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 16,
  },
  collapsibleBody: {
    borderTopWidth: 2,
    borderTopColor: colors.ink900,
    borderStyle: "dashed",
    padding: 16,
  },
  approval: {
    borderWidth: 2,
    borderColor: colors.ink900,
    borderRadius: 12,
    backgroundColor: colors.white,
    padding: 14,
  },
  trailHeader: {
    paddingHorizontal: 18,
    paddingVertical: 14,
    borderBottomWidth: 2,
    borderBottomColor: colors.ink900,
    borderStyle: "dashed",
  },
  bubble: {
    maxWidth: "88%",
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 10,
  },
  bubbleKaren: {
    borderWidth: 2,
    borderColor: colors.ink900,
    backgroundColor: colors.white,
  },
  bubbleThem: { backgroundColor: colors.face100 },
  draft: {
    borderWidth: 2,
    borderColor: colors.ink900,
    borderRadius: 12,
    backgroundColor: colors.bob100,
    padding: 14,
  },
  draftHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
  },
  copyButton: {
    minHeight: 36,
    minWidth: 64,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 2,
    borderColor: colors.ink900,
    borderRadius: 10,
    backgroundColor: colors.white,
    paddingHorizontal: 12,
  },
  groupOption: {
    borderWidth: 2,
    borderColor: colors.ink900,
    borderRadius: 12,
    backgroundColor: colors.white,
    padding: 12,
    gap: 2,
  },
  evidenceRow: { flexDirection: "row", alignItems: "flex-start", gap: 12 },
  simulator: {
    borderWidth: 2,
    borderStyle: "dashed",
    borderColor: colors.ink400,
    borderRadius: 12,
    padding: 16,
  },
  chip: {
    borderWidth: 1.5,
    borderColor: colors.ink900,
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 6,
    backgroundColor: colors.white,
  },
  chipSelected: { backgroundColor: colors.ink900 },
});
