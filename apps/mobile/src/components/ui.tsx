/**
 * Karen design-system primitives for React Native — the native twins of
 * apps/web/src/components (Card, Button, StatusBadge).
 */
import * as Haptics from "expo-haptics";
import type { ReactNode } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
  type StyleProp,
  type TextProps,
  type TextStyle,
  type ViewStyle,
} from "react-native";
import {
  humanize,
  statusTone,
  type CaseStatus,
  type StatusTone,
} from "@karenbot/api-client";
import { colors, fonts, sticker } from "@/lib/theme";

// ---------------------------------------------------------------------------
// Text
// ---------------------------------------------------------------------------

type Variant = "display" | "title" | "body" | "bodyBold" | "small" | "caption";

const textVariants: Record<Variant, TextStyle> = {
  display: { fontFamily: fonts.display, fontSize: 26, lineHeight: 32 },
  title: { fontFamily: fonts.display, fontSize: 18, lineHeight: 24 },
  body: { fontFamily: fonts.regular, fontSize: 15, lineHeight: 22 },
  bodyBold: { fontFamily: fonts.bold, fontSize: 15, lineHeight: 22 },
  small: { fontFamily: fonts.regular, fontSize: 13, lineHeight: 19 },
  caption: { fontFamily: fonts.bold, fontSize: 12, lineHeight: 16 },
};

export function T({
  variant = "body",
  color = colors.ink900,
  style,
  ...rest
}: TextProps & { variant?: Variant; color?: string }) {
  return (
    <Text
      {...rest}
      style={[textVariants[variant], { color }, style]}
      maxFontSizeMultiplier={1.6}
    />
  );
}

// ---------------------------------------------------------------------------
// Card
// ---------------------------------------------------------------------------

export function Card({
  children,
  tone = "white",
  style,
}: {
  children: ReactNode;
  tone?: "white" | "accent" | "bob" | "face";
  style?: StyleProp<ViewStyle>;
}) {
  const background = {
    white: colors.white,
    accent: colors.accent50,
    bob: colors.bob100,
    face: colors.face100,
  }[tone];
  return (
    <View style={[styles.card, { backgroundColor: background }, style]}>
      {children}
    </View>
  );
}

// ---------------------------------------------------------------------------
// Button
// ---------------------------------------------------------------------------

type ButtonVariant = "primary" | "secondary" | "danger";

const buttonColors: Record<ButtonVariant, { bg: string; fg: string }> = {
  primary: { bg: colors.accent500, fg: colors.white },
  secondary: { bg: colors.white, fg: colors.ink900 },
  danger: { bg: colors.white, fg: colors.accent600 },
};

export function Button({
  children,
  onPress,
  variant = "primary",
  disabled = false,
  loading = false,
  style,
}: {
  children: string;
  onPress: () => void;
  variant?: ButtonVariant;
  disabled?: boolean;
  loading?: boolean;
  style?: StyleProp<ViewStyle>;
}) {
  const { bg, fg } = buttonColors[variant];
  const inactive = disabled || loading;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled: inactive, busy: loading }}
      disabled={inactive}
      onPress={() => {
        void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
        onPress();
      }}
      style={({ pressed }) => [
        styles.button,
        { backgroundColor: bg, opacity: inactive ? 0.5 : 1 },
        pressed && styles.buttonPressed,
        style,
      ]}
    >
      {loading && <ActivityIndicator color={fg} style={{ marginRight: 8 }} />}
      <Text style={[styles.buttonText, { color: fg }]} maxFontSizeMultiplier={1.4}>
        {children}
      </Text>
    </Pressable>
  );
}

// ---------------------------------------------------------------------------
// Badges & banners
// ---------------------------------------------------------------------------

const toneColors: Record<StatusTone, { bg: string; fg: string }> = {
  green: { bg: colors.money100, fg: colors.money700 },
  amber: { bg: colors.bob100, fg: colors.ink900 },
  red: { bg: colors.accent100, fg: colors.accent700 },
  neutral: { bg: colors.face100, fg: colors.ink600 },
};

export function Pill({
  label,
  bg,
  fg,
}: {
  label: string;
  bg: string;
  fg: string;
}) {
  return (
    <View style={[styles.pill, { backgroundColor: bg }]}>
      <Text style={[styles.pillText, { color: fg }]} maxFontSizeMultiplier={1.3}>
        {label}
      </Text>
    </View>
  );
}

export function StatusBadge({ status }: { status: CaseStatus }) {
  const { bg, fg } = toneColors[statusTone(status)];
  return <Pill label={humanize(status)} bg={bg} fg={fg} />;
}

export function Banner({
  children,
  tone = "error",
}: {
  children: string;
  tone?: "error" | "warn" | "info";
}) {
  const palette = {
    error: { bg: colors.red50, fg: colors.red700 },
    warn: { bg: colors.bob100, fg: colors.ink900 },
    info: { bg: colors.face100, fg: colors.ink600 },
  }[tone];
  return (
    <View
      accessibilityRole={tone === "error" ? "alert" : undefined}
      style={[styles.banner, { backgroundColor: palette.bg }]}
    >
      <T variant="small" color={palette.fg} style={{ fontFamily: fonts.medium }}>
        {children}
      </T>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    ...sticker,
    padding: 18,
  },
  button: {
    minHeight: 48,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 12,
    borderWidth: 2,
    borderColor: colors.ink900,
    shadowColor: colors.ink900,
    shadowOffset: { width: 3, height: 3 },
    shadowOpacity: 1,
    shadowRadius: 0,
    elevation: 3,
  },
  buttonPressed: {
    transform: [{ translateX: 3 }, { translateY: 3 }],
    shadowOpacity: 0,
    elevation: 0,
  },
  buttonText: {
    fontFamily: fonts.bold,
    fontSize: 15,
    textAlign: "center",
    flexShrink: 1,
  },
  pill: {
    alignSelf: "flex-start",
    borderRadius: 999,
    borderWidth: 1.5,
    borderColor: colors.ink900,
    paddingHorizontal: 10,
    paddingVertical: 3,
  },
  pillText: {
    fontFamily: fonts.bold,
    fontSize: 12,
  },
  banner: {
    borderRadius: 12,
    borderWidth: 1.5,
    borderColor: colors.ink900,
    paddingHorizontal: 14,
    paddingVertical: 10,
  },
});
