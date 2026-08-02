import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from "react";

export function ConfirmAction({
  triggerLabel,
  confirmLabel,
  cancelAriaLabel,
  groupLabel,
  description,
  onConfirm,
  disabled = false,
}: {
  triggerLabel: string;
  confirmLabel: string;
  cancelAriaLabel: string;
  groupLabel: string;
  description: ReactNode;
  onConfirm: () => void | Promise<void>;
  disabled?: boolean;
}) {
  const [armed, setArmed] = useState(false);
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const cancel = useRef<HTMLButtonElement>(null);
  const restoreFocus = useRef(false);
  const descriptionId = useId();

  const disarm = useCallback(() => {
    setFailure(false);
    restoreFocus.current = true;
    setArmed(false);
  }, []);

  useEffect(() => {
    if (armed) {
      cancel.current?.focus();
      return;
    }
    if (restoreFocus.current) {
      restoreFocus.current = false;
      trigger.current?.focus();
    }
  }, [armed, disarm]);

  useEffect(() => {
    if (!armed) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      if (pending) return;
      event.preventDefault();
      disarm();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [armed, disarm, pending]);

  const confirm = async () => {
    if (disabled || pending) return;
    setPending(true);
    setFailure(false);
    try {
      await onConfirm();
      disarm();
    } catch {
      setFailure(true);
    } finally {
      setPending(false);
    }
  };

  if (!armed) {
    return (
      <button
        ref={trigger}
        type="button"
        className="btn btn--ghost"
        disabled={disabled}
        onClick={() => setArmed(true)}
      >
        {triggerLabel}
      </button>
    );
  }

  return (
    <div
      className="confirm-action"
      role="group"
      aria-label={groupLabel}
      aria-describedby={descriptionId}
      aria-busy={pending}
    >
      <p id={descriptionId} className="confirm-action__message" role="alert">{description}</p>
      {failure && (
        <p className="confirm-action__error" role="alert">
          Golavo could not confirm that the removal completed. Review the local record before retrying.
        </p>
      )}
      <div className="confirm-action__buttons">
        <button
          ref={cancel}
          type="button"
          className="btn btn--ghost"
          aria-label={cancelAriaLabel}
          disabled={pending}
          onClick={disarm}
        >
          Cancel
        </button>
        <button
          type="button"
          className="btn btn--danger"
          disabled={disabled || pending}
          onClick={() => void confirm()}
        >
          {pending ? "Removing…" : confirmLabel}
        </button>
      </div>
    </div>
  );
}
