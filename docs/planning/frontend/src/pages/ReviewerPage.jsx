import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import { reviewerApi, evaluationApi, recommendationApi } from '../services/api';

function StarDisplay({ rating, size = 'sm' }) {
  const sizeClass = size === 'lg' ? 'text-lg' : 'text-sm';
  return (
    <span className={sizeClass}>
      {[1, 2, 3, 4, 5].map((star) => (
        <span key={star} className={star <= rating ? 'text-yellow-400' : 'text-gray-300'}>
          ★
        </span>
      ))}
    </span>
  );
}

function ReviewerPage() {
  const { id } = useParams();
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [suggestionContext, setSuggestionContext] = useState('');

  const { data: reviewer, isLoading: reviewerLoading } = useQuery({
    queryKey: ['reviewer', id],
    queryFn: () => reviewerApi.get(id).then(r => r.data),
  });

  const { data: evaluations = [] } = useQuery({
    queryKey: ['evaluations', 'reviewer', id],
    queryFn: () => evaluationApi.list({ reviewer_id: id, limit: 100 }).then(r => r.data),
  });

  const { data: profile, isLoading: profileLoading } = useQuery({
    queryKey: ['profile', id],
    queryFn: () => recommendationApi.getProfile(id).then(r => r.data),
    enabled: evaluations.length >= 3,
  });

  const { data: recommendations = [], isLoading: recsLoading } = useQuery({
    queryKey: ['recommendations', id],
    queryFn: () => recommendationApi.getRecommendations(id, { limit: 10 }).then(r => r.data),
    enabled: evaluations.length >= 3,
  });

  const { data: llmStatus } = useQuery({
    queryKey: ['llm-status'],
    queryFn: () => recommendationApi.getStatus().then(r => r.data),
  });

  const suggestMutation = useMutation({
    mutationFn: () => recommendationApi.suggestNew(id, suggestionContext).then(r => r.data),
  });

  if (reviewerLoading) {
    return <div className="text-center py-8 text-gray-500">Loading...</div>;
  }

  if (!reviewer) {
    return <div className="text-center py-8 text-gray-500">Reviewer not found</div>;
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold text-gray-900">{reviewer.name}'s Profile</h1>
        <Link to="/evaluate" className="btn btn-primary">
          + New Evaluation
        </Link>
      </div>

      {/* Profile Summary */}
      {profile && (
        <div className="card mb-6">
          <h2 className="text-xl font-semibold mb-3">Preference Profile</h2>
          <p className="text-gray-700 mb-4">{profile.summary}</p>

          <div className="grid md:grid-cols-2 gap-4">
            <div>
              <h3 className="font-medium text-gray-600 mb-2">Notes They Love</h3>
              <div className="flex flex-wrap gap-1">
                {profile.preferred_notes.slice(0, 8).map(note => (
                  <span key={note} className="px-2 py-1 bg-green-100 text-green-700 rounded text-sm">
                    {note}
                  </span>
                ))}
                {profile.preferred_notes.length === 0 && (
                  <span className="text-gray-400 text-sm">Not enough data</span>
                )}
              </div>
            </div>

            <div>
              <h3 className="font-medium text-gray-600 mb-2">Notes to Avoid</h3>
              <div className="flex flex-wrap gap-1">
                {profile.disliked_notes.slice(0, 5).map(note => (
                  <span key={note} className="px-2 py-1 bg-red-100 text-red-700 rounded text-sm">
                    {note}
                  </span>
                ))}
                {profile.disliked_notes.length === 0 && (
                  <span className="text-gray-400 text-sm">None identified</span>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Recommendations */}
      {evaluations.length >= 3 ? (
        <div className="card mb-6">
          <h2 className="text-xl font-semibold mb-4">Recommended Fragrances</h2>

          {recsLoading ? (
            <div className="text-gray-500">Analyzing preferences...</div>
          ) : recommendations.length > 0 ? (
            <div className="space-y-3">
              {recommendations.map((rec) => (
                <div key={rec.fragrance.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <div className="flex-1">
                    <Link
                      to={`/fragrances/${rec.fragrance.id}`}
                      className="font-medium text-perfume-600 hover:text-perfume-700"
                    >
                      {rec.fragrance.name}
                    </Link>
                    <span className="text-gray-400 mx-2">by</span>
                    <span className="text-gray-600">{rec.fragrance.brand}</span>

                    {rec.reasons.length > 0 && (
                      <p className="text-sm text-green-600 mt-1">
                        ✓ {rec.reasons[0]}
                      </p>
                    )}
                    {rec.warnings.length > 0 && (
                      <p className="text-sm text-amber-600">
                        ⚠ {rec.warnings[0]}
                      </p>
                    )}
                  </div>

                  <div className="text-right">
                    <div className="text-lg font-semibold text-perfume-600">
                      {Math.round(rec.match_score * 100)}%
                    </div>
                    <div className="text-xs text-gray-500">match</div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500">No recommendations available yet.</p>
          )}

          {/* AI Suggestions */}
          {llmStatus?.configured && (
            <div className="mt-6 pt-6 border-t">
              <button
                onClick={() => setShowSuggestions(!showSuggestions)}
                className="text-perfume-600 hover:text-perfume-700 font-medium"
              >
                🤖 Get AI Suggestions for New Fragrances to Try
              </button>

              {showSuggestions && (
                <div className="mt-4">
                  <div className="flex gap-2 mb-4">
                    <input
                      type="text"
                      className="input flex-1"
                      placeholder="Optional context: 'for summer', 'date night', etc."
                      value={suggestionContext}
                      onChange={(e) => setSuggestionContext(e.target.value)}
                    />
                    <button
                      onClick={() => suggestMutation.mutate()}
                      disabled={suggestMutation.isPending}
                      className="btn btn-primary"
                    >
                      {suggestMutation.isPending ? 'Thinking...' : 'Get Suggestions'}
                    </button>
                  </div>

                  {suggestMutation.data && (
                    <div className="space-y-2">
                      {suggestMutation.data.map((suggestion, i) => (
                        <div key={i} className="p-3 bg-blue-50 rounded-lg">
                          <div className="font-medium">
                            {suggestion.name} <span className="text-gray-500">by {suggestion.brand}</span>
                          </div>
                          <p className="text-sm text-gray-600">{suggestion.reason}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      ) : (
        <div className="card mb-6 text-center py-8">
          <p className="text-gray-500 mb-2">
            Need at least 3 evaluations to generate recommendations.
          </p>
          <p className="text-sm text-gray-400">
            {reviewer.name} has {evaluations.length} evaluation{evaluations.length !== 1 ? 's' : ''}.
          </p>
        </div>
      )}

      {/* Evaluation History */}
      <div className="card">
        <h2 className="text-xl font-semibold mb-4">Evaluation History</h2>

        {evaluations.length === 0 ? (
          <p className="text-gray-500">No evaluations yet.</p>
        ) : (
          <div className="space-y-3">
            {evaluations.map((evaluation) => (
              <div key={evaluation.id} className="flex items-start justify-between p-3 bg-gray-50 rounded-lg">
                <div className="flex-1">
                  <Link
                    to={`/fragrances/${evaluation.fragrance_id}`}
                    className="font-medium text-perfume-600 hover:text-perfume-700"
                  >
                    {evaluation.fragrance?.name || 'Unknown'}
                  </Link>
                  <span className="text-gray-400 mx-2">by</span>
                  <span className="text-gray-600">{evaluation.fragrance?.brand}</span>

                  {evaluation.notes && (
                    <p className="text-sm text-gray-500 mt-1 italic">
                      "{evaluation.notes}"
                    </p>
                  )}
                </div>

                <StarDisplay rating={evaluation.rating} />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default ReviewerPage;
