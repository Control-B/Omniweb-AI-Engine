/** First stop when the app needs an Omniweb JWT: Clerk session ↔ engine JWT, then dashboard. */
export const AUTH_HANDOFF_PATH = "/auth/clerk-continue";

/** Subscriber sign-in / sign-up with Clerk (same app as omniweb.ai gateway). */
export const SIGN_IN_PATH = "/sign-in";

/** Legacy username/password portals (operators / admin). */
export const INTERNAL_LOGIN_PATH = "/login";
