/** Parse a conventional outfield formation. Ten players must be accounted for;
 * the goalkeeper is drawn separately. Invalid provider strings fail closed. */
export function parseFormation(value: string): number[] | null {
  const normalized = value.trim().replace(/[–—]/g, "-");
  if (!/^\d(?:-\d){2,4}$/.test(normalized)) return null;
  const rows = normalized.split("-").map(Number);
  if (rows.some((row) => row < 1 || row > 5) || rows.reduce((sum, row) => sum + row, 0) !== 10) return null;
  return rows;
}

export function FormationPitch({ formation, team }: { formation: string; team: string }) {
  const rows = parseFormation(formation);
  if (!rows) return null;
  const bands = [[1], ...rows.map((count) => Array.from({ length: count }, (_, i) => i))];
  return (
    <figure className="formation" aria-label={`${team} typical ${formation} formation`}>
      <svg viewBox="0 0 240 330" role="img" aria-hidden>
        <rect className="formation__field" x="3" y="3" width="234" height="324" rx="8" />
        <line x1="3" y1="165" x2="237" y2="165" />
        <circle cx="120" cy="165" r="30" />
        <rect x="60" y="3" width="120" height="48" />
        <rect x="60" y="279" width="120" height="48" />
        {bands.map((players, rowIndex) => {
          const y = 300 - rowIndex * (270 / (bands.length - 1));
          return players.map((_, index) => {
            const x = (240 / (players.length + 1)) * (index + 1);
            return <circle className="formation__player" key={`${rowIndex}-${index}`} cx={x} cy={y} r="8" />;
          });
        })}
      </svg>
      <figcaption><b>{team}</b><span className="num">{formation}</span></figcaption>
    </figure>
  );
}
