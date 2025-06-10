import axios from 'axios';

const API_URL = 'http://localhost:8001';

const getAuthHeaders = (token) => ({
  'Authorization': token.startsWith('Bearer ') ? token : `Bearer ${token}`,
  'Content-Type': 'application/json'
});

const withRetry = async (fn, retries = 3, delay = 1000) => {
  for (let attempt = 1; attempt <= retries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      if (attempt === retries || !error.message.includes('Network Error')) {
        throw error;
      }
      console.warn(`Attempt ${attempt} failed, retrying after ${delay}ms...`);
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }
};

export const createUser = async (payload) => {
  try {
    console.log('createUser payload:', payload);
    const response = await withRetry(() => 
      axios.post(`${API_URL}/users`, payload)
    );
    console.log('createUser response:', response.data);
    return response.data;
  } catch (error) {
    const errorMessage = error.response?.data?.detail || error.message || 'Failed to create user';
    console.error('createUser error:', errorMessage, error);
    throw new Error(errorMessage);
  }
};

export const login = async (payload) => {
  try {
    console.log('login payload:', payload);
    const response = await withRetry(() => 
      axios.post(`${API_URL}/login`, payload)
    );
    console.log('login response:', response.data);
    return response.data;
  } catch (error) {
    const errorMessage = error.response?.data?.detail || error.message || 'Login failed';
    console.error('login error:', errorMessage, error);
    throw new Error(errorMessage);
  }
};

export const uploadCredentials = async (userId, file, token) => {
  try {
    console.log('uploadCredentials for userId:', userId);
    const formData = file instanceof FormData ? file : (() => {
      const fd = new FormData();
      fd.append('credentials', file);
      return fd;
    })();
    const response = await withRetry(() => 
      axios.post(
        `${API_URL}/users/${userId}/upload-credentials`,
        formData,
        { headers: { ...getAuthHeaders(token), 'Content-Type': 'multipart/form-data' } }
      )
    );
    console.log('uploadCredentials response:', response.data);
    return response.data;
  } catch (error) {
    const errorMessage = error.response?.data?.detail || error.message || 'Failed to upload credentials';
    console.error('uploadCredentials error:', errorMessage, error);
    throw new Error(errorMessage);
  }
};

export const initiateGoogleAuth = async (userId, token) => {
  try {
    console.log('initiateGoogleAuth for userId:', userId);
    const response = await withRetry(() => 
      axios.get(
        `${API_URL}/users/${userId}/initiate-google-auth`,
        { headers: { ...getAuthHeaders(token) } }
      )
    );
    console.log('initiateGoogleAuth response:', response.data);
    return response.data;
  } catch (error) {
    const errorMessage = error.response?.data?.detail || error.message || 'Failed to initiate Google auth';
    console.error('initiateGoogleAuth error:', errorMessage, error);
    throw new Error(errorMessage);
  }
};

export const completeGoogleAuth = async (userId, token, code, state) => {
  if (!userId || typeof userId !== 'string') {
    throw new Error('Invalid userId: must be a non-empty string');
  }
  if (!token || typeof token !== 'string') {
    throw new Error('Invalid token: must be a non-empty string');
  }
  if (!code || typeof code !== 'string') {
    throw new Error('Invalid code: must be a non-empty string');
  }

  const apiEndpoint = `${API_URL}/users/${userId}/google-auth-complete`;

  try {
    console.log('Initiating completeGoogleAuth', {
      userId,
      code,
      tokenPreview: token.substring(0, 10) + '...',
      apiEndpoint,
      timestamp: new Date().toISOString(),
    });

    const response = await withRetry(() => 
      axios.post(
        apiEndpoint,
        { code, state },
        {
          headers: {
            ...getAuthHeaders(token),
            'Content-Type': 'application/json',
          },
        }
      )
    );

    console.log('completeGoogleAuth succeeded', {
      status: response.status,
      data: response.data,
      timestamp: new Date().toISOString(),
    });

    return { data: response.data, code };
  } catch (error) {
    const status = error.response?.status;
    const detail = error.response?.data?.detail;
    const errorMessage = detail || error.message || 'Failed to complete Google authentication';

    console.error('completeGoogleAuth failed', {
      userId,
      code,
      status,
      errorMessage,
      detail,
      stack: error.stack,
      timestamp: new Date().toISOString(),
    });

    const thrownError = new Error(errorMessage);
    thrownError.status = status;
    throw thrownError;
  }
};

