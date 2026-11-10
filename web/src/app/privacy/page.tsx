import type { Metadata } from "next";
import Link from "next/link";

import { LegalSection as Section } from "@/components/legal-section";
import { CONTACT_EMAIL, OPERATOR_ADDRESS, OPERATOR_NAME, PENDING } from "@/lib/legal";

export const metadata: Metadata = { title: "Privacy · FitFinder" };

// Every statement here must stay true: check docs/security.md, docs/environments.md and the
// ADRs when changing how data is stored, shown or deleted, and update this page with it.
// Structure follows GDPR Art. 13 and Swiss FADP Art. 19.
const LAST_UPDATED = "10 November 2026";

export default function PrivacyPage() {
  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-8 px-6 py-16 leading-7">
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">Privacy</h1>
        <p className="text-zinc-600 dark:text-zinc-400">
          What FitFinder stores about you, why, who can see it, and how to delete it. This notice
          covers the EU General Data Protection Regulation (GDPR) and the Swiss Federal Act on
          Data Protection (FADP). Last updated {LAST_UPDATED}.
        </p>
      </div>

      <Section title="Who is responsible">
        <p>
          FitFinder is run by {OPERATOR_NAME ?? PENDING}, {OPERATOR_ADDRESS ?? PENDING} (&ldquo;we&rdquo;).
          We are responsible (the &ldquo;controller&rdquo;) for the personal data described here.
          You can reach us at {CONTACT_EMAIL ?? PENDING}.
        </p>
      </Section>

      <Section title="What we store">
        <ul className="list-disc space-y-1 pl-5">
          <li>Your email address, to send you login links. There are no passwords.</li>
          <li>
            For each upload: the photo of the insole, the shoe model, size and insole condition
            you entered, the time you gave consent, and the measurements and fit labels we
            calculate from the photo.
          </li>
          <li>
            Two copies of each photo: the one you uploaded, and a cleaned copy our server makes
            from it (see below).
          </li>
          <li>Shoe models you add to the catalogue (brand, model, year).</li>
          <li>
            Technical data that every website request produces, such as your IP address, browser
            type and the time of the request, in our hosting providers&apos; logs.
          </li>
        </ul>
        <p>
          You need an email address to have an account. Uploading photos is voluntary: you can
          browse shoes without an account, and an account without uploads is fine too.
        </p>
      </Section>

      <Section title="Why we use it and on what legal basis">
        <ul className="list-disc space-y-2 pl-5">
          <li>
            <strong>Your account and login</strong> (email address, login cookies): to provide the
            service you signed up for. Legal basis: performance of our agreement with you (GDPR
            Art. 6(1)(b)).
          </li>
          <li>
            <strong>Measuring your photos and adding the results to the public shoe figures</strong>:
            based on your consent, which you give for each upload (GDPR Art. 6(1)(a)).
          </li>
          <li>
            <strong>Keeping the service running and secure</strong> (server logs, error reports,
            the limit of 20 uploads per day): our legitimate interest in a working, safe service
            that can&apos;t be abused (GDPR Art. 6(1)(f)).
          </li>
        </ul>
        <p>
          We don&apos;t sell your data, show ads or build profiles about you for marketing.
        </p>
      </Section>

      <Section title="Your consent">
        <p>
          Before each upload you tick a box to agree that we store the photo, measure the insole
          and count the measurements towards the public figures for that shoe. Without it,
          nothing is uploaded. We record when you agreed.
        </p>
        <p>
          You can withdraw your consent at any time by deleting the upload (see &ldquo;Deleting
          your data&rdquo;). This doesn&apos;t make what we did before unlawful, but from then on
          the photo, its measurements and its share in the public figures are gone.
        </p>
      </Section>

      <Section title="Where it is stored">
        <p>We use these service providers. They process data only on our behalf.</p>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            Your account, uploads and photos are stored with <strong>Supabase</strong> in the EU
            (Ireland).
          </li>
          <li>
            The website is hosted by <strong>Vercel</strong>, which runs its server functions in
            Dublin (Ireland). Pages are delivered through Vercel&apos;s worldwide network, from a
            server close to you.
          </li>
          <li>
            The service that measures your photos runs on <strong>Google Cloud</strong> in Belgium.
          </li>
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

      <Section title="Transfers outside the EU and Switzerland">
        <p>
          We choose EU locations wherever we can. Some of our providers, however, are US
          companies or part of US groups (Supabase, Vercel, Google, Sentry), and Vercel delivers
          pages from servers worldwide. Your data may therefore be accessed from or pass through
          countries outside the EU and Switzerland, in particular the United States. Where that
          happens, it is protected by the safeguards the law requires, such as the European
          Commission&apos;s standard contractual clauses or the provider&apos;s certification
          under the EU-US and Swiss-US Data Privacy Framework. You can ask us for details.
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
          insole. They describe the shoe, not you. The figures are calculated fresh each time a
          page is opened, so when you delete an upload it no longer counts.
        </p>
        <p>Shoe models you add to the catalogue are visible to everyone, without your name.</p>
      </Section>

      <Section title="Automated measuring">
        <p>
          Measurements and fit labels (for example &ldquo;wide forefoot&rdquo;) are calculated
          automatically from the photo. They describe the insole of a shoe. We don&apos;t use them
          to make decisions about you that have legal or similarly significant effects.
        </p>
      </Section>

      <Section title="Cookies">
        <p>
          We use cookies only to keep you logged in. They are needed for the service to work, so
          we don&apos;t ask for separate consent. There are no advertising or analytics trackers.
        </p>
      </Section>

      <Section title="How long we keep it">
        <ul className="list-disc space-y-1 pl-5">
          <li>
            <strong>Account:</strong> until you delete it.
          </li>
          <li>
            <strong>Uploads, photos and measurements:</strong> until you delete the upload or your
            account.
          </li>
          <li>
            <strong>Shoe models you added:</strong> they stay in the catalogue, but are no longer
            linked to you once you delete your account.
          </li>
          <li>
            <strong>Server logs and error reports:</strong> for a limited time, as set by our
            providers, then deleted automatically.
          </li>
          <li>
            <strong>Backups:</strong> deleted data can still exist in our database provider&apos;s
            backups for a limited time, until those backups are replaced by newer ones.
          </li>
        </ul>
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
      </Section>

      <Section title="Your rights">
        <p>You have the right to:</p>
        <ul className="list-disc space-y-1 pl-5">
          <li>ask what data we have about you and get a copy of it (access);</li>
          <li>have wrong data corrected (rectification);</li>
          <li>have your data deleted (erasure), which you can also do yourself, see above;</li>
          <li>have the use of your data restricted in certain cases (restriction);</li>
          <li>
            get the data you gave us in a common machine-readable format (portability). There is
            no export button yet: write to us and we&apos;ll send it;
          </li>
          <li>
            object to uses based on our legitimate interest, for reasons relating to your
            situation (objection);
          </li>
          <li>withdraw your consent at any time, with effect for the future.</li>
        </ul>
        <p>
          To use these rights, write to {CONTACT_EMAIL ?? PENDING}. We may ask you to confirm the
          request from the email address of your account, so we know it&apos;s you.
        </p>
        <p>
          You can also complain to a data protection authority, in particular in the EU or EEA
          country where you live or work, or, in Switzerland, to the Federal Data Protection and
          Information Commissioner (FDPIC). We&apos;d appreciate the chance to sort it out with you
          first.
        </p>
      </Section>

      <Section title="Changes to this notice">
        <p>
          If we change how we handle your data, we update this page and the date at the top. If a
          change matters for data we already have, we&apos;ll tell you by email before it takes
          effect, and ask for consent again where it&apos;s needed.
        </p>
        <p>
          See also our{" "}
          <Link href="/terms" className="underline">
            terms of use
          </Link>
          .
        </p>
      </Section>

      <Section title="Contact">
        <p>
          For questions about your data, or to ask what we store about you:{" "}
          {CONTACT_EMAIL ?? "contact details will be added here before launch."}
        </p>
      </Section>
    </main>
  );
}
