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
