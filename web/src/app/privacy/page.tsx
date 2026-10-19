import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

export const metadata: Metadata = { title: "Privacy · FitFinder" };

// Every statement here must stay true: check docs/security.md, docs/environments.md and the
// ADRs when changing how data is stored, shown or deleted, and update this page with it.
const LAST_UPDATED = "19 October 2026";

// Owner decision (#94): where people send privacy requests. Not the owner's personal address.
const CONTACT: string | null = null;

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-lg font-semibold">{title}</h2>
      {children}
    </section>
  );
}

export default function PrivacyPage() {
  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-8 px-6 py-16 leading-7">
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">Privacy</h1>
        <p className="text-zinc-600 dark:text-zinc-400">
          What FitFinder stores about you, who can see it, and how to delete it. Last updated{" "}
          {LAST_UPDATED}.
        </p>
      </div>

      <Section title="What we store">
        <ul className="list-disc space-y-1 pl-5">
          <li>Your email address, to send you login links. There are no passwords.</li>
          <li>
            For each upload: the photo of the insole, the shoe model, size and insole condition
            you entered, the time you gave consent, and the measurements we calculate from the
            photo.
          </li>
          <li>
            Two copies of each photo: the one you uploaded, and a cleaned copy our server makes
            from it (see below).
          </li>
        </ul>
        <p>
          We use cookies only to keep you logged in. There are no advertising or analytics
          trackers.
        </p>
      </Section>

      <Section title="Where it is stored">
        <ul className="list-disc space-y-1 pl-5">
          <li>
            Your account, uploads and photos are stored with <strong>Supabase</strong> in the EU
            (Ireland).
          </li>
          <li>
            The website is hosted by <strong>Vercel</strong>, which runs its server functions in
            Dublin (Ireland). Pages are delivered through Vercel&apos;s worldwide network.
          </li>
          <li>The service that measures your photos also runs in an EU region.</li>
          <li>
            Login emails are currently sent through Supabase&apos;s built-in email service. We plan
            to switch to our own email provider in the EU.
          </li>
          <li>
            If something breaks, a technical error report can be sent to <strong>Sentry</strong>{" "}
            (EU data region). Email addresses, cookies, login tokens and photo links are removed
            from it before it leaves our app.
          </li>
          <li>
            Our hosting providers keep technical logs (for example IP addresses) to run and
            protect the service.
          </li>
        </ul>
      </Section>

      <Section title="Your consent">
        <p>
          Before each upload you tick a box to agree that we store the photo to measure the
          insole. Without it, nothing is uploaded. We record when you agreed.
        </p>
      </Section>

      <Section title="Who can see your photos">
        <p>
          Both copies of your photo are kept in <strong>private</strong> storage. Only you can see
          them, on your upload&apos;s page while you are logged in. The page shows them through
          links that are signed for you and <strong>expire after 10 minutes</strong>, so a copied
          link stops working. Other users and visitors can&apos;t open them.
        </p>
        <p>
          Our measuring service reads your photo automatically to measure the insole. As the
          operator of FitFinder, we have technical access to the stored data in order to run the
          service.
        </p>
      </Section>

      <Section title="Location and camera data">
        <p>
          Photos can carry hidden information (EXIF), such as the GPS location where they were
          taken and the camera or phone model. Our upload page removes it in your browser, before
          the photo is sent. Our server then makes a separate cleaned copy that contains no such
          data at all, even if a photo arrived with it.
        </p>
      </Section>

      <Section title="What is public">
        <p>
          The shoe pages show measurements <strong>per shoe model and size</strong>, combined
          from everyone&apos;s uploads: how many insoles were measured, typical lengths and widths,
          and the most common fit labels. They never show photos, email addresses or who uploaded
          what.
        </p>
        <p>
          If only one person has measured a shoe in a given size, its figures come from that one
          insole. They describe the shoe, not you.
        </p>
      </Section>

      <Section title="Deleting your data">
        <ul className="list-disc space-y-1 pl-5">
          <li>
            <strong>One upload:</strong> on the upload&apos;s page, choose &ldquo;Delete this
            upload&rdquo;. This removes both photos and the measurements.
          </li>
          <li>
            <strong>Your whole account:</strong> on your{" "}
            <Link href="/account" className="underline">
              account page
            </Link>
            , choose &ldquo;Delete my account&rdquo;. This immediately removes your login, all your
            uploads, all your photos and all measurements. Shoe models you added to the catalogue
            stay, but are no longer linked to you.
          </li>
        </ul>
        <p>
          Deleted data can still exist in our database provider&apos;s backups for a limited time,
          until those backups are replaced by newer ones.
        </p>
      </Section>

      <Section title="Contact">
        <p>
          For questions about your data, or to ask what we store about you:{" "}
          {CONTACT ?? "contact details will be added here before launch."}
        </p>
      </Section>
    </main>
  );
}
