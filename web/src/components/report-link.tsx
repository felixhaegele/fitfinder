import Link from "next/link";
import type { ReactNode } from "react";

import { reportHref } from "@/lib/legal";

/** Link to report content: an email once the contact address is set, else the terms. */
export function ReportLink({ subject, children }: { subject: string; children: ReactNode }) {
  const href = reportHref(subject);
  return href.startsWith("mailto:") ? (
    <a href={href} className="underline">
      {children}
    </a>
  ) : (
    <Link href={href} className="underline">
      {children}
    </Link>
  );
}
