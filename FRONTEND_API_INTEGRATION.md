# Frontend API Integration - Summary

The frontend has been updated to use the PostgreSQL database via the API instead of localStorage.

## ✅ Completed Updates

### Core Files
- ✅ `src/services/api.js` - Created API service with all endpoints
- ✅ `src/store/db.js` - Updated to use API calls (async)
- ✅ `src/store/auth.js` - Updated to use API authentication (async)

### Pages Updated
- ✅ `src/pages/Auth/Login.jsx` - Async login
- ✅ `src/pages/Auth/LoginRegistrar.jsx` - Async login
- ✅ `src/pages/Registrar/College.jsx` - Async CRUD
- ✅ `src/pages/Registrar/Course.jsx` - Async CRUD
- ✅ `src/pages/Registrar/Schedule.jsx` - Async schedule operations
- ✅ `src/pages/Registrar/Instructor.jsx` - Async CRUD

## ✅ All Pages Updated

All pages have been successfully updated to use async API operations:

1. ✅ **src/pages/Registrar/Subject.jsx** - Updated
2. ✅ **src/pages/Registrar/Room.jsx** - Updated
3. ✅ **src/pages/Registrar/Day.jsx** - Updated
4. ✅ **src/pages/Registrar/Curriculum.jsx** - Updated
5. ✅ **src/pages/Instructor/Schedule.jsx** - Updated (with field name mapping)
6. ✅ **src/pages/Instructor/Account.jsx** - Updated (with field name mapping)
7. ✅ **src/pages/Admin/Users.jsx** - Updated

## Field Name Mapping

The backend uses snake_case while frontend may use camelCase. The API service handles entity name mapping, but field names need attention:

- `collegeId` → `college_id` (for courses)
- `firstName` → `first_name` (for instructors)
- `lastName` → `last_name` (for instructors)

The updated pages handle both formats for backward compatibility.

## How to Update Remaining Pages

### Pattern for CRUD Pages (Subject, Room, Day):

```javascript
// Before:
function load(){ setItems(list('entity')) }
useEffect(()=>{ load() },[])

// After:
async function load(){ 
	const data = await list('entity')
	setItems(data)
}
useEffect(()=>{ load() },[])

// Before:
function onSave(e){
	e.preventDefault()
	upsert('entity', item)
	load()
}

// After:
async function onSave(e){
	e.preventDefault()
	try {
		await upsert('entity', item)
		await load()
	} catch (error) {
		setError(error.message || 'Failed to save')
	}
}

// Before:
function onDelete(id){
	remove('entity', id)
	load()
}

// After:
async function onDelete(id){
	if (!confirm('Delete?')) return
	try {
		await remove('entity', id)
		await load()
	} catch (error) {
		alert(error.message || 'Failed to delete')
	}
}
```

## Testing

1. Start the backend: `cd api && python run.py`
2. Start the frontend: `npm run dev`
3. Test login with: `registrar/1234`, `instructor/1234`, or `admin/1234`
4. Test CRUD operations on each entity
5. Test schedule generation and saving

## Notes

- All API calls are now async - make sure to use `await` or `.then()`
- Error handling is important - wrap API calls in try/catch
- The API base URL is `http://localhost:8000/api` (configurable in `src/services/api.js`)

