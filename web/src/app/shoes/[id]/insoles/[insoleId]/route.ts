import { insolePdf, InsoleTooLargeError } from "@/lib/insole-pdf";
import { fileSlug, sizeLabel, UUID } from "@/lib/shoe-fit";
import { getInsole } from "@/lib/shoes";

/**
 * One insole as a printable PDF (#122, ADR 0014): its outline at 1:1, a page for each foot.
 * Shoe data only, from the same kind of function as the shoe page; never the photo.
 */
export async function GET(_request: Request, { params }: RouteContext<"/shoes/[id]/insoles/[insoleId]">) {
  const { id, insoleId } = await params;
  const insole = UUID.test(id) && UUID.test(insoleId) ? await getInsole(insoleId) : null;
  // The shoe id in the URL must match, so a link can't show one shoe's name with another's insole.
  if (!insole || insole.shoe_model_id !== id) {
    return new Response("Insole not found.", { status: 404, headers: { "Content-Type": "text/plain; charset=utf-8" } });
  }

  let pdf: Uint8Array;
  try {
    pdf = await insolePdf(insole);
  } catch (error) {
    if (error instanceof InsoleTooLargeError) {
      return new Response(error.message, { status: 422, headers: { "Content-Type": "text/plain; charset=utf-8" } });
    }
    throw error;
  }

  const name = fileSlug(insole.brand, insole.model, String(insole.year), sizeLabel(insole.size, insole.size_system));
  return new Response(new Blob([pdf as Uint8Array<ArrayBuffer>], { type: "application/pdf" }), {
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": `attachment; filename="fitfinder-insole-${name}.pdf"`,
      "Cache-Control": "no-store",
    },
  });
}
