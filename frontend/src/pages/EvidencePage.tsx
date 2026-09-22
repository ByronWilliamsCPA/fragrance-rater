import { followRouteLink, pathFor, type Route } from '../routing/routes'

const sources = [
  {
    key: 'nielsen',
    name: 'NielsenIQ: Beauty 2024 mid-year update',
    href: 'https://nielseniq.com/global/en/insights/commentary/2024/beauty-2024-mid-year-update/',
    use: 'Online share and growth for the broader beauty and personal-care category.',
    limit: 'Market-tracking data, not a perfume-only study or a test of this product.',
  },
  {
    key: 'circana',
    name: 'Circana: U.S. prestige beauty, first half of 2024',
    href: 'https://www.circana.com/post/us-prestige-beauty-industry-sales-grow-by-8-in-the-first-half-circana-reports',
    use: 'Fragrance growth and the relative growth of mini and travel formats.',
    limit:
      'U.S. prestige retail data; it does not show that personalized sampling caused the growth.',
  },
  {
    key: 'han',
    name: 'Han et al.: Cross-sampling through e-commerce warehouses',
    href: 'https://doi.org/10.1287/mnsc.2020.00902',
    use: 'A large field experiment connecting physical samples with later online visits and sales.',
    limit:
      'Six brands across cosmetics and consumer goods, not perfume; the 64% relative increase came from a small absolute spending baseline.',
  },
  {
    key: 'bawaShoemaker',
    name: 'Bawa and Shoemaker: Incremental brand sales from free samples',
    href: 'https://doi.org/10.1287/mksc.1030.0052',
    use: 'Two field experiments found incremental sales effects lasting as long as 12 months.',
    limit: 'Consumer products rather than fragrance; effects varied widely between two brands.',
  },
  {
    key: 'odoreYsl',
    name: 'Odore and YSL Beauty: Tracked fragrance-sampling campaign',
    href: 'https://www.odore.com/case-studies/ysl-product-sampling',
    use: 'A fragrance-specific campaign tied sample claims to full-size DTC purchases within 30 days.',
    limit:
      'Vendor-reported case study targeting high-intent visitors; no sample count, control group, or independent audit is disclosed.',
  },
  {
    key: 'lenochova',
    name: 'Lenochová et al.: Psychology of fragrance use',
    href: 'https://doi.org/10.1371/journal.pone.0033810',
    use: 'Evidence that the same perfume can interact differently with different wearers.',
    limit: 'Small experiments; the preferred-perfume comparison used 21 male odor donors.',
  },
  {
    key: 'distel',
    name: 'Distel et al.: Perception across three cultures',
    href: 'https://pubmed.ncbi.nlm.nih.gov/10321820/',
    use: 'Familiarity, intensity, and pleasantness were related in ratings of everyday odors.',
    limit:
      'Correlational ratings of 18 odors, not proof that increasing familiarity causes liking.',
  },
] as const

// Keyed by name, not array position: the snapshot stats below cite five of these seven
// sources (bawaShoemaker and distel back only the source ledger, with no single headline
// figure), and a future reorder of `sources` must not silently repoint a citation.
type SourceKey = (typeof sources)[number]['key']
const sourceByKey = Object.fromEntries(sources.map((source) => [source.key, source])) as Record<
  SourceKey,
  (typeof sources)[number]
>

type EvidencePageProps = {
  navigate: (route: Route) => void
}

