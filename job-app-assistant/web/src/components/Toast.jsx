import { createContext, useCallback, useContext, useRef, useState } from "react";
import { IconCheckCircle, IconAlertCircle, IconX } from "./Icons.jsx";

const ToastContext = createContext(null);

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast doit être utilisé dans <ToastProvider>");
  return ctx;
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const nextId = useRef(0);

  const dismiss = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const push = useCallback(
    (variant, text) => {
      const id = nextId.current++;
      setToasts((prev) => [...prev, { id, variant, text }]);
      setTimeout(() => dismiss(id), 4000);
    },
    [dismiss]
  );

  const value = {
    success: (text) => push("success", text),
    error: (text) => push("error", text),
  };

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="fixed bottom-4 right-4 left-4 sm:left-auto z-50 flex flex-col gap-2 items-end pointer-events-none">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`pointer-events-auto flex items-start gap-2.5 w-full sm:w-auto sm:min-w-[300px] max-w-sm rounded-xl border px-4 py-3 shadow-card animate-toast-in ${
              t.variant === "success"
                ? "bg-emerald-50 border-emerald-200 text-emerald-800"
                : "bg-red-50 border-red-200 text-red-800"
            }`}
          >
            {t.variant === "success" ? (
              <IconCheckCircle className="w-5 h-5 shrink-0 mt-0.5" />
            ) : (
              <IconAlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
            )}
            <p className="text-sm font-medium flex-1">{t.text}</p>
            <button
              onClick={() => dismiss(t.id)}
              className="shrink-0 opacity-60 hover:opacity-100 transition-opacity"
            >
              <IconX className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
