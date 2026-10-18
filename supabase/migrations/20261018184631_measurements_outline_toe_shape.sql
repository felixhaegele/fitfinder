-- Insole outline + side on measurements, toe_shape on classifications (#52).
--
-- Outline frame (owner decision "option A", 2026-10-18, one frame everywhere):
--   * millimetres; the heel point is the origin (0, 0) and the toe tip is (0, length_mm),
--     so the toe points along +y and x runs across the insole
--   * canonical foot is right: left insoles are mirrored (x -> -x) and `side` keeps the
--     original side; the medial (big-toe) side is at -x
--   * exactly 256 points, resampled evenly along the contour, starting at the heel point
--     and going heel -> medial -> toe -> lateral
--
-- Stored as jsonb [[x, y], ...] rather than numeric[] (reasoning in the #52 PR): pairs keep
-- their structure, PostgREST hands the web client a ready-to-draw array, and jsonb numbers
-- are Postgres numeric internally, so millimetre values keep exact decimals.
--
-- Like every measurement, the outline is re-computed per pipeline_version.
--
-- not null without a default only works because no hosted database has measurements or
-- classifications yet. Once production has data, a change like this needs a backfill step.
--
-- RLS: no new policies needed. The existing row-level select policies on measurements and
-- classifications cover every column, and insert/update/delete stay revoked from anon and
-- authenticated (only the worker writes, via the service role).

alter table public.measurements
  add column side text not null
    check (side in ('left', 'right')),
  add column outline_mm jsonb not null
    constraint measurements_outline_mm_shape check (
      -- case forces the order: jsonb_array_length() raises on a non-array instead of
      -- returning false, and plain `and` doesn't guarantee evaluation order.
      case
        when jsonb_typeof(outline_mm) <> 'array' then false
        else
          jsonb_array_length(outline_mm) = 256
          -- every point is an [x, y] pair ...
          and not jsonb_path_exists(outline_mm, '$[*] ? (@.type() != "array" || @.size() != 2)')
          -- ... of numbers
          and not jsonb_path_exists(outline_mm, '$[*][*] ? (@.type() != "number")')
          -- the outline starts at the heel point, the origin of the frame
          and outline_mm -> 0 = '[0, 0]'::jsonb
      end
    );

comment on column public.measurements.side is
  'Side of the photographed insole. Left outlines are mirrored onto right; this records the original.';
comment on column public.measurements.outline_mm is
  'Insole outline: 256 [x, y] points in mm. Heel point at (0, 0), toe along +y, right-foot frame '
  '(medial at -x), evenly resampled, ordered heel -> medial -> toe -> lateral.';

-- toe_shape describes the toe-end slant (which toe the insole is longest at), alongside
-- toe_box_shape (round/square/pointed), which stays. Both describe the shoe's toe box.
alter table public.classifications
  add column toe_shape text not null
    check (toe_shape in ('egyptian', 'roman', 'greek'));

comment on column public.classifications.toe_shape is
  'Toe-end slant of the insole: egyptian (longest at the big toe), roman (flat across the '
  'first toes), greek (longest at the 2nd toe).';
