import { render, screen, waitFor, fireEvent, within } from "@testing-library/react";
import { vi, describe, it, expect, beforeEach } from "vitest";
import App from "../App";
import { mockApi } from "./fixtures";
import { t } from "../lib/i18n";

vi.mock("../components/MapStage", () => ({
  default: (p: { cells: { h3: string }[]; onSelect?: (c: unknown) => void; marked?: string[] | null; highlight?: unknown }) => (
    <div data-testid="map" data-marked={(p.marked ?? []).join(",")} data-dim={p.highlight ? "yes" : "no"}>
      <button onClick={() => p.onSelect?.(p.cells[0])}>pick-a</button><button onClick={() => p.onSelect?.(p.cells[2])}>pick-c</button>
    </div>),
  boundsOf: () => [[0, 0], [1, 1]]
}));
const go = (path: string) => window.history.pushState({}, "", path);
beforeEach(() => { localStorage.clear(); document.documentElement.lang = "en"; });

describe("plan screen", () => {
  it("shows the plan with labels, the do-nothing baseline and the comparison with the simple list", async () => {
    mockApi(); go("/plan"); render(<App />);
    await waitFor(() => expect(screen.getByText("This plan")).toBeTruthy());
    expect(screen.getByText(/Versus doing nothing/)).toBeTruthy();
    expect(screen.getByText(/25% more weighted benefit/)).toBeTruthy();
    expect(screen.getAllByText("SIMULATED").length).toBeGreaterThan(0);
    expect(screen.getByTestId("map").dataset.marked).toBe("a,b");               // chosen sites are outlined on the map
    expect(screen.getByTestId("map").dataset.dim).toBe("yes");                  // everything else is dimmed
  });
  it("changing preset, budget and equity changes the numbers", async () => {
    mockApi(); go("/plan"); render(<App />);
    await waitFor(() => expect(screen.getByText("This plan")).toBeTruthy());
    const before = screen.getByText(/Chance it fits the budget/).closest("div")!.parentElement!.textContent;
    fireEvent.click(screen.getByRole("button", { name: "Heat first" }));
    await waitFor(() => expect(screen.getByText(/Weights \(policy choices\): cooling 60%/)).toBeTruthy());
    fireEvent.change(screen.getByRole("slider"), { target: { value: "2" } });
    fireEvent.click(screen.getByLabelText(/Equity rule/));
    await waitFor(() => expect(screen.getAllByText(/60%/).length).toBeGreaterThan(0));   // share of spend in top-third need with the equity rule
    expect(screen.getByText("This plan").closest("section")!.textContent).not.toBe(before);
  });
  it("opens an evidence card for a chosen site and a what-if inside it", async () => {
    const f = mockApi(); go("/plan"); render(<App />);
    await waitFor(() => expect(screen.getByText("This plan")).toBeTruthy());
    fireEvent.click(screen.getByText("pick-a"));
    const card = await screen.findByLabelText("Evidence for the selected site");
    expect(within(card).getByText(/needs field verification/)).toBeTruthy();
    expect(within(card).getByText(/no-regret/)).toBeTruthy();
    expect(within(card).getByText("Heat")).toBeTruthy();
    expect(within(card).getByText(/compared with doing nothing/)).toBeTruthy();
    fireEvent.click(within(card).getByRole("button", { name: /Run a detailed what-if/ }));
    await waitFor(() => expect(within(card).getByText(/SIMULATED: nothing built/)).toBeTruthy());
    expect(f.mock.calls.some(c => String(c[0]).includes("/api/scenarios/run"))).toBe(true);
  });
  it("says why there are no portfolios instead of showing anything", async () => {
    mockApi({ "/api/portfolios": { status: 503, body: { detail: { code: "baseline_not_built" } } },
      "/api/model-report": { body: { built: true, modules: { portfolio: { status: "failed", reason: "site_pixels.parquet not found" } }, heat_model: null, need: null } } });
    go("/plan"); render(<App />);
    await waitFor(() => expect(screen.getByText(/site_pixels.parquet not found/)).toBeTruthy());
    expect(screen.queryByText("This plan")).toBeNull();
  });
});

describe("compare screen", () => {
  it("shows three plans and doing nothing, and highlights what differs", async () => {
    mockApi(); go("/compare"); render(<App />);
    await waitFor(() => expect(screen.getAllByText("Plan A").length).toBeGreaterThan(0));
    const table = screen.getByRole("table");
    expect(within(table).getByText("Do nothing")).toBeTruthy();
    expect(within(table).getByText("Plan C")).toBeTruthy();
    expect(screen.getByText(/What differs/)).toBeTruthy();
    expect(screen.getAllByText(/Plan [BC] versus A/).length).toBe(2);
    expect(screen.getByText(/overstates the price of that benefit/)).toBeTruthy();
  });
});

