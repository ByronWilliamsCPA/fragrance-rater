import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { fragranceApi, evaluationApi, reviewerApi, recommendationApi } from '../services/api';

function StarDisplay({ rating }) {
  return (
    <span>
      {[1, 2, 3, 4, 5].map((star) => (
        <span key={star} className={star <= rating ? 'text-yellow-400' : 'text-gray-300'}>
          ★
        </span>
      ))}
    </span>
  );
}

function NotesList({ notes, label, color }) {
  if (!notes || notes.length === 0) return null;

  const colorClasses = {
    top: 'bg-yellow-100 text-yellow-800',
    heart: 'bg-pink-100 text-pink-800',
    base: 'bg-amber-100 text-amber-800',
  };

  return (
    <div className="mb-4">
      <h4 className="text-sm font-medium text-gray-500 mb-2">{label}</h4>
      <div className="flex flex-wrap gap-1">
        {notes.map((note) => (
          <span
            key={note.id}
            className={`px-2 py-1 rounded text-sm ${colorClasses[color] || 'bg-gray-100 text-gray-700'}`}
          >
            {note.name}
          </span>
        ))}
      </div>
    </div>
  );
}

function FragranceDetailPage() {
  const { id } = useParams();

  const { data: fragrance, isLoading } = useQuery({
    queryKey: ['fragrance', id],
    queryFn: () => fragranceApi.get(id).then(r => r.data),
  });

  const { data: evaluations = [] } = useQuery({
    queryKey: ['evaluations', 'fragrance', id],
    queryFn: () => evaluationApi.list({ fragrance_id: id }).then(r => r.data),
  });

  const { data: reviewers = [] } = useQuery({
    queryKey: ['reviewers'],
    queryFn: () => reviewerApi.list().then(r => r.data),
  });

  if (isLoading) {
    return <div className="text-center py-8 text-gray-500">Loading...</div>;
  }

  if (!fragrance) {
    return <div className="text-center py-8 text-gray-500">Fragrance not found</div>;
  }

  // Calculate family average rating
  const avgRating = evaluations.length > 0
    ? evaluations.reduce((sum, e) => sum + e.rating, 0) / evaluations.length
    : null;

  return (
    <div>
      <Link to="/fragrances" className="text-perfume-600 hover:text-perfume-700 mb-4 inline-block">
        ← Back to Fragrances
      </Link>

      <div className="grid md:grid-cols-3 gap-6">
        {/* Main Info */}
        <div className="md:col-span-2">
          <div className="card">
            <div className="flex items-start space-x-6">
              {fragrance.image_url ? (
                <img
                  src={fragrance.image_url}
                  alt={fragrance.name}
                  className="w-32 h-32 object-cover rounded-lg"
                />
              ) : (
                <div className="w-32 h-32 bg-gray-100 rounded-lg flex items-center justify-center text-4xl">
                  🌸
                </div>
              )}

              <div className="flex-1">
                <h1 className="text-2xl font-bold text-gray-900">{fragrance.name}</h1>
                <p className="text-lg text-gray-600">{fragrance.brand}</p>

                <div className="flex flex-wrap gap-2 mt-3">
                  {fragrance.primary_family && (
                    <span className="px-3 py-1 bg-perfume-100 text-perfume-700 rounded-full text-sm">
                      {fragrance.primary_family}
                    </span>
                  )}
                  {fragrance.subfamily && (
                    <span className="px-3 py-1 bg-gray-100 text-gray-700 rounded-full text-sm">
                      {fragrance.subfamily.replace('_', ' ')}
                    </span>
                  )}
                  {fragrance.gender_target && (
                    <span className="px-3 py-1 bg-gray-100 text-gray-600 rounded-full text-sm">
                      {fragrance.gender_target}
                    </span>
                  )}
                  {fragrance.concentration && (
                    <span className="px-3 py-1 bg-gray-100 text-gray-600 rounded-full text-sm uppercase">
                      {fragrance.concentration}
                    </span>
                  )}
                </div>

                <div className="flex items-center mt-4 space-x-6">
                  {fragrance.rating && (
                    <div>
                      <span className="text-yellow-400 text-xl">★</span>
                      <span className="ml-1 text-lg font-medium">{fragrance.rating.toFixed(1)}</span>
                      <span className="text-gray-400 text-sm ml-1">(community)</span>
                    </div>
                  )}

                  {avgRating && (
                    <div>
                      <span className="text-perfume-500 text-xl">★</span>
                      <span className="ml-1 text-lg font-medium">{avgRating.toFixed(1)}</span>
                      <span className="text-gray-400 text-sm ml-1">(family avg)</span>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Notes Pyramid */}
            <div className="mt-6 pt-6 border-t">
              <h3 className="font-semibold text-gray-800 mb-4">Fragrance Notes</h3>

              <NotesList notes={fragrance.top_notes} label="Top Notes" color="top" />
              <NotesList notes={fragrance.heart_notes} label="Heart Notes" color="heart" />
              <NotesList notes={fragrance.base_notes} label="Base Notes" color="base" />

              {!fragrance.top_notes?.length && !fragrance.heart_notes?.length && !fragrance.base_notes?.length && (
                <p className="text-gray-400">No note information available</p>
              )}
            </div>

            {/* Accords */}
            {fragrance.accords && Object.keys(fragrance.accords).length > 0 && (
              <div className="mt-6 pt-6 border-t">
                <h3 className="font-semibold text-gray-800 mb-4">Main Accords</h3>
                <div className="space-y-2">
                  {Object.entries(fragrance.accords)
                    .sort((a, b) => b[1] - a[1])
                    .slice(0, 6)
                    .map(([accord, intensity]) => (
                      <div key={accord} className="flex items-center">
                        <span className="w-24 text-sm text-gray-600 capitalize">{accord}</span>
                        <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-perfume-400 rounded-full"
                            style={{ width: `${Math.min(100, intensity * 100)}%` }}
                          />
                        </div>
                      </div>
                    ))
                  }
                </div>
              </div>
            )}

            {/* Meta info */}
            <div className="mt-6 pt-6 border-t text-sm text-gray-500">
              <div className="flex flex-wrap gap-4">
                {fragrance.launch_year && (
                  <span>Launched: {fragrance.launch_year}</span>
                )}
                {fragrance.longevity && (
                  <span>Longevity: {fragrance.longevity}</span>
                )}
                {fragrance.sillage && (
                  <span>Sillage: {fragrance.sillage}</span>
                )}
                <span className="capitalize">Source: {fragrance.data_source}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Sidebar - Family Evaluations */}
        <div className="space-y-4">
          <div className="card">
            <h3 className="font-semibold text-gray-800 mb-4">Family Evaluations</h3>

            {evaluations.length === 0 ? (
              <div>
                <p className="text-gray-500 mb-4">No one has evaluated this yet.</p>
                <Link to="/evaluate" className="btn btn-primary w-full text-center">
                  Be the First
                </Link>
              </div>
            ) : (
              <div className="space-y-4">
                {evaluations.map((evaluation) => (
                  <div key={evaluation.id} className="border-b pb-3 last:border-b-0">
                    <div className="flex justify-between items-center">
                      <Link
                        to={`/reviewer/${evaluation.reviewer_id}`}
                        className="font-medium text-perfume-600 hover:text-perfume-700"
                      >
                        {evaluation.reviewer?.name}
                      </Link>
                      <StarDisplay rating={evaluation.rating} />
                    </div>

                    {evaluation.notes && (
                      <p className="text-sm text-gray-500 mt-1 italic">
                        "{evaluation.notes}"
                      </p>
                    )}
                  </div>
                ))}

                <Link
                  to="/evaluate"
                  className="btn btn-secondary w-full text-center block mt-4"
                >
                  Add Another Evaluation
                </Link>
              </div>
            )}
          </div>

          {/* Who might like this */}
          {evaluations.length > 0 && reviewers.length > 0 && (
            <div className="card">
              <h3 className="font-semibold text-gray-800 mb-3">Who hasn't tried this?</h3>
              <div className="space-y-2">
                {reviewers
                  .filter(r => !evaluations.some(e => e.reviewer_id === r.id))
                  .map(reviewer => (
                    <Link
                      key={reviewer.id}
                      to={`/reviewer/${reviewer.id}`}
                      className="block text-gray-600 hover:text-perfume-600"
                    >
                      {reviewer.name}
                    </Link>
                  ))
                }
                {reviewers.every(r => evaluations.some(e => e.reviewer_id === r.id)) && (
                  <p className="text-gray-400 text-sm">Everyone has tried it!</p>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default FragranceDetailPage;
