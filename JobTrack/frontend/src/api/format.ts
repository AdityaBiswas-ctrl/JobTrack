import type { ApplicationStatus } from "./client";

export const statuses: ApplicationStatus[] = [
  "wishlist",
  "applied",
  "online_assessment",
  "interview",
  "offer",
  "rejected",
  "withdrawn",
];

export function formatStatus(status: string | number): string {
  return String(status)
    .split("_")
    .map((word) => word[0].toUpperCase() + word.slice(1))
    .join(" ");
}

export function formatDate(value: string | null): string {
  if (!value) return "Not set";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(
    new Date(`${value.slice(0, 10)}T00:00:00`),
  );
}

export function formatTimestamp(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}
