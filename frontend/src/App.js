import React, { useState, useEffect } from 'react';
import './App.css';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Main App Component
function App() {
  const [currentView, setCurrentView] = useState('home');
  const [authToken, setAuthToken] = useState(localStorage.getItem('authToken'));
  const [organization, setOrganization] = useState(null);

  useEffect(() => {
    if (authToken) {
      fetchOrganization();
    }
  }, [authToken]);

  const fetchOrganization = async () => {
    try {
      const response = await axios.get(`${API}/organizations/me`, {
        headers: { Authorization: `Bearer ${authToken}` }
      });
      if (response.data) {
        setOrganization(response.data);
      }
    } catch (error) {
      console.error('Failed to fetch organization:', error);
      localStorage.removeItem('authToken');
      setAuthToken(null);
      setOrganization(null);
    }
  };

  const handleLogin = (token, org) => {
    setAuthToken(token);
    setOrganization(org);
    localStorage.setItem('authToken', token);
    setCurrentView('dashboard');
  };

  const handleLogout = () => {
    setAuthToken(null);
    setOrganization(null);
    localStorage.removeItem('authToken');
    setCurrentView('home');
  };

  if (!authToken) {
    return <AuthPage onLogin={handleLogin} />;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <DashboardHeader 
        organization={organization} 
        onLogout={handleLogout}
        currentView={currentView}
        setCurrentView={setCurrentView}
      />
      <main className="max-w-6xl mx-auto px-4 py-8">
        {currentView === 'dashboard' && (
          <Dashboard organization={organization} authToken={authToken} />
        )}
        {currentView === 'form-settings' && (
          <FormSettings organization={organization} authToken={authToken} onUpdate={fetchOrganization} />
        )}
        {currentView === 'bbms-config' && (
          <BBMSConfig organization={organization} authToken={authToken} onUpdate={fetchOrganization} />
        )}
        {currentView === 'mode-settings' && (
          <ModeSettings organization={organization} authToken={authToken} onUpdate={fetchOrganization} />
        )}
        {currentView === 'embed-code' && (
          <EmbedCode organization={organization} />
        )}
        {currentView === 'transactions' && (
          <Transactions organization={organization} authToken={authToken} />
        )}
      </main>
    </div>
  );
}

