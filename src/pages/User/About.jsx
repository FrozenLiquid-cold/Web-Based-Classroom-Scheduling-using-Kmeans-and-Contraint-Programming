import { useNavigate } from 'react-router-dom'
import { logout } from '../../store/auth'

export default function About(){
    const navigate = useNavigate()
	return (
		<div>
            <div className="flex items-center justify-between mb-4">
                <h1 className="text-navy text-xl font-semibold">ABOUT</h1>
                <button className="px-3 py-1 rounded bg-red-600 text-white text-xs" onClick={()=>{ logout(); navigate('/login/registrar') }}>Log out</button>
            </div>
			<div className="text-sm text-gray-600">About page placeholder.</div>
		</div>
	)
}

