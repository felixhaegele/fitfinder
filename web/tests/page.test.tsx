import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Home from "@/app/page";

describe("Home page", () => {
  it("shows the product name and pitch", () => {
    render(<Home />);

    expect(screen.getByRole("heading", { level: 1, name: "FitFinder" })).toBeInTheDocument();
    expect(screen.getByText(/find cycling shoes that fit/i)).toBeInTheDocument();
  });
});
