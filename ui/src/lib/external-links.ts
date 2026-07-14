import { useEffect } from "react";
import type { MouseEvent as ReactMouseEvent } from "react";

function safeExternalUrl(value: string): string | null {
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:" ? url.toString() : null;
  } catch {
    return null;
  }
}

export function openExternalUrl(value: string): Promise<unknown> {
  const url = safeExternalUrl(value);
  if (!url || !window.__TAURI__) return Promise.resolve();
  return window.__TAURI__.core.invoke("open_external_url", { url });
}

/** Explicit handler for important external anchors such as Settings links. */
export function handleExternalLinkClick(event: ReactMouseEvent<HTMLAnchorElement>): void {
  if (!window.__TAURI__) return;
  event.preventDefault();
  void openExternalUrl(event.currentTarget.href).catch((error: unknown) => {
    console.error("Could not open external link", error);
  });
}

/**
 * Tauri webviews do not hand target=_blank links to the operating system by
 * default. Capture ordinary external anchors once at the app boundary and send
 * them to the user's default browser. Browser/source builds keep normal anchor
 * behaviour, so the same UI remains useful outside the packaged desktop app.
 */
export function useExternalLinks(): void {
  useEffect(() => {
    if (!window.__TAURI__) return;

    const handleClick = (event: MouseEvent) => {
      if (event.defaultPrevented || event.button !== 0) return;
      const target = event.target;
      if (!(target instanceof Element)) return;

      const anchor = target.closest<HTMLAnchorElement>("a[href][target='_blank']");
      if (!anchor) return;

      const url = safeExternalUrl(anchor.href);
      if (!url) return;

      event.preventDefault();
      void openExternalUrl(url).catch((error: unknown) => {
        console.error("Could not open external link", error);
      });
    };

    document.addEventListener("click", handleClick);
    return () => document.removeEventListener("click", handleClick);
  }, []);
}
