/**
 * Centralized API configuration for MindMesh backend.
 * Update API_BASE_URL to match your backend address.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/**
 * Check if the API backend is reachable via the /health endpoint.
 */
export async function checkApiHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE_URL}/health`, { signal: AbortSignal.timeout(3000) });
    return response.ok;
  } catch {
    return false;
  }
}

export { API_BASE_URL };
