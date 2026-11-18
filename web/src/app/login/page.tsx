import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { safeNextPath } from "@/lib/redirect";

import { LoginForm } from "./login-form";

export const metadata: Metadata = { title: "Log in · FitFinder" };

export default function LoginPage({ searchParams }: PageProps<"/login">) {
  return (
    <main className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center gap-6 px-6 py-24">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Log in or sign up</h1>
        <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
          No password needed. We&apos;ll email you a link.
        </p>
      </div>
      {/* searchParams are request data, so the form streams in behind a boundary. */}
      <Suspense>
        <LoginFormWithParams searchParams={searchParams} />
      </Suspense>
      {/* A magic link creates the account, so this is where people agree to the terms. */}
      <p className="text-sm text-zinc-600 dark:text-zinc-400">
        By logging in or signing up you agree to our{" "}
        <Link href="/terms" className="underline">
          terms of use
        </Link>
        . Our{" "}
        <Link href="/privacy" className="underline">
          privacy notice
        </Link>{" "}
        explains how we handle your data.
      </p>
    </main>
  );
}

async function LoginFormWithParams({
  searchParams,
}: {
  searchParams: PageProps<"/login">["searchParams"];
}) {
  const params = await searchParams;
  return <LoginForm next={safeNextPath(params.next)} linkError={params.error === "link"} />;
}
