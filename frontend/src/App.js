import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

const API = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

function App() {
  const [currentPage, setCurrentPage] = useState('login');
  const [organization, setOrganization] = useState(null);
  const [authToken, setAuthToken] = useState(localStorage.getItem('authToken'));

  useEffect(() => {
    if (authToken) {
      fetchOrganization();
    }
  }, [authToken]);

  const fetchOrganization = async () => {
    try {
      const response = await axios.get(`${API}/api/organizations/me`, {
        headers: { Authorization: `Bearer ${authToken}` }
      });
      setOrganization(response.data);
      setCurrentPage('dashboard');
    } catch (error) {
      console.error('Failed to fetch organization:', error);
      localStorage.removeItem('authToken');
      setAuthToken(null);
      setCurrentPage('login');
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('authToken');
    setAuthToken(null);
    setOrganization(null);
    setCurrentPage('login');
  };

  if (!authToken || currentPage === 'login') {
    return <AuthPage onLogin={(token) => {
      setAuthToken(token);
      localStorage.setItem('authToken', token);
    }} />;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <h1 className="text-2xl font-bold text-gray-900">Donation Page Builder</h1>
            <div className="flex items-center space-x-4">
              <span className="text-gray-600">Welcome, {organization?.name}</span>
              <button
                onClick={handleLogout}
                className="text-gray-500 hover:text-gray-700"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Navigation currentPage={currentPage} setCurrentPage={setCurrentPage} />
        
        <div className="mt-8">
          {currentPage === 'dashboard' && <Dashboard organization={organization} authToken={authToken} />}
          {currentPage === 'form-settings' && <FormSettings organization={organization} authToken={authToken} onUpdate={fetchOrganization} />}
          {currentPage === 'payment-setup' && <BBMSConfig organization={organization} authToken={authToken} onUpdate={fetchOrganization} />}
          {currentPage === 'mode-settings' && <ModeSettings organization={organization} authToken={authToken} onUpdate={fetchOrganization} />}
          {currentPage === 'embed-code' && <EmbedCode organization={organization} />}
          {currentPage === 'transactions' && <Transactions organization={organization} authToken={authToken} />}
        </div>
      </div>
    </div>
  );
}

// Navigation Component
const Navigation = ({ currentPage, setCurrentPage }) => {
  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: '📊' },
    { id: 'form-settings', label: 'Form Settings', icon: '⚙️' },
    { id: 'payment-setup', label: 'Payment Setup', icon: '💳' },
    { id: 'mode-settings', label: 'Mode Settings', icon: '🔄' },
    { id: 'embed-code', label: 'Embed Code', icon: '🔗' },
    { id: 'transactions', label: 'Transactions', icon: '📋' }
  ];

  return (
    <nav className="flex space-x-1 bg-white rounded-lg shadow-sm p-1">
      {navItems.map((item) => (
        <button
          key={item.id}
          onClick={() => setCurrentPage(item.id)}
          className={`flex items-center px-4 py-2 rounded-md text-sm font-medium ${
            currentPage === item.id
              ? 'bg-blue-100 text-blue-700'
              : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'
          }`}
        >
          <span className="mr-2">{item.icon}</span>
          {item.label}
        </button>
      ))}
    </nav>
  );
};

