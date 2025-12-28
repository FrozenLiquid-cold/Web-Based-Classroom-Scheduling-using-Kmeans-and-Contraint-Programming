import { useNavigate } from 'react-router-dom'
import { useEffect, useState } from 'react'

export default function Landing() {
	const navigate = useNavigate()
	const [scale, setScale] = useState(1)

	useEffect(() => {
		const BASE_WIDTH = 1920
		const BASE_HEIGHT = 1080
		const computeScale = () => {
			const s = Math.min(window.innerWidth / BASE_WIDTH, window.innerHeight / BASE_HEIGHT)
			setScale(s)
		}
		computeScale()
		window.addEventListener('resize', computeScale)
		return () => window.removeEventListener('resize', computeScale)
	}, [])
	return (
		<div className="min-h-screen flex items-center justify-center bg-[url('/assets/bg-circuit.png')] bg-cover bg-center">
			{/* Scaled 1920x1080 canvas to fit any viewport */}
			<div className="flex items-center justify-center" style={{ width: '100vw', height: '100vh' }}>
				<div className="relative text-center space-y-8 pt-20" style={{ width: 1920, height: 1080, transform: `scale(${scale})`, transformOrigin: 'center' }}>
					<img src="/assets/jrmsu-logo.png" alt="JRMSU" className="mx-auto w-40 h-40 object-contain" onError={(e)=>{e.currentTarget.style.display='none'}} />
					<div className="text-green-600 font-oswald uppercase text-3xl">JOSE RIZAL MEMORIAL STATE UNIVERSITY</div>
					<div className="flex flex-col items-center space-y-1">
						<div className="text-navy font-archivoBlack uppercase text-4xl">K-MEANS AND CONSTRAINT PROGRAMMING</div>
						<div className="text-navy font-archivoBlack uppercase text-4xl">CLASSROOM SCHEDULING SYSTEM</div>
					</div>
					<div className="grid grid-cols-3 gap-16 max-w-5xl mx-auto pt-6">
					{/* Admin */}
					<button className="group relative w-64 h-64 rounded-2xl bg-yellow-300/30 backdrop-blur-sm border border-white/40 mx-auto shadow-xl transition-transform duration-300 ease-out hover:-translate-y-1 hover:scale-105 hover:shadow-2xl hover:ring-2 hover:ring-royal/60" onClick={()=>navigate('/login/admin')}>
							<div className="absolute inset-0 flex flex-col items-center justify-center">
								<div className="font-archivoBlack text-[110px] text-[#82661f] drop-shadow transition-transform duration-300 group-hover:scale-125 group-hover:rotate-6">A</div>
								<div className="mt-2 font-poppins text-navy tracking-wide text-2xl">Admin</div>
							</div>
					</button>
						{/* Instructor */}
					<button className="group relative w-64 h-64 rounded-2xl bg-green-300/30 backdrop-blur-sm border border-white/40 mx-auto shadow-xl transition-transform duration-300 ease-out hover:-translate-y-1 hover:scale-105 hover:shadow-2xl hover:ring-2 hover:ring-royal/60" onClick={()=>navigate('/login/instructor')}>
							<div className="absolute inset-0 flex flex-col items-center justify-center">
								<div className="font-archivoBlack text-[110px] text-[#2F7E57] drop-shadow transition-transform duration-300 group-hover:scale-125 group-hover:rotate-6">I</div>
								<div className="mt-2 font-poppins text-navy tracking-wide text-2xl">Instructor</div>
							</div>
					</button>
						{/* Registrar (clickable) */}
						<button className="group relative w-64 h-64 rounded-2xl bg-blue-300/30 backdrop-blur-sm border border-white/40 mx-auto shadow-xl hover:bg-blue-300/40 transition-transform duration-300 ease-out hover:-translate-y-1 hover:scale-105 hover:shadow-2xl hover:ring-2 hover:ring-royal/60" onClick={()=>navigate('/login/registrar')}>
							<div className="absolute inset-0 flex flex-col items-center justify-center">
								<div className="font-archivoBlack text-[110px] text-royal drop-shadow transition-transform duration-300 group-hover:scale-125 group-hover:rotate-6">R</div>
								<div className="mt-2 font-poppins text-navy tracking-wide text-2xl">Registrar</div>
							</div>
						</button>
					</div>
					<div className="absolute left-0 right-0 bottom-10 mx-auto text-[21px] text-black/70 font-arialMtPro">Develop by : Allan Patrick Aniñon, Arabella Patayan, Claire Dela Peña © 2025</div>
				</div>
			</div>
		</div>
	)
}

