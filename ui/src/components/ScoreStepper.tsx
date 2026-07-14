import { MinusIcon, PlusIcon } from "./icons";

export function ScoreStepper({
  team,
  tone,
  value,
  onChange,
}: {
  team: string;
  tone: "home" | "away";
  value: number;
  onChange: (value: number) => void;
}) {
  const set = (next: number) => onChange(Math.max(0, Math.min(20, next)));
  return (
    <div className={`score-step score-step--${tone}`}>
      <div className="score-step__team">{team}</div>
      <div className="score-step__controls">
        <button type="button" onClick={() => set(value - 1)} disabled={value <= 0} aria-label={`Decrease ${team} score`}>
          <MinusIcon />
        </button>
        <input
          type="number"
          min={0}
          max={20}
          inputMode="numeric"
          aria-label={`${team} score`}
          value={value}
          onChange={(event) => set(Number(event.target.value))}
        />
        <button type="button" onClick={() => set(value + 1)} disabled={value >= 20} aria-label={`Increase ${team} score`}>
          <PlusIcon />
        </button>
      </div>
    </div>
  );
}
