/**
 * One auth surface for the app, whichever mode it runs in:
 *
 * - clerk: real Clerk sessions. Sign-in/up open Clerk's hosted Account
 *   Portal in a secure in-app browser (same Clerk instance as the web app),
 *   and every API request carries the session JWT — exactly what the API
 *   already verifies for the web.
 * - dev:   no Clerk key in a dev build. "Signing in" just flips a flag and
 *   requests use the API's dev-mode X-User-Email fallback (demo user).
 */
import { ClerkProvider, useAuth, useClerk } from "@clerk/expo";
import { useHostedAuth } from "@clerk/expo/hosted-auth";
import { tokenCache } from "@clerk/expo/token-cache";
import { seed, setSessionTokenGetter } from "@karenbot/api-client";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { AUTH_MODE, CLERK_PUBLISHABLE_KEY } from "./config";
import { unregisterForPush } from "./push";

export interface AppAuth {
  mode: typeof AUTH_MODE;
  isLoaded: boolean;
  isSignedIn: boolean;
  /** Resolves true when a session was created. */
  signIn: (flow: "sign-in" | "sign-up") => Promise<boolean>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AppAuth | null>(null);

export function useAppAuth(): AppAuth {
  const value = useContext(AuthContext);
  if (value === null) throw new Error("useAppAuth outside AuthProvider");
  return value;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  if (AUTH_MODE === "clerk") {
    return (
      <ClerkProvider
        publishableKey={CLERK_PUBLISHABLE_KEY}
        tokenCache={tokenCache}
      >
        <ClerkAuthBridge>{children}</ClerkAuthBridge>
      </ClerkProvider>
    );
  }
  return <DevAuthProvider>{children}</DevAuthProvider>;
}

function ClerkAuthBridge({ children }: { children: ReactNode }) {
  const { isLoaded, isSignedIn, getToken } = useAuth();
  const { signOut } = useClerk();
  const { startHostedAuth } = useHostedAuth();

  // Every API request carries the Clerk session JWT while signed in.
  // Assigned during render (idempotent), not in an effect: children's
  // effects run before this component's, so a screen's first fetch would
  // otherwise go out without the token.
  setSessionTokenGetter(isSignedIn ? () => getToken() : null);
  useEffect(() => () => setSessionTokenGetter(null), []);

  const signIn = useCallback(
    async (flow: "sign-in" | "sign-up") => {
      const result = await startHostedAuth({ mode: flow });
      return result.createdSessionId !== null;
    },
    [startHostedAuth],
  );

  const value = useMemo<AppAuth>(
    () => ({
      mode: AUTH_MODE,
      isLoaded,
      isSignedIn: isSignedIn === true,
      signIn,
      // Unregister while the session is still valid, then end it.
      signOut: async () => {
        await unregisterForPush();
        await signOut();
      },
    }),
    [isLoaded, isSignedIn, signIn, signOut],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

function DevAuthProvider({ children }: { children: ReactNode }) {
  const [isSignedIn, setSignedIn] = useState(false);

  const value = useMemo<AppAuth>(
    () => ({
      mode: AUTH_MODE,
      isLoaded: true,
      isSignedIn,
      signIn: async () => {
        if (AUTH_MODE !== "dev") return false;
        // Idempotent: creates the demo user + companies on a dev API.
        await seed();
        setSignedIn(true);
        return true;
      },
      signOut: async () => {
        await unregisterForPush();
        setSignedIn(false);
      },
    }),
    [isSignedIn],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
