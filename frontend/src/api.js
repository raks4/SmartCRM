const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api'

async function api(path, options = {}) {
    const response = await fetch(`${API_BASE}${path}`, {
        credentials: 'include',
        headers: {
            'Content-Type': 'application/json',
            ...(options.headers || {}),
        },
        ...options,
    })

    const data = await response.json().catch(() => ({}))

    if (!response.ok) {
        const error = new Error(data.detail || 'Request failed.')
        error.status = response.status
        throw error
    }

    return data
}

export const authApi = {
    login: (payload) => api('/auth/login/', { method: 'POST', body: JSON.stringify(payload) }),
    logout: () => api('/auth/logout/', { method: 'POST' }),
    session: () => api('/auth/session/'),
}

export const leadApi = {
    list: () => api('/leads/'),
    create: (payload) => api('/leads/', { method: 'POST', body: JSON.stringify(payload) }),
    dashboard: () => api('/dashboard/'),
}
