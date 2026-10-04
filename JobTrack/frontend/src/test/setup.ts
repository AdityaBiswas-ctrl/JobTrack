import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll, vi } from "vitest";
import { setToken } from "../api/client";
import { server } from "./server";

beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
  const nativeFetch = globalThis.fetch.bind(globalThis);
  vi.stubGlobal(
    "fetch",
    (input: RequestInfo | URL, init?: RequestInit) => {
      const requestInit = { ...init };
      delete requestInit.signal;
      return nativeFetch(input, requestInit);
    },
  );
});
afterEach(() => {
  cleanup();
  server.resetHandlers();
  setToken(null);
});
afterAll(() => {
  vi.unstubAllGlobals();
  server.close();
});
