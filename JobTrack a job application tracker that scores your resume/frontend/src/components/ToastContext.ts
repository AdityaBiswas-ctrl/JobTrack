import { createContext, useContext } from "react";

export type ToastKind = "success" | "error";
export type ToastContextValue = {
  showToast: (message: string, kind?: ToastKind) => void;
};

export const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast(): ToastContextValue {
  const value = useContext(ToastContext);
  if (!value) throw new Error("useToast must be used inside ToastProvider");
  return value;
}
