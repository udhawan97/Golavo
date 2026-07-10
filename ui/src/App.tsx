export default function App() {
  return (
    <main
      style={{
        fontFamily: "ui-sans-serif, system-ui, -apple-system, sans-serif",
        maxWidth: 640,
        margin: "12vh auto",
        padding: "0 1.5rem",
        color: "#101312",
        lineHeight: 1.5,
      }}
    >
      <h1 style={{ letterSpacing: 3, fontWeight: 800 }}>GOLAVO</h1>
      <p style={{ fontStyle: "italic", color: "#0b6e4f", marginTop: "-0.4rem" }}>
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
