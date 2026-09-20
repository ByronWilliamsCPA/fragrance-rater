export function CalibrationProtocolPage() {
  return (
    <div className="prose">
      <section>
        <div className="page-heading">
          <div>
            <h2>Calibration protocol</h2>
          </div>
        </div>
        <p className="hero-statement">
          What actually happens between picking up a coded sample and seeing what it was.
        </p>
      </section>
      <section>
        <h3>Find your sample by its code</h3>
        <p>
          Every sample is labeled with a code, not a name. The code is what ties your responses to
          a specific presentation; it never tells you, or anyone recording on your behalf, what the
          fragrance is. On the Calibration screen, choose your assignment, then work through the
          sessions shown for it.
        </p>
      </section>
      <section>
        <h3>Two blind stages, locked independently</h3>
        <div className="flow-steps">
          <div className="flow-step">
            <strong>Blotter screen</strong>
            <p>
              A first blind impression from a paper blotter, usually logged at a couple of
              elapsed-time points as it dries down.
            </p>
          </div>
          <span className="flow-arrow" aria-hidden="true">
            →
          </span>
          <div className="flow-step">
            <strong>Skin test</strong>
            <p>
              An optional second blind stage on skin, for samples selected to continue past the
              blotter screen.
            </p>
          </div>
          <span className="flow-arrow" aria-hidden="true">
            →
          </span>
          <div className="flow-step">
            <strong>Lock</strong>
            <p>
              Once a stage is locked, that stage's blind entry is closed. Locking is what starts
              the countdown toward reveal, not a deadline you have to beat.
            </p>
          </div>
        </div>
        <p>
          Each stage's responses are append-only: saving a new observation never overwrites an
          earlier one for the same presentation and stage. If nothing was detected, intensity is
          recorded as zero and liking is left blank rather than guessed.
        </p>
      </section>
      <section>
        <h3>What each observation records</h3>
        <ul className="data-list">
          <li>Independent 0–5 perceptual dimensions (how it presents, not how much you like it).</li>
          <li>0–10 liking, wear, buy, and appreciation scales.</li>
          <li>Perceived notes and any free-text impressions you want to add.</li>
          <li>
            Elapsed time since application, so a dry-down observation isn't mistaken for an
            opening one.
          </li>
        </ul>
      </section>
      <section>
        <h3>When your identities appear</h3>
        <p>
          Reveal isn't a fixed date; it's a state your enrollment reaches once the required blind
          work is done:
        </p>
        <ul className="data-list">
          <li>
            Baseline samples stay hidden until every required blotter screen, hidden repeat, and
            planned skin test is locked, and the skin plan itself has been finalized. A plan can be
            finalized as empty if no samples were selected to continue to skin.
          </li>
          <li>
            Holdout samples stay hidden separately, on their own timeline: each one clears only
            once its own blotter stage is locked.
          </li>
        </ul>
        <p>
          Once your enrollment is eligible, revealed identities appear on the Calibration screen
          automatically. After reveal, you can still add observations, but they're recorded as
          post-reveal notes appended alongside your original blind responses, not replacements for
          them.
        </p>
      </section>
      <section>
        <h3>Concealed repeats</h3>
        <p>
          A few presentations in a baseline are the same fragrance shown to you more than once,
          interleaved with the rest and never flagged as a repeat. You're not meant to notice them.
          They exist to measure how consistent your own ratings are from one presentation to the
          next, which matters for judging whether any single rating reflects a real preference or
          just noise.
        </p>
      </section>
      <section>
        <h3>Holdouts are frozen before you smell them</h3>
        <p>
          For a holdout presentation, the system's prediction, its confidence, the exact model
          version, and what data produced it are all written down and locked before you record a
          blind reaction. Your response is then compared against that frozen prediction, not the
          other way around.
        </p>
        <p>
          Holdout ratings are never fed back into training the model version being scored, and they
          stay excluded from ordinary training data indefinitely afterward. This version has no
          mechanism that later releases a holdout rating into training.
        </p>
      </section>
      <section>
        <details>
          <summary>Access and verification details</summary>
          <ul className="data-list">
            <li>
              The code-to-fragrance mapping used to label physical samples is only ever available
              to managers, through a route participants can't reach.
            </li>
            <li>
              Skin-selection reasons and other pre-reveal experimental metadata are withheld from
              participant views for the same reason: they could hint at identity before reveal is
              earned.
            </li>
            <li>
              Sample identity, concentration, and provenance are verified and tracked exactly, for
              both baseline and holdout fragrances, so what you rated is what gets recorded.
            </li>
          </ul>
        </details>
      </section>
    </div>
  )
}
