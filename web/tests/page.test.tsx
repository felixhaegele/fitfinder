import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import Home from "@/app/page";

// Without vitest globals, Testing Library doesn't unmount between tests by itself.
afterEach(cleanup);

describe("Home page", () => {
  it("leads with the benefit and the product name", () => {
    render(<Home />);

    expect(
      screen.getByRole("heading", { level: 1, name: "Cycling shoes that fit your feet" }),
    ).toBeInTheDocument();
    expect(screen.getByText("FitFinder")).toBeInTheDocument();
  });

  it("offers upload as the primary action and browsing as the secondary one", () => {
    render(<Home />);

    const ctas = screen
      .getAllByRole("link")
      .filter((link) => ["Upload a shoe", "View shoes"].includes(link.textContent ?? ""));
    // Primary first, in reading order.
    expect(ctas.map((link) => [link.textContent, link.getAttribute("href")])).toEqual([
      ["Upload a shoe", "/upload"],
      ["View shoes", "/shoes"],
    ]);
    expect(screen.getByRole("link", { name: "printed A4 template" })).toHaveAttribute("href", "/template");
  });

  it("explains the three steps in order", () => {
    render(<Home />);

    expect(screen.getByRole("heading", { level: 2, name: "How it works" })).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent)).toEqual([
      "Print the template",
      "Photograph the insole",
      "Compare by fit",
    ]);
  });
});
