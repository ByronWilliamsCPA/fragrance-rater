import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { importApi, recommendationApi, fragranceApi } from '../services/api';

function ImportPage() {
  const queryClient = useQueryClient();
  const [uploadStatus, setUploadStatus] = useState(null);

  // Get status info
  const { data: fragellaStatus } = useQuery({
    queryKey: ['fragella-status'],
    queryFn: () => importApi.fragellaStatus().then(r => r.data),
  });

  const { data: llmStatus } = useQuery({
    queryKey: ['llm-status'],
    queryFn: () => recommendationApi.getStatus().then(r => r.data),
  });

  const { data: fragranceCount } = useQuery({
    queryKey: ['fragrance-count'],
    queryFn: () => fragranceApi.list({ limit: 1 }).then(r => r.data.length),
  });

  // Mutations
  const seedReviewersMutation = useMutation({
    mutationFn: () => importApi.seedReviewers(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reviewers'] });
    },
  });

  const uploadMutation = useMutation({
    mutationFn: (file) => importApi.uploadKaggle(file),
    onSuccess: (response) => {
      setUploadStatus({
        type: 'success',
        data: response.data,
      });
      queryClient.invalidateQueries({ queryKey: ['fragrances'] });
      queryClient.invalidateQueries({ queryKey: ['fragrance-count'] });
    },
    onError: (error) => {
      setUploadStatus({
        type: 'error',
        message: error.response?.data?.detail || 'Upload failed',
      });
    },
  });

  const handleFileUpload = (event) => {
    const file = event.target.files[0];
    if (file) {
      setUploadStatus(null);
      uploadMutation.mutate(file);
    }
  };

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-3xl font-bold text-gray-900 mb-8">Data Management</h1>

      {/* Status Cards */}
      <div className="grid md:grid-cols-3 gap-4 mb-8">
        <div className="card">
          <h3 className="text-sm font-medium text-gray-500">Fragrances in Database</h3>
          <p className="text-2xl font-bold text-perfume-600 mt-1">
            {fragranceCount ?? '...'}
          </p>
        </div>

        <div className="card">
          <h3 className="text-sm font-medium text-gray-500">Fragella API</h3>
          <p className="text-2xl font-bold mt-1">
            {fragellaStatus?.configured ? (
              <span className="text-green-600">
                {fragellaStatus.requests_remaining}/{fragellaStatus.monthly_limit}
              </span>
            ) : (
              <span className="text-gray-400">Not configured</span>
            )}
          </p>
          <p className="text-xs text-gray-400">requests remaining</p>
        </div>

        <div className="card">
          <h3 className="text-sm font-medium text-gray-500">LLM Recommendations</h3>
          <p className="text-2xl font-bold mt-1">
            {llmStatus?.configured ? (
              <span className="text-green-600">Active</span>
            ) : (
              <span className="text-gray-400">Not configured</span>
            )}
          </p>
          {llmStatus?.configured && (
            <p className="text-xs text-gray-400">{llmStatus.model}</p>
          )}
        </div>
      </div>

      {/* Seed Reviewers */}
      <div className="card mb-6">
        <h2 className="text-xl font-semibold mb-4">Family Members</h2>
        <p className="text-gray-600 mb-4">
          Create the default family member accounts: Byron, Veronica, Bayden, and Ariannah.
        </p>

        <button
          onClick={() => seedReviewersMutation.mutate()}
          disabled={seedReviewersMutation.isPending}
          className="btn btn-primary"
        >
          {seedReviewersMutation.isPending ? 'Creating...' : 'Create Family Reviewers'}
        </button>

        {seedReviewersMutation.isSuccess && (
          <p className="mt-3 text-green-600">
            ✓ Reviewers created: {seedReviewersMutation.data.data.all_reviewers.join(', ')}
          </p>
        )}
      </div>

      {/* Kaggle Import */}
      <div className="card mb-6">
        <h2 className="text-xl font-semibold mb-4">Import Kaggle Dataset</h2>
        <p className="text-gray-600 mb-4">
          Upload a CSV file from Kaggle fragrance datasets. The importer handles various
          column formats automatically.
        </p>

        <div className="mb-4">
          <h3 className="font-medium text-gray-700 mb-2">Recommended Datasets:</h3>
          <ul className="text-sm text-gray-600 space-y-1">
            <li>
              <a
                href="https://www.kaggle.com/datasets/olgagmiufana1/fragrantica-com-fragrance-dataset"
                target="_blank"
                rel="noopener noreferrer"
                className="text-perfume-600 hover:underline"
              >
                Fragrantica.com Fragrance Dataset
              </a>
            </li>
            <li>
              <a
                href="https://www.kaggle.com/datasets/nandini1999/perfume-recommendation-dataset"
                target="_blank"
                rel="noopener noreferrer"
                className="text-perfume-600 hover:underline"
              >
                Perfume Recommendation Dataset
              </a>
            </li>
          </ul>
        </div>

        <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center">
          <input
            type="file"
            accept=".csv"
            onChange={handleFileUpload}
            className="hidden"
            id="csv-upload"
            disabled={uploadMutation.isPending}
          />
          <label
            htmlFor="csv-upload"
            className={`cursor-pointer ${uploadMutation.isPending ? 'opacity-50' : ''}`}
          >
            <div className="text-4xl mb-2">📁</div>
            <p className="text-gray-600">
              {uploadMutation.isPending ? 'Uploading...' : 'Click to upload CSV file'}
            </p>
          </label>
        </div>

        {uploadStatus?.type === 'success' && (
          <div className="mt-4 p-4 bg-green-50 rounded-lg">
            <h4 className="font-medium text-green-800">Import Complete</h4>
            <ul className="text-sm text-green-700 mt-2">
              <li>Total records: {uploadStatus.data.total_records}</li>
              <li>Imported: {uploadStatus.data.imported}</li>
              <li>Skipped (duplicates): {uploadStatus.data.skipped}</li>
              {uploadStatus.data.errors > 0 && (
                <li className="text-amber-600">Errors: {uploadStatus.data.errors}</li>
              )}
            </ul>
          </div>
        )}

        {uploadStatus?.type === 'error' && (
          <div className="mt-4 p-4 bg-red-50 rounded-lg">
            <p className="text-red-700">{uploadStatus.message}</p>
          </div>
        )}
      </div>

      {/* Data Sources Explanation */}
      <div className="card">
        <h2 className="text-xl font-semibold mb-4">Data Source Priority</h2>
        <p className="text-gray-600 mb-4">
          When you search for a fragrance, the system checks sources in this order:
        </p>

        <ol className="space-y-3">
          <li className="flex items-start">
            <span className="flex-shrink-0 w-6 h-6 bg-perfume-100 text-perfume-700 rounded-full flex items-center justify-center text-sm font-medium mr-3">1</span>
            <div>
              <span className="font-medium">Local Database</span>
              <p className="text-sm text-gray-500">Previously imported or manually entered fragrances</p>
            </div>
          </li>

          <li className="flex items-start">
            <span className="flex-shrink-0 w-6 h-6 bg-perfume-100 text-perfume-700 rounded-full flex items-center justify-center text-sm font-medium mr-3">2</span>
            <div>
              <span className="font-medium">Fragella API</span>
              <p className="text-sm text-gray-500">
                High-quality structured data (20 requests/month free tier)
                {fragellaStatus?.configured && (
                  <span className="text-green-600 ml-2">✓ Configured</span>
                )}
              </p>
            </div>
          </li>

          <li className="flex items-start">
            <span className="flex-shrink-0 w-6 h-6 bg-perfume-100 text-perfume-700 rounded-full flex items-center justify-center text-sm font-medium mr-3">3</span>
            <div>
              <span className="font-medium">Fragrantica Scraper</span>
              <p className="text-sm text-gray-500">Fallback web scraping when APIs unavailable</p>
            </div>
          </li>

          <li className="flex items-start">
            <span className="flex-shrink-0 w-6 h-6 bg-perfume-100 text-perfume-700 rounded-full flex items-center justify-center text-sm font-medium mr-3">4</span>
            <div>
              <span className="font-medium">Manual Entry</span>
              <p className="text-sm text-gray-500">Add fragrances yourself if not found</p>
            </div>
          </li>
        </ol>

        <div className="mt-6 p-4 bg-blue-50 rounded-lg">
          <h4 className="font-medium text-blue-800">API Configuration</h4>
          <p className="text-sm text-blue-700 mt-1">
            Set <code className="bg-blue-100 px-1 rounded">FRAGELLA_API_KEY</code> and{' '}
            <code className="bg-blue-100 px-1 rounded">OPENROUTER_API_KEY</code> in your
            environment variables to enable external data fetching and AI recommendations.
          </p>
        </div>
      </div>
    </div>
  );
}

export default ImportPage;
