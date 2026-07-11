import { createContext, useContext } from "react";
import type { UpdaterController } from "./updater";

/** Provided once at the App root; the header pill, the update sheet, and the
 *  settings view all share the same controller instance. */
export const UpdaterContext = createContext<UpdaterController | null>(null);

export function useUpdater(): UpdaterController {
  const ctx = useContext(UpdaterContext);
  if (!ctx) throw new Error("useUpdater must be used inside <UpdaterContext.Provider>");
  return ctx;
}