export function EvidencePage({ navigate }: EvidencePageProps) {
  return (
    <div className="prose">
      <section>
        <div className="page-heading">
          <div>
            <p className="eyebrow">Evidence and opportunity</p>
            <h2>Why better fragrance discovery matters</h2>
          </div>
        </div>
        <p className="hero-statement">
          Fragrance is increasingly bought through digital channels, but the thing being purchased
          cannot be smelled on a screen, and the same fragrance can behave differently from one
          wearer to another.
        </p>
        <p className="disclosure">
          This page separates published evidence from the hypotheses Fragrance Rater still needs to
          test. Figures describe their cited markets and studies; they are not performance claims
          about this application.
        </p>
        <p>
          <a
            className="inline-target-link"
            href={pathFor('about')}
            onClick={(event) => followRouteLink(event, 'about', navigate)}
          >
            How this project learns your taste
          </a>
        </p>
      </section>

      <section aria-labelledby="evidence-snapshot">
        <div className="section-head">
          <h3 id="evidence-snapshot">What the available data says</h3>
        </div>
        <dl className="evidence-stats">
          <div>
            <dt>41%</dt>
            <dd>
              of beauty and personal-care sales tracked by NielsenIQ occurred through e-commerce in
              the first half of 2024. Online beauty sales grew 14.1% over the preceding year.
              <a href={sourceByKey.nielsen.href}> Source and scope</a>
            </dd>
          </div>
          <div>
            <dt>+12%</dt>
            <dd>
              U.S. prestige-fragrance dollar growth in the first half of 2024. Mini and travel-size
              unit sales grew at twice the rate of the overall fragrance category.
              <a href={sourceByKey.circana.href}> Source and scope</a>
            </dd>
          </div>
          <div>
            <dt>+64%</dt>
            <dd>
              relative spending during the campaign month for sampled customers versus matched
              controls in a 55,000-sample e-commerce field experiment. The relative lift came from a
              low spending baseline. Purchase and spending effects lasted at least three months;
              store-visit effects lasted longer.
              <a href={sourceByKey.han.href}> Source and scope</a>
            </dd>
          </div>
          <div>
            <dt>8.33%</dt>
            <dd>
              of sample recipients reportedly bought a full-size product within 30 days in a tracked
              YSL fragrance campaign. The campaign operator also reported 8× attributed ROI, but did
              not publish a control group or complete methodology.
              <a href={sourceByKey.odoreYsl.href}> Source and scope</a>
            </dd>
          </div>
          <div>
            <dt>21</dt>
            <dd>
              odor donors in the study's preferred-perfume comparison. Their body odor paired with
              their self-selected perfume was rated more favorably than when paired with an assigned
              perfume, even though the perfumes alone did not differ in pleasantness.
              <a href={sourceByKey.lenochova.href}> Source and scope</a>
            </dd>
          </div>
        </dl>
        <div className="evidence-claim">
          <p className="eyebrow">A claim the evidence can support</p>
          <blockquote>
            Physical product sampling can increase trial and sales, and field studies show that its
            effects can persist beyond the initial promotion. Fragrance-specific campaign data also
            shows that a measurable share of targeted sample recipients later purchase a full-size
            product. The size of that benefit depends on the product, audience, distribution method,
            and follow-up journey.
          </blockquote>
        </div>
      </section>

      <section aria-labelledby="two-audiences">
        <div className="section-head">
          <h3 id="two-audiences">One discovery problem, two beneficiaries</h3>
        </div>
        <div className="audience-grid">
          <article>
            <p className="eyebrow">For fragrance buyers</p>
            <h4>Spend sample money where it can teach you the most</h4>
            <p>
              Popularity and note similarity can help someone browse, but neither establishes how a
              finished perfume will smell to that person or develop on their skin. A measured
              preference baseline can produce a shorter, more varied sampling list, including
              fragrances from smaller producers that popularity rankings may never surface.
            </p>
            <ul className="data-list">
              <li>Discover beyond familiar brands and crowd averages.</li>
              <li>Prioritize samples before committing to a bottle.</li>
              <li>
                Learn separately what smells good, what fits a setting, and what is worth buying.
              </li>
            </ul>
          </article>
          <article>
            <p className="eyebrow">For makers and sellers</p>
            <h4>Put limited samples in front of better-qualified prospects</h4>
            <p>
              Sampling has a real cost, especially for an independent producer. The opportunity is
              not to promise that every matched person will buy. It is to rank who should try what,
              then measure the complete path from recommendation to sample, wear, purchase, and
              repeat behavior.
            </p>
            <ul className="data-list">
              <li>Reach people whose measured responses suggest a useful trial.</li>
              <li>
                Give less-discovered products a route that does not depend only on popularity.
              </li>
              <li>Learn which contexts, formats, and offers turn interest into durable use.</li>
            </ul>
          </article>
        </div>
      </section>

      <section aria-labelledby="approach-chain">
        <div className="section-head">
          <h3 id="approach-chain">How the approach is meant to work</h3>
        </div>
        <ol className="evidence-chain">
          <li>
            <strong>Measure the individual</strong>
            <span>
              Blind reactions to a deliberately varied set reveal more than a style label.
            </span>
          </li>
          <li>
            <strong>Rank candidates</strong>
            <span>
              Search both known favorites and less-visible perfumes for informative matches.
            </span>
          </li>
          <li>
            <strong>Prioritize samples</strong>
            <span>
              Recommend a manageable shortlist rather than another speculative full bottle.
            </span>
          </li>
          <li>
            <strong>Follow the outcome</strong>
            <span>Record liking, actual wear, purchase, and repeat use by setting and season.</span>
          </li>
        </ol>
      </section>

      <section aria-labelledby="proof-needed">
        <div className="section-head">
          <h3 id="proof-needed">What we still have to prove</h3>
        </div>
        <p>
          Published work supports the market tension and the value of physical trial. It does not
          yet prove that Fragrance Rater can allocate samples better than a retailer quiz, a
          popularity list, or a simple note-based recommender. That claim must come from prospective
          outcomes collected by the application.
        </p>
        <p>
          The evidence is strong enough to say that samples can generate incremental sales. It is
          not strong enough to promise a universal conversion rate or fragrance-customer retention
          effect. Fragrance Rater should measure incremental lift against an eligible comparison
          group, not only count purchases after a sample was sent.
        </p>
        <div className="measurement-grid">
          <div>
            <h4>Buyer measures</h4>
            <ul className="data-list">
              <li>Useful candidates per sampling budget</li>
              <li>Sample satisfaction and avoided unsuitable bottles</li>
              <li>Actual wear and rewear by setting and season</li>
              <li>Purchase under a recorded price, size, and offer</li>
            </ul>
          </div>
          <div>
            <h4>Seller measures</h4>
            <ul className="data-list">
              <li>Recommendation-to-sample acquisition</li>
              <li>Sample-to-wear and sample-to-purchase conversion</li>
              <li>New-to-brand and less-discovered-product reach</li>
              <li>Repeat use, repurchase, and mature outcome windows</li>
            </ul>
          </div>
        </div>
        <p className="disclosure">
          The generated reports' “86% less regret” and “3.2× repurchase” figures remain unsupported.
          Better evidence supports a more precise claim: sampling can improve sales, but the size
          and duration of the effect vary, and fragrance-specific incremental lift still needs a
          controlled measurement.
        </p>
      </section>

      <section aria-labelledby="source-notes">
        <div className="section-head">
          <h3 id="source-notes">Sources, uses, and limits</h3>
        </div>
        <ol className="source-ledger">
          {sources.map((source) => (
            <li key={source.href}>
              <a href={source.href}>{source.name}</a>
              <span>
                <strong>What it supports:</strong> {source.use}
              </span>
              <span>
                <strong>Limit:</strong> {source.limit}
              </span>
            </li>
          ))}
        </ol>
      </section>
    </div>
  )
}
