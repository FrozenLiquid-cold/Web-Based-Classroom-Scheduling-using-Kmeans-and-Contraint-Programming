import { Routes, Route, Navigate } from 'react-router-dom'
import Landing from './pages/Landing'
import Login from './pages/Auth/Login'
import RegistrarLayout from './layouts/RegistrarLayout'
import InstructorLayout from './layouts/InstructorLayout'
import Dashboard from './pages/Registrar/Dashboard'
import InstructorDashboard from './pages/Instructor/Dashboard'
import College from './pages/Registrar/College'
import Course from './pages/Registrar/Program'
import Instructor from './pages/Registrar/Instructor'
import Day from './pages/Registrar/Day'
import Subject from './pages/Registrar/Subject'
import Room from './pages/Registrar/Room'
import Buildings from './pages/Registrar/Buildings'
import BuildingDistances from './pages/Registrar/BuildingDistances'
import Schedule from './pages/Registrar/Schedule'
import InstructorSchedule from './pages/Instructor/Schedule'
import InstructorSwapRequests from './pages/Instructor/SwapRequests'
import Curriculum from './pages/Registrar/Curriculum'
import Settings from './pages/Registrar/Settings'

import RegistrarAccount from './pages/Registrar/Account'
import InstructorAccount from './pages/Instructor/Account'
import AdminLayout from './layouts/AdminLayout'
import AdminDashboard from './pages/Admin/Dashboard'
import AdminUsers from './pages/Admin/Users'
import AdminRoomSchedule from './pages/Admin/RoomSchedule'

import { isAuthenticated } from './store/auth'

function Guard({ children, role }) {
	const targetPath = role === 'instructor' ? '/login/instructor' : role === 'admin' ? '/login/admin' : '/login/registrar'
	return isAuthenticated(role) ? children : <Navigate to={targetPath} replace />
}

export default function App() {
	return (
		<Routes>
			<Route path="/" element={<Landing />} />
			<Route path="/login/:role" element={<Login />} />

			<Route
				path="/r"
				element={
					<Guard role="registrar">
						<RegistrarLayout />
					</Guard>
				}
			>
				<Route index element={<Navigate to="dashboard" replace />} />
				<Route path="dashboard" element={<Dashboard />} />
				<Route path="college" element={<College />} />
				<Route path="course" element={<Course />} />
				<Route path="instructor" element={<Instructor />} />
				<Route path="day" element={<Day />} />
				<Route path="subject" element={<Subject />} />
				<Route path="room" element={<Room />} />
				<Route path="buildings" element={<Buildings />} />
				<Route path="distances" element={<BuildingDistances />} />
				<Route path="curriculum" element={<Curriculum />} />
				<Route path="schedule" element={<Schedule />} />
				<Route path="settings" element={<Settings />} />

				<Route path="account" element={<RegistrarAccount />} />
			</Route>

			<Route
				path="/i"
				element={
					<Guard role="instructor">
						<InstructorLayout />
					</Guard>
				}
			>
				<Route index element={<Navigate to="dashboard" replace />} />
				<Route path="dashboard" element={<InstructorDashboard />} />
				<Route path="schedule" element={<InstructorSchedule />} />
				<Route path="swap-requests" element={<InstructorSwapRequests />} />
				<Route path="account" element={<InstructorAccount />} />

			</Route>

			<Route
				path="/a"
				element={
					<Guard role="admin">
						<AdminLayout />
					</Guard>
				}
			>
				<Route index element={<Navigate to="dashboard" replace />} />
				<Route path="dashboard" element={<AdminDashboard />} />
				<Route path="users" element={<AdminUsers />} />
				<Route path="room-schedule" element={<AdminRoomSchedule />} />

			</Route>
		</Routes>
	)
}

