const fs = require("fs");
const path = require("path");

/** Read a single KEY=value from a .env file (no shell expansion). */
function readEnvFileValue(filePath, key) {
  try {
    const raw = fs.readFileSync(filePath, "utf8");
    const line = raw.split("\n").find((l) => {
      const t = l.trim();
      if (!t || t.startsWith("#")) return false;
      return t.startsWith(`${key}=`);
    });
    if (!line) return "";
    const v = line.slice(line.indexOf("=") + 1).trim();
    return v.replace(/^["']|["']$/g, "");
  } catch {
    return "";
  }
}

// Clerk: browser code can only read NEXT_PUBLIC_*. The FastAPI / root .env use
// CLERK_PUBLISHABLE_KEY (same value). Map it here so one variable works everywhere.
// Also read ../.env so a single repo-root .env is enough for `pnpm dev` in dashboard/.
const parentEnvPath = path.join(__dirname, "..", ".env");
const clerkFromParent = readEnvFileValue(parentEnvPath, "CLERK_PUBLISHABLE_KEY");
const clerkPublishableKey = (
  process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY ||
  process.env.CLERK_PUBLISHABLE_KEY ||
  clerkFromParent ||
  ""
).trim();

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  env: {
    NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: clerkPublishableKey,
  },

  // In development, proxy /api to the engine so the browser never makes a cross-origin request
  // (avoids CORS issues when running Next.js locally against the production API).
  // In production (DO App Platform) the ingress layer routes /api → the FastAPI service directly.
  async rewrites() {
    const engineUrl =
      process.env.NEXT_PUBLIC_ENGINE_URL ||
      process.env.NEXT_PUBLIC_API_URL ||
      "http://localhost:8000";
    // Only add proxy in dev to avoid double-routing in production
    if (process.env.NODE_ENV === "production") return [];
    return [
      {
        source: "/api/:path*",
        destination: `${engineUrl}/api/:path*`,
      },
    ];
  },

  // Allow embedding the widget in an iframe on the same origin (e.g. /landing preview).
  async headers() {
    const widgetEmbedHeaders = [
      {
        key: "Content-Security-Policy",
        value: "frame-ancestors *",
      },
      {
        key: "Permissions-Policy",
        value: "microphone=(self)",
      },
    ];
    return [
      {
        source: "/widget",
        headers: widgetEmbedHeaders,
      },
      {
        // Embeddable on customer sites: CSP allows framing; mic still needs allow="microphone" on the iframe.
        source: "/widget/:path*",
        headers: widgetEmbedHeaders,
      },
      {
        source: "/landing",
        headers: [{ key: "X-Frame-Options", value: "SAMEORIGIN" }],
      },
    ];
  },
};

module.exports = nextConfig;
