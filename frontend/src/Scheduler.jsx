import React, { useState, useCallback, useEffect, useRef } from 'react';
import { Input, Button, Upload, message, Form, Select, Spin } from 'antd';
import { motion } from 'framer-motion';
import { createUser, login, uploadCredentials, initiateGoogleAuth, completeGoogleAuth, updateUserServices, getUserInfo, getCredentialsStatus, initiateLinkedInAuth, completeLinkedInAuth, saveLinkedInAppCredentials } from './services/api';
import './SchedulerF.css';
import { useLocation, useNavigate } from 'react-router-dom';
const { Option } = Select;

class ErrorBoundary extends React.Component {
  state = { hasError: false, error: null };

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('Rendering error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="app-container">
          <h2>Error Rendering Component</h2>
          <p>{this.state.error?.message || 'An unexpected error occurred.'}</p>
          <Button onClick={() => window.location.reload()}>Refresh</Button>
        </div>
      );
    }
    return this.props.children;
  }
}

const Scheduler_Design = () => {
  const [step, setStep] = useState('login');
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    name: '',
    status: '',
    linkedinClientId: '',
    linkedinClientSecret: '',
    credentialsFile: null,
  });
  const [loading, setLoading] = useState(false);
  const [userId, setUserId] = useState(() => localStorage.getItem('userId') || null);
  const [token, setToken] = useState(() => localStorage.getItem('token') || null);
  const [credentialStatus, setCredentialStatus] = useState({});
  const [userInfo, setUserData] = useState({ name: '', status: '' });
  const [servicesData, setServicesData] = useState({
    services: [
      { name: 'Gmail', enabled: false, schedule: { frequency: 'daily', time: '09:00' }, connected: false },
      { name: 'Calendar', enabled: false, schedule: { frequency: 'hourly', time: '00:30' }, connected: false },
      { name: 'LinkedIn', enabled: false, schedule: { frequency: 'weekly', day_of_week: 'mon', hour: '10:00' }, connected: false },
    ],
  });

  const location = useLocation();
  const navigate = useNavigate();
  const processedGoogleCodeRef = useRef(null);
  const processedLinkedInCodeRef = useRef(null);

  const decodeToken = (token) => {
    try {
      const base64Url = token.split('.')[1];
      const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
      const jsonPayload = decodeURIComponent(
        atob(base64)
          .split('')
          .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
          .join('')
      );
      return JSON.parse(jsonPayload);
    } catch (error) {
      console.error('Failed to decode token:', error);
      return null;
    }
  };

  useEffect(() => {
    if (location.pathname === '/linkedin-callback') return;

    const urlParams = new URLSearchParams(location.search);
    const code = urlParams.get('code');
    const state = urlParams.get('state');
    const tokenFromStorage = localStorage.getItem('token');
    const userIdFromStorage = localStorage.getItem('userId');

    if (!code || !state || processedGoogleCodeRef.current === code || !tokenFromStorage || !userIdFromStorage) {
      console.log('Skipping Google OAuth callback:', { code, state, processedCode: processedGoogleCodeRef.current });
      return;
    }

    console.log('Processing Google callback', { userId: userIdFromStorage, code, state });
    setLoading(true);
    processedGoogleCodeRef.current = code;

    completeGoogleAuth(userIdFromStorage, tokenFromStorage, code, state)
      .then(() => {
        console.log('Google OAuth completed');
        message.success('Google authentication completed');
        window.history.replaceState({}, document.title, window.location.pathname);
        setStep('services');
        navigate('/services');
      })
      .catch(error => {
        console.error('Google OAuth error:', {
          message: error.message,
          status: error.response?.status,
          data: error.response?.data,
        });
        message.error('Google authentication failed');
        setStep('signup');
        navigate('/signup');
      })
      .finally(() => {
        processedGoogleCodeRef.current = null;
        setLoading(false);
      });
  }, [location, navigate]);

  const handleLinkedInCallback = useCallback(async (code, state) => {
    const tokenFromStorage = localStorage.getItem('token');
    const userIdFromStorage = localStorage.getItem('userId');

    if (!tokenFromStorage || !userIdFromStorage) {
      console.log('Missing session credentials');
      message.error('Session expired. Please sign in again.');
      navigate('/login');
      return;
    }

    console.log('Processing LinkedIn callback', { userId: userIdFromStorage, code, state });
    setLoading(true);
    try {
      await completeLinkedInAuth(userIdFromStorage, tokenFromStorage, code, state);
      console.log('LinkedIn auth completed');
      message.success('LinkedIn authentication completed');
      const status = await getCredentialsStatus(userIdFromStorage, tokenFromStorage);
      setCredentialStatus(status);
      window.history.replaceState({}, document.title, window.location.pathname);
      setStep('services');
      navigate('/services');
    } catch (error) {
      console.error('LinkedIn callback error:', {
        message: error.message,
        status: error.response?.status,
        data: error.response?.data,
      });
      message.error(error.response?.data?.detail || error.message || 'LinkedIn authentication failed');
    } finally {
      processedLinkedInCodeRef.current = null;
      setLoading(false);
    }
  }, [navigate]);

  useEffect(() => {
    if (location.pathname !== '/linkedin-callback') return;

    const urlParams = new URLSearchParams(location.search);
    const code = urlParams.get('code');
    const state = urlParams.get('state');

    if (!code || !state || processedLinkedInCodeRef.current === code) {
      console.log('Skipping LinkedIn OAuth callback:', { code, state, processedCode: processedLinkedInCodeRef.current });
      return;
    }

    processedLinkedInCodeRef.current = code;
    handleLinkedInCallback(code, state);
  }, [location, handleLinkedInCallback]);

  useEffect(() => {
    const token = localStorage.getItem('token');
    const userId = localStorage.getItem('userId');
    if (token && userId) {
      getUserInfo(userId, token)
        .then((data) => {
          setUserData({ name: data.name, status: data.status });
          console.log('User info fetched:', data);
        })
        .catch((error) => console.error('Get user info error:', error));
      getCredentialsStatus(userId, token)
        .then((status) => {
          setCredentialStatus(status);
          const updatedServices = servicesData.services.map(service => ({
            ...service,
            connected: status[service.name.toLowerCase()]?.valid || false
          }));
          setServicesData(prev => ({ ...prev, services: updatedServices }));
          console.log('Credentials status fetched:', status);
        })
        .catch((error) => console.error('Get credentials status error:', error));
    }
  }, [userId, token]);

  const handleFileChange = useCallback((info) => {
    const file = info.fileList[0]?.originFileObj || null;
    setFormData((prev) => ({ ...prev, credentialsFile: file }));
    console.log('Credentials file selected:', file?.name || 'none');
  }, []);

  const handleLogin = async (values) => {
  console.log('Login attempt:', { email: values.email, password: '***' });
  setLoading(true);
  try {
    const response = await login({
      email: values.email,
      password: values.password,
    });
    setUserId(response.user_id);
    setToken(response.access_token);
    localStorage.setItem('token', response.access_token);
    localStorage.setItem('userId', response.user_id.toString());
    setStep('services');
    navigate('/services');
    message.success('Login successful');
    console.log('Login successful:', response);
  } catch (error) {
    const errorMessage = error.message === 'Invalid email or password'
      ? 'Incorrect email or password. Please try again or reset your password.'
      : error.message || 'Login failed';
    message.error(errorMessage);
    console.error('Login error:', error);
  } finally {
    setLoading(false);
  }
  };

  const handleSignUp = async () => {
    console.log('Attempting signup with formData:', {
      email: formData.email,
      name: formData.name,
      status: formData.status,
      hasPassword: !!formData.password,
      hasCredentialsFile: !!formData.credentialsFile,
      linkedinClientId: formData.linkedinClientId ? 'provided' : 'none',
      linkedinClientSecret: formData.linkedinClientSecret ? '****' : 'none',
    });

    if (!formData.email || !formData.password || !formData.name || !formData.status) {
      const missingFields = [
        !formData.email && 'Email',
        !formData.password && 'Password',
        !formData.name && 'Name',
        !formData.status && 'Status',
      ].filter(Boolean).join(', ');
      const errorMessage = `${missingFields} ${missingFields.includes(',') ? 'are' : 'is'} required`;
      message.error(errorMessage);
      console.log('Validation failed:', errorMessage);
      return;
    }

    if (!formData.credentialsFile) {
      message.error('Google credentials file is required');
      console.log('Validation failed: No Google credentials file');
      return;
    }

    if (formData.linkedinClientId && !formData.linkedinClientSecret) {
      message.warning('LinkedIn Client Secret is missing. Both Client ID and Secret are required.');
      console.log('Validation warning: LinkedIn Client ID provided but Client Secret missing');
    } else if (!formData.linkedinClientId && formData.linkedinClientSecret) {
      message.warning('LinkedIn Client ID is missing. Both Client ID and Secret are required.');
      console.log('Validation warning: LinkedIn Client Secret provided but Client ID missing');
    }

    setLoading(true);
    try {
      console.log('Calling createUser...');
      const userResponse = await createUser({
        email: formData.email.trim(),
        password: formData.password,
        name: formData.name.trim(),
        status: formData.status.trim(),
        services: [],
        api_credentials: {},
      });
      const { user_id, access_token } = userResponse;
      console.log('User created:', { user_id, access_token: access_token?.substring(0, 10) + '...' });

      setUserId(user_id.toString());
      setToken(access_token);
      localStorage.setItem('userId', user_id.toString());
      localStorage.setItem('token', access_token);

      console.log('Uploading Google credentials for user:', user_id);
      const formDataUpload = new FormData();
      formDataUpload.append('credentials', formData.credentialsFile);
      await uploadCredentials(user_id, formDataUpload, access_token);
      console.log('Google credentials uploaded successfully');
      message.success('Google credentials uploaded successfully');

      if (formData.linkedinClientId && formData.linkedinClientSecret) {
        console.log('Saving LinkedIn credentials for user:', user_id);
        await saveLinkedInAppCredentials(user_id, access_token, {
          client_id: formData.linkedinClientId.trim(),
          client_secret: formData.linkedinClientSecret.trim(),
        });
        console.log('LinkedIn credentials saved successfully');
        message.success('LinkedIn credentials saved successfully');
      } else {
        console.log('No LinkedIn credentials provided; skipping saveLinkedInAppCredentials');
      }

      console.log('Initiating Google OAuth for user:', user_id);
      const googleAuthResult = await initiateGoogleAuth(user_id, access_token);
      console.log('Google OAuth initiation result:', googleAuthResult);
      if (googleAuthResult.status === 'success' && googleAuthResult.authorization_url) {
        console.log('Redirecting to Google OAuth URL:', googleAuthResult.authorization_url);
        window.location.href = googleAuthResult.authorization_url;
        return;
      } else {
        console.error('Google OAuth initiation failed: Invalid response', googleAuthResult);
        message.error('Failed to initiate Google authentication');
        setStep('signup');
        navigate('/signup');
      }
    } catch (error) {
      const errorMessage = error.response?.data?.detail || error.message || 'Signup failed';
      console.error('Signup error:', {
        message: errorMessage,
        status: error.response?.status,
        data: error.response?.data,
        stack: error.stack,
      });
      message.error(errorMessage);
    } finally {
      console.log('handleSignUp completed');
      setLoading(false);
    }
  };

  const handleLinkedInAuth = async () => {
    console.log('handleLinkedInAuth started', { userId, token: token?.substring(0, 10) + '...', credentialStatus });
    if (!credentialStatus.linkedin?.hasAppCredentials) {
      console.log('LinkedIn credentials missing');
      message.error('No LinkedIn credentials provided. Please sign up again with valid credentials.');
      return;
    }
    if (!userId || !token) {
      console.log('Missing userId or token');
      message.error('User not authenticated. Please sign up again.');
      navigate('/signup');
      return;
    }
    setLoading(true);
    try {
      console.log('Calling initiateLinkedInAuth');
      const response = await initiateLinkedInAuth(userId, token);
      console.log('Received LinkedIn auth URL', response);
      window.location.href = response.authorization_url;
    } catch (error) {
      console.error('LinkedIn auth initiation error:', {
        message: error.message,
        status: error.response?.status,
        data: error.response?.data,
      });
      message.error(error.response?.data?.detail || error.message || 'Failed to initiate LinkedIn authentication');
    } finally {
      console.log('handleLinkedInAuth completed');
      setLoading(false);
    }
  };

  const handleServiceSubmit = async () => {
    setLoading(true);
    try {
      const payload = {
        user_id: userId,
        services: servicesData.services
          .filter((s) => s.enabled)
          .map((s) => ({
            service: s.name,
            schedule: s.schedule,
          })),
      };
      await updateUserServices(payload, token);
      message.success('Services updated successfully');
      console.log('Services updated:', payload);
    } catch (error) {
      message.error(error.message || 'Failed to update services');
      console.error('Service update error:', error);
    } finally {
      setLoading(false);
    }
  };

  const renderLogin = () => (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="app-container"
    >
      <div className="app-header">
        <h1 className="title">HR Service Scheduler</h1>
        <p className="app-subtitle">Login to Your Account</p>
      </div>
      <div className="signup-container">
        <motion.div
          className="control-panel signup"
          whileHover={{ scale: 1.02 }}
          transition={{ type: 'spring', stiffness: 300 }}
        >
          <div className="panel-header">
            <h2 className="section-title">Login</h2>
            <p className="panel-subtitle">Sign in to your account</p>
          </div>
          
          <div className="form-group">
            <div className="form-row">
              <div className="form-column">
                <Form onFinish={handleLogin} layout="vertical">
                  <Form.Item
                    name="email"
                    rules={[{ required: true, message: 'Please input your email!' }]}
                  >
                    <Input placeholder="Email" className="modern-input" />
                  </Form.Item>
                  <Form.Item
                    name="password"
                    rules={[{ required: true, message: 'Please input your password!' }]}
                  >
                    <Input.Password placeholder="Password" className="modern-input" />
                  </Form.Item>
                  <Form.Item>
                    <Button
                      type="primary"
                      htmlType="submit"
                      className="submit-button"
                      loading={loading}
                      block
                    >
                      Login
                    </Button>
                  </Form.Item>
                </Form>
              </div>
            </div>
          </div>
          <div className="switch-auth">
            <p>Don't have an account? <a onClick={() => { setStep('signup'); navigate('/signup'); }}>Sign Up</a></p>
          </div>
        </motion.div>
      </div>
    </motion.div>
  );

  const renderSignUp = () => (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="app-container"
    >
      <div className="app-header">
        <h1 className="title">HR Service Scheduler</h1>
        <p className="app-subtitle">Create Your Account</p>
      </div>
      <div className="signup-container">
        <motion.div
          className="control-panel signup"
          whileHover={{ scale: 1.02 }}
          transition={{ type: 'spring', stiffness: 300 }}
        >
          <div className="panel-header">
            <h2 className="section-title">Sign Up</h2>
            <p className="panel-subtitle">Create your account to get started</p>
          </div>
          
          <div className="form-group">
            <div className="form-row">
              <div className="form-column">
                <label className="input-label">Email</label>
                <Input
                  placeholder="your.email@example.com"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  className="modern-input"
                />
                
                <label className="input-label">Password</label>
                <Input.Password
                  placeholder="Create a password"
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  className="modern-input"
                />
                
                <label className="input-label">Full Name</label>
                <Input
                  placeholder="John Doe"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="modern-input"
                />
              </div>
              
              <div className="form-column">
                <label className="input-label">Status (e.g., HR Manager)</label>
                <Input
                  placeholder="HR Manager"
                  value={formData.status}
                  onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                  className="modern-input"
                />
                
                <label className="input-label">LinkedIn Client ID</label>
                <Input
                  placeholder="Enter LinkedIn Client ID"
                  value={formData.linkedinClientId}
                  onChange={(e) => setFormData({...formData, linkedinClientId: e.target.value})}
                  className="modern-input"
                />
                
                <label className="input-label">LinkedIn Client Secret</label>
                <Input.Password
                  placeholder="Enter LinkedIn Client Secret"
                  value={formData.linkedinClientSecret}
                  onChange={(e) => setFormData({...formData, linkedinClientSecret: e.target.value})}
                  className="modern-input"
                />
              </div>
            </div>
            
            <div className="file-upload-section">
              <label className="input-label">Upload Google Credentials (json)</label>
              <Upload
                accept=".json"
                showUploadList={false}
                beforeUpload={() => false}
                onChange={handleFileChange}
              >
                <div className="file-upload-container">
                  <div className="file-input-label">
                    {formData.credentialsFile 
                      ? formData.credentialsFile.name 
                      : "Select Google credentials file"}
                  </div>
                  <div className="upload-icon">📁</div>
                </div>
              </Upload>
              {formData.credentialsFile && (
                <p className="credential-note">{formData.credentialsFile.name} selected</p>
              )}
            </div>
          </div>
          <motion.div whileHover={{ scale: 1.05 }}>
            <Button
              type="primary"
              onClick={handleSignUp}
              className="submit-button"
              loading={loading}
              block
            >
              Create Account
            </Button>
          </motion.div>
          <div className="switch-auth">
            <p>Already have an Account? <a onClick={() => { setStep('login'); navigate('/login'); }}>Log in</a></p>
          </div>
        </motion.div>
      </div>
    </motion.div>
  );
  const renderServices = () => (
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    animate={{ opacity: 1, y: 0 }}
    className="app-container"
  >
    <div className="app-header">
      <h1 className="title">HR Service Scheduler</h1>
      <p className="app-subtitle">Configure Your Services</p>
    </div>
    <div className="services-dashboard">
      <motion.div
        className="control-panel services"
        whileHover={{ scale: 1.02 }}
        transition={{ type: "spring", stiffness: 300 }}
        style={{ minHeight: "800px" }} // Kept for consistency
      >
        <div className="panel-header">
          <h2 className="section-title">Service Configuration</h2>
          <p className="panel-subtitle">Set up your HR services</p>
        </div>

        <div className="user-welcome">
          <div className="avatar">{userInfo.name ? userInfo.name.charAt(0) : "U"}</div>
          <div className="user-info">
            <h3 className="user-name">Welcome back, {userInfo.name || "User"}</h3>
            <p className="user-status">{userInfo.status || "N/A"}</p>
          </div>
        </div>

        <div className="form-group">
          <div className="services-grid">
            {servicesData.services.map((service, index) => (
              <div key={service.name} className={`service-card ${service.name.toLowerCase()}`}>
                <div className="service-header">
                  <div className="service-title">
                    <div className={`service-icon ${service.name.toLowerCase()}-icon`}>
                      {service.name === "Gmail" && "📧"}
                      {service.name === "Calendar" && "📅"}
                      {service.name === "LinkedIn" && "💼"}
                    </div>
                    <h4 className="service-name">{service.name}</h4>
                  </div>
                  <span className={`service-status ${service.connected ? "connected" : ""}`}>
                    {service.connected ? "Connected" : "Not Connected"}
                  </span>
                </div>

                <div className="service-toggle">
                  <span className="toggle-label">Enable Scheduling</span>
                  <div className="switch-container">
                    <label className="switch-toggle">
                      <input
                        type="checkbox"
                        checked={service.enabled}
                        onChange={(e) => {
                          const newServices = [...servicesData.services];
                          newServices[index].enabled = e.target.checked;
                          setServicesData({ services: newServices });
                        }}
                      />
                      <span className="switch-slider"></span>
                    </label>
                    <span className={`switch-text ${service.enabled ? "on" : ""}`}>
                      {service.enabled ? "ON" : "OFF"}
                    </span>
                  </div>
                </div>

                {service.enabled && (
                  <div className="schedule-config">
                    <div className="schedule-settings">
                      <div className="schedule-detail">
                        <label className="detail-label">Frequency</label>
                        <Select
                          value={service.schedule.frequency}
                          onChange={(value) => {
                            const newServices = [...servicesData.services];
                            newServices[index].schedule.frequency = value;
                            setServicesData({ services: newServices });
                          }}
                          className="schedule-select"
                        >
                          <Option value="daily">Daily</Option>
                          <Option value="hourly">Hourly</Option>
                          <Option value="weekly">Weekly</Option>
                        </Select>
                      </div>

                      <div className="schedule-detail">
                        <label className="detail-label">Time</label>
                        <input
                          type="time"
                          value={service.schedule.time || service.schedule.hour}
                          onChange={(e) => {
                            const newServices = [...servicesData.services];
                            if (service.schedule.frequency === "weekly") {
                              newServices[index].schedule.hour = e.target.value;
                            } else {
                              newServices[index].schedule.time = e.target.value;
                            }
                            setServicesData({ services: newServices });
                          }}
                          className="schedule-time"
                        />
                      </div>

                      {service.schedule.frequency === "weekly" && (
                        <div className="schedule-detail">
                          <label className="detail-label">Day</label>
                          <Select
                            value={service.schedule.day_of_week}
                            onChange={(value) => {
                              const newServices = [...servicesData.services];
                              newServices[index].schedule.day_of_week = value;
                              setServicesData({ services: newServices });
                            }}
                            className="schedule-select"
                          >
                            <Option value="mon">Monday</Option>
                            <Option value="tue">Tuesday</Option>
                            <Option value="wed">Wednesday</Option>
                            <Option value="thu">Thursday</Option>
                            <Option value="fri">Friday</Option>
                            <Option value="sat">Saturday</Option>
                            <Option value="sun">Sunday</Option>
                          </Select>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {service.name === "LinkedIn" && !service.connected && (
                  <Button
                    type="primary"
                    onClick={handleLinkedInAuth}
                    loading={loading}
                    disabled={!credentialStatus?.linkedin?.hasAppCredentials}
                    className="connect-button"
                  >
                    Connect LinkedIn
                  </Button>
                )}
              </div>
            ))}
          </div>
        </div>

        <div className="action-buttons">
          <Button
            type="primary"
            onClick={handleServiceSubmit}
            loading={loading}
            className="submit-button"
          >
            Save Configuration
          </Button>

          <Button
            type="link"
            onClick={() => {
              localStorage.removeItem("token");
              localStorage.removeItem("userId");
              setUserId(null);
              setToken(null);
              setStep("login");
              navigate("/login");
            }}
            className="logout-button"
          >
            Logout
          </Button>
        </div>
      </motion.div>

      <div className="schedule-container" style={{ minHeight: "800px" }}>
        <div className="panel-header">
          <h2 className="section-title">Scheduled Services</h2>
          <p className="panel-subtitle">{servicesData.services.filter((s) => s.enabled).length} active services</p>
        </div>
        {servicesData.services.filter((s) => s.enabled).length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">📋</div>
            <p>No services scheduled yet</p>
            <p>Configure services to get started</p>
          </div>
        ) : (
          <div className="schedule-list">
            {servicesData.services
              .filter((service) => service.enabled)
              .map((service, index) => (
                <div key={index} className="schedule-card">
                  <div className="schedule-header">
                    <div className="service-info">
                      <div className={`schedule-icon ${service.name.toLowerCase()}-icon`}>
                        {service.name === "Gmail" && "📧"}
                        {service.name === "Calendar" && "📅"}
                        {service.name === "LinkedIn" && "💼"}
                      </div>
                      <span className="schedule-name">{service.name}</span>
                      <span className="schedule-status">Active</span>
                    </div>
                  </div>
                  <div className="schedule-details">
                    <div className="detail-item">
                      <span className="detail-label">Frequency:</span>
                      <span className="detail-value">{service.schedule.frequency}</span>
                    </div>
                    <div className="detail-item">
                      <span className="detail-label">Time:</span>
                      <span className="detail-value">{service.schedule.time || service.schedule.hour}</span>
                    </div>
                    {service.schedule.frequency === "weekly" && (
                      <div className="detail-item">
                        <span className="detail-label">Day:</span>
                        <span className="detail-value">
                          {service.schedule.day_of_week === "mon"
                            ? "Monday"
                            : service.schedule.day_of_week === "tue"
                            ? "Tuesday"
                            : service.schedule.day_of_week === "wed"
                            ? "Wednesday"
                            : service.schedule.day_of_week === "thu"
                            ? "Thursday"
                            : service.schedule.day_of_week === "fri"
                            ? "Friday"
                            : service.schedule.day_of_week === "sat"
                            ? "Saturday"
                            : "Sunday"}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              ))}
          </div>
        )}
      </div>
    </div>
  </motion.div>
  );



  console.log('Rendering Scheduler_Design:', { step });

  return (
    <ErrorBoundary>
      <Spin spinning={loading}>
        {step === 'login' && renderLogin()}
        {step === 'signup' && renderSignUp()}
        {step === 'services' && renderServices()}
      </Spin>
    </ErrorBoundary>
  );
};

export default Scheduler_Design;