/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  // Allow embedding the widget in an iframe on the same origin (e.g. /landing preview).
  async headers() {
    return [
      {
        source: "/widget/:path*",
        headers: [{ key: "X-Frame-Options", value: "SAMEORIGIN" }],
      },
      {
        source: "/landing",
        headers: [{ key: "X-Frame-Options", value: "SAMEORIGIN" }],
      },
    ];
  },
};

module.exports = nextConfig;
