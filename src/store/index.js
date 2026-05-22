import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '../api/auth'

export const useUserStore = defineStore('user', () => {
  // State
  const _storedUser = localStorage.getItem('user_info')
  const user = ref(_storedUser ? (() => { try { return JSON.parse(_storedUser) } catch { return null } })() : null)
  const token = ref(localStorage.getItem('access_token') || '')
  const refreshToken = ref(localStorage.getItem('refresh_token') || '')
  const isLoading = ref(false)

  // Getters
  const isAuthenticated = computed(() => {
    return !!token.value && !!user.value
  })

  const isGuest = computed(() => {
    return !!localStorage.getItem('guest_mode')
  })

  const username = computed(() => {
    return user.value?.username || ''
  })

  const userEmail = computed(() => {
    return user.value?.email || ''
  })

  // Actions
  async function login(username, password) {
    isLoading.value = true
    try {
      const response = await authApi.login({ username, password })

      if (response.success) {
        // Save token (后端返回格式为 { token, refresh_token, userInfo })
        token.value = response.data.token
        refreshToken.value = response.data.refresh_token || ''
        localStorage.setItem('access_token', response.data.token)
        if (response.data.refresh_token) {
          localStorage.setItem('refresh_token', response.data.refresh_token)
        }

        // 保存用户信息到本地存储
        if (response.data.userInfo) {
          localStorage.setItem('user_info', JSON.stringify(response.data.userInfo))
          user.value = response.data.userInfo
        }

        return { success: true }
      } else {
        return {
          success: false,
          error: response.error || '登录失败'
        }
      }
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || '登录失败'
      }
    } finally {
      isLoading.value = false
    }
  }

  async function register(userData) {
    isLoading.value = true
    try {
      const response = await authApi.register(userData)
      if (response.success) {
        return { success: true, user: response.data }
      } else {
        return {
          success: false,
          error: response.error || '注册失败'
        }
      }
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || '注册失败'
      }
    } finally {
      isLoading.value = false
    }
  }

  async function fetchUserInfo() {
    try {
      const response = await authApi.getMe()
      user.value = response
    } catch (error) {
      // If token is invalid, logout
      await logout()
      throw error
    }
  }

  async function refreshAuthToken() {
    if (!refreshToken.value) {
      await logout()
      return
    }

    try {
      const newToken = await authApi.refreshToken({
        refresh_token: refreshToken.value
      })
      token.value = newToken
      refreshToken.value = localStorage.getItem('refresh_token') || ''
      return newToken
    } catch (error) {
      await logout()
      throw error
    }
  }

  async function logout() {
    // Clear local state
    user.value = null
    token.value = ''
    refreshToken.value = ''

    // Clear localStorage
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('user_info')
    localStorage.removeItem('guest_mode')
  }

  function setGuestMode() {
    localStorage.setItem('guest_mode', 'true')
    user.value = {
      id: 0,
      username: '游客',
      full_name: '游客用户',
      email: 'guest@example.com',
      avatar_url: null,
      is_active: true,
      is_superuser: false
    }
  }

  function checkAuthStatus() {
    const storedToken = localStorage.getItem('access_token')
    const storedUserInfo = localStorage.getItem('user_info')

    if (storedToken) {
      token.value = storedToken
      refreshToken.value = localStorage.getItem('refresh_token') || ''

      // 如果有保存的用户信息，直接使用
      if (storedUserInfo) {
        try {
          user.value = JSON.parse(storedUserInfo)
        } catch (e) {
          console.error('解析用户信息失败:', e)
        }
      }

      // Try to fetch user info to验证token有效性
      fetchUserInfo().catch(() => {
        // If failed, logout
        logout()
      })
    }
  }

  function clearError() {
    // This can be used to clear any error state if needed
  }

  return {
    // State
    user,
    token,
    refreshToken,
    isLoading,

    // Getters
    isAuthenticated,
    username,
    userEmail,

    // Actions
    login,
    register,
    fetchUserInfo,
    refreshAuthToken,
    logout,
    checkAuthStatus,
    setGuestMode,
    clearError,
    isGuest
  }
})

