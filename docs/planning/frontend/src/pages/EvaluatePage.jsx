import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { reviewerApi, evaluationApi, fragranceApi } from '../services/api';

// Star rating component
function StarRating({ value, onChange, size = 'lg' }) {
  const [hover, setHover] = useState(0);
  const sizeClasses = size === 'lg' ? 'w-10 h-10' : 'w-6 h-6';

  return (
    <div className="flex space-x-1">
      {[1, 2, 3, 4, 5].map((star) => (
        <button
          key={star}
          type="button"
          className={`${sizeClasses} transition-colors ${
            star <= (hover || value) ? 'text-yellow-400' : 'text-gray-300'
          } hover:text-yellow-500`}
          onMouseEnter={() => setHover(star)}
          onMouseLeave={() => setHover(0)}
          onClick={() => onChange(star)}
        >
          <svg fill="currentColor" viewBox="0 0 20 20">
            <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
          </svg>
        </button>
      ))}
    </div>
  );
}

function EvaluatePage() {
  const queryClient = useQueryClient();

  const [formData, setFormData] = useState({
    fragranceName: '',
    fragranceBrand: '',
    reviewerId: '',
    rating: 0,
    notes: '',
  });

  const [searchResults, setSearchResults] = useState([]);
  const [selectedFragrance, setSelectedFragrance] = useState(null);
  const [submitStatus, setSubmitStatus] = useState(null);

  // Get reviewers
  const { data: reviewers = [] } = useQuery({
    queryKey: ['reviewers'],
    queryFn: () => reviewerApi.list().then(r => r.data),
  });

  // Search fragrances as user types
  const searchFragrances = async (query) => {
    if (query.length < 2) {
      setSearchResults([]);
      return;
    }

    try {
      const response = await fragranceApi.list({ query, limit: 10 });
      setSearchResults(response.data);
    } catch (error) {
      console.error('Search error:', error);
    }
  };

  // Submit evaluation
  const submitMutation = useMutation({
    mutationFn: async () => {
      // Use quick evaluate endpoint
      return evaluationApi.quickEvaluate({
        fragrance_name: formData.fragranceName,
        fragrance_brand: formData.fragranceBrand || undefined,
        reviewer_name: reviewers.find(r => r.id.toString() === formData.reviewerId)?.name,
        rating: formData.rating,
        notes: formData.notes || undefined,
      });
    },
    onSuccess: (response) => {
      setSubmitStatus({ type: 'success', message: 'Evaluation saved!' });
      queryClient.invalidateQueries({ queryKey: ['evaluations'] });
      // Reset form
      setFormData({
        fragranceName: '',
        fragranceBrand: '',
        reviewerId: formData.reviewerId, // Keep reviewer selected
        rating: 0,
        notes: '',
      });
      setSelectedFragrance(null);
      setTimeout(() => setSubmitStatus(null), 3000);
    },
    onError: (error) => {
      setSubmitStatus({
        type: 'error',
        message: error.response?.data?.detail || 'Failed to save evaluation',
      });
    },
  });

  const handleFragranceSelect = (fragrance) => {
    setSelectedFragrance(fragrance);
    setFormData({
      ...formData,
      fragranceName: fragrance.name,
      fragranceBrand: fragrance.brand,
    });
    setSearchResults([]);
  };

  const canSubmit = formData.fragranceName && formData.reviewerId && formData.rating > 0;

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-3xl font-bold text-gray-900 mb-8">New Evaluation</h1>

      {submitStatus && (
        <div className={`mb-6 p-4 rounded-lg ${
          submitStatus.type === 'success'
            ? 'bg-green-50 text-green-800 border border-green-200'
            : 'bg-red-50 text-red-800 border border-red-200'
        }`}>
          {submitStatus.message}
        </div>
      )}

      <div className="card space-y-6">
        {/* Fragrance Search */}
        <div>
          <label className="label">Fragrance Name *</label>
          <div className="relative">
            <input
              type="text"
              className="input"
              placeholder="Start typing to search..."
              value={formData.fragranceName}
              onChange={(e) => {
                setFormData({ ...formData, fragranceName: e.target.value });
                searchFragrances(e.target.value);
                setSelectedFragrance(null);
              }}
            />

            {searchResults.length > 0 && (
              <div className="absolute z-10 w-full mt-1 bg-white rounded-lg shadow-lg border border-gray-200 max-h-60 overflow-auto">
                {searchResults.map((fragrance) => (
                  <button
                    key={fragrance.id}
                    type="button"
                    className="w-full px-4 py-3 text-left hover:bg-gray-50 border-b last:border-b-0"
                    onClick={() => handleFragranceSelect(fragrance)}
                  >
                    <div className="font-medium">{fragrance.name}</div>
                    <div className="text-sm text-gray-500">{fragrance.brand}</div>
                  </button>
                ))}
              </div>
            )}
          </div>
          <p className="text-sm text-gray-500 mt-1">
            {selectedFragrance
              ? `Selected: ${selectedFragrance.name} by ${selectedFragrance.brand}`
              : "Type to search existing fragrances, or enter a new one (we'll look it up)"
            }
          </p>
        </div>

        {/* Brand (optional if not selected from search) */}
        {!selectedFragrance && (
          <div>
            <label className="label">Brand (optional)</label>
            <input
              type="text"
              className="input"
              placeholder="e.g., Chanel, Dior, Tom Ford..."
              value={formData.fragranceBrand}
              onChange={(e) => setFormData({ ...formData, fragranceBrand: e.target.value })}
            />
          </div>
        )}

        {/* Reviewer Selection */}
        <div>
          <label className="label">Who's reviewing? *</label>
          <div className="flex flex-wrap gap-2">
            {reviewers.map((reviewer) => (
              <button
                key={reviewer.id}
                type="button"
                className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${
                  formData.reviewerId === reviewer.id.toString()
                    ? 'bg-perfume-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
                onClick={() => setFormData({ ...formData, reviewerId: reviewer.id.toString() })}
              >
                {reviewer.name}
              </button>
            ))}
          </div>
          {reviewers.length === 0 && (
            <p className="text-sm text-amber-600 mt-2">
              No reviewers found. Go to Import → Seed Reviewers to create default family members.
            </p>
          )}
        </div>

        {/* Rating */}
        <div>
          <label className="label">Rating *</label>
          <StarRating
            value={formData.rating}
            onChange={(rating) => setFormData({ ...formData, rating })}
          />
          <p className="text-sm text-gray-500 mt-1">
            {formData.rating === 1 && "Not for me"}
            {formData.rating === 2 && "Didn't like it"}
            {formData.rating === 3 && "It's okay"}
            {formData.rating === 4 && "Really liked it"}
            {formData.rating === 5 && "Love it!"}
          </p>
        </div>

        {/* Notes */}
        <div>
          <label className="label">Notes (optional)</label>
          <textarea
            className="input min-h-[100px]"
            placeholder="Any observations... What did you like or dislike? How did it wear?"
            value={formData.notes}
            onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
          />
        </div>

        {/* Submit */}
        <button
          type="button"
          className="btn btn-primary w-full py-3"
          disabled={!canSubmit || submitMutation.isPending}
          onClick={() => submitMutation.mutate()}
        >
          {submitMutation.isPending ? 'Saving...' : 'Save Evaluation'}
        </button>
      </div>
    </div>
  );
}

export default EvaluatePage;
