import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import Home from "@/app/page";

// Without vitest globals, Testing Library doesn't unmount between tests by itself.
afterEach(cleanup);

describe("Home page", () => {
  it("shows the product name and pitch", () => {
    render(<Home />);

    expect(screen.getByRole("heading", { level: 1, name: "FitFinder" })).toBeInTheDocument();
    expect(screen.getByText(/find cycling shoes that fit/i)).toBeInTheDocument();
  });

  it("shows the three steps in order, each with its link", () => {
    render(<Home />);

    expect(screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent)).toEqual([
      "Print the template",
      "Upload an insole photo",
      "Browse shoes by fit",
    ]);
    expect(screen.getByRole("link", { name: "Get the template" })).toHaveAttribute("href", "/template");
    expect(screen.getByRole("link", { name: "Upload a photo" })).toHaveAttribute("href", "/upload");
    expect(screen.getByRole("link", { name: "Browse shoes" })).toHaveAttribute("href", "/shoes");
  });
});
