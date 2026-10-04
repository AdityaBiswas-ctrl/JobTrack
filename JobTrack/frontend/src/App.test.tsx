import { useEffect } from "react";
import { render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { SessionRedirect } from "./App";
import { api, setToken } from "./api/client";
import { server } from "./test/server";

describe("application authentication flow", () => {
  it("redirects to login and clears the token when an API request returns 401", async () => {
    setToken("expired-token");
    server.use(
      http.get("/api/auth/me", () => HttpResponse.json({ detail: "Unauthorized" }, { status: 401 })),
    );
    render(
      <MemoryRouter initialEntries={["/private"]}>
        <SessionRedirect />
        <Routes>
          <Route element={<TriggerUnauthorized />} path="/private" />
          <Route element={<p>Login screen</p>} path="/login" />
        </Routes>
        </MemoryRouter>
    );

    expect(await screen.findByText("Login screen")).toBeInTheDocument();
    expect(sessionStorage.getItem("jobtrack_token")).toBeNull();
  });
});

function TriggerUnauthorized() {
  useEffect(() => {
    void api.me().catch(() => undefined);
  }, []);
  return <p>Private screen</p>;
}