// Authentication Page
const AuthPage = ({ onLogin }) => {
  const [isLogin, setIsLogin] = useState(true);
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: ''
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      // Validate form data
      if (!formData.email?.trim() || !formData.password?.trim()) {
        throw new Error('Email and password are required');
      }

      if (!isLogin && !formData.name?.trim()) {
        throw new Error('Organization name is required');
      }

      if (formData.password.length < 6) {
        throw new Error('Password must be at least 6 characters long');
      }

      const endpoint = isLogin ? '/organizations/login' : '/organizations/register';
      const payload = isLogin ? 
        { email: formData.email.trim(), password: formData.password } :
        { 
          name: formData.name.trim(), 
          admin_email: formData.email.trim(), 
          admin_password: formData.password 
        };

      console.log('Sending request to:', `${API}${endpoint}`);
      console.log('Payload:', { ...payload, admin_password: '[HIDDEN]', password: '[HIDDEN]' });

      const response = await axios.post(`${API}${endpoint}`, payload);
      
      if (response.data && response.data.access_token && response.data.organization) {
        onLogin(response.data.access_token, response.data.organization);
      } else {
        throw new Error('Invalid response from server');
      }
    } catch (error) {
      console.error('Authentication error:', error);
      const errorMessage = error.response?.data?.detail || error.message || 'Authentication failed';
      setError(typeof errorMessage === 'string' ? errorMessage : 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-xl p-8 w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-800">Donation Builder</h1>
          <p className="text-gray-600 mt-2">Create beautiful donation pages for your organization</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {!isLogin && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Organization Name</label>
              <input
                type="text"
                required
                value={formData.name}
                onChange={(e) => setFormData({...formData, name: e.target.value})}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Your Organization"
              />
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Admin Email</label>
            <input
              type="email"
              required
              value={formData.email}
              onChange={(e) => setFormData({...formData, email: e.target.value})}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="admin@organization.com"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Password</label>
            <input
              type="password"
              required
              value={formData.password}
              onChange={(e) => setFormData({...formData, password: e.target.value})}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Password"
            />
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 text-white font-medium py-2 px-4 rounded-md hover:bg-blue-700 disabled:bg-gray-400"
          >
            {loading ? 'Processing...' : (isLogin ? 'Sign In' : 'Create Account')}
          </button>
        </form>

        <div className="mt-6 text-center">
          <button
            onClick={() => setIsLogin(!isLogin)}
            className="text-blue-600 hover:text-blue-800 text-sm"
          >
            {isLogin ? 'Need an account? Sign up' : 'Already have an account? Sign in'}
          </button>
        </div>
      </div>
    </div>
  );
};

// Dashboard Header
const DashboardHeader = ({ organization, onLogout, currentView, setCurrentView }) => {
  const navigation = [
    { id: 'dashboard', label: 'Dashboard', icon: '📊' },
    { id: 'form-settings', label: 'Form Settings', icon: '⚙️' },
    { id: 'bbms-config', label: 'Payment Setup', icon: '💳' },
    { id: 'mode-settings', label: 'Mode Settings', icon: '🔧' },
    { id: 'embed-code', label: 'Embed Code', icon: '🔗' },
    { id: 'transactions', label: 'Transactions', icon: '📈' }
  ];

  return (
    <header className="bg-white shadow-sm border-b">
      <div className="max-w-6xl mx-auto px-4">
        <div className="flex justify-between items-center py-4">
          <div className="flex items-center space-x-4">
            <h1 className="text-xl font-bold text-gray-800">
              {organization?.name || 'Donation Builder'}
            </h1>
          </div>
          
      <div className="flex items-center space-x-6">
            <div className={`px-3 py-1 rounded-full text-sm font-medium ${
              organization?.test_mode 
                ? 'bg-yellow-100 text-yellow-800' 
                : 'bg-green-100 text-green-800'
            }`}>
              {organization?.test_mode ? '🧪 Test Mode' : '🚀 Live Mode'}
            </div>
            <nav className="flex space-x-1">
              {navigation.map(item => (
                <button
                  key={item.id}
                  onClick={() => setCurrentView(item.id)}
                  className={`px-3 py-2 rounded-md text-sm font-medium ${
                    currentView === item.id
                      ? 'bg-blue-100 text-blue-700'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                  }`}
                >
                  {item.icon} {item.label}
                </button>
              ))}
            </nav>
            
            <button
              onClick={onLogout}
              className="text-gray-600 hover:text-gray-900 text-sm"
            >
              Sign Out
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};

// Dashboard Component
const Dashboard = ({ organization, authToken }) => {
  const [stats, setStats] = useState({ total_donations: 0, total_amount: 0, recent_count: 0 });

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const response = await axios.get(`${API}/organizations/${organization.id}/transactions`, {
        headers: { Authorization: `Bearer ${authToken}` }
      });
      
      const transactions = response.data;
      const total_amount = transactions.reduce((sum, t) => sum + (t.status === 'completed' ? t.amount : 0), 0);
      const recent_count = transactions.filter(t => {
        const dayAgo = new Date(Date.now() - 24 * 60 * 60 * 1000);
        return new Date(t.created_at) > dayAgo;
      }).length;

      setStats({
        total_donations: transactions.filter(t => t.status === 'completed').length,
        total_amount,
        recent_count
      });
    } catch (error) {
      console.error('Failed to fetch stats:', error);
    }
  };

  const statusColor = organization?.has_bbms_configured ? 'text-green-600' : 'text-orange-600';
  const statusText = organization?.has_bbms_configured ? 'Active' : 'Setup Required';

  return (
    <div className="space-y-8">
      <div className="flex justify-between items-start">
        <div>
          <h2 className="text-2xl font-bold text-gray-800">Dashboard</h2>
          <p className="text-gray-600 mt-1">Overview of your donation campaigns</p>
        </div>
        <div className={`px-3 py-1 rounded-full text-sm font-medium ${statusColor} bg-gray-100`}>
          {statusText}
        </div>
      </div>

      {!organization?.has_bbms_configured && (
        <div className="bg-orange-50 border border-orange-200 rounded-lg p-6">
          <div className="flex items-start">
            <div className="text-orange-500 text-2xl mr-3">⚠️</div>
            <div>
              <h3 className="text-lg font-medium text-orange-800">Payment Setup Required</h3>
              <p className="text-orange-700 mt-1">
                Configure your Blackbaud BBMS credentials to start accepting donations.
              </p>
              <button className="mt-3 bg-orange-600 text-white px-4 py-2 rounded-md hover:bg-orange-700">
                Setup Payment Processing
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white p-6 rounded-lg shadow-sm border">
          <div className="flex items-center">
            <div className="text-blue-500 text-2xl mr-3">💰</div>
            <div>
              <p className="text-sm font-medium text-gray-600">Total Raised</p>
              <p className="text-2xl font-bold text-gray-900">${stats.total_amount.toFixed(2)}</p>
            </div>
          </div>
        </div>

        <div className="bg-white p-6 rounded-lg shadow-sm border">
          <div className="flex items-center">
            <div className="text-green-500 text-2xl mr-3">🎯</div>
            <div>
              <p className="text-sm font-medium text-gray-600">Total Donations</p>
              <p className="text-2xl font-bold text-gray-900">{stats.total_donations}</p>
            </div>
          </div>
        </div>

        <div className="bg-white p-6 rounded-lg shadow-sm border">
          <div className="flex items-center">
            <div className="text-purple-500 text-2xl mr-3">📈</div>
            <div>
              <p className="text-sm font-medium text-gray-600">Recent (24h)</p>
              <p className="text-2xl font-bold text-gray-900">{stats.recent_count}</p>
            </div>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow-sm border p-6">
        <h3 className="text-lg font-medium text-gray-800 mb-4">Quick Actions</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <button className="p-4 border rounded-lg hover:bg-gray-50 text-left">
            <div className="text-2xl mb-2">⚙️</div>
            <div className="font-medium">Customize Form</div>
            <div className="text-sm text-gray-600">Update donation amounts and fields</div>
          </button>
          
          <button className="p-4 border rounded-lg hover:bg-gray-50 text-left">
            <div className="text-2xl mb-2">🔗</div>
            <div className="font-medium">Get Embed Code</div>
            <div className="text-sm text-gray-600">Add donation form to your website</div>
          </button>
          
          <button className="p-4 border rounded-lg hover:bg-gray-50 text-left">
            <div className="text-2xl mb-2">📊</div>
            <div className="font-medium">View Reports</div>
            <div className="text-sm text-gray-600">Analyze donation trends</div>
          </button>
          
          <button className="p-4 border rounded-lg hover:bg-gray-50 text-left">
            <div className="text-2xl mb-2">💳</div>
            <div className="font-medium">Payment Settings</div>
            <div className="text-sm text-gray-600">Configure BBMS credentials</div>
          </button>
        </div>
      </div>
    </div>
  );
};

// Form Settings Component
const FormSettings = ({ organization, authToken, onUpdate }) => {
  const [settings, setSettings] = useState(organization?.form_settings || {});
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      await axios.put(`${API}/organizations/form-settings`, settings, {
        headers: { Authorization: `Bearer ${authToken}` }
      });
      setSuccess(true);
      onUpdate();
      setTimeout(() => setSuccess(false), 3000);
    } catch (error) {
      console.error('Failed to update settings:', error);
    } finally {
      setLoading(false);
    }
  };

  const addPresetAmount = () => {
    const newAmount = prompt('Enter donation amount:');
    if (newAmount && !isNaN(newAmount)) {
      setSettings({
        ...settings,
        preset_amounts: [...(settings.preset_amounts || []), parseInt(newAmount)]
      });
    }
  };

  const removePresetAmount = (index) => {
    const amounts = [...settings.preset_amounts];
    amounts.splice(index, 1);
    setSettings({ ...settings, preset_amounts: amounts });
  };

  return (
    <div className="max-w-2xl">
      <h2 className="text-2xl font-bold text-gray-800 mb-6">Form Settings</h2>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="bg-white rounded-lg shadow-sm border p-6">
          <h3 className="text-lg font-medium text-gray-800 mb-4">Organization Information</h3>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Organization Description
              </label>
              <textarea
                value={settings.organization_description || ''}
                onChange={(e) => setSettings({...settings, organization_description: e.target.value})}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                rows={3}
                placeholder="Tell donors about your organization..."
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Thank You Message
              </label>
              <textarea
                value={settings.thank_you_message || ''}
                onChange={(e) => setSettings({...settings, thank_you_message: e.target.value})}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                rows={2}
                placeholder="Thank you message after successful donation..."
              />
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-sm border p-6">
          <h3 className="text-lg font-medium text-gray-800 mb-4">Donation Amounts</h3>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Preset Amounts
              </label>
              <div className="flex flex-wrap gap-2 mb-3">
                {(settings.preset_amounts || []).map((amount, index) => (
                  <div key={index} className="flex items-center bg-gray-100 rounded-lg px-3 py-1">
                    <span className="text-sm font-medium">${amount}</span>
                    <button
                      type="button"
                      onClick={() => removePresetAmount(index)}
                      className="ml-2 text-red-500 hover:text-red-700"
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
              <button
                type="button"
                onClick={addPresetAmount}
                className="text-blue-600 hover:text-blue-800 text-sm font-medium"
              >
                + Add Amount
              </button>
            </div>

            <div className="flex items-center">
              <input
                type="checkbox"
                id="custom-amount"
                checked={settings.custom_amount_enabled || false}
                onChange={(e) => setSettings({...settings, custom_amount_enabled: e.target.checked})}
                className="mr-2"
              />
              <label htmlFor="custom-amount" className="text-sm font-medium text-gray-700">
                Allow custom donation amounts
              </label>
            </div>
          </div>
        </div>

        {success && (
          <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-md">
            Settings updated successfully!
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="bg-blue-600 text-white font-medium py-2 px-6 rounded-md hover:bg-blue-700 disabled:bg-gray-400"
        >
          {loading ? 'Saving...' : 'Save Settings'}
        </button>
      </form>
    </div>
  );
};

// BBMS Configuration Component
const BBMSConfig = ({ organization, authToken, onUpdate }) => {
  const [credentials, setCredentials] = useState({
    merchant_id: '',
    access_token: ''
  });
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      await axios.post(`${API}/organizations/configure-bbms`, credentials, {
        headers: { Authorization: `Bearer ${authToken}` }
      });
      setSuccess(true);
      onUpdate();
      setCredentials({ merchant_id: '', access_token: '' });
      setTimeout(() => setSuccess(false), 3000);
    } catch (error) {
      setError(error.response?.data?.detail || 'Failed to configure BBMS');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl">
      <h2 className="text-2xl font-bold text-gray-800 mb-6">Payment Setup</h2>

      <div className="bg-white rounded-lg shadow-sm border p-6">
        <h3 className="text-lg font-medium text-gray-800 mb-4">Blackbaud BBMS Configuration</h3>
        
        <div className={`border rounded-md mb-4 px-4 py-3 ${
          organization?.test_mode 
            ? 'bg-yellow-50 border-yellow-200 text-yellow-700' 
            : 'bg-green-50 border-green-200 text-green-700'
        }`}>
          {organization?.test_mode ? '🧪' : '🚀'} <strong>
            {organization?.test_mode ? 'Test Mode Active:' : 'Production Mode Active:'}
          </strong> {organization?.test_mode 
            ? 'All payments will be processed in Blackbaud\'s sandbox environment. No real money will be charged.'
            : 'Payments will be processed with real money. Ensure you have valid production credentials.'
          }
        </div>
        
        {organization?.has_bbms_configured && (
          <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-md mb-6">
            ✅ BBMS is configured and ready to accept donations
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Merchant Account ID
            </label>
            <input
              type="text"
              required
              value={credentials.merchant_id}
              onChange={(e) => setCredentials({...credentials, merchant_id: e.target.value})}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Your BBMS Merchant Account ID"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Access Token
            </label>
            <input
              type="password"
              required
              value={credentials.access_token}
              onChange={(e) => setCredentials({...credentials, access_token: e.target.value})}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Your Blackbaud Access Token"
            />
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md">
              {error}
            </div>
          )}

          {success && (
            <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-md">
              BBMS credentials configured successfully!
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="bg-blue-600 text-white font-medium py-2 px-6 rounded-md hover:bg-blue-700 disabled:bg-gray-400"
          >
            {loading ? 'Configuring...' : 'Configure BBMS'}
          </button>
        </form>

        <div className="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-md">
          <h4 className="font-medium text-blue-800 mb-2">📋 How to get your Blackbaud credentials:</h4>
          
          <div className="space-y-4 text-sm text-blue-700">
            <div>
              <p className="font-medium mb-2">Step 1: Create Blackbaud Developer Account</p>
              <ol className="list-decimal list-inside space-y-1 ml-4">
                <li>Go to <a href="https://developer.sky.blackbaud.com" target="_blank" rel="noopener noreferrer" className="text-blue-600 underline">developer.sky.blackbaud.com</a></li>
                <li>Sign in with your Blackbaud account or create one</li>
                <li>Complete the developer registration process</li>
              </ol>
            </div>
            
            <div>
              <p className="font-medium mb-2">Step 2: Create Application</p>
              <ol className="list-decimal list-inside space-y-1 ml-4">
                <li>Click "My Applications" in the developer portal</li>
                <li>Click "Create Application" or "Add Application"</li>
                <li>Fill in application details (name, description, etc.)</li>
                <li>Enable <strong>Payments API</strong> in the API access section</li>
                <li>Set redirect URI to: <code className="bg-blue-100 px-1 rounded">https://localhost</code></li>
                <li>Save your application</li>
              </ol>
            </div>
            
            <div>
              <p className="font-medium mb-2">Step 3: Get Application Credentials</p>
              <ol className="list-decimal list-inside space-y-1 ml-4">
                <li>In your application settings, find your <strong>Application ID</strong></li>
                <li>Note down your <strong>Application Secret</strong></li>
                <li>These are your OAuth2 credentials</li>
              </ol>
            </div>
            
            <div>
              <p className="font-medium mb-2">Step 4: Get Access Token (Manual Method)</p>
              <ol className="list-decimal list-inside space-y-1 ml-4">
                <li>Go to the "Authorization" section in your application</li>
                <li>Click "Authorize Application" or use the OAuth2 flow</li>
                <li>This will redirect you and provide an authorization code</li>
                <li>Exchange the code for an access token using the OAuth2 token endpoint</li>
              </ol>
            </div>
            
            <div>
              <p className="font-medium mb-2">Step 5: Get Merchant Account ID</p>
              <ol className="list-decimal list-inside space-y-1 ml-4">
                <li>Log into your Blackbaud BBMS merchant portal</li>
                <li>Navigate to Account Settings or Configuration</li>
                <li>Find your Merchant Account ID (usually starts with "BBMS")</li>
              </ol>
            </div>
            
            <div className="bg-yellow-50 border border-yellow-200 rounded p-3 mt-4">
              <p className="font-medium text-yellow-800">⚠️ Note:</p>
              <p className="text-yellow-700">
                Getting an access token manually is complex. For a production application, 
                we recommend implementing the full OAuth2 flow. Contact us if you need help 
                with the OAuth2 integration.
              </p>
            </div>
            
            <div className="bg-green-50 border border-green-200 rounded p-3 mt-4">
              <p className="font-medium text-green-800">💡 Alternative:</p>
              <p className="text-green-700">
                If you're having trouble with the manual token process, you can start in 
                Test Mode with dummy credentials to explore the platform, then get proper 
                credentials when you're ready to go live.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// Mode Settings Component
const ModeSettings = ({ organization, authToken, onUpdate }) => {
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [pendingMode, setPendingMode] = useState(null);

  const handleModeToggle = async (newTestMode) => {
    // If switching to production, show confirmation
    if (!newTestMode && organization?.test_mode) {
      setPendingMode(newTestMode);
      setShowConfirm(true);
      return;
    }
    
    // If switching to test mode, proceed directly
    await updateMode(newTestMode);
  };

  const updateMode = async (testMode) => {
    setLoading(true);

    try {
      await axios.put(`${API}/organizations/test-mode`, 
        { test_mode: testMode }, 
        { headers: { Authorization: `Bearer ${authToken}` } }
      );
      setSuccess(true);
      onUpdate();
      setShowConfirm(false);
      setPendingMode(null);
      setTimeout(() => setSuccess(false), 3000);
    } catch (error) {
      console.error('Failed to update mode:', error);
    } finally {
      setLoading(false);
    }
  };

  const confirmModeChange = () => {
    updateMode(pendingMode);
  };

  const cancelModeChange = () => {
    setShowConfirm(false);
    setPendingMode(null);
  };

  return (
    <div className="max-w-2xl">
      <h2 className="text-2xl font-bold text-gray-800 mb-6">Mode Settings</h2>

      <div className="bg-white rounded-lg shadow-sm border p-6">
        <h3 className="text-lg font-medium text-gray-800 mb-4">Payment Processing Mode</h3>
        
        <div className="space-y-6">
          {/* Current Mode Display */}
          <div className={`border rounded-lg p-4 ${
            organization?.test_mode 
              ? 'bg-yellow-50 border-yellow-200' 
              : 'bg-green-50 border-green-200'
          }`}>
            <div className="flex items-center justify-between">
              <div>
                <h4 className={`font-medium ${
                  organization?.test_mode ? 'text-yellow-800' : 'text-green-800'
                }`}>
                  {organization?.test_mode ? '🧪 Test Mode' : '🚀 Production Mode'}
                </h4>
                <p className={`text-sm mt-1 ${
                  organization?.test_mode ? 'text-yellow-700' : 'text-green-700'
                }`}>
                  {organization?.test_mode 
                    ? 'Safe testing environment - no real payments processed'
                    : 'Live environment - real payments will be processed'
                  }
                </p>
              </div>
              <div className={`text-2xl ${
                organization?.test_mode ? 'text-yellow-600' : 'text-green-600'
              }`}>
                {organization?.test_mode ? '🧪' : '🚀'}
              </div>
            </div>
          </div>

          {/* Mode Options */}
          <div className="space-y-4">
            <h4 className="font-medium text-gray-800">Switch Mode:</h4>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Test Mode Option */}
              <button
                onClick={() => handleModeToggle(true)}
                disabled={loading || organization?.test_mode}
                className={`p-4 border rounded-lg text-left transition-all ${
                  organization?.test_mode
                    ? 'bg-yellow-50 border-yellow-200 cursor-default'
                    : 'border-gray-200 hover:border-yellow-300 hover:bg-yellow-50'
                } ${loading ? 'opacity-50' : ''}`}
              >
                <div className="flex items-center justify-between mb-2">
                  <h5 className="font-medium text-gray-800">🧪 Test Mode</h5>
                  {organization?.test_mode && (
                    <span className="text-yellow-600 text-sm font-medium">ACTIVE</span>
                  )}
                </div>
                <p className="text-sm text-gray-600">
                  Safe testing environment. No real payments will be processed.
                </p>
                <ul className="text-xs text-gray-500 mt-2 list-disc list-inside">
                  <li>Sandbox API endpoints</li>
                  <li>Test payment processing</li>
                  <li>No actual charges</li>
                </ul>
              </button>

              {/* Production Mode Option */}
              <button
                onClick={() => handleModeToggle(false)}
                disabled={loading || !organization?.test_mode}
                className={`p-4 border rounded-lg text-left transition-all ${
                  !organization?.test_mode
                    ? 'bg-green-50 border-green-200 cursor-default'
                    : 'border-gray-200 hover:border-green-300 hover:bg-green-50'
                } ${loading ? 'opacity-50' : ''}`}
              >
                <div className="flex items-center justify-between mb-2">
                  <h5 className="font-medium text-gray-800">🚀 Production Mode</h5>
                  {!organization?.test_mode && (
                    <span className="text-green-600 text-sm font-medium">ACTIVE</span>
                  )}
                </div>
                <p className="text-sm text-gray-600">
                  Live environment. Real payments will be processed.
                </p>
                <ul className="text-xs text-gray-500 mt-2 list-disc list-inside">
                  <li>Production API endpoints</li>
                  <li>Real payment processing</li>
                  <li>Actual charges to donors</li>
                </ul>
              </button>
            </div>
          </div>

          {success && (
            <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-md">
              Mode updated successfully!
            </div>
          )}
        </div>
      </div>

      {/* Important Notes */}
      <div className="mt-6 bg-blue-50 border border-blue-200 rounded-lg p-6">
        <h4 className="font-medium text-blue-800 mb-2">📋 Important Notes:</h4>
        <ul className="text-sm text-blue-700 list-disc list-inside space-y-1">
          <li>Organizations start in Test Mode by default for safety</li>
          <li>You can switch between modes at any time</li>
          <li>BBMS credentials must match the selected mode (test vs production)</li>
          <li>Existing donation forms will use the current mode setting</li>
          <li>Transaction history is maintained separately for each mode</li>
        </ul>
      </div>

      {/* Confirmation Modal */}
      {showConfirm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md mx-4">
            <h3 className="text-lg font-bold text-gray-800 mb-4">⚠️ Switch to Production Mode?</h3>
            <p className="text-gray-600 mb-6">
              You're about to switch to Production Mode. This means:
            </p>
            <ul className="text-sm text-gray-600 list-disc list-inside mb-6 space-y-1">
              <li>Real payments will be processed</li>
              <li>Donors will be charged actual money</li>
              <li>You need valid production BBMS credentials</li>
              <li>All transactions will be live</li>
            </ul>
            <p className="text-sm font-medium text-orange-700 mb-6">
              Make sure you have tested thoroughly in Test Mode first!
            </p>
            <div className="flex space-x-3">
              <button
                onClick={confirmModeChange}
                disabled={loading}
                className="flex-1 bg-red-600 text-white font-medium py-2 px-4 rounded-md hover:bg-red-700 disabled:bg-gray-400"
              >
                {loading ? 'Switching...' : 'Yes, Switch to Production'}
              </button>
              <button
                onClick={cancelModeChange}
                className="flex-1 bg-gray-200 text-gray-800 font-medium py-2 px-4 rounded-md hover:bg-gray-300"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
const EmbedCode = ({ organization }) => {
  const [copied, setCopied] = useState(false);

  const embedCode = `<div id="donation-widget-${organization?.id}"></div>
<script>
(function() {
  const iframe = document.createElement('iframe');
  iframe.src = '${BACKEND_URL}/embed/donate/${organization?.id}';
  iframe.width = '100%';
  iframe.height = '600';
  iframe.frameBorder = '0';
  iframe.style.border = 'none';
  iframe.style.borderRadius = '8px';
  
  document.getElementById('donation-widget-${organization?.id}').appendChild(iframe);
})();
</script>`;

  const copyToClipboard = () => {
    navigator.clipboard.writeText(embedCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="max-w-4xl">
      <h2 className="text-2xl font-bold text-gray-800 mb-6">Embed Code</h2>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <div>
          <h3 className="text-lg font-medium text-gray-800 mb-4">How to embed your donation form</h3>
          
          <div className="space-y-4 text-sm text-gray-600">
            <div className="flex items-start">
              <div className="bg-blue-100 text-blue-800 rounded-full w-6 h-6 flex items-center justify-center text-xs font-bold mr-3 mt-0.5">1</div>
              <div>
                <p className="font-medium text-gray-800">Copy the embed code</p>
                <p>Use the code provided on the right side of this page.</p>
              </div>
            </div>
            
            <div className="flex items-start">
              <div className="bg-blue-100 text-blue-800 rounded-full w-6 h-6 flex items-center justify-center text-xs font-bold mr-3 mt-0.5">2</div>
              <div>
                <p className="font-medium text-gray-800">Paste in your website</p>
                <p>Add the code to any HTML page where you want the donation form to appear.</p>
              </div>
            </div>
            
            <div className="flex items-start">
              <div className="bg-blue-100 text-blue-800 rounded-full w-6 h-6 flex items-center justify-center text-xs font-bold mr-3 mt-0.5">3</div>
              <div>
                <p className="font-medium text-gray-800">Start accepting donations</p>
                <p>Your donation form will appear as an embedded iframe and start accepting payments immediately.</p>
              </div>
            </div>
          </div>

          <div className="mt-6 p-4 bg-yellow-50 border border-yellow-200 rounded-md">
            <h4 className="font-medium text-yellow-800 mb-2">⚠️ Requirements:</h4>
            <ul className="text-sm text-yellow-700 list-disc list-inside space-y-1">
              <li>Ensure your BBMS credentials are configured</li>
              <li>Test the form before going live</li>
              <li>The iframe will be responsive and adapt to your page width</li>
            </ul>
          </div>
        </div>

        <div>
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-lg font-medium text-gray-800">Embed Code</h3>
            <button
              onClick={copyToClipboard}
              className={`px-4 py-2 rounded-md text-sm font-medium ${
                copied 
                  ? 'bg-green-100 text-green-700' 
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              {copied ? '✓ Copied!' : 'Copy Code'}
            </button>
          </div>
          
          <div className="bg-gray-900 text-gray-100 p-4 rounded-lg overflow-x-auto">
            <pre className="text-xs leading-relaxed">
              <code>{embedCode}</code>
            </pre>
          </div>

          <div className="mt-6">
            <h4 className="font-medium text-gray-800 mb-3">Preview</h4>
            <div className="border-2 border-dashed border-gray-300 rounded-lg p-4 bg-gray-50">
              <iframe
                src={`${BACKEND_URL}/embed/donate/${organization?.id}`}
                width="100%"
                height="400"
                frameBorder="0"
                className="rounded-lg"
                title="Donation Form Preview"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// Transactions Component
const Transactions = ({ organization, authToken }) => {
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchTransactions();
  }, []);

  const fetchTransactions = async () => {
    try {
      const response = await axios.get(`${API}/organizations/${organization.id}/transactions`, {
        headers: { Authorization: `Bearer ${authToken}` }
      });
      setTransactions(response.data);
    } catch (error) {
      console.error('Failed to fetch transactions:', error);
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getStatusBadge = (status) => {
    const colors = {
      completed: 'bg-green-100 text-green-800',
      pending: 'bg-yellow-100 text-yellow-800',
      failed: 'bg-red-100 text-red-800',
      cancelled: 'bg-gray-100 text-gray-800'
    };
    
    return `px-2 py-1 rounded-full text-xs font-medium ${colors[status] || colors.pending}`;
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div>
      <h2 className="text-2xl font-bold text-gray-800 mb-6">Transactions</h2>

      <div className="bg-white rounded-lg shadow-sm border">
        {transactions.length === 0 ? (
          <div className="text-center py-12">
            <div className="text-gray-400 text-4xl mb-4">💰</div>
            <h3 className="text-lg font-medium text-gray-800 mb-2">No transactions yet</h3>
            <p className="text-gray-600">Donations will appear here once you start receiving them.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Donor
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Amount
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Date
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {transactions.map((transaction) => (
                  <tr key={transaction.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div>
                        <div className="text-sm font-medium text-gray-900">
                          {transaction.donor_name}
                        </div>
                        <div className="text-sm text-gray-500">
                          {transaction.donor_email}
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                      ${transaction.amount.toFixed(2)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={getStatusBadge(transaction.status)}>
                        {transaction.status.charAt(0).toUpperCase() + transaction.status.slice(1)}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {formatDate(transaction.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default App;