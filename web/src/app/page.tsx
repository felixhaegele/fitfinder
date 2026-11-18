import Link from "next/link";

const button =
  "rounded-md px-5 py-2.5 text-center font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-900 dark:focus-visible:outline-zinc-100";

const STEPS = [
  {
    title: "Print the template",
    text: "Print our A4 sheet at actual size. Its corner markers let us measure in millimetres.",
  },
  {
    title: "Photograph the insole",
    text: "Lay the shoe's insole on the sheet, take a photo from straight above and add the model and size.",
  },
  {
    title: "Compare by fit",
    text: "We measure length, width, arch and toe box, so you can compare shoes by shape, not just by size.",
  },
] as const;

export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-16 px-6 py-24">
      <section aria-labelledby="hero" className="flex flex-col gap-6">
        <p className="text-sm font-medium text-zinc-500">FitFinder</p>
        <h1 id="hero" className="text-4xl font-semibold tracking-tight sm:text-5xl">
          Cycling shoes that fit your feet
        </h1>
        <p className="text-lg leading-8 text-zinc-600 dark:text-zinc-400">
          Sizes say little about shape. We measure real insoles, so you can see how wide a shoe is
          at the ball, how much arch it has and how its toe box is shaped before you buy.
        </p>
        <div className="flex flex-col gap-3 sm:flex-row">
          <Link
            href="/upload"
            className={`${button} bg-zinc-900 text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300`}
          >
            Upload a shoe
          </Link>
          <Link
            href="/shoes"
            className={`${button} border border-zinc-300 hover:bg-zinc-50 dark:border-zinc-700 dark:hover:bg-zinc-900`}
          >
            View shoes
          </Link>
        </div>
        <p className="text-sm text-zinc-500">
          Uploading is free. You need an account and a{" "}
          <Link href="/template" className="font-medium underline">
            printed A4 template
          </Link>
          . Browsing needs neither.
        </p>
      </section>

      <section aria-labelledby="how-it-works" className="flex flex-col gap-6">
        <h2 id="how-it-works" className="text-xl font-semibold">
          How it works
        </h2>
        <ol className="grid gap-6 sm:grid-cols-3">
          {STEPS.map((step, i) => (
            <li key={step.title} className="flex flex-col gap-2">
              <span className="text-sm font-medium text-zinc-500">Step {i + 1}</span>
              <h3 className="font-semibold">{step.title}</h3>
              <p className="text-sm text-zinc-600 dark:text-zinc-400">{step.text}</p>
            </li>
          ))}
        </ol>
      </section>
    </main>
  );
}
