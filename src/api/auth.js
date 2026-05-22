import axios from 'axios'

// Create axios instance
const api = axios.create({
  baseURL: 'http://localhost:8000/api',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token')
    const isGuest = localStorage.getItem('guest_mode')

    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    } else if (isGuest) {
      // For guest mode, we can add a special header or use a default token
      config.headers['X-Guest-Mode'] = 'true'
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response.data,
  async (error) => {
    const originalRequest = error.config

    // Handle 401 errors (unauthorized)
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true

      try {
        // Try to refresh token
        const refreshToken = localStorage.getItem('refresh_token')
        if (refreshToken) {
          const response = await axios.post(
            `${api.defaults.baseURL}/user/refresh`,
            { refresh_token: refreshToken }
          )

          // Save new token
          const newToken = response.data?.data?.token
          const newRefreshToken = response.data?.data?.refresh_token
          if (!newToken) throw new Error('无效的刷新响应')
          localStorage.setItem('access_token', newToken)
          if (newRefreshToken) localStorage.setItem('refresh_token', newRefreshToken)
          originalRequest.headers.Authorization = `Bearer ${newToken}`

          // Retry original request
          return api(originalRequest)
        }
      } catch (refreshError) {
        // Refresh failed, redirect to login
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        window.location.href = '/login'
        return Promise.reject(refreshError)
      }
    }

    return Promise.reject(error)
  }
)

// 处理后端标准响应格式的辅助函数
const handleResponse = (response) => {
  // 后端返回格式: { code: 200, message: "成功", data: {...} }
  if (response.code === 200 || response.code === 0) {
    return response.data
  }
  throw new Error(response.message || '请求失败')
}

export const authApi = {
  // 用户登录
  async login(credentials) {
    const response = await api.post('/user/login', credentials)
    // 处理后端响应格式
    if (response.code === 200) {
      const { token, refresh_token, userInfo } = response.data
      // 保存 token 和用户信息
      localStorage.setItem('access_token', token)
      if (refresh_token) localStorage.setItem('refresh_token', refresh_token)
      localStorage.setItem('user_info', JSON.stringify(userInfo))
      return { success: true, data: { token, refresh_token, userInfo } }
    }
    return { success: false, error: response.message }
  },

  // 用户注册
  async register(userData) {
    const response = await api.post('/user/register', userData)
    // 处理后端响应格式
    if (response.code === 200) {
      return { success: true, data: response.data }
    }
    return { success: false, error: response.message }
  },

  // 获取当前用户信息
  async getMe() {
    const response = await api.get('/user/info')
    if (response.code === 200) {
      return response.data
    }
    throw new Error(response.message)
  },

  // 更新用户信息
  async updateUser(userData) {
    const response = await api.put('/user/update', userData)
    if (response.code === 200) {
      // 更新本地存储的用户信息
      localStorage.setItem('user_info', JSON.stringify(response.data))
      return response.data
    }
    throw new Error(response.message)
  },

  // 修改密码
  async changePassword(passwordData) {
    const response = await api.put('/user/password', passwordData)
    if (response.code === 200) {
      return { success: true, message: response.message }
    }
    return { success: false, error: response.message }
  },

  // 刷新 token（如果后端实现了）
  async refreshToken(refreshData) {
    const response = await api.post('/user/refresh', refreshData)
    if (response.code === 200) {
      const { token, refresh_token } = response.data
      localStorage.setItem('access_token', token)
      if (refresh_token) localStorage.setItem('refresh_token', refresh_token)
      return token
    }
    throw new Error(response.message)
  },

  // 退出登录
  logout() {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('user_info')
    localStorage.removeItem('guest_mode')
  },

  // 获取 AI 配置
  async getAIConfig() {
    const response = await api.get('/user/ai-config')
    if (response.code === 200) return response.data
    throw new Error(response.message)
  },

  // 保存 AI 配置
  async updateAIConfig(config) {
    const response = await api.put('/user/ai-config', config)
    if (response.code === 200) return response.data
    throw new Error(response.message)
  },
}

// 导出原始 api 实例供其他模块使用
export default api