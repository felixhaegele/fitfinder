"""Reasons a photo can't be measured, with the message shown to the user.

A rejection is a normal outcome (the submission becomes `rejected` with the message as
`rejection_reason`), not a crash: the job is not retried.
"""

from enum import StrEnum


class RejectionCode(StrEnum):
    MARKERS_NOT_FOUND = "markers_not_found"
    PAPER_NOT_FLAT = "paper_not_flat"
    TOO_DARK = "too_dark"
    INSOLE_NOT_FOUND = "insole_not_found"
    TOO_BLURRY = "too_blurry"
    INSOLE_TOUCHES_EDGE = "insole_touches_edge"


MESSAGES: dict[RejectionCode, str] = {
    RejectionCode.MARKERS_NOT_FOUND: (
        "We couldn't find the black squares on the template. Make sure all four are "
        "visible, in focus and not covered, then take the photo again."
    ),
    RejectionCode.PAPER_NOT_FLAT: (
        "The template doesn't seem to lie flat. Smooth out the paper on a flat surface "
        "and take the photo again from straight above."
    ),
    RejectionCode.TOO_DARK: (
        "The photo is too dark to measure. Take it again in bright, even light, for "
        "example near a window in daylight, without flash."
    ),
    RejectionCode.INSOLE_NOT_FOUND: (
        "We couldn't find the insole on the template. Lay it inside the grey dashed lines "
        "on the white paper and take the photo again. Very light-coloured insoles may not "
        "stand out enough from the paper."
    ),
    RejectionCode.TOO_BLURRY: (
        "The photo is too blurry to measure the insole's edge precisely. Hold the phone "
        "steady, tap the insole on screen to focus, and take the photo again."
    ),
    RejectionCode.INSOLE_TOUCHES_EDGE: (
        "The insole reaches over the grey dashed lines or out of the photo. Place it fully "
        "inside the dashed lines with white paper all around it, and make sure the whole "
        "sheet is in the photo. Insoles longer than about 29 cm don't fit on A4 yet."
    ),
}


class Rejection(Exception):  # noqa: N818 - it's an outcome, not an error
    def __init__(self, code: RejectionCode, detail: str = "") -> None:
        self.code = code
        self.message = MESSAGES[code]
        # For logs and debugging only; never shown to the user.
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else str(code))