// Auth Page Component
const AuthPage = ({ onLogin }) => {
  const [isLogin, setIsLogin] = useState(true);
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    name: ''
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const endpoint = isLogin ? '/api/organizations/login' : '/api/organizations/register';
      const data = isLogin 
        ? { email: formData.email, password: formData.password }
        : { admin_email: formData.email, admin_password: formData.password, name: formData.name };

      console.log('Making request to:', `${API}${endpoint}`);
      console.log('Request data:', data);
      console.log('API base URL:', API);

      const response = await axios.post(`${API}${endpoint}`, data);
      console.log('Response:', response.data);
      onLogin(response.data.access_token);
    } catch (error) {
      console.error('Request failed:', error);
      console.error('Error response:', error.response);
      setError(error.response?.data?.detail || error.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div>
          <h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900">
            {isLogin ? 'Sign in to your account' : 'Create your organization'}
          </h2>
        </div>
        <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
          <div className="space-y-4">
            {!isLogin && (
              <input
                type="text"
                required
                value={formData.name}
                onChange={(e) => setFormData({...formData, name: e.target.value})}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Organization Name"
              />
            )}
            <input
              type="email"
              required
              value={formData.email}
              onChange={(e) => setFormData({...formData, email: e.target.value})}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Email address"
            />
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

          <div className="text-center">
            <button
              type="button"
              onClick={() => setIsLogin(!isLogin)}
              className="text-blue-600 hover:text-blue-500"
            >
              {isLogin ? "Don't have an account? Sign up" : "Already have an account? Sign in"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

// Dashboard Component  
const Dashboard = ({ organization, authToken }) => {
  const [stats, setStats] = useState({ totalDonations: 0, totalAmount: 0, recentCount: 0 });

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const response = await axios.get(`${API}/api/organizations/${organization.id}/transactions`, {
        headers: { Authorization: `Bearer ${authToken}` }
      });
      const transactions = response.data;
      
      const completed = transactions.filter(t => t.status === 'completed');
      const totalAmount = completed.reduce((sum, t) => sum + (t.amount || 0), 0);
      const recentCount = completed.filter(t => {
        const transactionDate = new Date(t.created_at);
        const weekAgo = new Date();
        weekAgo.setDate(weekAgo.getDate() - 7);
        return transactionDate > weekAgo;
      }).length;

      setStats({
        totalDonations: completed.length,
        totalAmount: totalAmount,
        recentCount: recentCount
      });
    } catch (error) {
      console.error('Failed to fetch stats:', error);
    }
  };

  const quickActions = [
    {
      title: 'Setup Payment Processing',
      description: 'Configure Blackbaud BBMS for donations',
      icon: '💳',
      action: 'payment-setup',
      color: 'blue'
    },
    {
      title: 'Customize Form',
      description: 'Edit donation amounts and fields',
      icon: '⚙️',
      action: 'form-settings',
      color: 'green'
    },
    {
      title: 'Test Payment Flow',
      description: 'Open test form in new window',
      icon: '🧪',
      action: () => window.open(`${BACKEND_URL}/api/embed/test-donate`, '_blank'),
      color: 'yellow'
    },
    {
      title: 'Get Embed Code',
      description: 'Copy code for your website',
      icon: '🔗',
      action: 'embed-code',
      color: 'purple'
    },
    {
      title: 'View Transactions',
      description: 'See donation history',
      icon: '📋',
      action: 'transactions',
      color: 'indigo'
    }
  ];

  return (
    <div>
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-gray-800 mb-6">Dashboard Overview</h2>
        
        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <div className="bg-white rounded-lg shadow-sm p-6 border">
            <div className="flex items-center">
              <div className="text-3xl mr-4">💰</div>
              <div>
                <p className="text-sm font-medium text-gray-600">Total Donations</p>
                <p className="text-2xl font-bold text-gray-900">{stats.totalDonations}</p>
              </div>
            </div>
          </div>
          
          <div className="bg-white rounded-lg shadow-sm p-6 border">
            <div className="flex items-center">
              <div className="text-3xl mr-4">💵</div>
              <div>
                <p className="text-sm font-medium text-gray-600">Total Amount</p>
                <p className="text-2xl font-bold text-gray-900">${stats.totalAmount.toFixed(2)}</p>
              </div>
            </div>
          </div>
          
          <div className="bg-white rounded-lg shadow-sm p-6 border">
            <div className="flex items-center">
              <div className="text-3xl mr-4">📈</div>
              <div>
                <p className="text-sm font-medium text-gray-600">This Week</p>
                <p className="text-2xl font-bold text-gray-900">{stats.recentCount}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Mode Status */}
        <div className={`border rounded-lg p-4 mb-8 ${
          organization?.test_mode 
            ? 'bg-yellow-50 border-yellow-200' 
            : 'bg-green-50 border-green-200'
        }`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <span className="text-2xl mr-3">
                {organization?.test_mode ? '🧪' : '🚀'}
              </span>
              <div>
                <h3 className={`font-medium ${
                  organization?.test_mode ? 'text-yellow-800' : 'text-green-800'
                }`}>
                  {organization?.test_mode ? 'Test Mode Active' : 'Production Mode Active'}
                </h3>
                <p className={`text-sm ${
                  organization?.test_mode ? 'text-yellow-700' : 'text-green-700'
                }`}>
                  {organization?.test_mode 
                    ? 'Safe testing environment - no real payments processed'
                    : 'Live environment - real payments will be processed'
                  }
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div>
        <h3 className="text-xl font-semibold text-gray-800 mb-4">Quick Actions</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {quickActions.map((action, index) => (
            <QuickActionCard key={index} {...action} />
          ))}
        </div>
      </div>
    </div>
  );
};

const QuickActionCard = ({ title, description, icon, action, color }) => {
  const [currentPage, setCurrentPage] = useState('');
  
  const handleClick = () => {
    if (typeof action === 'function') {
      action();
    } else {
      // This would need to be passed down from parent component
      window.location.hash = action;
    }
  };

  const colorClasses = {
    blue: 'border-blue-200 hover:border-blue-300 hover:bg-blue-50',
    green: 'border-green-200 hover:border-green-300 hover:bg-green-50',
    yellow: 'border-yellow-200 hover:border-yellow-300 hover:bg-yellow-50',
    purple: 'border-purple-200 hover:border-purple-300 hover:bg-purple-50',
    indigo: 'border-indigo-200 hover:border-indigo-300 hover:bg-indigo-50'
  };

  return (
    <button
      onClick={handleClick}
      className={`bg-white border rounded-lg p-4 text-left transition-all ${colorClasses[color]} hover:shadow-md`}
    >
      <div className="flex items-start">
        <span className="text-2xl mr-3">{icon}</span>
        <div>
          <h4 className="font-medium text-gray-900 mb-1">{title}</h4>
          <p className="text-sm text-gray-600">{description}</p>
        </div>
      </div>
    </button>
  );
};

// Form Settings Component
const FormSettings = ({ organization, authToken, onUpdate }) => {
  const [settings, setSettings] = useState({
    preset_amounts: [25, 50, 100, 250, 500],
    custom_amount_enabled: true,
    required_fields: ['name', 'email'],
    organization_description: 'Help us make a difference',
    thank_you_message: 'Thank you for your generous donation!'
  });
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    if (organization?.form_settings) {
      setSettings(organization.form_settings);
    }
  }, [organization]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      // Sort preset amounts in ascending order
      const sortedSettings = {
        ...settings,
        preset_amounts: [...settings.preset_amounts].sort((a, b) => a - b)
      };

      await axios.put(`${API}/organizations/${organization.id}/form-settings`, sortedSettings, {
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
    const newAmount = prompt('Enter preset amount:');
    if (newAmount && !isNaN(newAmount) && parseFloat(newAmount) > 0) {
      const amounts = [...settings.preset_amounts, parseFloat(newAmount)];
      setSettings({
        ...settings,
        preset_amounts: amounts.sort((a, b) => a - b) // Sort in ascending order
      });
    }
  };

  const removePresetAmount = (index) => {
    const amounts = settings.preset_amounts.filter((_, i) => i !== index);
    setSettings({...settings, preset_amounts: amounts});
  };

  return (
    <div className="max-w-2xl">
      <h2 className="text-2xl font-bold text-gray-800 mb-6">Form Settings</h2>

      {success && (
        <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-md mb-6">
          Form settings updated successfully!
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="bg-white rounded-lg shadow-sm border p-6">
          <h3 className="text-lg font-medium text-gray-800 mb-4">Donation Amounts</h3>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Preset Amounts (sorted automatically)
              </label>
              <div className="flex flex-wrap gap-2 mb-3">
                {settings.preset_amounts.sort((a, b) => a - b).map((amount, index) => (
                  <div key={index} className="flex items-center bg-gray-100 rounded-md px-3 py-2">
                    <span className="mr-2">${amount}</span>
                    <button
                      type="button"
                      onClick={() => removePresetAmount(index)}
                      className="text-red-500 hover:text-red-700 text-sm"
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
              <button
                type="button"
                onClick={addPresetAmount}
                className="bg-blue-100 text-blue-700 px-3 py-2 rounded-md text-sm hover:bg-blue-200"
              >
                + Add Amount
              </button>
            </div>

            <div className="flex items-center">
              <input
                type="checkbox"
                id="custom_amount"
                checked={settings.custom_amount_enabled}
                onChange={(e) => setSettings({...settings, custom_amount_enabled: e.target.checked})}
                className="mr-2"
              />
              <label htmlFor="custom_amount" className="text-sm font-medium text-gray-700">
                Allow custom amounts
              </label>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-sm border p-6">
          <h3 className="text-lg font-medium text-gray-800 mb-4">Organization Details</h3>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Organization Description
              </label>
              <textarea
                value={settings.organization_description}
                onChange={(e) => setSettings({...settings, organization_description: e.target.value})}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                rows={3}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Thank You Message
              </label>
              <textarea
                value={settings.thank_you_message}
                onChange={(e) => setSettings({...settings, thank_you_message: e.target.value})}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                rows={2}
              />
            </div>
          </div>
        </div>

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

// BBMS Configuration Component (Simplified)
const BBMSConfig = ({ organization, authToken, onUpdate }) => {
  const [merchantIds, setMerchantIds] = useState({
    test_merchant_id: '',
    production_merchant_id: ''
  });
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (organization) {
      setMerchantIds({
        test_merchant_id: organization.bb_test_merchant_id || '',
        production_merchant_id: organization.bb_production_merchant_id || ''
      });
    }
  }, [organization]);

  const handleMerchantSetup = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      await axios.post(`${API}/organizations/bbms-setup`, merchantIds, {
        headers: { Authorization: `Bearer ${authToken}` }
      });
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (error) {
      setError(error.response?.data?.detail || 'Failed to save merchant IDs');
    } finally {
      setLoading(false);
    }
  };

  const handleOAuthConnect = async () => {
    setError('');
    
    // Use the current mode's merchant ID for OAuth
    const currentMerchantId = organization?.test_mode 
      ? merchantIds.test_merchant_id 
      : merchantIds.production_merchant_id;

    if (!currentMerchantId.trim()) {
      const modeText = organization?.test_mode ? 'test' : 'production';
      setError(`Please enter your ${modeText} merchant account ID first`);
      return;
    }

    try {
      // Use environment variables for app credentials (set by developer)
      const response = await axios.post(`${API}/organizations/bbms-oauth/start`, 
        { 
          merchant_id: currentMerchantId,
          app_id: process.env.REACT_APP_BB_APPLICATION_ID || "2e2c42a7-a2f5-4fd3-a0bc-d4b3b36d8cea",
          app_secret: process.env.REACT_APP_BB_APPLICATION_SECRET || "3VuF4BNX72+dClCDheqMN7xPfsu29GKGxdaobEIbWXU="
        }, 
        { headers: { Authorization: `Bearer ${authToken}` } }
      );

      // Open OAuth window
      const popup = window.open(
        response.data.oauth_url,
        'blackbaud_oauth',
        'width=600,height=700,scrollbars=yes,resizable=yes'
      );

      if (!popup) {
        throw new Error('Popup blocked. Please allow popups for this site.');
      }

      // Monitor popup
      const checkClosed = setInterval(() => {
        if (popup.closed) {
          clearInterval(checkClosed);
          onUpdate(); // Refresh organization data
        }
      }, 1000);

    } catch (error) {
      console.error('OAuth start failed:', error);
      setError(error.response?.data?.detail || error.message || 'Failed to start OAuth flow');
    }
  };

  // Listen for OAuth completion
  useEffect(() => {
    const handleMessage = (event) => {
      if (event.data.type === 'BLACKBAUD_AUTH_COMPLETE') {
        if (event.data.success) {
          setSuccess(true);
          onUpdate();
          setTimeout(() => setSuccess(false), 3000);
        } else {
          setError(event.data.error || 'OAuth authentication failed');
        }
      }
    };

    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [onUpdate]);

  return (
    <div className="max-w-2xl">
      <h2 className="text-2xl font-bold text-gray-800 mb-6">Payment Setup</h2>

      <div className="bg-white rounded-lg shadow-sm border p-6">
        <h3 className="text-lg font-medium text-gray-800 mb-4">Blackbaud BBMS Configuration</h3>
        
        <div className={`border rounded-md mb-6 px-4 py-3 ${
          organization?.test_mode 
            ? 'bg-yellow-50 border-yellow-200 text-yellow-700' 
            : 'bg-green-50 border-green-200 text-green-700'
        }`}>
          {organization?.test_mode ? '🧪' : '🚀'} <strong>
            {organization?.test_mode ? 'Test Mode Active:' : 'Production Mode Active:'}
          </strong> {organization?.test_mode 
            ? 'Using test merchant account for sandbox payments'
            : 'Using production merchant account for live payments'
          }
        </div>
        
        {organization?.has_bbms_configured && (
          <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-md mb-6 flex items-center justify-between">
            <div>
              <span className="font-medium">✅ BBMS is configured and ready to accept donations</span>
            </div>
            <a
              href={`${BACKEND_URL}/api/embed/test-donate`}
              target="_blank"
              rel="noopener noreferrer"
              className="bg-green-600 text-white px-4 py-2 rounded-md hover:bg-green-700 text-sm font-medium"
            >
              🧪 Test Payment Flow
            </a>
          </div>
        )}

        {/* Instructions */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
          <h4 className="font-medium text-blue-800 mb-2">📋 How to Set Up Payments:</h4>
          <ol className="list-decimal list-inside text-blue-700 space-y-1 text-sm">
            <li>Enter your Blackbaud BBMS merchant account IDs below</li>
            <li>Click "Connect with Blackbaud" to authorize the integration</li>
            <li>Your donation forms will be ready to accept payments!</li>
          </ol>
        </div>

        {/* Merchant ID Setup */}
        <form onSubmit={handleMerchantSetup} className="space-y-4 mb-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Test Merchant Account ID
            </label>
            <input
              type="text"
              value={merchantIds.test_merchant_id}
              onChange={(e) => setMerchantIds({...merchantIds, test_merchant_id: e.target.value})}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Your test/sandbox merchant account ID"
            />
            <p className="text-xs text-gray-500 mt-1">
              Used for testing payments (sandbox environment)
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Production Merchant Account ID
            </label>
            <input
              type="text"
              value={merchantIds.production_merchant_id}
              onChange={(e) => setMerchantIds({...merchantIds, production_merchant_id: e.target.value})}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Your live merchant account ID"
            />
            <p className="text-xs text-gray-500 mt-1">
              Used for live payments (production environment)
            </p>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="bg-gray-600 text-white font-medium py-2 px-4 rounded-md hover:bg-gray-700 disabled:bg-gray-400"
          >
            {loading ? 'Saving...' : 'Save Merchant Account IDs'}
          </button>
        </form>

        {/* OAuth Connection */}
        <div className="space-y-4">
          <h4 className="font-medium text-gray-800">Connect with Blackbaud</h4>
          
          <button
            onClick={handleOAuthConnect}
            className="w-full bg-blue-600 text-white font-medium py-3 px-4 rounded-md hover:bg-blue-700 flex items-center justify-center"
          >
            <svg className="w-5 h-5 mr-2" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2C6.477 2 2 6.477 2 12s4.477 10 10 10 10-4.477 10-10S17.523 2 12 2zm0 18c-4.418 0-8-3.582-8-8s3.582-8 8-8 8 3.582 8 8-3.582 8-8 8zm-1-13v6l5 3 1-1.5-4-2.5V7h-2z"/>
            </svg>
            Connect with Blackbaud
          </button>
          
          <p className="text-sm text-gray-600 text-center">
            Secure OAuth2 authentication - authorizes payment processing
          </p>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md mt-4">
            {error}
          </div>
        )}

        {success && (
          <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-md mt-4">
            Configuration updated successfully!
          </div>
        )}

        {/* Developer Info Link */}
        <div className="mt-6 p-4 bg-gray-50 border border-gray-200 rounded-md">
          <h4 className="font-medium text-gray-800 mb-2">👨‍💻 For Developers</h4>
          <p className="text-sm text-gray-600 mb-2">
            Need help setting up the SKY API integration?
          </p>
          <a
            href={`${BACKEND_URL}/api/developer-instructions`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 hover:text-blue-800 text-sm font-medium"
          >
            View Developer Setup Instructions →
          </a>
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
                    ? 'Safe testing environment - uses test merchant account'
                    : 'Live environment - uses production merchant account'
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
                  Safe testing environment. Uses test merchant account.
                </p>
                <ul className="text-xs text-gray-500 mt-2 list-disc list-inside">
                  <li>Sandbox payments only</li>
                  <li>Test credit card numbers</li>
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
                  Live environment. Uses production merchant account.
                </p>
                <ul className="text-xs text-gray-500 mt-2 list-disc list-inside">
                  <li>Real payment processing</li>
                  <li>Actual charges to donors</li>
                  <li>Live merchant account</li>
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
          <li>Test mode uses your test merchant account ID</li>
          <li>Production mode uses your production merchant account ID</li>
          <li>Existing donation forms automatically use the current mode</li>
          <li>Always test thoroughly before switching to production</li>
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
              <li>Uses your production merchant account</li>
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

// Embed Code Component (Updated)
const EmbedCode = ({ organization }) => {
  const [copied, setCopied] = useState(false);

  const embedCode = `<div id="donation-widget-${organization?.id}"></div>
<script>
(function() {
  const iframe = document.createElement('iframe');
  iframe.src = '${BACKEND_URL}/api/embed/donate/${organization?.id}';
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

  const currentMerchantId = organization?.test_mode 
    ? organization?.bb_test_merchant_id 
    : organization?.bb_production_merchant_id;

  const hasConfiguredMerchant = Boolean(currentMerchantId);

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

          {/* Mode-specific information */}
          <div className={`mt-6 p-4 rounded-md border ${
            organization?.test_mode 
              ? 'bg-yellow-50 border-yellow-200' 
              : 'bg-green-50 border-green-200'
          }`}>
            <h4 className={`font-medium mb-2 ${
              organization?.test_mode ? 'text-yellow-800' : 'text-green-800'
            }`}>
              {organization?.test_mode ? '🧪 Test Mode Information:' : '🚀 Production Mode Information:'}
            </h4>
            <ul className={`text-sm list-disc list-inside space-y-1 ${
              organization?.test_mode ? 'text-yellow-700' : 'text-green-700'
            }`}>
              {organization?.test_mode ? (
                <>
                  <li>Uses test merchant account: {organization?.bb_test_merchant_id || 'Not configured'}</li>
                  <li>Process mode: "Test" - sandbox payments only</li>
                  <li>Use test credit card numbers for donations</li>
                  <li><a href="https://kb.blackbaud.com/knowledgebase/articles/Article/64901" target="_blank" rel="noopener noreferrer" className="underline">View test credit card numbers →</a></li>
                </>
              ) : (
                <>
                  <li>Uses production merchant account: {organization?.bb_production_merchant_id || 'Not configured'}</li>
                  <li>Process mode: "Live" - real credit card processing</li>
                  <li>Processes actual payments from donors</li>
                  <li>Transactions appear in your Blackbaud merchant portal</li>
                </>
              )}
            </ul>
          </div>

          {!hasConfiguredMerchant && (
            <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-md">
              <h4 className="font-medium text-red-800 mb-2">⚠️ Configuration Required:</h4>
              <p className="text-sm text-red-700">
                Configure your {organization?.test_mode ? 'test' : 'production'} merchant account ID in Payment Setup before embedding the form.
              </p>
            </div>
          )}
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
            <div className="flex justify-between items-center mb-3">
              <h4 className="font-medium text-gray-800">Preview</h4>
              <div className="flex space-x-2">
                <a
                  href={`${BACKEND_URL}/api/embed/test-donate`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm bg-blue-100 text-blue-700 px-3 py-1 rounded-md hover:bg-blue-200 transition-colors"
                >
                  🧪 Demo Form (New Window)
                </a>
                <span className={`text-sm px-3 py-1 rounded-md ${
                  organization?.test_mode 
                    ? 'bg-yellow-100 text-yellow-700' 
                    : 'bg-green-100 text-green-700'
                }`}>
                  {organization?.test_mode ? 'Test Mode' : 'Production Mode'}
                </span>
              </div>
            </div>
            <div className="border-2 border-dashed border-gray-300 rounded-lg p-4 bg-gray-50">
              {hasConfiguredMerchant ? (
                <iframe
                  src={`${BACKEND_URL}/api/embed/donate/${organization?.id}`}
                  width="100%"
                  height="400"
                  frameBorder="0"
                  className="rounded-lg"
                  title="Donation Form Preview"
                />
              ) : (
                <div className="flex flex-col items-center justify-center h-64 text-gray-500 space-y-4">
                  <div className="text-4xl">⚠️</div>
                  <div className="text-center">
                    <h5 className="font-medium text-gray-800 mb-2">Preview Unavailable</h5>
                    <p className="text-sm">Configure your {organization?.test_mode ? 'test' : 'production'} merchant account ID in Payment Setup first.</p>
                    <a
                      href={`${BACKEND_URL}/api/embed/test-donate`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-block mt-3 bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 text-sm"
                    >
                      🧪 Try Demo Form Instead
                    </a>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// Transactions Component (Updated)
const Transactions = ({ organization, authToken }) => {
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchTransactions();
  }, []);

  const fetchTransactions = async () => {
    try {
      const response = await axios.get(`${API}/api/organizations/${organization.id}/transactions`, {
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
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold text-gray-800">Transactions</h2>
        <a
          href="https://host.nxt.blackbaud.com/payment-portal/transactions"
          target="_blank"
          rel="noopener noreferrer"
          className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 text-sm font-medium"
        >
          View in Blackbaud Portal →
        </a>
      </div>

      <div className="bg-white rounded-lg shadow-sm border">
        {transactions.length === 0 ? (
          <div className="text-center py-12">
            <div className="text-gray-400 text-4xl mb-4">💰</div>
            <h3 className="text-lg font-medium text-gray-800 mb-2">No transactions yet</h3>
            <p className="text-gray-600 mb-4">Donations will appear here once you start receiving them.</p>
            <div className="space-y-2">
              <a
                href={`${BACKEND_URL}/api/embed/test-donate`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-block bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 text-sm font-medium mr-2"
              >
                🧪 Try Demo Form
              </a>
              <a
                href="https://host.nxt.blackbaud.com/payment-portal/transactions"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-block bg-gray-600 text-white px-4 py-2 rounded-md hover:bg-gray-700 text-sm font-medium"
              >
                Check Blackbaud Portal
              </a>
            </div>
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
                    Mode
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
                      ${transaction.amount?.toFixed(2) || '0.00'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={getStatusBadge(transaction.status)}>
                        {transaction.status?.charAt(0).toUpperCase() + transaction.status?.slice(1) || 'Unknown'}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                        transaction.test_mode 
                          ? 'bg-yellow-100 text-yellow-800' 
                          : 'bg-green-100 text-green-800'
                      }`}>
                        {transaction.test_mode ? 'Test' : 'Live'}
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