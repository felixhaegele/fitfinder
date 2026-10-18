import type { Metadata } from "next";
import { Suspense } from "react";

import { requireUser } from "@/lib/auth";
import { createClient } from "@/lib/supabase/server";

import { UploadForm } from "./upload-form";

export const metadata: Metadata = { title: "Upload an insole · FitFinder" };

export default function UploadPage() {
  return (
    <main className="mx-auto flex w-full max-w-xl flex-1 flex-col gap-6 px-6 py-16">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Upload an insole</h1>
        <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
          Place the shoe&apos;s insole on the printed FitFinder template and take a photo from
          straight above, with all four corner markers visible.
        </p>
      </div>
      <Suspense fallback={<p className="text-zinc-500">Loading…</p>}>
        <UploadFormForUser />
      </Suspense>
    </main>
  );
}

async function UploadFormForUser() {
  const user = await requireUser("/upload");
  const supabase = await createClient();
  const { data: shoeModels } = await supabase
    .from("shoe_models")
    .select("id, brand, model, year")
    .order("brand")
    .order("model")
    .order("year", { ascending: false });

  return <UploadForm userId={user.id} shoeModels={shoeModels ?? []} />;
}
