"""Tunable numbers of the measurement pipeline, in one place.

Changing any of these can move measurement results, so a change must keep the fixture
regression tests (#25) within tolerance or be deliberate.
"""

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
