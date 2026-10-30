import { describe, expect, it } from "vitest";
import { LANG_NAME, t, translatePageText } from "../lib/i18n";

describe("application-wide language copy", () => {
  it("provides the same language choices and navigation labels", () => {
    expect(Object.keys(LANG_NAME).sort()).toEqual(["el", "en", "mr"]);
    for (const lang of ["mr", "el"] as const) {
      expect(t(lang, "nav_atlas")).not.toBe(t("en", "nav_atlas"));
      expect(t(lang, "nav_language")).toBeTruthy();
      expect(t(lang, "footer_method")).toBeTruthy();
      expect(t(lang, "translation_notice")).not.toBe(t("en", "translation_notice"));
    }
  });

  it("localizes primary page headings and safely falls back for unreviewed copy", () => {
    expect(translatePageText("mr", "The data audit.")).not.toBe("The data audit.");
    expect(translatePageText("el", "The data audit.")).not.toBe("The data audit.");
    expect(translatePageText("mr", "A chart label not in the dictionary")).toBe("A chart label not in the dictionary");
  });

  it("interpolates citizen-view values without losing numeric values", () => {
    expect(t("mr", "trees", { n: 12, avg: 8 })).toContain("12");
    expect(t("el", "heat", { p: 65 })).toContain("65");
  });
});
