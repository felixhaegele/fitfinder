"""Tunable numbers of the measurement pipeline, in one place.

Changing any of these can move measurement results, so a change must keep the fixture
regression tests (#25) within tolerance or be deliberate.
"""

# Stored on every measurements row, so old submissions can be re-measured and results from
# different pipeline versions are never mixed. **Bump it whenever a number in this file up
# to the classification section changes**, or the markers/warp/segment/measure logic does:
# patch = a threshold nudge, minor = a new measurement, major = a different frame or
# definition. The classifier has its own CLASSIFIER_VERSION below.
PIPELINE_VERSION = "1.0.0"

# Resolution of the flattened top-down page image. 10 px/mm makes an A4 page 2100 x 2970 px:
# fine enough for 0.1 mm rounding, small enough to process in well under a second.
PX_PER_MM = 10.0

# Each marker gives 4 corners, and a homography needs 4 points, so 1 marker would do in
# theory. 3 keeps the points spread over the page (accurate) and tolerates one marker
# being covered or in a reflection.
MIN_MARKERS = 3

# Largest allowed distance (mm) between a detected marker corner and where the homography
# puts it. Flat paper photographed in focus stays well below 0.5 mm; above this, the paper
# is curled or folded and measurements would be off.
MAX_MARKER_FIT_ERROR_MM = 1.5

# --- Segmentation (#22, ADR 0005) ---

# The search region is the measuring zone shrunk by this much, so the grey dashed guides
# printed on its border are never mistaken for part of the insole.
ZONE_MARGIN_MM = 1.5

# Paper brightness (0-255, 90th percentile inside the zone) below which the photo is
# too dark: noise then swamps the insole's edge. Normal indoor light gives 150-250.
MIN_PAPER_BRIGHTNESS = 60.0

# Window for estimating the paper's brightness everywhere (lighting flattening). Must be
# wider than any insole (~115 mm at most) so the window always reaches some paper.
BACKGROUND_WINDOW_MM = 121

# Smallest brightness difference between insole and paper, as a fraction of the paper's
# brightness (after flattening), that counts as "an insole is there".
MIN_INSOLE_CONTRAST = 0.15

# Smallest plausible insole area. A child's EU 30 insole is about 10 000 mm^2.
MIN_INSOLE_AREA_MM2 = 8000.0

# Opening/closing kernel that removes noise specks from the insole mask. Small enough to
# keep a pointed toe tip intact.
CLEANUP_KERNEL_MM = 0.7

# Largest allowed edge blur (Gaussian sigma, mm, measured on the flattened page). A phone
# photo in focus is around 0.1-0.3 mm. The limit is set by the *markers*, not the insole:
# blurred marker corners skew the homography, so in the synthetic tests a 0.6 mm blur
# already moves page points by ~0.6 mm and 0.9 mm by ~2 mm, while segmentation itself
# stays within ~0.1 mm. 0.5 mm keeps the whole pipeline inside the 1 mm tolerance.
MAX_EDGE_BLUR_MM = 0.5

# The insole "touches the edge" of the search region if at least this much of its
# outline (mm) lies on that edge.
EDGE_TOUCH_MIN_MM = 1.0

# --- Measuring (#23) ---

# Before measuring, the outline is resampled every OUTLINE_STEP_MM and smoothed along its
# length with a Gaussian of OUTLINE_SMOOTHING_MM, to remove the pixel staircase (at
# 10 px/mm a pixel is 0.1 mm). Larger smoothing would round off a pointed toe tip.
OUTLINE_STEP_MM = 0.1
OUTLINE_SMOOTHING_MM = 0.4

# Telling heel from toe: the half of the insole (split at mid-length) with at least this
# many times the other half's area is the forefoot. Insoles are well above it (the
# synthetic ones are around 1.2-1.4). Closer than this, the template's insole_axis decides.
FOREFOOT_AREA_RATIO = 1.05

# Upper bound on the rounds of "take the extremes along the axis, re-aim the axis through
# them". It settles in 2-6 rounds; the bound only guards against a pathological outline.
AXIS_MAX_ITERATIONS = 20

# --- Classification (#24) ---
#
# Rule-based, on ratios, so the labels don't depend on the shoe size. Every
# classifications row stores CLASSIFIER_VERSION, so old submissions can be re-classified.
# **Bump it whenever any number below changes**, or the classify logic does:
# patch = a threshold nudge, minor = a new rule, major = new labels.
#
# These v1 thresholds are first guesses, placed between the synthetic fixtures' shapes
# (tests/fixtures). They must be calibrated on real insoles (v2: crowd data).
CLASSIFIER_VERSION = "1.0.0"

# width_class from ball width / length. Typical insoles are around 0.36-0.38.
WIDTH_NARROW_BELOW = 0.355
WIDTH_WIDE_ABOVE = 0.390

# arch_class from arch (midfoot) width / ball width. A high arch leaves a narrow midfoot
# on the insole, a low (flat) arch a wide one. Typical insoles are around 0.55-0.58.
ARCH_HIGH_BELOW = 0.52
ARCH_LOW_ABOVE = 0.60

# toe_box_shape from the toe width at 90 % of the length / ball width: how much of the
# ball width the toe box keeps near its end. Synthetic pointed / round / square toes give
# 0.58 / 0.77 / 0.93.
TOE_BOX_POINTED_BELOW = 0.67
TOE_BOX_SQUARE_ABOVE = 0.85

# toe_shape from the toe-end slant of the stored outline: how much further forward the
# toe end reaches at the big toe than at the 2nd/3rd toe. Measured at these fractions of
# the toe-box width (at 85 % of the length) from its medial edge, as a fraction of that
# width. Positive = longest at the big toe.
TOE_SLANT_AT = (0.15, 0.45)
# Above this: egyptian (longest at the big toe).
TOE_SLANT_EGYPTIAN_ABOVE = 0.03
# Below this: greek (longest near the 2nd toe / centre). In between: roman (level across
# the first toes). The band reaches further down than up because even a flat-fronted
# (square) toe box rounds off at its medial corner, near the big-toe sample point:
# synthetic square toes give about -0.08.
TOE_SLANT_GREEK_BELOW = -0.10
