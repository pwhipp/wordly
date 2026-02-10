export default function ScoreBoard({
  scores,
  playerScore,
  scoreContainerRef,
  playerScoreRef,
  solutionWord,
  solutionDefinition,
  onClose
}) {
  const scoresToRender =
    scores.length === 0 && playerScore ? [playerScore] : scores;

  return (
    <div className="modal">
      <div className="modal-content scores">
        <h2>Hi Scores</h2>
        <div className="score-container" ref={scoreContainerRef}>
          {scoresToRender.length ? (
            scoresToRender.map((entry) => {
              const isPlayer = playerScore?.uid === entry.uid;
              return (
                <div
                  key={entry.uid}
                  className={`score-row ${isPlayer ? "highlight" : ""}`}
                  ref={isPlayer ? playerScoreRef : null}
                >
                  <span>{entry.name}</span>
                  <span>{entry.tries} tries</span>
                  <span>{entry.duration}s</span>
                </div>
              );
            })
          ) : (
            <p>No scores yet.</p>
          )}
        </div>
        <p className="score-note">Ranked by fewest tries, then fastest time.</p>
        {solutionWord && (
          <p className="score-solution">{`${solutionWord}: ${solutionDefinition}`}</p>
        )}
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            onClose();
          }}
        >
          Close
        </button>
      </div>
    </div>
  );
}
