import Link from "next/link";

export function SiteFooter() {
  return (
    <footer className="border-t border-zinc-200 dark:border-zinc-800">
      <div className="mx-auto flex w-full max-w-4xl gap-6 px-6 py-4 text-sm text-zinc-600 dark:text-zinc-400">
        <Link href="/privacy">Privacy</Link>
        <Link href="/template">Printable template</Link>
      </div>
    </footer>
  );
}
