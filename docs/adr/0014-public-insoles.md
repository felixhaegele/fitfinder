# 0014. Publish each measured insole's shoe data and outline, so users can print it 1:1

- **Status:** Accepted (amends [0011](0011-public-shoe-fit-summary.md))
- **Date:** 2026-11-10

## Context

Numbers alone don't tell a cyclist whether a shoe fits. What they want to know is simple: does my foot fit on this insole? The owner wants each shoe page (one per brand, model and year) to list every measured insole. Each insole gets a PDF of its shape at 1:1. The user prints it, stands on it with their larger foot, and sees whether the foot fits inside the line (#122). Which foot is larger varies from person to person, so the PDF needs a page for each foot.

ADR 0011 only allowed **aggregates** per shoe and per size, and named the outline as a per-person field. A table with one row per insole, and a PDF of one insole's outline, are rows. So that rule has to change.

The owner decided (2026-11-10) that an insole's data describes the shoe, not the person. That covers its size, measurements, fit labels, condition (new / used), the side that was photographed, and its outline. ADR 0011 already accepted the same argument for the measurements at n = 1. There are no real uploads yet, so nobody has consented under the old wording.

## Decision

We will publish per-insole shoe data through two more `security definer` functions, built like those of ADR 0011. They have the same grants, a pinned `search_path`, and the same private "newest results of done submissions" view. That view gets the extra columns appended.

- `public.shoe_insoles(shoe_model uuid)`: one row per done submission of the shoe. Columns: insole id, size, size system, insole condition, side, length, ball, heel and arch width, and the four labels. Rows are ordered by size and length, never by date, so the order doesn't reveal who uploaded when.
- `public.shoe_insole(insole uuid)`: one insole with the shoe's id, brand, model and year, plus its outline (`outline_mm`), for the PDF.

They never return the user, email, photo or processed-image path, any date, the rejection reason, or the submission id.

The insole id is a new `submissions.public_id`. It is random, unique, and filled in by default; users can't choose or change it. We don't use the submission id, because that one belongs to the owner (`/submissions/<id>`), and a public link should never name a private row. We don't use the measurement id either, because re-processing creates a new measurement and the link should keep working.

The web serves the PDF from `GET /shoes/[id]/insoles/[insoleId]`, and builds it with `pdf-lib` (`web/src/lib/insole-pdf.ts`):

- The outline is drawn at 1:1 on A4, along the diagonal like the photo template (ADR 0004). If an insole doesn't fit the page or would touch the text, the outline is turned a few degrees or shifted a few millimetres. Insoles up to about 315 mm fit, which covers everything the photo template can measure (about 300 mm).
- **Page 1 is the left foot and page 2 the right foot.** Outlines are stored as a right foot (ADR 0009), and a pair's insoles are mirror images, so the left page is the mirror.
- Each page shows the shoe and insole details and a 100 mm check ruler, and asks for "actual size" printing. The photo is never in it.
- The route only answers when the shoe id in the URL matches the insole's shoe.

The privacy page and the upload consent say that each insole's measurements and outline are published on the shoe's page, without the photo or the uploader's name.

## Alternatives considered

- **One median outline per shoe model and size.** This stays an aggregate, so ADR 0011 could have stayed as it was. But a median of a few outlines is a shape nobody measured. A real insole is easier to trust, and showing each one makes bad uploads easy to spot.
- **Publish from a minimum number of uploads, or only "new" insoles.** The owner keeps n = 1, as in ADR 0011, so the site has content early. The outline is only the insole's edge, not the foot's imprint, so a used insole adds no personal detail.
- **Open the tables to anon with RLS.** Still rejected for the reasons in ADR 0011: it would publish user ids, image paths and dates.
- **Generate the PDF in the worker (Python, like `/print`).** That would keep all PDF code in one language, but it needs a new job or endpoint and storage for generated files. The web already has everything the PDF needs, and making it on request means a deleted upload's PDF is gone at once.

## Consequences

- Anyone can now see each insole's data and download its outline. Someone who knows that a person uploaded a given shoe in a given size can find that insole. That was already true of the per-size numbers at n = 1, and it still says nothing about the person beyond the shoe they own.
- **Deleting an upload or an account removes its row and PDF**, because both are built from the database on each request. PDFs that were already downloaded can't be recalled. The privacy page says so.
- Any new column in `shoe_insoles` or `shoe_insole` is a privacy decision. `supabase/tests/database/97_public_insoles.test.sql` pins both column lists, so changing one is always deliberate.
- An A3 template (ADR 0004) would need a bigger page here too. Until then, an insole that doesn't fit A4 gets "too large to print on A4" (HTTP 422).
- Fake or bad uploads are now visible one by one, which helps outlier handling in v2.
