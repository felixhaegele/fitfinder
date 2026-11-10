import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import TermsPage from "@/app/terms/page";

afterEach(cleanup);

describe("Terms page", () => {
  it("has the reporting section at the anchor that report links point to", () => {
    render(<TermsPage />);

    const heading = screen.getByRole("heading", { level: 2, name: "Reporting content" });
    expect(heading.closest("section")).toHaveAttribute("id", "reporting");
  });

  it("shows placeholders, not made-up details, while the owner details are unset", () => {
    render(<TermsPage />);

    expect(screen.getAllByText(/\[to be added before launch\]/).length).toBeGreaterThan(0);
    expect(screen.getByText(/at least 16 years old/)).toBeInTheDocument();
  });
});
