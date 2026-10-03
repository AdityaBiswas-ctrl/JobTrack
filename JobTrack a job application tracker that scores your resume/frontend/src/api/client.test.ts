import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api, getToken, setToken } from "./client";
import { server } from "../test/server";

describe("API client authentication", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("attaches the stored token to authenticated requests", async () => {
    let authorization = "";
    server.use(
      http.get("/api/auth/me", ({ request }) => {
        authorization = request.headers.get("Authorization") ?? "";
        return HttpResponse.json({ id: 1, email: "one@example.com", created_at: "2025-01-01T00:00:00Z" });
      }),
    );
    setToken("signed-token");

    const profile = await api.me();

    expect(authorization).toBe("Bearer signed-token");
    expect(profile.email).toBe("one@example.com");
  });

  it("clears the session and notifies the app after a 401", async () => {
    server.use(http.get("/api/auth/me", () => HttpResponse.json({ detail: "Unauthorized" }, { status: 401 })));
    setToken("expired-token");
    const onUnauthorized = vi.fn();
    window.addEventListener("jobtrack:unauthorized", onUnauthorized);

    await expect(api.me()).rejects.toMatchObject({ status: 401 });

    expect(getToken()).toBeNull();
    expect(sessionStorage.getItem("jobtrack_token")).toBeNull();
    expect(onUnauthorized).toHaveBeenCalledOnce();
    window.removeEventListener("jobtrack:unauthorized", onUnauthorized);
  });

  it("does not redirect again when a session was already cleared", async () => {
    server.use(http.get("/api/auth/me", () => HttpResponse.json({ detail: "Unauthorized" }, { status: 401 })));
    setToken(null);
    const onUnauthorized = vi.fn();
    window.addEventListener("jobtrack:unauthorized", onUnauthorized);

    await expect(api.me()).rejects.toMatchObject({ status: 401 });

    expect(onUnauthorized).not.toHaveBeenCalled();
    window.removeEventListener("jobtrack:unauthorized", onUnauthorized);
  });
});
