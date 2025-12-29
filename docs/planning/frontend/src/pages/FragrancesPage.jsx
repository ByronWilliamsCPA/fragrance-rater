import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { fragranceApi } from '../services/api';

function FragrancesPage() {
  const [search, setSearch] = useState('');
  const [filters, setFilters] = useState({
    family: '',
    gender: '',
  });

  const { data: fragrances = [], isLoading } = useQuery({
    queryKey: ['fragrances', search, filters],
    queryFn: () => fragranceApi.list({
      query: search || undefined,
      family: filters.family || undefined,
      gender: filters.gender || undefined,
      limit: 100,
    }).then(r => r.data),
  });

  const families = ['fresh', 'floral', 'amber', 'woody'];
  const genders = ['feminine', 'masculine', 'unisex'];

  return (
    <div>
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Fragrances</h1>
        <Link to="/evaluate" className="btn btn-primary">
          + Add Evaluation
        </Link>
      </div>

      {/* Search and Filters */}
      <div className="card mb-6">
        <div className="flex flex-wrap gap-4">
          <div className="flex-1 min-w-[200px]">
            <input
              type="text"
              className="input"
              placeholder="Search by name or brand..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>

          <select
            className="input w-auto"
            value={filters.family}
            onChange={(e) => setFilters({ ...filters, family: e.target.value })}
          >
            <option value="">All Families</option>
            {families.map(f => (
              <option key={f} value={f}>{f.charAt(0).toUpperCase() + f.slice(1)}</option>
            ))}
          </select>

          <select
            className="input w-auto"
            value={filters.gender}
            onChange={(e) => setFilters({ ...filters, gender: e.target.value })}
          >
            <option value="">All Genders</option>
            {genders.map(g => (
              <option key={g} value={g}>{g.charAt(0).toUpperCase() + g.slice(1)}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Results */}
      {isLoading ? (
        <div className="text-center py-8 text-gray-500">Loading...</div>
      ) : fragrances.length === 0 ? (
        <div className="card text-center py-8">
          <p className="text-gray-500 mb-4">
            {search || filters.family || filters.gender
              ? 'No fragrances match your search.'
              : 'No fragrances in database yet.'
            }
          </p>
          <Link to="/import" className="btn btn-secondary">
            Import Fragrances
          </Link>
        </div>
      ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {fragrances.map(fragrance => (
            <Link
              key={fragrance.id}
              to={`/fragrances/${fragrance.id}`}
              className="card hover:shadow-md transition-shadow"
            >
              <div className="flex items-start space-x-4">
                {fragrance.image_url ? (
                  <img
                    src={fragrance.image_url}
                    alt={fragrance.name}
                    className="w-16 h-16 object-cover rounded"
                  />
                ) : (
                  <div className="w-16 h-16 bg-gray-100 rounded flex items-center justify-center text-2xl">
                    🌸
                  </div>
                )}

                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-gray-900 truncate">
                    {fragrance.name}
                  </h3>
                  <p className="text-sm text-gray-500">{fragrance.brand}</p>

                  <div className="flex flex-wrap gap-1 mt-2">
                    {fragrance.primary_family && (
                      <span className="px-2 py-0.5 bg-perfume-100 text-perfume-700 rounded text-xs">
                        {fragrance.primary_family}
                      </span>
                    )}
                    {fragrance.gender_target && (
                      <span className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-xs">
                        {fragrance.gender_target}
                      </span>
                    )}
                  </div>

                  {fragrance.rating && (
                    <div className="flex items-center mt-2 text-sm">
                      <span className="text-yellow-400">★</span>
                      <span className="ml-1 text-gray-600">{fragrance.rating.toFixed(1)}</span>
                    </div>
                  )}
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

export default FragrancesPage;
