import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { 
  Search, 
  Filter, 
  FileText, 
  Calendar, 
  HardDrive,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Hash
} from 'lucide-react';
import FileIndexerAPI from '../lib/api';
import { formatFileSize, formatDateTime, getFileTypeIcon, truncateText } from '../lib/utils';
import type { SearchRequest, FileRecord } from '../types/api';

export default function SearchFiles() {
  const [searchParams, setSearchParams] = useState<SearchRequest>({
    limit: 50,
    offset: 0,
  });
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);

  const { data: searchResults, isLoading, error } = useQuery({
    queryKey: ['search', searchParams],
    queryFn: () => FileIndexerAPI.searchFiles(searchParams),
  });

  const handleSearch = (params: Partial<SearchRequest>) => {
    setSearchParams(prev => ({ ...prev, ...params, offset: 0 }));
    setCurrentPage(1);
  };

  const handlePageChange = (page: number) => {
    const offset = (page - 1) * (searchParams.limit || 50);
    setSearchParams(prev => ({ ...prev, offset }));
    setCurrentPage(page);
  };

  const totalPages = searchResults ? Math.ceil(searchResults.total_count / (searchParams.limit || 50)) : 0;

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="text-center">
        <h1 className="text-3xl font-bold gradient-text mb-2">Search Files</h1>
        <p className="text-slate-600">
          Find files across your entire index with powerful filters
        </p>
      </div>

      {/* Search Form */}
      <div className="card">
        <div className="card-content space-y-4">
          {/* Basic Search */}
          <div className="flex flex-col md:flex-row gap-4">
            <div className="flex-1">
              <label className="block text-sm font-medium text-slate-700 mb-2">
                Filename Pattern
              </label>
              <div className="relative">
                <Search className="w-4 h-4 absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400" />
                <input
                  type="text"
                  className="input pl-10"
                  placeholder="e.g., *.pdf, photo*, document.txt"
                  value={searchParams.filename_pattern || ''}
                  onChange={(e) => handleSearch({ filename_pattern: e.target.value || undefined })}
                />
              </div>
            </div>
            
            <div className="flex-1">
              <label className="block text-sm font-medium text-slate-700 mb-2">
                Path Pattern
              </label>
              <input
                type="text"
                className="input"
                placeholder="e.g., /home/user/*, */Documents/*"
                value={searchParams.path_pattern || ''}
                onChange={(e) => handleSearch({ path_pattern: e.target.value || undefined })}
              />
            </div>
          </div>

          {/* Advanced Filters Toggle */}
          <button
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="flex items-center space-x-2 text-primary-600 hover:text-primary-700 transition-colors"
          >
            <Filter className="w-4 h-4" />
            <span>Advanced Filters</span>
            {showAdvanced ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>

          {/* Advanced Filters */}
          {showAdvanced && (
            <div className="border-t pt-4 space-y-4 animate-slide-up">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {/* File Size Range */}
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    <HardDrive className="w-4 h-4 inline mr-1" />
                    Min Size (bytes)
                  </label>
                  <input
                    type="number"
                    className="input"
                    placeholder="e.g., 1048576 (1MB)"
                    value={searchParams.min_size || ''}
                    onChange={(e) => handleSearch({ min_size: e.target.value ? parseInt(e.target.value) : undefined })}
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    Max Size (bytes)
                  </label>
                  <input
                    type="number"
                    className="input"
                    placeholder="e.g., 104857600 (100MB)"
                    value={searchParams.max_size || ''}
                    onChange={(e) => handleSearch({ max_size: e.target.value ? parseInt(e.target.value) : undefined })}
                  />
                </div>

                {/* Checksum Filter */}
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    <Hash className="w-4 h-4 inline mr-1" />
                    Has Checksum
                  </label>
                  <select
                    className="input"
                    value={searchParams.has_checksum === undefined ? '' : searchParams.has_checksum.toString()}
                    onChange={(e) => {
                      const value = e.target.value;
                      handleSearch({ 
                        has_checksum: value === '' ? undefined : value === 'true' 
                      });
                    }}
                  >
                    <option value="">Any</option>
                    <option value="true">Yes</option>
                    <option value="false">No</option>
                  </select>
                </div>

                {/* Results per page */}
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    Results per page
                  </label>
                  <select
                    className="input"
                    value={searchParams.limit || 50}
                    onChange={(e) => handleSearch({ limit: parseInt(e.target.value) })}
                  >
                    <option value={25}>25</option>
                    <option value={50}>50</option>
                    <option value={100}>100</option>
                    <option value={200}>200</option>
                  </select>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Results */}
      <div className="card">
        <div className="card-header">
          <div className="flex justify-between items-center">
            <div>
              <h3 className="text-lg font-semibold text-slate-900">Search Results</h3>
              {searchResults && (
                <p className="text-sm text-slate-600">
                  Found {searchResults.total_count.toLocaleString()} files
                </p>
              )}
            </div>
            
            {/* Pagination Info */}
            {searchResults && totalPages > 1 && (
              <div className="text-sm text-slate-600">
                Page {currentPage} of {totalPages}
              </div>
            )}
          </div>
        </div>

        <div className="card-content">
          {isLoading ? (
            <div className="text-center py-8">
              <div className="animate-spin w-8 h-8 border-4 border-primary-500 border-t-transparent rounded-full mx-auto"></div>
              <p className="mt-4 text-slate-600">Searching files...</p>
            </div>
          ) : error ? (
            <div className="text-center py-8 text-red-600">
              <p>Error loading search results</p>
            </div>
          ) : !searchResults?.files.length ? (
            <div className="text-center py-8 text-slate-500">
              <FileText className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p>No files found matching your criteria</p>
              <p className="text-sm mt-2">Try adjusting your search parameters</p>
            </div>
          ) : (
            <div className="space-y-2">
              {searchResults.files.map((file: FileRecord, index: number) => (
                <div
                  key={`${file.path}-${file.filename}-${index}`}
                  className="flex items-center justify-between p-4 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
                >
                  <div className="flex items-center space-x-4 flex-1 min-w-0">
                    <div className="text-2xl flex-shrink-0">
                      {getFileTypeIcon(file.filename)}
                    </div>
                    
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center space-x-2">
                        <h4 className="font-medium text-slate-900 truncate">
                          {file.filename}
                        </h4>
                                                 {file.checksum && (
                           <div title="Has checksum">
                             <Hash className="w-3 h-3 text-green-500" />
                           </div>
                         )}
                      </div>
                      <p className="text-sm text-slate-500 truncate" title={file.path}>
                        {truncateText(file.path, 60)}
                      </p>
                      <div className="flex items-center space-x-4 text-xs text-slate-400 mt-1">
                        <span className="flex items-center space-x-1">
                          <HardDrive className="w-3 h-3" />
                          <span>{formatFileSize(file.file_size)}</span>
                        </span>
                        <span className="flex items-center space-x-1">
                          <Calendar className="w-3 h-3" />
                          <span>{formatDateTime(file.modification_datetime)}</span>
                        </span>
                      </div>
                    </div>
                  </div>

                  <button
                    className="p-2 text-slate-400 hover:text-slate-600 transition-colors"
                    title="View details"
                  >
                    <ExternalLink className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Pagination */}
        {searchResults && totalPages > 1 && (
          <div className="border-t p-4">
            <div className="flex justify-center space-x-2">
              <button
                onClick={() => handlePageChange(currentPage - 1)}
                disabled={currentPage === 1}
                className="btn btn-secondary disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Previous
              </button>
              
              {/* Page numbers */}
              {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                const page = Math.max(1, currentPage - 2) + i;
                if (page > totalPages) return null;
                
                return (
                  <button
                    key={page}
                    onClick={() => handlePageChange(page)}
                    className={`px-3 py-1 rounded ${
                      page === currentPage
                        ? 'bg-primary-600 text-white'
                        : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                    }`}
                  >
                    {page}
                  </button>
                );
              })}
              
              <button
                onClick={() => handlePageChange(currentPage + 1)}
                disabled={currentPage === totalPages}
                className="btn btn-secondary disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
} 