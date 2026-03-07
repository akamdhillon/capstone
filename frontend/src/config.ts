export const API_BASE_URL = import.meta.env.VITE_API_URL as string || 'http://localhost:8000';

export const WS_BASE_URL = API_BASE_URL.replace(/^http/, 'ws');
