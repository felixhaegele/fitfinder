// Runs in the browser before upload. Re-encoding through a canvas drops all metadata
// (GPS position, camera, time) because only pixels are copied. This is for privacy and
// smaller uploads; it is NOT a security check: the worker treats every file as untrusted.

/** ~14 px per mm across A4's long side: plenty for measuring, well under the 10 MiB limit. */
export const MAX_LONG_EDGE = 4000;
const JPEG_QUALITY = 0.92;

export class UnsupportedPhotoError extends Error {}

export async function preparePhoto(file: File): Promise<Blob> {
  let bitmap: ImageBitmap;
  try {
    // "from-image" applies the EXIF orientation first. Phones often store photos sideways
    // and only note the rotation in EXIF; without this the photo would end up rotated.
    bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
  } catch {
    // e.g. HEIC on a browser that can't decode it (all iOS browsers can)
    throw new UnsupportedPhotoError("We can't read this photo. Please use a JPEG or PNG.");
  }

  const scale = Math.min(1, MAX_LONG_EDGE / Math.max(bitmap.width, bitmap.height));
  const width = Math.round(bitmap.width * scale);
  const height = Math.round(bitmap.height * scale);

  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d");
  if (!context) {
    throw new UnsupportedPhotoError("Your browser can't process photos. Please try another one.");
  }
  context.drawImage(bitmap, 0, 0, width, height);
  bitmap.close();

  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new UnsupportedPhotoError("Couldn't process the photo."))),
      "image/jpeg",
      JPEG_QUALITY,
    );
  });
}
