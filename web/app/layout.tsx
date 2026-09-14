import "./globals.css";

export const metadata = {
  title: "Baltimore Side Quest",
  description: "Auto-scraped, quiz-matched things to do in and around Baltimore.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="max-w-3xl mx-auto px-4 py-8">{children}</body>
    </html>
  );
}
