/** @type {import('next').NextConfig} */
const nextConfig = {
  // Static Web App: exporta HTML/JS/CSS estaticos (o app e 100% client-side,
  // fala com o backend via NEXT_PUBLIC_API_URL). 'next build' gera ./out.
  output: "export",
  images: { unoptimized: true },
};
export default nextConfig;
