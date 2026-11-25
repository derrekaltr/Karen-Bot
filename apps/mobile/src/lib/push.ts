/**
 * Push notifications: "Karen got an offer — approve it?"
 *
 * The API decides *what* pings (company offers, escalations, cancellations
 * confirmed — never the customer's own taps) and sends via Expo's push
 * service. This module only gets permission, registers the phone's Expo
 * push token with the API, and unregisters on sign-out.
 *
 * Remote push needs a real device in a development or store build with an
 * EAS project id (`eas init`). Expo Go, simulators, and web report
 * "unsupported" and the UI simply hides the opt-in.
 */
import {
  registerPushDevice,
  unregisterPushDevice,
} from "@karenbot/api-client";
import Constants, { ExecutionEnvironment } from "expo-constants";
import * as Device from "expo-device";
import * as Notifications from "expo-notifications";
import { Platform } from "react-native";

// Foreground: show the banner too (the case screen also refreshes itself).
if (Platform.OS !== "web") {
  Notifications.setNotificationHandler({
    handleNotification: async () => ({
      shouldShowBanner: true,
      shouldShowList: true,
      shouldPlaySound: true,
      shouldSetBadge: false,
    }),
  });
}

export type PushSupport =
  | { supported: true; projectId: string }
  | { supported: false; reason: string };

export function pushSupport(): PushSupport {
  if (Platform.OS === "web") return { supported: false, reason: "web" };
  if (!Device.isDevice) return { supported: false, reason: "simulator" };
  if (Constants.executionEnvironment === ExecutionEnvironment.StoreClient) {
    return { supported: false, reason: "expo-go" };
  }
  const projectId =
    Constants.expoConfig?.extra?.eas?.projectId ?? Constants.easConfig?.projectId;
  if (typeof projectId !== "string" || projectId === "") {
    return { supported: false, reason: "no-eas-project-id" };
  }
  return { supported: true, projectId };
}

export type PermissionState = "granted" | "denied" | "undetermined" | "unsupported";

export async function permissionState(): Promise<PermissionState> {
  if (!pushSupport().supported) return "unsupported";
  const { status } = await Notifications.getPermissionsAsync();
  return status as PermissionState;
}

/** The token registered for the signed-in user, for sign-out cleanup. */
let registeredToken: string | null = null;

/**
 * Register this phone with the API. With `prompt`, asks iOS for permission
 * first (only call from an explicit user tap); without it, registers only
 * if permission was already granted — safe on every launch, which also
 * picks up rotated tokens.
 */
export async function registerForPush({
  prompt,
}: {
  prompt: boolean;
}): Promise<PermissionState> {
  const support = pushSupport();
  if (!support.supported) return "unsupported";

  let { status } = await Notifications.getPermissionsAsync();
  if (status !== "granted" && prompt) {
    ({ status } = await Notifications.requestPermissionsAsync({
      ios: { allowAlert: true, allowSound: true, allowBadge: false },
    }));
  }
  if (status !== "granted") return status as PermissionState;

  const { data: token } = await Notifications.getExpoPushTokenAsync({
    projectId: support.projectId,
  });
  await registerPushDevice(token, Platform.OS === "android" ? "android" : "ios");
  registeredToken = token;
  return "granted";
}

/** Sign-out: stop this phone receiving the user's case alerts. Best effort. */
export async function unregisterForPush(): Promise<void> {
  const token = registeredToken;
  registeredToken = null;
  if (token === null) return;
  try {
    await unregisterPushDevice(token);
  } catch {
    // Offline or already signed out server-side: the API also drops tokens
    // Expo reports dead, and re-registration on next sign-in moves it.
  }
}

/** Case id carried in a Karen notification's data payload, if any. */
export function caseIdFrom(
  notification: Notifications.Notification,
): string | null {
  const caseId = notification.request.content.data?.case_id;
  return typeof caseId === "string" && caseId !== "" ? caseId : null;
}
