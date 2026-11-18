import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ReportLink } from "@/components/report-link";
import { reportHref } from "@/lib/legal";

vi.mock("@/lib/legal", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/legal")>()),
  reportHref: vi.fn(),
}));

afterEach(cleanup);

describe("ReportLink", () => {
  it("links to the terms while there is no contact email", () => {
    vi.mocked(reportHref).mockReturnValue("/terms#reporting");
    render(<ReportLink subject="Report: shoe">Report it</ReportLink>);

    expect(screen.getByRole("link", { name: "Report it" })).toHaveAttribute("href", "/terms#reporting");
  });

  it("opens an email with the subject once the contact email is set", () => {
    vi.mocked(reportHref).mockReturnValue("mailto:report@example.org?subject=Report%3A%20shoe");
    render(<ReportLink subject="Report: shoe">Report it</ReportLink>);

    expect(reportHref).toHaveBeenCalledWith("Report: shoe");
    expect(screen.getByRole("link", { name: "Report it" })).toHaveAttribute(
      "href",
      "mailto:report@example.org?subject=Report%3A%20shoe",
    );
  });
});
