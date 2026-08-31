import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { OutsideSignals } from "../../src/components/OutsideSignals";
import "../../src/index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <OutsideSignals matchId="m_player_dossier_fixture" home="Local Home" away="Local Away" />
  </StrictMode>,
);
