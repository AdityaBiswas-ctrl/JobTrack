import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { AuthPage } from "./AuthPage";
import { server } from "../test/server";

function renderAuthPage(mode: "login" | "signup" = "login") {
  const queryClient = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <AuthPage mode={mode} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("login form", () => {
  it("shows validation errors before sending invalid data", async () => {
    const user = userEvent.setup();
    renderAuthPage();

    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Enter a valid email address")).toBeInTheDocument();
    expect(screen.getByText("Password must be at least 8 characters")).toBeInTheDocument();
  });

  it("submits credentials using the API's OAuth2 form fields", async () => {
    const user = userEvent.setup();
    let submittedEmail = "";
    let submittedPassword = "";
    let contentType = "";
    server.use(
      http.post("/api/auth/login", async ({ request }) => {
        contentType = request.headers.get("Content-Type") ?? "";
        const form = await request.formData();
        submittedEmail = String(form.get("username"));
        submittedPassword = String(form.get("password"));
        return HttpResponse.json({ access_token: "login-token", token_type: "bearer" });
      }),
    );
    renderAuthPage();

    await user.type(screen.getByLabelText("Email address"), "person@example.com");
    await user.type(screen.getByLabelText("Password"), "correct-horse");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(submittedEmail).toBe("person@example.com"));
    expect(submittedPassword).toBe("correct-horse");
    expect(contentType).toContain("application/x-www-form-urlencoded");
    expect(sessionStorage.getItem("jobtrack_token")).toBe("login-token");
  });

  it("sends signup values as JSON", async () => {
    const user = userEvent.setup();
    let submitted: unknown;
    server.use(
      http.post("/api/auth/signup", async ({ request }) => {
        submitted = await request.json();
        return HttpResponse.json(
          { id: 7, email: "new@example.com", created_at: "2025-01-01T00:00:00Z" },
          { status: 201 },
        );
      }),
    );
    renderAuthPage("signup");

    await user.type(screen.getByLabelText("Email address"), "new@example.com");
    await user.type(screen.getByLabelText("Password"), "better-secret");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    await waitFor(() =>
      expect(submitted).toEqual({ email: "new@example.com", password: "better-secret" }),
    );
  });
});
