import Link from "next/link";

const STEPS = [
  {
    title: "Print the template",
    text: "Print our A4 sheet at actual size. Its corner markers let us measure in millimetres.",
    href: "/template",
    link: "Get the template",
  },
  {
    title: "Upload an insole photo",
    text: "Lay a shoe's insole on the sheet, take a photo from above and tell us the model and size.",
    href: "/upload",
    link: "Upload a photo",
  },
  {
    title: "Browse shoes by fit",
    text: "Compare shoes by length, width, arch and toe box, measured from real insoles.",
    href: "/shoes",
    link: "Browse shoes",
  },
] as const;

export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col justify-center gap-10 px-6 py-24">
      <div className="flex flex-col gap-4">
        <h1 className="text-4xl font-semibold tracking-tight">FitFinder</h1>
        <p className="text-lg leading-8 text-zinc-600 dark:text-zinc-400">
          Find cycling shoes that fit your feet. Photograph a shoe&apos;s insole on our printable
          template, and we measure its shape so you can compare shoes by fit, not just by size.
        </p>
      </div>

      <ol className="grid gap-6 sm:grid-cols-3">
        {STEPS.map((step, i) => (
          <li key={step.href} className="flex flex-col gap-2">
            <span className="text-sm font-medium text-zinc-500">Step {i + 1}</span>
            <h2 className="font-semibold">{step.title}</h2>
            <p className="text-sm text-zinc-600 dark:text-zinc-400">{step.text}</p>
            <Link href={step.href} className="mt-auto text-sm font-medium underline">
              {step.link}
            </Link>
          </li>
        ))}
      </ol>
    </main>
  );
}
