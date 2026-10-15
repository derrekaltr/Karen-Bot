"use client";

import { useAuth } from "@clerk/nextjs";
import { useEffect } from "react";
import { setSessionTokenGetter } from "@/lib/api";

/**
 * Registers the Clerk session-token getter with the API client so every
 * backend request carries `Authorization: Bearer <session JWT>` while a
 * user is signed in. Rendered once inside ClerkProvider (see layout).
 */
export function ClerkTokenBridge() {
  const { getToken, isSignedIn } = useAuth();

  useEffect(() => {
    if (isSignedIn) {
      setSessionTokenGetter(() => getToken());
    } else {
      setSessionTokenGetter(null);
    }
    return () => setSessionTokenGetter(null);
  }, [getToken, isSignedIn]);

  return null;
}
