import { Routes, Route, Link, useLocation } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { reviewerApi } from './services/api';

// Pages
import HomePage from './pages/HomePage';
import EvaluatePage from './pages/EvaluatePage';
import FragrancesPage from './pages/FragrancesPage';
import FragranceDetailPage from './pages/FragranceDetailPage';
import ReviewerPage from './pages/ReviewerPage';
import ImportPage from './pages/ImportPage';

function Navigation() {
  const location = useLocation();

  const navItems = [
    { path: '/', label: 'Home' },
    { path: '/evaluate', label: 'Evaluate' },
    { path: '/fragrances', label: 'Fragrances' },
    { path: '/import', label: 'Import' },
  ];

  return (
    <nav className="bg-white shadow-sm border-b">
      <div className="max-w-6xl mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          <Link to="/" className="text-xl font-bold text-perfume-600">
            🌸 Fragrance Tracker
          </Link>

          <div className="flex space-x-1">
            {navItems.map(({ path, label }) => (
              <Link
                key={path}
                to={path}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  location.pathname === path
                    ? 'bg-perfume-100 text-perfume-700'
                    : 'text-gray-600 hover:bg-gray-100'
                }`}
              >
                {label}
              </Link>
            ))}
          </div>
        </div>
      </div>
    </nav>
  );
}

function App() {
  // Prefetch reviewers
  useQuery({
    queryKey: ['reviewers'],
    queryFn: () => reviewerApi.list().then(r => r.data),
  });

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />

      <main className="max-w-6xl mx-auto px-4 py-8">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/evaluate" element={<EvaluatePage />} />
          <Route path="/fragrances" element={<FragrancesPage />} />
          <Route path="/fragrances/:id" element={<FragranceDetailPage />} />
          <Route path="/reviewer/:id" element={<ReviewerPage />} />
          <Route path="/import" element={<ImportPage />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
