import * as api from '../services/api'

// Debug logging flag (disable in production)
const DEBUG = import.meta.env.DEV;

// Keep seedIfEmpty for backward compatibility (no-op since we use API now)
export function seedIfEmpty(seed) {
	// No longer needed - data comes from database
	if (DEBUG) {
		console.log('seedIfEmpty called but data now comes from API');
	}
}

// Cache for list() calls to prevent duplicate API requests
// Use window object to persist across hot reloads
const getCache = () => {
	if (!window.__dbListCache) {
		window.__dbListCache = {
			cache: new Map(),
			pending: new Map()
		};
	}
	return window.__dbListCache;
};

const CACHE_TTL = 30000; // 30 seconds cache

// List entities from API with caching and request deduplication
export async function list(entity) {
	const { cache, pending } = getCache();
	const cacheKey = entity;
	
	// Check cache first - synchronous check
	const cached = cache.get(cacheKey);
	if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
		// Return cached data immediately (no API call)
		return cached.data;
	}
	
	// Check if there's already a pending request
	if (pending.has(cacheKey)) {
		// Return the existing promise to deduplicate concurrent requests
		return pending.get(cacheKey);
	}
	
	// Create promise FIRST, then store it synchronously BEFORE any async operations
	// This ensures the second call will always see the pending request
	const promise = (async () => {
		try {
			const data = await api.list(entity);
			const result = Array.isArray(data) ? data : [];
			
			// Cache the result
			cache.set(cacheKey, {
				data: result,
				timestamp: Date.now()
			});
			
			return result;
		} catch (error) {
			if (DEBUG) {
				console.error(`Error listing ${entity}:`, error);
			}
			// On error, remove from cache and pending
			cache.delete(cacheKey);
			return [];
		} finally {
			// Remove from pending requests when done
			// Reduced delay to 500ms - enough for deduplication but less memory overhead
			setTimeout(() => {
				pending.delete(cacheKey);
			}, 500);
		}
	})();
	
	// Store promise SYNCHRONOUSLY and IMMEDIATELY - this is the critical line
	// Both calls will execute this, but the second one will see the first's promise
	pending.set(cacheKey, promise);
	
	return promise;
}

// Upsert (create or update) entity via API
export async function upsert(entity, item) {
	try {
		const result = item.id 
			? await api.update(entity, item.id, item)
			: await api.create(entity, item);
		// Invalidate cached list for this entity so UI refreshes
		// immediately after add/edit.
		const { cache } = getCache();
		cache.delete(entity);
		return result;
	} catch (error) {
		if (DEBUG) {
			console.error(`Error upserting ${entity}:`, error);
		}
		throw error;
	}
}

// Remove entity via API
export async function remove(entity, id) {
	try {
		await api.remove(entity, id);
		// Invalidate cached list for this entity so UI reflects
		// deletions immediately.
		const { cache } = getCache();
		cache.delete(entity);
	} catch (error) {
		if (DEBUG) {
			console.error(`Error removing ${entity}:`, error);
		}
		throw error;
	}
}

// Save key - handles schedule keys specially
export async function saveKey(key, value) {
	// Handle schedule keys: jrmsu.schedule.{courseId}.{year}.{sem}
	if (key.startsWith('jrmsu.schedule.')) {
		const parts = key.split('.');
		if (parts.length === 5) {
			const courseId = parseInt(parts[2]);
			const year = parseInt(parts[3]);
			const semester = parseInt(parts[4]);
			
			if (courseId && year && semester) {
				try {
					await api.saveSchedule(courseId, year, semester, value);
					return;
				} catch (error) {
					if (DEBUG) {
						console.error('Error saving schedule:', error);
					}
					throw error;
				}
			}
		}
	}
	
	// Fallback to localStorage for other keys (if needed)
	try {
		localStorage.setItem(key, JSON.stringify(value));
	} catch (error) {
		if (DEBUG) {
			console.error('LocalStorage save failed:', error);
		}
		// Don't throw - localStorage failures shouldn't break the app
	}
}

// Get key - handles schedule keys specially
export async function getKey(key, fallback = null) {
	// Handle schedule keys: jrmsu.schedule.{courseId}.{year}.{sem}
	if (key.startsWith('jrmsu.schedule.')) {
		const parts = key.split('.');
		if (parts.length === 5) {
			const courseId = parseInt(parts[2]);
			const year = parseInt(parts[3]);
			const semester = parseInt(parts[4]);
			
			if (courseId && year && semester) {
				try {
					const result = await api.loadSchedule(courseId, semester, year);
					return result?.items ?? fallback;
				} catch (error) {
					if (DEBUG) {
						console.error('Error loading schedule:', error);
					}
					return fallback;
				}
			}
		}
		// Invalid schedule key format - return fallback
		return fallback;
	}
	
	// Fallback to localStorage for other keys
	try {
		const val = localStorage.getItem(key);
		return val ? JSON.parse(val) : fallback;
	} catch (error) {
		// Parse error or localStorage access error - always return fallback
		if (DEBUG) {
			console.error('Error reading from localStorage:', error);
		}
		return fallback;
	}
}

