import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import type { Resume } from "../api/client";
import { ScoreResumePanel } from "./ScoreResumePanel";
import { ToastProvider } from "./Toast";
import { server } from "../test/server";

const resumes: Resume[] = [{
  id: 4,
  user_id: 3,
  label: "Backend resume",
  filename: "backend.pdf",
  uploaded_at: "2025-02-03T00:00:00Z",
}];

function renderScorePanel() {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { mutations: { retry: false } } })}>
      <ToastProvider>
        <ScoreResumePanel applicationId={9} hasJobDescription resumes={resumes} />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

async function selectResumeAndScore() {
  const user = userEvent.setup();
  await user.selectOptions(screen.getByLabelText("Choose a resume"), "4");
  await user.click(screen.getByRole("button", { name: "Score resume" }));
  return user;
}

describe("resume scoring feedback", () => {
  it("disables the button while scoring and reports success", async () => {
    let finishRequest: (() => void) | undefined;
    const requestStarted = vi.fn();
    server.use(
      http.post("/api/applications/9/score", async () => {
        requestStarted();
        await new Promise<void>((resolve) => { finishRequest = resolve; });
        return HttpResponse.json({
          id: 11,
          application_id: 9,
          resume_id: 4,
          jd_hash: "abc",
          match_score: 82,
          missing_keywords: ["sql"],
          scorer_status: "ok",
          latency_ms: 500,
          created_at: "2025-02-03T00:00:00Z",
          cache_hit: false,
        });
      }),
    );
    renderScorePanel();

    await selectResumeAndScore();

    expect(await screen.findByRole("status")).toHaveTextContent("the scorer may be waking up");
    expect(screen.getByRole("button", { name: "Scoring…" })).toBeDisabled();
    await waitFor(() => expect(requestStarted).toHaveBeenCalledOnce());
    await act(async () => finishRequest?.());
    expect(await screen.findByText("Resume scored successfully.")).toBeInTheDocument();
  });

  it.each([
    [503, "The scorer may be waking up. Please try again shortly."],
    [429, "You’ve reached 10 scoring attempts this hour. The limit resets within an hour."],
  ])("shows friendly feedback for HTTP %s", async (status, message) => {
    server.use(
      http.post("/api/applications/9/score", () =>
        HttpResponse.json({ detail: "Scoring unavailable" }, { status }),
      ),
    );
    renderScorePanel();

    await selectResumeAndScore();

    expect(await screen.findByText(message)).toBeInTheDocument();
  });
});
