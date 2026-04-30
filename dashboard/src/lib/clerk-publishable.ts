/**
 * Must match `next.config.js` sources for `env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`
 * (NEXT_PUBLIC_* first, then CLERK_PUBLISHABLE_KEY). Docker/DO often set only the latter
 * at build time; reading both keeps RootLayout, middleware, and SSO route aligned.
 */
export function resolvedClerkPublishableKey(): string {
  return (
    process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY ||
    process.env.CLERK_PUBLISHABLE_KEY ||
    ""
  ).trim();
}