describe("report", () => {
  it("renders the chosen plan with sources, limits and a print button", async () => {
    mockApi(); go("/report?preset=heat_first&budget=1&equity=50"); render(<App />);
    await waitFor(() => expect(screen.getByText(/Greening plan: Heat first/)).toBeTruthy());
    expect(screen.getByText(/equity rule 50%/)).toBeTruthy();
    expect(screen.getByRole("button", { name: /Print or save as PDF/ })).toBeTruthy();
    expect(screen.getByText(/not surveyed parcels/)).toBeTruthy();
    await waitFor(() => expect(screen.getByText(/NABARD; IEG/)).toBeTruthy());
    expect(screen.getByText(/No return on investment is claimed/)).toBeTruthy();
  });
  it("refuses a plan that is not in the pre-solved grid", async () => {
    mockApi(); go("/report?preset=nonsense&budget=1&equity=0"); render(<App />);
    await waitFor(() => expect(screen.getByText(/not in the pre-solved grid/)).toBeTruthy());
  });
});

describe("citizen view", () => {
  it("answers 'what is planned near me' in plain English and says when a site is proposed", async () => {
    mockApi(); go("/city"); render(<App />);
    await waitFor(() => expect(screen.getByText(t("en", "title"))).toBeTruthy());
    expect(screen.getByText(t("en", "pick"))).toBeTruthy();
    fireEvent.click(screen.getByText("pick-a"));
    await waitFor(() => expect(screen.getByText(/is proposed in this area/)).toBeTruthy());
    expect(screen.getByText(/Trees counted here: about 4 per hectare/)).toBeTruthy();
    expect(screen.getByText(/hotter than 67% of the city/)).toBeTruthy();         // cell a is hotter than 2 of 3 cells
    expect(screen.getByText(t("en", "parkYes", { p: "10", dist: "300", area: "0.5" }))).toBeTruthy();
    expect(screen.getByText(/has not been set up/)).toBeTruthy();                // no feedback link configured: said, not faked
  });
  it("explains why a place has no site: no open land versus lower need", async () => {
    mockApi(); go("/city"); render(<App />);
    await waitFor(() => expect(screen.getByText("pick-c")).toBeTruthy());
    fireEvent.click(screen.getByText("pick-c"));
    await waitFor(() => expect(screen.getByText(t("en", "planNoOpen"))).toBeTruthy());     // hexagon c has no candidate site
  });
  it("switches to Marathi with a visible review notice, falls back to English, and remembers the choice", async () => {
    mockApi(); go("/city"); render(<App />);
    await waitFor(() => expect(screen.getByText(t("en", "title"))).toBeTruthy());
    expect(screen.queryByRole("note")).toBeNull();
    const citizenLanguageSwitch = document.querySelector(".citizen .langswitch");
    expect(citizenLanguageSwitch).toBeTruthy();
    fireEvent.click(within(citizenLanguageSwitch as HTMLElement).getByRole("button", { name: "मराठी" }));
    await waitFor(() => expect(screen.getByText(t("mr", "title"))).toBeTruthy());
    expect(screen.getByRole("note").textContent).toContain("Please treat the English as the reference");
    expect(screen.getByRole("note").textContent).toContain(t("mr", "review"));
    expect(document.documentElement.lang).toBe("mr");
    expect(localStorage.getItem("ecometrix-lang")).toBe("mr");
  });
  it("every Marathi string has an English twin and placeholders match", async () => {
    const mod = await import("../lib/i18n");
    for (const key of ["trees", "heat", "parkYes", "planYes"] as const) {
      const ph = (s: string) => (s.match(/\{\w+\}/g) ?? []).sort().join();
      expect(ph(mod.t("mr", key))).toBe(ph(mod.t("en", key)));
    }
  });
});

describe("evaluation screen and navigation", () => {
  it("shows the tornado, the honest-claims table and the human checks that are still to do", async () => {
    mockApi(); go("/evaluation"); render(<App />);
    await waitFor(() => expect(screen.getByText(/mini forest.capex inr per m2/i)).toBeTruthy());
    expect(screen.getByText("We can say")).toBeTruthy(); expect(screen.getByText("We must not say")).toBeTruthy();
    expect(screen.getByText(/not been done yet/)).toBeTruthy();
    expect(screen.getByText(/proven optimal/)).toBeTruthy();
    fireEvent.click(screen.getByRole("tab", { name: "Pocket park" }));
    await waitFor(() => expect(screen.getByText(/No assumption moves/)).toBeTruthy());
  });
  it("sensitivity missing is said plainly", async () => {
    mockApi({ "/api/sensitivity": { status: 503, body: { detail: { code: "baseline_not_built" } } } }); go("/evaluation"); render(<App />);
    await waitFor(() => expect(screen.getByText(/Sensitivity results are not available/)).toBeTruthy());
  });
  it("the More menu reaches the citizen view", async () => {
    mockApi(); go("/method"); render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: /More/ }));
    const menu = document.querySelector(".more__menu")!;
    expect(within(menu as HTMLElement).getByText("Citizen view")).toBeTruthy();
  });
});
