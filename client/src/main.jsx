import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { PostHogProvider } from 'posthog-js/react'

// Determine the backend URL based on environment
const getBackendUrl = () => {
    // In development, backend typically runs on port 8000
    if (import.meta.env.DEV) {
        return 'http://localhost:5000';
    }
    // In production, backend and frontend are served from the same domain
    return window.location.origin;
};

const options = {
    api_host: getBackendUrl() + '/ingest', // Use backend URL for the proxy
    defaults: '2025-05-24',
    // Note: We no longer use VITE_PUBLIC_POSTHOG_HOST since we proxy through our backend
}

createRoot(document.getElementById('root')).render(
    <PostHogProvider apiKey={import.meta.env.VITE_PUBLIC_POSTHOG_KEY} options={options}>
        <App />
    </PostHogProvider>
);
