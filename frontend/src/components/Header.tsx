"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";

export function Header() {
  const { user, loading, logout } = useAuth();
  const pathname = usePathname();

  return (
    <header className="border-b border-[var(--border)] bg-[var(--card)]">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
        <a href="/" className="text-lg font-bold tracking-tight">
          🇳🇱 Dutch News Learner
        </a>
        <nav className="flex items-center gap-4 text-sm text-[var(--muted)]">
          <Link
            href="/"
            className={`hover:text-[var(--foreground)] ${
              pathname === "/" ? "text-[var(--foreground)]" : ""
            }`}
          >
            Episodes
          </Link>
          {loading ? (
            <span className="text-[var(--muted)]">…</span>
          ) : user ? (
            <>
              <span className="text-[var(--foreground)]">{user.email}</span>
              <button
                onClick={logout}
                className="hover:text-[var(--foreground)]"
              >
                Log out
              </button>
            </>
          ) : (
            <>
              <Link
                href="/login"
                className={`hover:text-[var(--foreground)] ${
                  pathname === "/login" ? "text-[var(--foreground)]" : ""
                }`}
              >
                Log in
              </Link>
              <Link
                href="/register"
                className={`rounded-md bg-[var(--accent)] px-3 py-1 text-sm font-medium text-white hover:opacity-90 ${
                  pathname === "/register" ? "opacity-90" : ""
                }`}
              >
                Sign up
              </Link>
            </>
          )}
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
  );
}
