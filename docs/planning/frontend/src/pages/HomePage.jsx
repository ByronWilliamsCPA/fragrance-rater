import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { evaluationApi, reviewerApi } from '../services/api';

function StarDisplay({ rating }) {
  return (
    <div className="flex">
      {[1, 2, 3, 4, 5].map((star) => (
        <span
          key={star}
          className={`w-4 h-4 ${star <= rating ? 'text-yellow-400' : 'text-gray-300'}`}
        >
          ★
        </span>
      ))}
    </div>
  );
}

function HomePage() {
  const { data: evaluations = [], isLoading: evalLoading } = useQuery({
    queryKey: ['evaluations', 'recent'],
    queryFn: () => evaluationApi.list({ limit: 20 }).then(r => r.data),
  });

  const { data: reviewers = [] } = useQuery({
    queryKey: ['reviewers'],
    queryFn: () => reviewerApi.list().then(r => r.data),
  });

  // Group evaluations by reviewer
  const evaluationsByReviewer = reviewers.map(reviewer => ({
    reviewer,
    evaluations: evaluations.filter(e => e.reviewer_id === reviewer.id),
    avgRating: evaluations
      .filter(e => e.reviewer_id === reviewer.id)
      .reduce((sum, e, _, arr) => sum + e.rating / arr.length, 0),
  }));

  return (
    <div>
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Fragrance Tracker</h1>
        <Link to="/evaluate" className="btn btn-primary">
          + New Evaluation
        </Link>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <div className="card text-center">
          <div className="text-3xl font-bold text-perfume-600">{evaluations.length}</div>
          <div className="text-sm text-gray-500">Evaluations</div>
        </div>
        <div className="card text-center">
          <div className="text-3xl font-bold text-perfume-600">
            {new Set(evaluations.map(e => e.fragrance_id)).size}
          </div>
          <div className="text-sm text-gray-500">Fragrances Tried</div>
        </div>
        <div className="card text-center">
          <div className="text-3xl font-bold text-perfume-600">{reviewers.length}</div>
          <div className="text-sm text-gray-500">Family Members</div>
        </div>
        <div className="card text-center">
          <div className="text-3xl font-bold text-perfume-600">
            {evaluations.length > 0
              ? (evaluations.reduce((s, e) => s + e.rating, 0) / evaluations.length).toFixed(1)
              : '-'
            }
          </div>
          <div className="text-sm text-gray-500">Avg Rating</div>
        </div>
      </div>

      {/* Reviewer Cards */}
      <h2 className="text-xl font-semibold text-gray-800 mb-4">Family Members</h2>
      <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {reviewers.map(reviewer => {
          const reviewerEvals = evaluations.filter(e => e.reviewer_id === reviewer.id);
          return (
            <Link
              key={reviewer.id}
              to={`/reviewer/${reviewer.id}`}
              className="card hover:shadow-md transition-shadow"
            >
              <h3 className="font-semibold text-lg">{reviewer.name}</h3>
              <p className="text-sm text-gray-500">
                {reviewerEvals.length} evaluation{reviewerEvals.length !== 1 ? 's' : ''}
              </p>
              {reviewerEvals.length > 0 && (
                <div className="mt-2">
                  <StarDisplay
                    rating={Math.round(
                      reviewerEvals.reduce((s, e) => s + e.rating, 0) / reviewerEvals.length
                    )}
                  />
                </div>
              )}
            </Link>
          );
        })}

        {reviewers.length === 0 && (
          <div className="col-span-full text-center py-8 text-gray-500">
            <p className="mb-4">No family members set up yet.</p>
            <Link to="/import" className="btn btn-secondary">
              Set Up Reviewers
            </Link>
          </div>
        )}
      </div>

      {/* Recent Evaluations */}
      <h2 className="text-xl font-semibold text-gray-800 mb-4">Recent Evaluations</h2>

      {evalLoading ? (
        <div className="text-center py-8 text-gray-500">Loading...</div>
      ) : evaluations.length === 0 ? (
        <div className="card text-center py-8">
          <p className="text-gray-500 mb-4">No evaluations yet. Time to smell some perfume!</p>
          <Link to="/evaluate" className="btn btn-primary">
            Add First Evaluation
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {evaluations.slice(0, 10).map(evaluation => (
            <div key={evaluation.id} className="card flex items-center justify-between">
              <div className="flex-1">
                <Link
                  to={`/fragrances/${evaluation.fragrance_id}`}
                  className="font-medium text-perfume-600 hover:text-perfume-700"
                >
                  {evaluation.fragrance?.name || 'Unknown Fragrance'}
                </Link>
                <span className="text-gray-400 mx-2">by</span>
                <span className="text-gray-600">{evaluation.fragrance?.brand}</span>
              </div>

              <div className="flex items-center space-x-4">
                <span className="text-sm text-gray-500">
                  {evaluation.reviewer?.name}
                </span>
                <StarDisplay rating={evaluation.rating} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default HomePage;
