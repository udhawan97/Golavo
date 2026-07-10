export default function App() {
  return (
    <main
      style={{
        fontFamily: "ui-sans-serif, system-ui, -apple-system, sans-serif",
        maxWidth: 640,
        margin: "12vh auto",
        padding: "0 1.5rem",
        color: "#1a1a1a",
        lineHeight: 1.5,
      }}
    >
      <picture>
        <source media="(prefers-color-scheme: dark)" srcSet="/brand/golavo-lockup-dark.svg" />
        <img src="/brand/golavo-lockup-light.svg" alt="Golavo" width={380} />
      </picture>
      <p style={{ fontStyle: "italic", color: "#bc002d", marginTop: "0.4rem" }}>
        The numbers remember everything. The beautiful game still keeps the last word.
      </p>
      <p>
        Pre-alpha scaffold. The forecast engine and interface arrive in Phase 2 — see the{" "}
        <a href="https://udhawan97.github.io/Golavo" style={{ color: "#c9a227" }}>
          documentation
        </a>
        .
      </p>
    </main>
  );
}
