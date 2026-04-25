/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
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
