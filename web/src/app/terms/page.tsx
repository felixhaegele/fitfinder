import type { Metadata } from "next";
import Link from "next/link";

import { LegalSection as Section } from "@/components/legal-section";
import {
  CONTACT_EMAIL,
  GOVERNING_LAW,
  MINIMUM_AGE,
  OPERATOR_ADDRESS,
  OPERATOR_NAME,
  PENDING,
} from "@/lib/legal";

export const metadata: Metadata = { title: "Terms of use · FitFinder" };

// Keep in line with /privacy: the licence below ends when data is deleted, because the privacy
// notice promises real deletion (ADR 0006). FitFinder is free and non-commercial (Vercel Hobby
// plan), so there are no payment or advertising clauses.
const LAST_UPDATED = "10 November 2026";

export default function TermsPage() {
  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-8 px-6 py-16 leading-7">
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">Terms of use</h1>
        <p className="text-zinc-600 dark:text-zinc-400">
          The rules for using FitFinder. Last updated {LAST_UPDATED}.
        </p>
      </div>

      <Section title="About these terms">
        <p>
          FitFinder is run by {OPERATOR_NAME ?? PENDING}, {OPERATOR_ADDRESS ?? PENDING} (&ldquo;we&rdquo;).
          These terms apply when you use the website. By creating an account you agree to them.
          You can browse shoes without an account; the rules on fair use below apply then too.
        </p>
        <p>
          How we handle personal data is explained in our{" "}
          <Link href="/privacy" className="underline">
            privacy notice
          </Link>
          .
        </p>
      </Section>

      <Section title="The service">
        <p>
          FitFinder measures shoe insoles from photos and shows, per shoe model and size, how the
          insoles of that shoe are shaped. It is a free, non-commercial project and is still being
          built. Features can change, and we may pause or end the service. We&apos;ll try to give
          you notice before ending it, so you can delete your data first.
        </p>
      </Section>

      <Section title="Your account">
        <ul className="list-disc space-y-1 pl-5">
          <li>You must be at least {MINIMUM_AGE} years old to create an account.</li>
          <li>
            You log in with links sent to your email address. Keep access to that mailbox to
            yourself: whoever can read it can log in as you.
          </li>
          <li>One account per person. Don&apos;t create accounts for other people.</li>
        </ul>
      </Section>

      <Section title="What you can upload">
        <ul className="list-disc space-y-1 pl-5">
          <li>
            Only photos of a shoe insole lying on the{" "}
            <Link href="/template" className="underline">
              FitFinder template
            </Link>
            .
          </li>
          <li>
            No people, faces, documents or anything else that shows personal information, yours
            or anyone else&apos;s.
          </li>
          <li>Only photos you took yourself or are allowed to use.</li>
          <li>
            Shoe details (brand, model, year, size) that are true to the best of your knowledge.
            Don&apos;t upload made-up or deliberately misleading insoles: other cyclists rely on
            these figures.
          </li>
        </ul>
      </Section>

      <Section title="Fair use">
        <p>Don&apos;t:</p>
        <ul className="list-disc space-y-1 pl-5">
          <li>try to get around the upload limit, access controls or other protections;</li>
          <li>
            try to access other people&apos;s accounts or photos, or probe, attack or overload the
            service;
          </li>
          <li>collect data from the website automatically in bulk;</li>
          <li>use FitFinder for anything unlawful.</li>
        </ul>
        <p>
          If you find a security problem, please tell us at {CONTACT_EMAIL ?? PENDING} instead of
          testing it further.
        </p>
      </Section>

      <Section title="Your content">
        <p>
          Your photos stay yours. So that we can run FitFinder, you allow us, free of charge, to
          store and process your photos and shoe details, to measure the insole, and to include
          the measurements in the combined public figures for that shoe model and size. We
          don&apos;t show your photos to anyone else.
        </p>
        <p>
          This permission ends when you delete the upload or your account. From then on the photo
          and its measurements are gone, and they no longer count in the public figures. The one
          exception is shoe models you added to the catalogue (brand, model, year): they are
          facts about a shoe, so they stay, without any link to you.
        </p>
        <p>We may remove uploads that break these terms.</p>
      </Section>

      <Section title="Measurements are estimates">
        <p>
          Measurements and fit labels are calculated automatically from photos, many of them
          taken by other users. They can be wrong: because of the photo, the printout, a worn
          insole or a mistake in our software. Shoe makers can also change a shoe without changing
          its name.
        </p>
        <p>
          Use FitFinder as a guide, not as a promise that a shoe will fit. Try shoes on, and check
          the seller&apos;s return policy before you buy. FitFinder is not medical advice: if you
          have foot problems, ask a professional.
        </p>
      </Section>

      <Section title="Liability">
        <p>
          FitFinder is free, and we provide it as it is, without any promise that it is always
          available, free of errors or suitable for a particular purpose.
        </p>
        <p>
          We are fully liable for damage we cause intentionally or through gross negligence, for
          injury to life, body or health, and wherever the law doesn&apos;t allow liability to be
          limited. Beyond that, to the extent the law allows, we are not liable for damage from
          using FitFinder, in particular for a shoe bought on the basis of its figures that
          doesn&apos;t fit.
        </p>
      </Section>

      <Section title="Ending your use">
        <p>
          You can stop using FitFinder at any time and delete your account on your{" "}
          <Link href="/account" className="underline">
            account page
          </Link>
          . We may suspend or delete accounts that seriously or repeatedly break these terms. If
          we do, we&apos;ll tell you why, unless that would help someone abuse the service.
        </p>
      </Section>

      <Section title="Changes to these terms">
        <p>
          We may update these terms, for example when FitFinder gets new features. We change the
          date at the top, and tell you by email about important changes before they take effect.
          If you don&apos;t agree, you can delete your account. If you keep using FitFinder after
          the change takes effect, the new terms apply.
        </p>
      </Section>

      <Section title="Open-source code">
        <p>
          FitFinder&apos;s source code is published under the MIT licence. That licence covers the
          code only. These terms cover using the website and the data on it.
        </p>
      </Section>

      <Section title="Law and disputes">
        <p>
          These terms are governed by {GOVERNING_LAW ?? PENDING}. If you use FitFinder as a
          consumer, you keep the protection of the mandatory consumer law of the country where you
          live, and you can bring a claim in the courts there.
        </p>
        <p>
          If a part of these terms is invalid, the rest still applies.
        </p>
      </Section>

      <Section title="Contact">
        <p>Questions about these terms: {CONTACT_EMAIL ?? PENDING}.</p>
      </Section>
    </main>
  );
}
