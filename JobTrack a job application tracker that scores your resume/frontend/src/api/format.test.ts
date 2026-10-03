import { describe, expect, it } from "vitest";
import { formatDate, formatStatus } from "./format";

describe("display formatting", () => {
  it("formats multiword statuses for people", () => {
    expect(formatStatus("online_assessment")).toBe("Online Assessment");
  });

  it("formats missing application dates without a placeholder date", () => {
    expect(formatDate(null)).toBe("Not set");
  });
});
