/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",

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
    return [
      {
        // Embeddable on customer sites: CSP allows framing; mic still needs allow="microphone" on the iframe.
        source: "/widget/:path*",
        headers: [
          {
            key: "Content-Security-Policy",
            value: "frame-ancestors *",
          },
          {
            key: "Permissions-Policy",
            value: "microphone=(self)",
          },
        ],
      },
      {
        source: "/landing",
        headers: [{ key: "X-Frame-Options", value: "SAMEORIGIN" }],
      },
    ];
  },
};

module.exports = nextConfig;
