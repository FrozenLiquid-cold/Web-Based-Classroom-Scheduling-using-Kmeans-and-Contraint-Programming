import React from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import './styles/tailwind.css'
import './styles/theme.css'
import { seedIfEmpty } from './store/db'
import { seedData } from './data/mockData'

// Seed initial data on first load
seedIfEmpty(seedData)

// React.StrictMode disabled to prevent double-mounting in development
// This eliminates duplicate API calls caused by StrictMode's intentional double-rendering
// StrictMode is useful for detecting side effects but causes duplicate requests

createRoot(document.getElementById('root')).render(
  <BrowserRouter>
    <App />
  </BrowserRouter>
)

