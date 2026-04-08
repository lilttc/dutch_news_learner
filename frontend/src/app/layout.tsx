import type { Metadata } from "next";
import { Analytics } from "@vercel/analytics/next";
import { Header } from "@/components/Header";
import { Providers } from "@/components/Providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "Dutch News Learner",
  description:
    "Learn Dutch from daily NOS Journaal episodes - vocabulary, transcripts, quizzes",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="nl">
      <body className="min-h-screen">
        <Providers>
          <Header />
          <main className="mx-auto max-w-5xl px-4 py-6">{children}</main>
          <footer className="border-t border-[var(--border)] py-6 text-center text-xs text-[var(--muted)]">
            Dutch News Learner - Learn Dutch from NOS Journaal in Makkelijke Taal
          </footer>
        </Providers>
        <Analytics />
      </body>
    </html>
  );
}
