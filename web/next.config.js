/** @type {import('next').NextConfig} */
module.exports = {
  reactStrictMode: true,
  // Keep the Firebase Admin SDK out of the bundle; it runs as a normal Node package on Vercel.
  experimental: { serverComponentsExternalPackages: ["firebase-admin"] },
};
