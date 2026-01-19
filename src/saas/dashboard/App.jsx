import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom';
import axios from 'axios';
import './App.css';

// API Client
const api = axios.create({
  baseURL: process.env.REACT_APP_API_URL || 'http://localhost:3001',
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ===== AUTH CONTEXT =====

const AuthContext = React.createContext();

function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('auth_token');
    if (token) {
      api.get('/api/auth/me')
        .then(res => setUser(res.data))
        .catch(() => localStorage.removeItem('auth_token'))
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const login = async (email, password) => {
    const res = await api.post('/api/auth/login', { email, password });
    localStorage.setItem('auth_token', res.data.token);
    setUser(res.data.user);
    return res.data;
  };

  const register = async (email, password, name, organization) => {
    const res = await api.post('/api/auth/register', { email, password, name, organization });
    localStorage.setItem('auth_token', res.data.token);
    setUser(res.data.user);
    return res.data;
  };

  const logout = () => {
    localStorage.removeItem('auth_token');
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

function useAuth() {
  return React.useContext(AuthContext);
}

// ===== LOGIN PAGE =====

function LoginPage() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isRegister, setIsRegister] = useState(false);
  const [name, setName] = useState('');
  const [organization, setOrganization] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      if (isRegister) {
        const { register } = useAuth();
        await register(email, password, name, organization);
      } else {
        await login(email, password);
      }
      navigate('/dashboard');
    } catch (err) {
      setError(err.response?.data?.error || 'Authentication failed');
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <h1>🤖 OrbitQA</h1>
        <h2>{isRegister ? 'Create Account' : 'Login'}</h2>

        <form onSubmit={handleSubmit}>
          {isRegister && (
            <>
              <div className="form-group">
                <label>Name</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </div>
              <div className="form-group">
                <label>Organization</label>
                <input
                  type="text"
                  value={organization}
                  onChange={(e) => setOrganization(e.target.value)}
                  required
                />
              </div>
            </>
          )}

          <div className="form-group">
            <label>Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label>Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>

          {error && <div className="error">{error}</div>}

          <button type="submit" className="btn btn-primary">
            {isRegister ? 'Create Account' : 'Login'}
          </button>
        </form>

        <p>
          {isRegister ? 'Already have an account? ' : "Don't have an account? "}
          <a onClick={() => setIsRegister(!isRegister)}>
            {isRegister ? 'Login' : 'Register'}
          </a>
        </p>
      </div>
    </div>
  );
}

// ===== DASHBOARD PAGE =====

function DashboardPage() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [newTestUrl, setNewTestUrl] = useState('');

  useEffect(() => {
    loadTestRuns();
  }, []);

  const loadTestRuns = async () => {
    try {
      const res = await api.get('/api/test-runs?limit=10');
      setRuns(res.data.runs);
    } catch (error) {
      console.error('Failed to load test runs:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleNewTest = async (e) => {
    e.preventDefault();
    try {
      await api.post('/api/test-runs', { url: newTestUrl });
      setNewTestUrl('');
      loadTestRuns();
    } catch (error) {
      alert('Failed to create test: ' + error.response?.data?.error);
    }
  };

  const handleViewResults = (runId) => {
    navigate(`/results/${runId}`);
  };

  const handleDeleteRun = async (runId) => {
    if (window.confirm('Delete this test run?')) {
      try {
        await api.delete(`/api/test-runs/${runId}`);
        loadTestRuns();
      } catch (error) {
        alert('Failed to delete test run');
      }
    }
  };

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <div className="header-left">
          <h1>🤖 OrbitQA Dashboard</h1>
        </div>
        <div className="header-right">
          <span>{user?.name}</span>
          <button className="btn btn-secondary" onClick={() => navigate('/settings')}>
            ⚙️ Settings
          </button>
          <button className="btn btn-secondary" onClick={logout}>
            🚪 Logout
          </button>
        </div>
      </header>

      <main className="dashboard-content">
        <div className="new-test-section">
          <h2>Start New Test</h2>
          <form onSubmit={handleNewTest}>
            <input
              type="url"
              placeholder="Enter website URL (https://example.com)"
              value={newTestUrl}
              onChange={(e) => setNewTestUrl(e.target.value)}
              required
            />
            <button type="submit" className="btn btn-primary">
              🚀 Start Test
            </button>
          </form>
        </div>

        <div className="test-runs-section">
          <h2>Recent Test Runs</h2>
          {loading ? (
            <p>Loading...</p>
          ) : runs.length === 0 ? (
            <p>No test runs yet. Start one above!</p>
          ) : (
            <div className="test-runs-table">
              <table>
                <thead>
                  <tr>
                    <th>URL</th>
                    <th>Status</th>
                    <th>Started</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((run) => (
                    <tr key={run.id}>
                      <td><a href={run.url} target="_blank" rel="noopener noreferrer">{run.url}</a></td>
                      <td>
                        <span className={`badge badge-${run.status}`}>
                          {run.status}
                        </span>
                      </td>
                      <td>{new Date(run.created_at).toLocaleDateString()}</td>
                      <td>
                        <button
                          className="btn btn-small"
                          onClick={() => handleViewResults(run.id)}
                        >
                          📊 View
                        </button>
                        <button
                          className="btn btn-small btn-danger"
                          onClick={() => handleDeleteRun(run.id)}
                        >
                          🗑️
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

// ===== RESULTS PAGE =====

function ResultsPage() {
  const { id } = require('react-router-dom').useParams();
  const navigate = useNavigate();
  const [testRun, setTestRun] = useState(null);
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadResults();
  }, [id]);

  const loadResults = async () => {
    try {
      const [runRes, resultsRes] = await Promise.all([
        api.get(`/api/test-runs/${id}`),
        api.get(`/api/test-runs/${id}/results`),
      ]);
      setTestRun(runRes.data);
      setResults(resultsRes.data);
    } catch (error) {
      console.error('Failed to load results:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div className="dashboard"><p>Loading...</p></div>;

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <button className="btn btn-secondary" onClick={() => navigate('/dashboard')}>
          ← Back
        </button>
        <h1>📊 Test Results</h1>
      </header>

      <main className="dashboard-content">
        {testRun && (
          <>
            <div className="test-info">
              <h2>{testRun.url}</h2>
              <p>Status: <span className={`badge badge-${testRun.status}`}>{testRun.status}</span></p>
              <p>Started: {new Date(testRun.created_at).toLocaleString()}</p>
            </div>

            <div className="results-grid">
              {results.map((result) => (
                <div key={result.id} className="result-card">
                  <h3>🌐 {result.browser}</h3>
                  <div className="result-content">
                    <div className="result-section">
                      <h4>🔴 Issues Found: {result.issues?.length || 0}</h4>
                      <ul>
                        {result.issues?.slice(0, 5).map((issue, i) => (
                          <li key={i}>{issue}</li>
                        ))}
                      </ul>
                    </div>

                    <div className="result-section">
                      <h4>🛠️ Technologies: {result.technologies?.length || 0}</h4>
                      <div className="tech-tags">
                        {result.technologies?.slice(0, 5).map((tech, i) => (
                          <span key={i} className="tag">{tech}</span>
                        ))}
                      </div>
                    </div>

                    <div className="result-section">
                      <h4>⚡ Performance</h4>
                      {result.performance && (
                        <p>Load Time: {result.performance.loadTime}ms</p>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </main>
    </div>
  );
}

// ===== SETTINGS PAGE =====

function SettingsPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [settings, setSettings] = useState(null);
  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [newMemberEmail, setNewMemberEmail] = useState('');
  const [newMemberName, setNewMemberName] = useState('');

  useEffect(() => {
    loadSettings();
    loadMembers();
  }, []);

  const loadSettings = async () => {
    try {
      const res = await api.get('/api/settings');
      setSettings(res.data);
    } catch (error) {
      console.error('Failed to load settings:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadMembers = async () => {
    try {
      const res = await api.get('/api/team/members');
      setMembers(res.data);
    } catch (error) {
      console.error('Failed to load members:', error);
    }
  };

  const handleInviteMember = async (e) => {
    e.preventDefault();
    try {
      await api.post('/api/team/members', {
        email: newMemberEmail,
        name: newMemberName,
      });
      setNewMemberEmail('');
      setNewMemberName('');
      loadMembers();
      alert('Member invited successfully!');
    } catch (error) {
      alert('Failed to invite member: ' + error.response?.data?.error);
    }
  };

  const handleRegenerateKey = async () => {
    if (window.confirm('Regenerate API key? This will invalidate the current key.')) {
      try {
        const res = await api.post('/api/settings/api-key/regenerate');
        setSettings({ ...settings, api_key: res.data.api_key });
        alert('API key regenerated!');
      } catch (error) {
        alert('Failed to regenerate key');
      }
    }
  };

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <button className="btn btn-secondary" onClick={() => navigate('/dashboard')}>
          ← Back
        </button>
        <h1>⚙️ Settings</h1>
      </header>

      <main className="dashboard-content">
        <div className="settings-section">
          <h2>API Key</h2>
          {settings && (
            <>
              <div className="api-key-display">
                <input type="text" value={settings.api_key} readOnly />
                <button onClick={handleRegenerateKey} className="btn btn-secondary">
                  🔄 Regenerate
                </button>
              </div>
            </>
          )}
        </div>

        <div className="settings-section">
          <h2>Team Members</h2>
          {user?.role === 'admin' || user?.role === 'owner' ? (
            <>
              <form onSubmit={handleInviteMember}>
                <div className="form-group">
                  <label>Invite Member</label>
                  <input
                    type="email"
                    placeholder="Email"
                    value={newMemberEmail}
                    onChange={(e) => setNewMemberEmail(e.target.value)}
                    required
                  />
                  <input
                    type="text"
                    placeholder="Name"
                    value={newMemberName}
                    onChange={(e) => setNewMemberName(e.target.value)}
                    required
                  />
                  <button type="submit" className="btn btn-primary">
                    👤 Invite
                  </button>
                </div>
              </form>

              <div className="members-list">
                {members.map((member) => (
                  <div key={member.id} className="member-item">
                    <span>{member.name} ({member.email})</span>
                    <span className="badge">{member.role}</span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <p>Only admins can manage team members</p>
          )}
        </div>
      </main>
    </div>
  );
}

// ===== PROTECTED ROUTE =====

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();

  if (loading) return <div>Loading...</div>;
  if (!user) return <Navigate to="/login" />;

  return children;
}

// ===== MAIN APP =====

function App() {
  const { loading } = useAuth();

  if (loading) return <div className="loading">Loading...</div>;

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <DashboardPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/results/:id"
          element={
            <ProtectedRoute>
              <ResultsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/settings"
          element={
            <ProtectedRoute>
              <SettingsPage />
            </ProtectedRoute>
          }
        />
        <Route path="/" element={<Navigate to="/dashboard" />} />
      </Routes>
    </BrowserRouter>
  );
}

export default function Root() {
  return (
    <AuthProvider>
      <App />
    </AuthProvider>
  );
}
