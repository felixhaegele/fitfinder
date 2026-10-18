import { statusCopy } from "@/lib/submission-status";

const TONES = {
  neutral: "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
  busy: "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300",
  good: "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-300",
  bad: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300",
};

export function StatusBadge({ status }: { status: string }) {
  const copy = statusCopy(status);
  return (
    <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${TONES[copy.tone]}`}>
      {copy.label}
    </span>
  );
}
