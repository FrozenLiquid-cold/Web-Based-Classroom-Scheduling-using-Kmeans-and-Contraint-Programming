// API service for backend communication
const API_URL = 'http://localhost:8000/api'

const ENTITY_MAP = {
  college: 'colleges',
  course: 'courses',
  instructor: 'instructors',
  day: 'days',
  subject: 'subjects',
  room: 'rooms',
}

const TIMEOUTS = {
  DEFAULT: 300000, // 5 minutes
  SCHEDULE: 600000 // 10 minutes
}

// Helper: default headers with token
function defaultHeaders(extra = {}) {
  const token = localStorage.getItem('api_token')
  return {
    'Content-Type': 'application/json',
    ...(token && { Authorization: `Bearer ${token}` }),
    ...extra,
  }
}

export async function updateProfile(data) {
  try {
    const result = await apiCall('/auth/profile', {
      method: 'PUT',
      body: JSON.stringify(data),
    })

    // If a new token is issued, update local storage to keep the
    // session consistent with the changed username.
    if (result && result.ok && result.token) {
      localStorage.setItem('api_token', result.token)
      localStorage.setItem(
        'jrmsu.session',
        JSON.stringify({
          role: result.role,
          username: result.username,
          instructorId: result.instructor_id,
        })
      )
    }

    return result
  } catch (error) {
    console.error('Update profile error:', error)
    throw error
  }
}

// Core API call with timeout + error handling
async function apiCall(endpoint, options = {}) {
  const timeout =
    typeof options.timeout === 'number' ? options.timeout : TIMEOUTS.DEFAULT

  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeout)

  try {
    const response = await fetch(`${API_URL}${endpoint}`, {
      ...options,
      headers: defaultHeaders(options.headers),
      signal: controller.signal,
    })

    clearTimeout(timeoutId)

    if (!response.ok) {
      const error = await response.json().catch(() => null)
      throw new Error(
        (error && (error.detail || error.message || error.error)) ||
        `HTTP ${response.status}: ${response.statusText}`
      )
    }

    if (response.status === 204 || response.headers.get('content-length') === '0') {
      return null
    }

    return await response.json()
  } catch (error) {
    clearTimeout(timeoutId)
    if (error.name === 'AbortError') {
      throw new Error(
        `Request timeout after ${timeout / 1000}s — schedule generation took too long.`
      )
    }
    console.error('API call error:', error)
    throw error
  }
}

// Entity CRUD operations
export async function list(entity) {
  const backendEntity = ENTITY_MAP[entity] || entity
  try {
    return await apiCall(`/${backendEntity}`)
  } catch (error) {
    console.error(`Error listing ${entity}:`, error)
    return []
  }
}

export async function get(entity, id) {
  const backendEntity = ENTITY_MAP[entity] || entity
  return apiCall(`/${backendEntity}/${id}`)
}

export async function create(entity, data) {
  const backendEntity = ENTITY_MAP[entity] || entity
  return apiCall(`/${backendEntity}`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function update(entity, id, data) {
  const backendEntity = ENTITY_MAP[entity] || entity
  return apiCall(`/${backendEntity}/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export async function remove(entity, id) {
  const backendEntity = ENTITY_MAP[entity] || entity
  return apiCall(`/${backendEntity}/${id}`, { method: 'DELETE' })
}

// Authentication
export async function login(role, username, password) {
  try {
    const result = await apiCall(`/auth/login/${role}`, {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    })

    if (result.token) {
      localStorage.setItem('api_token', result.token)
      localStorage.setItem(
        'jrmsu.session',
        JSON.stringify({
          role: result.role,
          username: result.username,
          instructorId: result.instructor_id,
        })
      )

      // For instructors, mark that they should update their
      // credentials on first login (per browser). This flag is
      // cleared after they save changes in the Account page.
      if (result.role === 'instructor' && result.instructor_id) {
        const key = `jrmsu.instructor.mustChange.${result.instructor_id}`
        if (localStorage.getItem(key) === null) {
          localStorage.setItem(key, 'true')
        }
      }
      return { ok: true, ...result }
    }

    return { ok: false, message: result.detail || 'Invalid credentials' }
  } catch (error) {
    console.error('Login error:', error)
    return { ok: false, message: error.message || 'Login failed' }
  }
}

export async function logout() {
  try {
    await apiCall('/auth/logout', { method: 'POST' })
  } catch (error) {
    console.error('Logout error:', error)
  } finally {
    localStorage.removeItem('api_token')
    localStorage.removeItem('jrmsu.session')
  }
}

// Schedule operations
export async function generateSchedule(
  courseId,
  yearOrYears,
  semester,
  subjectIds = null,
  options = {}
) {
  const { waitSeconds, ...extraPayload } = options || {}
  const payload = {
    course_id: courseId,
    semester,
    subject_ids: subjectIds,
    ...extraPayload,
  }

  if (Array.isArray(yearOrYears)) {
    payload.years = yearOrYears
  } else if (typeof yearOrYears === 'number') {
    payload.year = yearOrYears
  } else if (yearOrYears == null && !payload.year && !payload.years) {
    payload.years = [1, 2, 3, 4]
  }

  const query = typeof waitSeconds === 'number' ? `?wait_seconds=${waitSeconds}` : ''

  return apiCall(`/schedule/generate${query}`, {
    method: 'POST',
    body: JSON.stringify(payload),
    timeout: TIMEOUTS.SCHEDULE,
  })
}

export async function saveSchedule(courseId, year, semester, items) {
  return apiCall('/schedule/save', {
    method: 'POST',
    body: JSON.stringify({ course_id: courseId, year, semester, items }),
  })
}

export async function loadSchedule(courseId, semester, year = null, instructorId = null) {
  const params = new URLSearchParams({ course_id: courseId, semester })
  if (year !== null) params.append('year', year)
  if (instructorId) params.append('instructor_id', instructorId)
  return apiCall(`/schedule/load?${params.toString()}`)
}

export async function getInstructorWorkload(instructorId, semester) {
  if (!instructorId) throw new Error('Missing instructorId')
  const params = new URLSearchParams({ semester })
  return apiCall(`/instructors/${encodeURIComponent(instructorId)}/workload?${params.toString()}`)
}

export async function deleteSchedule(courseId, year, semester) {
  const params = new URLSearchParams({ course_id: courseId, year, semester })
  return apiCall(`/schedule/delete?${params.toString()}`, { method: 'DELETE' })
}

export async function getScheduleStatus(jobId) {
  return apiCall(`/schedule/status?job_id=${encodeURIComponent(jobId)}`, {
    timeout: TIMEOUTS.SCHEDULE,
  })
}

export async function scheduleCourse(courseId, year, semester, blocksCount) {
  const response = await fetch(`${API_URL}/schedule_course`, {
    method: 'POST',
    headers: defaultHeaders(),
    body: JSON.stringify({
      course_id: courseId,
      year,
      semester,
      blocks_count: blocksCount,
    }),
  })

  const rawBody = await response.text()
  let json

  if (rawBody) {
    try {
      json = JSON.parse(rawBody)
    } catch (parseError) {
      throw new Error('Server returned an unexpected response. Please try again.')
    }
  } else {
    json = {}
  }

  if (!response.ok) {
    if (response.status === 409 && json.status === 'no_feasible_schedule') {
      return json
    }
    throw new Error(json.detail || json.message || rawBody || 'Failed to generate schedule')
  }

  return json
}

export async function validateScheduleItem(item) {
  return apiCall('/validate/schedule-item', {
    method: 'POST',
    body: JSON.stringify(item),
  })
}
