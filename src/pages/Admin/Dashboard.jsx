export default function Dashboard() {
    return (
        <div className="relative flex flex-col items-center justify-center py-16">
            <img src="/assets/jrmsu-logo.png" alt="JRMSU" className="mx-auto w-40 h-40 object-contain" onError={(e) => { e.currentTarget.style.display = 'none' }} />
            <div className="mt-6 text-[#1d8a50] font-oswald uppercase tracking-wider text-2xl">JOSE RIZAL MEMORIAL STATE UNIVERSITY</div>
            <div className="mt-4 text-center leading-tight">
                <div className="text-navy font-archivoBlack uppercase text-2xl tracking-wide">K-MEANS AND CONSTRAINT PROGRAMMING INTELLIGENT</div>
                <div className="text-navy font-archivoBlack uppercase text-2xl tracking-wide">TIMETABLING SYSTEM</div>
            </div>
        </div>
    )
}
