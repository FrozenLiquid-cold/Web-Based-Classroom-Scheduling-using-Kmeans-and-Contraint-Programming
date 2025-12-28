import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { logout } from '../../store/auth'

export default function RegistrarAccount(){
    const navigate = useNavigate()
    const session = (()=>{
        try{ return JSON.parse(localStorage.getItem('jrmsu.session')||'null') }catch{ return null }
    })()
    
    const [isEditing, setIsEditing] = useState(false)
    const [formData, setFormData] = useState({
        fullName: session?.fullName || '',
        username: session?.username || 'User',
        email: session?.email || '',
        password: '',
        confirmPassword: ''
    })

    function handleSave(){
        if (formData.password && formData.password !== formData.confirmPassword) {
            alert('Passwords do not match')
            return
        }
        // Update session data
        const updatedSession = { ...session, ...formData }
        if (formData.password) {
            // Password would be hashed in real app
            delete updatedSession.password
            delete updatedSession.confirmPassword
        }
        localStorage.setItem('jrmsu.session', JSON.stringify(updatedSession))
        setIsEditing(false)
        alert('Profile updated successfully!')
    }

    function handleCancel(){
        setFormData({
            fullName: session?.fullName || '',
            username: session?.username || 'User',
            email: session?.email || '',
            password: '',
            confirmPassword: ''
        })
        setIsEditing(false)
    }

    return (
        <div className="max-w-4xl mx-auto">
            <div className="bg-white/90 rounded-xl shadow ring-1 ring-black/10 p-8">
                {/* Profile Header */}
                <div className="flex items-start justify-between mb-8 pb-8 border-b border-gray-200">
                    <div className="flex items-center gap-6">
                        <div className="w-24 h-24 rounded-full bg-gradient-to-br from-royal to-navy flex items-center justify-center shadow-lg">
                            <img src="/assets/user.png" alt="User" className="w-12 h-12 object-contain opacity-90" onError={(e)=>{e.currentTarget.style.display='none'}} />
                        </div>
                        <div>
                            <h2 className="text-2xl font-bold text-navy mb-1">{formData.fullName || formData.username}</h2>
                            <p className="text-gray-600 text-sm mb-1">@{formData.username}</p>
                            <span className="inline-block px-3 py-1 bg-royal/10 text-royal rounded-full text-xs font-semibold">Registrar</span>
                        </div>
                    </div>
                    {!isEditing && (
                        <button 
                            className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-royal text-white hover:opacity-90 transition" 
                            onClick={()=>setIsEditing(true)}
                        >
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4"><path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg>
                            <span>Edit Profile</span>
                        </button>
                    )}
                </div>

                {/* Account Information */}
                <div className="mb-8">
                    <h3 className="text-xl font-semibold text-navy mb-6">Account Information</h3>
                    
                    <div className="space-y-5">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">Full Name</label>
                            {isEditing ? (
                                <input 
                                    type="text" 
                                    className="w-full px-4 py-2 rounded-lg border border-gray-300 focus:ring-2 focus:ring-royal focus:border-transparent outline-none" 
                                    value={formData.fullName}
                                    onChange={(e)=>setFormData({...formData, fullName: e.target.value})}
                                    placeholder="Enter full name"
                                />
                            ) : (
                                <div className="text-gray-900">{formData.fullName || 'Not set'}</div>
                            )}
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">Username</label>
                            {isEditing ? (
                                <input 
                                    type="text" 
                                    className="w-full px-4 py-2 rounded-lg border border-gray-300 focus:ring-2 focus:ring-royal focus:border-transparent outline-none" 
                                    value={formData.username}
                                    onChange={(e)=>setFormData({...formData, username: e.target.value})}
                                    placeholder="Enter username"
                                />
                            ) : (
                                <div className="text-gray-900">{formData.username}</div>
                            )}
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">Email</label>
                            {isEditing ? (
                                <input 
                                    type="email" 
                                    className="w-full px-4 py-2 rounded-lg border border-gray-300 focus:ring-2 focus:ring-royal focus:border-transparent outline-none" 
                                    value={formData.email}
                                    onChange={(e)=>setFormData({...formData, email: e.target.value})}
                                    placeholder="Enter email address"
                                />
                            ) : (
                                <div className="text-gray-900">{formData.email || 'Not set'}</div>
                            )}
                        </div>

                        {isEditing && (
                            <>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-2">New Password</label>
                                    <input 
                                        type="password" 
                                        className="w-full px-4 py-2 rounded-lg border border-gray-300 focus:ring-2 focus:ring-royal focus:border-transparent outline-none" 
                                        value={formData.password}
                                        onChange={(e)=>setFormData({...formData, password: e.target.value})}
                                        placeholder="Leave blank to keep current password"
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-2">Confirm Password</label>
                                    <input 
                                        type="password" 
                                        className="w-full px-4 py-2 rounded-lg border border-gray-300 focus:ring-2 focus:ring-royal focus:border-transparent outline-none" 
                                        value={formData.confirmPassword}
                                        onChange={(e)=>setFormData({...formData, confirmPassword: e.target.value})}
                                        placeholder="Confirm new password"
                                    />
                                </div>
                            </>
                        )}
                    </div>

                    {isEditing && (
                        <div className="flex items-center gap-3 mt-8 pt-6 border-t border-gray-200">
                            <button 
                                className="inline-flex items-center gap-2 px-6 py-2 rounded-full bg-green-600 text-white hover:opacity-90 transition" 
                                onClick={handleSave}
                            >
                                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
                                <span>Save Changes</span>
                            </button>
                            <button 
                                className="inline-flex items-center gap-2 px-6 py-2 rounded-full bg-gray-400 text-white hover:opacity-90 transition" 
                                onClick={handleCancel}
                            >
                                <span>Cancel</span>
                            </button>
                        </div>
                    )}
                </div>

                {/* Account Actions */}
                <div className="pt-6 border-t border-gray-200">
                    <h3 className="text-xl font-semibold text-navy mb-6">Account Actions</h3>
                    <button 
                        className="inline-flex items-center gap-2 px-6 py-2 rounded-full bg-red-600 text-white hover:opacity-90 transition" 
                        onClick={()=>{ 
                            if(confirm('Are you sure you want to log out?')) {
                                logout(); 
                                navigate('/login/registrar')
                            }
                        }}
                    >
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4"><path d="M17 7l-1.41 1.41L18.17 11H8v2h10.17l-2.58 2.59L17 17l5-5zM4 5h8V3H4c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h8v-2H4V5z"/></svg>
                        <span>Log Out</span>
                    </button>
                </div>
            </div>
        </div>
    )
}


