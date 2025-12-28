import { NavLink, Outlet } from 'react-router-dom'

export default function UsersLayout(){
    return (
        <div className="max-w-5xl mx-auto">
            <Outlet />
        </div>
    )
}


