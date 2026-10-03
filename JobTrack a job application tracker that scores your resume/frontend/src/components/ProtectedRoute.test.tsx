import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { setToken } from "../api/client";
import { ProtectedRoute } from "./ProtectedRoute";

describe("protected routes", () => {
  it("redirects to login when there is no token", () => {
    setToken(null);
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={["/private"]}>
          <Routes>
            <Route element={<p>Login screen</p>} path="/login" />
            <Route element={<ProtectedRoute />}>
              <Route element={<p>Private data</p>} path="/private" />
            </Route>
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(screen.getByText("Login screen")).toBeInTheDocument();
    expect(screen.queryByText("Private data")).not.toBeInTheDocument();
  });
});
