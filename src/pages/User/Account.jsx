import { useNavigate } from 'react-router-dom'
import { logout } from '../../store/auth'

export default function Account(){
    const navigate = useNavigate()
    const session = (()=>{
        try{ return JSON.parse(localStorage.getItem('jrmsu.session')||'null') }catch{ return null }
    })()
	return (
		<div>
            <div className="flex items-center justify-between mb-4">
                <h1 className="text-navy text-xl font-semibold">ACCOUNT</h1>
                <button className="px-3 py-1 rounded bg-red-600 text-white text-xs" onClick={()=>{ logout(); navigate('/login/registrar') }}>Log out</button>
            </div>
            <div className="bg-white/90 rounded-xl shadow ring-1 ring-black/10 p-6">
                <div className="flex items-center gap-4">
                    <div className="w-16 h-16 rounded-full bg-[#e6ebff] flex items-center justify-center">
                        <img src="/assets/user.png" alt="User" className="w-8 h-8 object-contain" onError={(e)=>{e.currentTarget.style.display='none'}} />
                    </div>
                    <div>
                        <div className="text-navy font-semibold">{session?.username || 'User'}</div>
                        <div className="text-gray-600 text-sm">Username</div>
                    </div>
                </div>
            </div>
		</div>
	)
}

