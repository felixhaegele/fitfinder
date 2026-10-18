import Link from "next/link";
import { Suspense } from "react";

import { signOut } from "@/app/auth/actions";
import { getUser } from "@/lib/auth";

export function SiteHeader() {
  return (
    <header className="border-b border-zinc-200 dark:border-zinc-800">
      <div className="mx-auto flex w-full max-w-4xl items-center justify-between px-6 py-3">
        <Link href="/" className="font-semibold">
          FitFinder
        </Link>
        {/* The rest of the page is static; only this part waits for the session. */}
        <Suspense fallback={<span className="text-sm text-zinc-400">…</span>}>
          <AuthStatus />
        </Suspense>
      </div>
    </header>
  );
}

async function AuthStatus() {
  const user = await getUser();

  if (!user) {
    return (
      <Link href="/login" className="text-sm font-medium">
        Log in
      </Link>
    );
  }

  return (
    <div className="flex items-center gap-4 text-sm">
      <Link href="/account" className="text-zinc-600 dark:text-zinc-400">
        {user.email}
      </Link>
      <form action={signOut}>
        <button type="submit" className="font-medium">
          Log out
        </button>
      </form>
    </div>
  );
}
