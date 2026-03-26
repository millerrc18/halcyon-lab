export const API_BASE = process.env.REACT_APP_API_URL || '/api';
export const IS_CLOUD = API_BASE.includes('render.com') || API_BASE.includes('onrender.com');
export const API_SECRET = process.env.REACT_APP_API_SECRET || '';