export const updateUserServices = async (payload, token) => {
  try {
    console.log('updateUserServices payload:', payload);
    const response = await withRetry(() => 
      axios.post(
        `${API_URL}/users/${payload.user_id}/services`,
        payload,
        { headers: { ...getAuthHeaders(token) } }
      )
    );
    console.log('updateUserServices response:', response.data);
    return response.data;
  } catch (error) {
    const errorMessage = error.response?.data?.message || error.message || 'Failed to update services';
    console.error('updateUserServices error:', errorMessage, error);
    throw new Error(errorMessage);
  }
};

export const getUserInfo = async (userId, token) => {
  try {
    console.log('getUserInfo for userId:', userId);
    const response = await withRetry(() => 
      axios.get(
        `${API_URL}/users/${userId}`,
        { headers: { ...getAuthHeaders(token) } }
      )
    );
    console.log('getUserInfo response:', response.data);
    return response.data;
  } catch (error) {
    const errorMessage = error.response?.data?.message || error.message || 'Failed to get user info';
    console.error('getUserInfo error:', errorMessage, error);
    throw new Error(errorMessage);
  }
};

export const getCredentialsStatus = async (userId, token) => {
  try {
    console.log('getCredentialsStatus for user:', userId);
    const response = await withRetry(() => 
      axios.get(
        `${API_URL}/users/${userId}/credentials-status`,
        { headers: { ...getAuthHeaders(token) } }
      )
    );
    console.log('getCredentialsStatus response:', response.data);
    return {
      google: response.data.google,
      linkedin: {
        hasAppCredentials: response.data.linkedin.configured,
        valid: response.data.linkedin.valid
      }
    };
  } catch (error) {
    const errorMessage = error.response?.data?.detail || error.message || 'Failed to get credentials status';
    console.error('getCredentialsStatus error:', errorMessage, error);
    throw new Error(errorMessage);
  }
};

export const saveLinkedInAppCredentials = async (userId, token, credentials) => {
  try {
    console.log('Saving LinkedIn credentials for user:', userId);
    const response = await withRetry(() => 
      axios.post(
        `${API_URL}/users/${userId}/linkedin-app`,
        credentials,
        {
          headers: {
            ...getAuthHeaders(token),
            'Content-Type': 'application/json'
          }
        }
      )
    );
    console.log('LinkedIn credentials saved:', response.data);
    return response.data;
  } catch (error) {
    const errorMessage = error.response?.data?.detail || 
                         error.message || 
                         'Failed to save LinkedIn credentials';
    console.error('saveLinkedInAppCredentials error:', errorMessage, error);
    throw new Error(errorMessage);
  }
};

export const initiateLinkedInAuth = async (userId, token) => {
  console.log('initiateLinkedInAuth called', { userId, token: token?.substring(0, 10) + '...' });
  try {
    const response = await withRetry(() => 
      axios.get(
        `${API_URL}/users/${userId}/initiate-linkedin-auth`,
        { headers: { ...getAuthHeaders(token) } }
      )
    );
    console.log('initiateLinkedInAuth success', response.data);
    return response.data;
  } catch (error) {
    console.error('initiateLinkedInAuth error:', {
      message: error.message,
      status: error.response?.status,
      data: error.response?.data,
    });
    throw new Error(error.response?.data?.detail || error.message || 'Failed to initiate LinkedIn authentication');
  }
};
export const completeLinkedInAuth = async (userId, token, code, state) => {
  try {
    console.log('Completing LinkedIn auth for user:', userId);
    const response = await withRetry(() => 
      axios.post(
        `${API_URL}/users/${userId}/linkedin-auth-complete`,
        { code, state },
        {
          headers: {
            ...getAuthHeaders(token)
          }
        }
      )
    );
    console.log('LinkedIn auth completed:', response.data);
    return response.data;
  } catch (error) {
    const errorMessage = error.response?.data?.detail || 
                         error.message || 
                         'Failed to complete LinkedIn authentication';
    console.error('completeLinkedInAuth error:', errorMessage, error);
    throw new Error(errorMessage);
  }
};