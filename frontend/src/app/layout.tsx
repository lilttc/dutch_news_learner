import type { Metadata } from "next";
import { Analytics } from "@vercel/analytics/next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Dutch News Learner",
  description:
    "Learn Dutch from daily NOS Journaal episodes — vocabulary, transcripts, quizzes",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="nl">
      <body className="min-h-screen">
        <header className="border-b border-[var(--border)] bg-[var(--card)]">
          <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
            <a href="/" className="text-lg font-bold tracking-tight">
              🇳🇱 Dutch News Learner
            </a>
            <nav className="flex items-center gap-4 text-sm text-[var(--muted)]">
              <a href="/" className="hover:text-[var(--foreground)]">
                Episodes
              </a>
              <a
                href="https://buymeacoffee.com/lilttc"
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-md bg-[#FFDD00] px-3 py-1 text-sm font-medium text-black hover:bg-[#e5c700]"
              >
                ☕ Buy me a coffee
              </a>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-5xl px-4 py-6">{children}</main>
        <footer className="border-t border-[var(--border)] py-6 text-center text-xs text-[var(--muted)]">
          Dutch News Learner — Learn Dutch from NOS Journaal in Makkelijke Taal
        </footer>
        <Analytics />
      </body>
    </html>
  );
}
