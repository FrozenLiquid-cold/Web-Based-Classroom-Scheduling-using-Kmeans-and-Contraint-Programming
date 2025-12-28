import * as api from '../services/api'

const SESSION_KEY = 'jrmsu.session'

export function isAuthenticated(role) {
	try {
		const session = JSON.parse(localStorage.getItem(SESSION_KEY) || 'null')
		if (!session) return false
		if (role) {
			return session.role === role
		}
		return !!(session && (session.role === 'registrar' || session.role === 'instructor' || session.role === 'admin'))
	} catch {
		return false
	}
}

export async function loginRegistrar(username, password) {
	try {
		const result = await api.login('registrar', username, password)
		return result
	} catch (error) {
		return { ok: false, message: error.message || 'Login failed' }
	}
}

export async function loginInstructor(username, password) {
	try {
		const result = await api.login('instructor', username, password)
		return result
	} catch (error) {
		return { ok: false, message: error.message || 'Login failed' }
	}
}

export async function loginAdmin(username, password) {
	try {
		const result = await api.login('admin', username, password)
		return result
	} catch (error) {
		return { ok: false, message: error.message || 'Login failed' }
	}
}

export async function logout() {
	await api.logout()
}

