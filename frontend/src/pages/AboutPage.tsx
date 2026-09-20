import { followRouteLink, pathFor, type Route } from '../routing/routes'

type AboutPageProps = {
  navigate: (route: Route) => void
}

export function AboutPage({ navigate }: AboutPageProps) {
  return (
    <div className="prose">
      <section>
        <div className="page-heading">
          <div>
            <h2>How this project learns your taste</h2>
          </div>
        </div>
        <p className="hero-statement">
          Learn your fragrance taste by measuring what you actually respond to.
        </p>
      </section>
      <section>
        <h3>Where the idea came from</h3>
        <p>
          For several years, this project's creator ran a wine-tour company. Two things stood out.
          Regional food and fruit could offer a decent pairing clue, but the more reliable signal
          came from something simpler: watching how a guest reacted to a few carefully chosen wines
          with known profiles. A handful of honest reactions revealed a pattern faster than any list
          of stated preferences, and that pattern was what actually predicted what a guest would
          enjoy next.
        </p>
        <p>
          Fragrance raises the same question, but the clues are much less obvious. A guest can taste
          a wine and describe what they notice; a note list on a fragrance doesn't work the same
          way, and liking one fragrance that contains a certain material doesn't reliably predict
          liking another one that shares it. So this project asks a more direct question: can we
          learn someone's fragrance preferences from their reactions to a deliberately chosen set of
          complete fragrances, and then prove we've learned something real by predicting how they'll
          respond to fragrances they haven't smelled yet?
        </p>
      </section>
      <section>
        <h3>Why fragrance is harder</h3>
        <p>
          Wine pairing has food and region as rough starting clues. Fragrance doesn't have an
          equivalent shortcut. A note list ("bergamot, iris, cedar") describes ingredients, not the
          experience of smelling the finished composition, and the same note can read completely
          differently depending on what it's blended with, at what concentration, and on whose skin.
          Liking a fragrance built around a note doesn't reliably predict liking a different
          fragrance built around the same note.
        </p>
        <p>
          That doesn't make fragrance more complex than wine; it means the signals that predict a
          person's preferences are harder to isolate from ingredient lists alone. The practical
          answer is the same one that worked at the tasting table: pay attention to reactions to
          complete, real examples, not to what someone believes their preferences are on paper.
        </p>
      </section>
      <section>
        <h3>How calibration works</h3>
        <p>Learning someone's preferences happens in five stages:</p>
        <div className="flow-steps">
          <div className="flow-step">
            <strong>Blind baseline</strong>
            <p>
              The evaluator smells a set of complete fragrances, blind, without knowing what they
              are or why they were chosen.
            </p>
          </div>
          <span className="flow-arrow" aria-hidden="true">
            →
          </span>
          <div className="flow-step">
            <strong>Preference model</strong>
            <p>
              Those reactions are used to build a picture of what this particular person tends to
              like, dislike, and respond strongly to.
            </p>
          </div>
          <span className="flow-arrow" aria-hidden="true">
            →
          </span>
          <div className="flow-step">
            <strong>Frozen predictions</strong>
            <p>
              Before the evaluator smells anything new, a manager can freeze the model's
              prediction for that fragrance, writing it down and locking it in first.
            </p>
          </div>
          <span className="flow-arrow" aria-hidden="true">
            →
          </span>
          <div className="flow-step">
            <strong>Blind holdouts</strong>
            <p>
              The evaluator then smells that new, still-unidentified fragrance and records a genuine
              blind reaction.
            </p>
          </div>
          <span className="flow-arrow" aria-hidden="true">
            →
          </span>
          <div className="flow-step">
            <strong>Validation</strong>
            <p>
              The locked-in prediction and the actual reaction are compared, which is what tells us
              whether the model learned something real.
            </p>
          </div>
        </div>
        <p>
          For the step-by-step mechanics behind this: sample codes, locking, and exactly when
          identities reveal.
        </p>
        <p>
          <a
            className="inline-target-link"
            href={pathFor('protocol')}
            onClick={(event) => followRouteLink(event, 'protocol', navigate)}
          >
            Read the calibration protocol
          </a>
        </p>
      </section>
      <section>
        <h3>Why repeats matter</h3>
        <p>
          A handful of the baseline fragrances are presented more than once, without the evaluator
          being told which ones. This isn't a trick; it's how the system checks its own instrument.
          If an evaluator's reaction to the same fragrance changes noticeably between presentations,
          that tells us something about how stable their responses are on a given day, and that gets
          factored in before anything is treated as a firm preference signal. Exactly which
          fragrances repeat, and when, is kept concealed so it can't influence the reaction being
          measured.
        </p>
      </section>
      <section>
        <h3>Prediction, not memorization</h3>
        <p>
          The holdout stage is the part of this project that actually proves something. When a
          manager freezes a prediction ahead of a holdout fragrance, the model's prediction, which
          model version made it, what data it was trained on, and when it made the call are all
          written down and locked first. Only after that does the evaluator smell the fragrance and
          record a real reaction.
        </p>
        <p>
          The model never gets to learn from a holdout fragrance and then claim credit for
          predicting it afterward; the observation from that blind evaluation isn't allowed into the
          training data for the model version being scored. It's the difference between a model that
          studied with the answer key and one that took a closed-book test: only the closed-book
          result means anything.
        </p>
      </section>
      <section>
        <h3>What happens after calibration</h3>
        <p>
          Once the initial calibration and validation stages are complete, the model doesn't stop
          learning. Ordinary fragrance ratings recorded afterward continue to refine future versions
          of the preference model. The baseline set an evaluator starts with is a deliberately
          chosen starting point, not meant to be the last word on their fragrance universe.
          Targeting new baseline fragrances based on what the model still doesn't know, adaptive
          sampling, is planned future work, not something this version does. Holdout ratings stay
          excluded from training indefinitely: this version has no mechanism that later releases
          them into ordinary training data.
        </p>
      </section>
      <section>
        <h3>What this is not</h3>
        <ul className="data-list">
          <li>
            A ranking of the "best" fragrances. There isn't one; there's only what a fragrance
            predicts about a specific person's taste.
          </li>
          <li>
            Designed so every evaluator will like every baseline fragrance. Some of them are chosen
            specifically because they're polarizing.
          </li>
          <li>
            An influencer or review system. Nobody's opinion here is being published or scored
            against anyone else's.
          </li>
          <li>
            A note-matching quiz. Matching a fragrance to a preference by its listed notes is
            exactly the shortcut this project is trying to avoid.
          </li>
          <li>
            A test an evaluator can fail. Disliking a fragrance, even strongly, is useful
            information: it helps mark where somebody's preferences stop, not what's wrong with
            their answer.
          </li>
        </ul>
      </section>
      <section>
        <details>
          {/*
            Counts below (33/39/13/6/10) are the baseline-only half of the authoritative
            43-fragrance/49-presentation V3.1 baseline; see
            docs/planning/evidence/baseline-v3.1-universal-and-holdout.md for the source and
            the reconciliation (33 + 10 holdout = 43; 39 + 10 holdout = 49). Update both places
            together if the baseline is revised.
          */}
          <summary>Technical methodology</summary>
          <ul className="data-list">
            <li>33 unique fragrances make up the universal baseline.</li>
            <li>
              Those fragrances are delivered as 39 blinded presentations across 13 sessions of
              three.
            </li>
            <li>
              Six of the baseline presentations are concealed repeats of earlier ones, used to
              measure within-evaluator reliability. Which ones are never disclosed.
            </li>
            <li>
              Presentation order is randomized and counterbalanced, so a presentation's slot in a
              session never doubles as its smelling order.
            </li>
            <li>
              After baseline calibration, 10 separate validation holdouts test genuine out-of-sample
              prediction.
            </li>
            <li>
              Every enrolled evaluator draws from the full holdout set, in an order shuffled
              independently for them; their identities stay concealed until that evaluator's own
              holdout stage is locked.
            </li>
            <li>
              When a manager freezes a checkpoint for an eligible holdout, the predicted liking,
              which model version and training-data cutoff produced it, and the timestamp are all
              frozen before the evaluator smells the fragrance.
            </li>
            <li>
              That frozen prediction is compared against the evaluator's actual blind rating. The
              holdout observation is excluded from training data for the model run being scored.
            </li>
            <li>
              Once a holdout's validation is complete, its rating stays excluded from training
              indefinitely: this version has no mechanism that later releases it into ordinary
              training data.
            </li>
            <li>
              Exact fragrance version, concentration, and provenance are tracked and preserved
              throughout, for both baseline and holdout fragrances.
            </li>
          </ul>
        </details>
      </section>
    </div>
  )
}
