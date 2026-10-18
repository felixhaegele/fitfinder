"""Reasons a photo can't be measured, with the message shown to the user.

A rejection is a normal outcome (the submission becomes `rejected` with the message as
`rejection_reason`), not a crash: the job is not retried.
"""

from enum import StrEnum


class RejectionCode(StrEnum):
    MARKERS_NOT_FOUND = "markers_not_found"
    PAPER_NOT_FLAT = "paper_not_flat"


MESSAGES: dict[RejectionCode, str] = {
    RejectionCode.MARKERS_NOT_FOUND: (
        "We couldn't find the black squares on the template. Make sure all four are "
        "visible, in focus and not covered, then take the photo again."
    ),
    RejectionCode.PAPER_NOT_FLAT: (
        "The template doesn't seem to lie flat. Smooth out the paper on a flat surface "
        "and take the photo again from straight above."
    ),
}


class Rejection(Exception):  # noqa: N818 - it's an outcome, not an error
    def __init__(self, code: RejectionCode, detail: str = "") -> None:
        self.code = code
        self.message = MESSAGES[code]
        # For logs and debugging only; never shown to the user.
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else str(code))
