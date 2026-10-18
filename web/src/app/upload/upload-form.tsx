"use client";

import { type FormEvent, useId, useState } from "react";

import { preparePhoto, UnsupportedPhotoError } from "@/lib/prepare-photo";
import { INSOLE_CONDITIONS, NEW_SHOE, SIZE_SYSTEMS } from "@/lib/submission-form";
import { createClient } from "@/lib/supabase/client";

import { createSubmission } from "./actions";

type ShoeModel = { id: string; brand: string; model: string; year: number };

const input =
  "rounded-md border border-zinc-300 px-3 py-2 text-base font-normal dark:border-zinc-700 dark:bg-zinc-900";
const label = "flex flex-col gap-1 text-sm font-medium";

export function UploadForm({ userId, shoeModels }: { userId: string; shoeModels: ShoeModel[] }) {
  const [shoeModelId, setShoeModelId] = useState("");
  const [status, setStatus] = useState<"idle" | "processing" | "uploading" | "saving">("idle");
  const [error, setError] = useState<string | null>(null);

  const brands = Map.groupBy(shoeModels, (m) => m.brand);
  // Selects get a separate <label htmlFor>: wrapped in a <label>, their option texts
  // would become part of the accessible name.
  const shoeSelectId = useId();
  const sizeSystemId = useId();
  const busy = status !== "idle";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    const form = new FormData(event.currentTarget);
    const file = form.get("photo");
    if (!(file instanceof File) || file.size === 0) {
      setError("Please choose a photo.");
      return;
    }

    try {
      setStatus("processing");
      const photo = await preparePhoto(file);

      // Straight from the browser to the private bucket: photos are often bigger than a
      // server request may be, and RLS only lets users write into their own folder.
      setStatus("uploading");
      const imagePath = `${userId}/${crypto.randomUUID()}.jpg`;
      const { error: uploadError } = await createClient()
        .storage.from("insoles")
        .upload(imagePath, photo, { contentType: "image/jpeg" });
      if (uploadError) {
        throw new Error("upload failed");
      }

      setStatus("saving");
      form.delete("photo");
      form.set("imagePath", imagePath);
      // Redirects on success; only returns when something went wrong.
      const result = await createSubmission(form);
      if (result) {
        setError(result.error);
      }
    } catch (e) {
      setError(
        e instanceof UnsupportedPhotoError ? e.message : "The upload failed. Please try again.",
      );
    }
    setStatus("idle");
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-5">
      <div className={label}>
        <label htmlFor={shoeSelectId}>Shoe model</label>
        <select
          id={shoeSelectId}
          name="shoeModelId"
          required
          value={shoeModelId}
          onChange={(e) => setShoeModelId(e.target.value)}
          className={input}
        >
          <option value="" disabled>
            Choose your shoe…
          </option>
          {[...brands].map(([brand, models]) => (
            <optgroup key={brand} label={brand}>
              {models.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.brand} {m.model} ({m.year})
                </option>
              ))}
            </optgroup>
          ))}
          <option value={NEW_SHOE}>My shoe isn&apos;t listed</option>
        </select>
      </div>

      {shoeModelId === NEW_SHOE && (
        <fieldset className="grid grid-cols-1 gap-3 rounded-lg border border-zinc-200 p-4 sm:grid-cols-3 dark:border-zinc-800">
          <legend className="px-1 text-sm font-medium">New shoe model</legend>
          <label className={label}>
            Brand
            <input name="brand" required maxLength={100} className={input} />
          </label>
          <label className={label}>
            Model
            <input name="model" required maxLength={200} className={input} />
          </label>
          <label className={label}>
            Model year
            <input name="year" type="number" required min={1990} max={2100} className={input} />
          </label>
        </fieldset>
      )}

      <div className="grid grid-cols-2 gap-3">
        <label className={label}>
          Size
          <input name="size" inputMode="decimal" required placeholder="e.g. 43 or 42.5" className={input} />
        </label>
        <div className={label}>
          <label htmlFor={sizeSystemId}>Size system</label>
          <select id={sizeSystemId} name="sizeSystem" defaultValue="eu" className={input}>
            {Object.entries(SIZE_SYSTEMS).map(([value, system]) => (
              <option key={value} value={value}>
                {system.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* No preselection: like consent, the user must actively choose. */}
      <fieldset className="flex flex-col gap-2">
        <legend className="text-sm font-medium">Insole condition</legend>
        {Object.entries(INSOLE_CONDITIONS).map(([value, text]) => (
          <label key={value} className="flex items-center gap-3 text-sm">
            <input type="radio" name="insoleCondition" value={value} required />
            {text}
          </label>
        ))}
      </fieldset>

      <label className={label}>
        Photo of the insole on the template
        {/* On phones, accept="image/*" offers the camera directly. */}
        <input name="photo" type="file" accept="image/*" required className="text-sm font-normal" />
      </label>

      <label className="flex items-start gap-3 text-sm">
        <input name="consent" type="checkbox" required className="mt-1" />
        <span>
          I agree that FitFinder stores this photo to measure the insole. Location and camera
          data are removed before upload. I can delete my photos at any time.
        </span>
      </label>

      {error && (
        <p role="alert" className="text-sm text-red-600">
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={busy}
        className="rounded-md bg-zinc-900 px-4 py-2 font-medium text-white disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
      >
        {
          {
            idle: "Upload",
            processing: "Preparing photo…",
            uploading: "Uploading…",
            saving: "Saving…",
          }[status]
        }
      </button>
    </form>
  );
}
