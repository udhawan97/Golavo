import { useEffect } from "react";

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

      let url: URL;
      try {
        url = new URL(anchor.href);
      } catch {
        return;
      }
      if (url.protocol !== "https:" && url.protocol !== "http:") return;

      event.preventDefault();
      void window.__TAURI__!.core.invoke("open_external_url", {
        url: url.toString(),
      }).catch((error: unknown) => {
        console.error("Could not open external link", error);
      });
    };

    document.addEventListener("click", handleClick);
    return () => document.removeEventListener("click", handleClick);
  }, []);
}
