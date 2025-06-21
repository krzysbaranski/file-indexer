export interface FileRecord {
  path: string;
  filename: string;
  checksum: string | null;
  modification_datetime: string;
  file_size: number;
  indexed_at: string;
}

export interface SearchRequest {
  filename_pattern?: string;
  path_pattern?: string;
  checksum?: string;
  has_checksum?: boolean;
  min_size?: number;
  max_size?: number;
  modified_after?: string;
  modified_before?: string;
  limit?: number;
  offset?: number;
}

export interface SearchResponse {
  files: FileRecord[];
  total_count: number;
  has_more: boolean;
}

export interface DuplicateGroup {
  checksum: string;
  file_size: number;
  file_count: number;
  files: FileRecord[];
}

export interface DuplicatesResponse {
  duplicate_groups: DuplicateGroup[];
  total_groups: number;
  total_duplicate_files: number;
}

export interface DatabaseStats {
  total_files: number;
  total_size: number;
  files_with_checksums: number;
  files_without_checksums: number;
  duplicate_files: number;
  duplicate_groups: number;
  average_file_size: number;
  largest_file_size: number;
  smallest_file_size: number;
  most_recent_modification: string | null;
  oldest_modification: string | null;
  unique_directories: number;
}

export interface SizeDistribution {
  size_range: string;
  count: number;
  total_size: number;
}

export interface ExtensionStats {
  extension: string;
  count: number;
  total_size: number;
  average_size: number;
}

export interface VisualizationData {
  size_distribution: SizeDistribution[];
  extension_stats: ExtensionStats[];
  modification_timeline: Array<{
    month: string | null;
    count: number;
    total_size: number;
  }>;
}

export interface HealthCheck {
  status: string;
  database_connected: boolean;
  database_path: string | null;
  total_files: number;
  api_version: string;
} 