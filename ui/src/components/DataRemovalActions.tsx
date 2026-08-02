import { ConfirmAction } from "./ConfirmAction";

export function FollowHistoryRemovalAction({ onConfirm }: { onConfirm: () => void | Promise<void> }) {
  return (
    <ConfirmAction
      triggerLabel="Remove follow history"
      confirmLabel="Confirm remove follow history"
      cancelAriaLabel="Cancel removing follow history"
      groupLabel="Remove local follow history"
      description={<>This removes followed-match subscriptions and their event history only. Forecasts, picks, refresh generations, OpenLigaDB data, and user artifacts are not touched.</>}
      onConfirm={onConfirm}
    />
  );
}

export function ProposalRemovalAction({ onConfirm }: { onConfirm: () => void | Promise<void> }) {
  return (
    <ConfirmAction
      triggerLabel="Remove all proposals"
      confirmLabel="Confirm remove all proposals"
      cancelAriaLabel="Cancel removing all proposals"
      groupLabel="Remove all local correction proposals"
      description={<>This removes every local proposal, evidence capture and staged export. It does not touch source packs, forecasts, followed matches, picks, or OpenLigaDB data.</>}
      onConfirm={onConfirm}
    />
  );
}

export function EvidenceRemovalAction({
  hostname,
  disabled,
  onConfirm,
}: {
  hostname: string;
  disabled: boolean;
  onConfirm: () => void | Promise<void>;
}) {
  return (
    <ConfirmAction
      triggerLabel="Remove evidence"
      confirmLabel="Confirm remove evidence"
      cancelAriaLabel={`Cancel removing evidence from ${hostname}`}
      groupLabel={`Remove local evidence from ${hostname}`}
      description={<>This deletes the raw local capture, invalidates any local annotation, and removes staged exports. A copy already saved or submitted cannot be recalled.</>}
      disabled={disabled}
      onConfirm={onConfirm}
    />
  );
}
