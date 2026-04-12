import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { loginRegistrar, loginInstructor, loginAdmin } from '../../store/auth'

export default function Login() {
	const { role = 'registrar' } = useParams()
	const [username, setUsername] = useState('')
	const [password, setPassword] = useState('')
	const [showPassword, setShowPassword] = useState(false)
	const [error, setError] = useState('')
	const navigate = useNavigate()

	async function submit(e) {
		e.preventDefault()
		try {
			let res
			if (role === 'instructor') {
				res = await loginInstructor(username, password)
				if (res.ok) navigate('/i/dashboard')
			} else if (role === 'admin') {
				res = await loginAdmin(username, password)
				if (res.ok) navigate('/a/dashboard')
			} else {
				res = await loginRegistrar(username, password)
				if (res.ok) navigate('/r/dashboard')
			}
			if (!res.ok) setError(res.message || 'Login failed')
		} catch (error) {
			setError(error.message || 'Login failed')
		}
	}

	const roleLabel = (role || 'registrar').toUpperCase()

	return (
		<div className="min-h-screen flex items-center justify-center bg-[url('/assets/bg-circuit.png')] bg-cover bg-center">
			<form onSubmit={submit} className="relative w-[350px] p-8 rounded-[28px] bg-white/80 backdrop-blur border border-white/50 shadow-[8px_10px_0_0_rgba(0,0,0,0.15)]">
				<button
					type="button"
					onClick={() => navigate('/')}
					className="absolute left-4 top-4 text-[11px] text-navy hover:underline flex items-center gap-1"
				>
					<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4">
						<path d="M15.75 19.5L8.25 12l7.5-7.5" />
					</svg>
					<span>Back to Home</span>
				</button>
				<div className="text-center space-y-2">
					<img src="/assets/jrmsu-logo.png" alt="JRMSU" className="mx-auto w-16 h-16 object-contain" onError={(e) => { e.currentTarget.style.display = 'none' }} />
					<div className="leading-tight">
						<div className="text-navy font-archivoBlack uppercase text-[14px] tracking-widest">K-MEANS AND CONSTRAINT</div>
						<div className="text-navy font-archivoBlack uppercase text-[14px] tracking-widest">PROGRAMMING INTELLIGENT</div>
						<div className="text-navy font-archivoBlack uppercase text-[14px] tracking-widest">TIMETABLING SYSTEM</div>
					</div>
					<div className="text-[#F5A524] font-righteous uppercase tracking-[0.40em] text-1xl">{roleLabel}</div>
				</div>

				<div className="mt-6 space-y-4">
					<div className="relative">
						<input className="w-full h-10 rounded-full bg-white/90 border border-black/10 px-5 text-sm placeholder-black/60 outline-none focus:ring-2 focus:ring-royal/50" placeholder="Username" value={username} onChange={e => setUsername(e.target.value)} />
					</div>
					<div className="relative">
						<input type={showPassword ? 'text' : 'password'} className="w-full h-10 rounded-full bg-white/90 border border-black/10 px-5 pr-12 text-sm placeholder-black/60 outline-none focus:ring-2 focus:ring-royal/50" placeholder="Password" value={password} onChange={e => setPassword(e.target.value)} />
						<button type="button" aria-label="Toggle password" onClick={() => setShowPassword(v => !v)} className="absolute right-4 top-1/2 -translate-y-1/2 text-black/60 hover:text-black/80">
							<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5"><path d="M1.458 12C2.732 7.943 6.61 5 12 5s9.268 2.943 10.542 7c-1.274 4.057-5.152 7-10.542 7S2.732 16.057 1.458 12zm10.542 4a4 4 0 100-8 4 4 0 000 8z" /></svg>
						</button>
					</div>
					{error && <div className="text-red-600 text-[13px]">{error}</div>}
					<button className="w-full h-10 rounded-full bg-royal text-white font-medium active:scale-[0.99] shadow-[0_6px_0_0_rgba(0,0,0,0.2)]">Login</button>
				</div>
			</form>
		</div>
	)
}


