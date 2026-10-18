import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = { title: "Account deleted · FitFinder" };

export default function AccountDeletedPage() {
  return (
    <main className="mx-auto flex w-full max-w-xl flex-1 flex-col gap-6 px-6 py-16">
      <h1 className="text-2xl font-semibold tracking-tight">Your account has been deleted</h1>
      <p role="status">
        Your login, your submissions and all your photos have been removed from FitFinder.
      </p>
      <Link href="/" className="text-sm font-medium underline">
        Back to the home page
      </Link>
    </main>
  );
}
