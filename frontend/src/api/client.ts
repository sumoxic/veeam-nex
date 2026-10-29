/**
 * HTTP 客户端。
 *
 * 后端统一响应封装：{ code, message, data }，code=0 表示成功。
 * 这里做三件事：
 *   1. 解包 data，业务层拿到的直接是后端 data 字段；
 *   2. 401 时自动刷新令牌并重放原请求（并发 401 只刷新一次）；
 *   3. 业务错误统一抛 ApiError，页面只需 try/catch 一次。
 */
import axios, {
  type AxiosError,
  type AxiosInstance,
  type AxiosRequestConfig,
  type AxiosResponse,
} from 'axios'

export const ACCESS_TOKEN_KEY = 'vi_access_token'
export const REFRESH_TOKEN_KEY = 'vi_refresh_token'

/** 后端业务错误码：未登录 / 令牌失效 */
const CODE_UNAUTHORIZED = 40100

export class ApiError extends Error {
  code: number

  constructor(code: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.code = code
  }
}

const instance: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api/v1',
  timeout: 60000,
  withCredentials: true,
})

/** 并发 401 时共享同一个刷新请求，避免 N 次刷新把用户踢下线 */
let refreshPromise: Promise<string> | null = null

function readToken(key: string): string {
  return localStorage.getItem(key) || ''
}

export function writeTokens(accessToken: string, refreshToken?: string) {
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken)
  if (refreshToken) localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken)
}

export function clearTokens() {
  localStorage.removeItem(ACCESS_TOKEN_KEY)
  localStorage.removeItem(REFRESH_TOKEN_KEY)
}

export function hasToken(): boolean {
  return Boolean(readToken(ACCESS_TOKEN_KEY))
}

/** 用刷新令牌换新的访问令牌 */
async function doRefresh(): Promise<string> {
  const refreshToken = readToken(REFRESH_TOKEN_KEY)
  const response = await axios.post(
    `${import.meta.env.VITE_API_BASE || '/api/v1'}/auth/refresh`,
    {},
    { headers: refreshToken ? { 'X-Refresh-Token': refreshToken } : {}, withCredentials: true },
  )
  const body = response.data
  if (!body || body.code !== 0 || !body.data?.access_token) {
    throw new ApiError(body?.code ?? CODE_UNAUTHORIZED, body?.message || '登录已过期')
  }
  writeTokens(body.data.access_token, body.data.refresh_token)
  return body.data.access_token as string
}

/** 刷新令牌（单飞） */
function refreshAccessToken(): Promise<string> {
  if (!refreshPromise) {
    refreshPromise = doRefresh().finally(() => {
      refreshPromise = null
    })
  }
  return refreshPromise
}

// ---- 请求拦截：带上访问令牌 ----
instance.interceptors.request.use((config) => {
  const token = readToken(ACCESS_TOKEN_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// ---- 响应拦截：解包 + 401 自动刷新 ----
instance.interceptors.response.use(
  async (response: AxiosResponse) => {
    const body = response.data
    // 非标准响应（例如文件下载）原样返回
    if (!body || typeof body !== 'object' || !('code' in body)) {
      return response
    }
    if (body.code === 0) {
      return { ...response, data: body.data } as AxiosResponse
    }
    if (body.code === CODE_UNAUTHORIZED) {
      try {
        const token = await refreshAccessToken()
        const config = response.config as AxiosRequestConfig & { _retried?: boolean }
        if (config._retried) {
          clearTokens()
          throw new ApiError(body.code, body.message || '登录已过期')
        }
        config._retried = true
        config.headers = { ...config.headers, Authorization: `Bearer ${token}` }
        return instance.request(config)
      } catch {
        clearTokens()
        throw new ApiError(body.code, body.message || '登录已过期')
      }
    }
    throw new ApiError(body.code, body.message || '请求失败')
  },
  async (error: AxiosError) => {
    const response = error.response
    const body = response?.data as { code?: number; message?: string } | undefined
    if (response?.status === 401) {
      try {
        const token = await refreshAccessToken()
        const config = error.config as AxiosRequestConfig & { _retried?: boolean }
        if (config && !config._retried) {
          config._retried = true
          config.headers = { ...config.headers, Authorization: `Bearer ${token}` }
          return instance.request(config)
        }
      } catch {
        clearTokens()
      }
    }
    if (body?.code !== undefined) {
      throw new ApiError(body.code, body.message || '请求失败')
    }
    throw error
  },
)

/** GET，返回后端的 data 字段 */
export async function get<T>(url: string, params?: Record<string, unknown>): Promise<T> {
  const response = await instance.get(url, { params })
  return response.data as T
}

/** POST，返回后端的 data 字段 */
export async function post<T>(
  url: string,
  data?: unknown,
  config?: AxiosRequestConfig,
): Promise<T> {
  const response = await instance.post(url, data, config)
  return response.data as T
}

/** PUT，返回后端的 data 字段 */
export async function put<T>(
  url: string,
  data?: unknown,
  config?: AxiosRequestConfig,
): Promise<T> {
  const response = await instance.put(url, data, config)
  return response.data as T
}

/** DELETE，返回后端的 data 字段 */
export async function del<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  const response = await instance.delete(url, config)
  return response.data as T
}

export default instance
