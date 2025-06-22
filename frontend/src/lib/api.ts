import axios from 'axios';
import type {
  SearchRequest,
  SearchResponse,
  DuplicatesRequest,
  DuplicatesResponse,
  DatabaseStats,
  VisualizationData,
  HealthCheck,
} from '../types/api';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
});

export class FileIndexerAPI {
  static async healthCheck(): Promise<HealthCheck> {
    const response = await api.get<HealthCheck>('/health/');
    return response.data;
  }

  static async searchFiles(params: SearchRequest): Promise<SearchResponse> {
    const response = await api.get<SearchResponse>('/search/', { params });
    return response.data;
  }

  static async searchFilesAdvanced(request: SearchRequest): Promise<SearchResponse> {
    const response = await api.post<SearchResponse>('/search/', request);
    return response.data;
  }

  static async findDuplicates(params: DuplicatesRequest = {}): Promise<DuplicatesResponse> {
    const response = await api.get<DuplicatesResponse>('/duplicates/', { params });
    return response.data;
  }

  static async findDuplicatesAdvanced(request: DuplicatesRequest): Promise<DuplicatesResponse> {
    const response = await api.post<DuplicatesResponse>('/duplicates/', request);
    return response.data;
  }

  static async getDatabaseStats(): Promise<DatabaseStats> {
    const response = await api.get<DatabaseStats>('/stats/');
    return response.data;
  }

  static async getVisualizationData(): Promise<VisualizationData> {
    const response = await api.get<VisualizationData>('/stats/visualization');
    return response.data;
  }
}

export default FileIndexerAPI; 