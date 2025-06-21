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
  Info,
  ClipboardCopy,
  Eye,
  Folder,
  FolderOpen,
  Home,
  ChevronRight,
  MoreVertical,
  ExternalLink
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
  const [currentFolder, setCurrentFolder] = useState<string>('');
  const [browsing, setBrowsing] = useState(false);
  const [breadcrumbs, setBreadcrumbs] = useState<string[]>([]);

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

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text).then(() => {
      // Could add a toast notification here
    }).catch(err => {
      console.error('Failed to copy:', err);
    });
  };

  const browseFolder = (folderPath: string) => {
    const pathParts = folderPath.split('/').filter(part => part !== '');
    setBreadcrumbs(pathParts);
    setCurrentFolder(folderPath);
    setBrowsing(true);
    
    // Update search params to show files in this folder
    const folderPattern = folderPath.endsWith('/') ? `${folderPath}%` : `${folderPath}/%`;
    setSearchParams({
      ...searchParams,
      path_pattern: folderPattern,
      offset: 0
    });
    setCurrentPage(1);
  };

  const navigateToBreadcrumb = (index: number) => {
    if (index === -1) {
      // Go back to search results
      setBrowsing(false);
      setCurrentFolder('');
      setBreadcrumbs([]);
      setSearchParams({
        ...searchParams,
        path_pattern: undefined,
        offset: 0
      });
    } else {
      const newPath = '/' + breadcrumbs.slice(0, index + 1).join('/');
      browseFolder(newPath);
    }
  };

  const getFileDirectory = (filePath: string) => {
    const lastSlashIndex = filePath.lastIndexOf('/');
    return lastSlashIndex > 0 ? filePath.substring(0, lastSlashIndex) : '/';
  };

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="text-center">
        <h1 className="text-3xl font-bold gradient-text mb-2">
          {browsing ? 'Browse Files' : 'Search Files'}
        </h1>
        <p className="text-gray-600">
          {browsing ? 'Browse files in folders like Finder' : 'Find files across your entire index with powerful filters'}
        </p>
      </div>

      {/* Breadcrumb Navigation */}
      {browsing && (
        <div className="card">
          <div className="card-content py-3">
            <div className="flex items-center space-x-2 text-sm">
              <button
                onClick={() => navigateToBreadcrumb(-1)}
                className="flex items-center space-x-1 px-2 py-1 rounded hover:bg-gray-100 transition-colors"
              >
                <Search className="h-4 w-4" />
                <span>Search Results</span>
              </button>
              
              {breadcrumbs.length > 0 && (
                <>
                  <ChevronRight className="h-4 w-4 text-gray-400" />
                  <button
                    onClick={() => navigateToBreadcrumb(-1)}
                    className="flex items-center space-x-1 px-2 py-1 rounded hover:bg-gray-100 transition-colors"
                  >
                    <Home className="h-4 w-4" />
                    <span>Root</span>
                  </button>
                </>
              )}
              
              {breadcrumbs.map((part, index) => (
                <React.Fragment key={index}>
                  <ChevronRight className="h-4 w-4 text-gray-400" />
                  <button
                    onClick={() => navigateToBreadcrumb(index)}
                    className={`px-2 py-1 rounded hover:bg-gray-100 transition-colors ${
                      index === breadcrumbs.length - 1 ? 'font-medium text-blue-600' : 'text-gray-700'
                    }`}
                  >
                    {part}
                  </button>
                </React.Fragment>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Search Form */}
      {!browsing && (
        <div className="card">
          <div className="card-content space-y-4">
          {/* Basic Search */}
          <div className="flex flex-col md:flex-row gap-4">
            <div className="flex-1">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Filename Pattern
                <div className="group relative inline-block ml-1">
                  <Info className="w-3 h-3 text-gray-400 cursor-help" />
                  <div className="invisible group-hover:visible absolute bottom-full left-0 mb-2 w-64 p-2 bg-gray-900 text-white text-xs rounded shadow-lg z-10">
                    SQL patterns: Use % for wildcards (e.g., %.pdf, photo%, document.txt)
                  </div>
                </div>
              </label>
              <div className="relative">
                <Search className="w-4 h-4 absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
                <input
                  type="text"
                  className="input pl-10 text-sm"
                  placeholder="e.g., %.pdf, photo%, document.txt"
                  value={searchParams.filename_pattern || ''}
                  onChange={(e) => handleSearch({ filename_pattern: e.target.value || undefined })}
                />
              </div>
            </div>
            
            <div className="flex-1">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Path Pattern
                <div className="group relative inline-block ml-1">
                  <Info className="w-3 h-3 text-gray-400 cursor-help" />
                  <div className="invisible group-hover:visible absolute bottom-full left-0 mb-2 w-64 p-2 bg-gray-900 text-white text-xs rounded shadow-lg z-10">
                    SQL patterns: Use % for wildcards (e.g., /home/user/%, %/Documents/%)
                  </div>
                </div>
              </label>
              <input
                type="text"
                className="input text-sm"
                placeholder="e.g., /home/user/%, %/Documents/%"
                value={searchParams.path_pattern || ''}
                onChange={(e) => handleSearch({ path_pattern: e.target.value || undefined })}
              />
            </div>
          </div>

          {/* Advanced Filters Toggle */}
          <button
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="flex items-center space-x-2 text-blue-600 hover:text-blue-700 transition-colors text-sm"
          >
            <Filter className="w-4 h-4" />
            <span>Advanced Filters</span>
            {showAdvanced ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>

          {/* Advanced Filters */}
          {showAdvanced && (
            <div className="border-t pt-4 space-y-4 animate-slide-up">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {/* File Size Range */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Min Size (MB)
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    className="input text-sm"
                    placeholder="e.g., 1"
                    value={searchParams.min_size ? (searchParams.min_size / (1024 * 1024)).toFixed(1) : ''}
                    onChange={(e) => {
                      const mb = parseFloat(e.target.value);
                      handleSearch({ min_size: isNaN(mb) ? undefined : Math.round(mb * 1024 * 1024) });
                    }}
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Max Size (MB)
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    className="input text-sm"
                    placeholder="e.g., 100"
                    value={searchParams.max_size ? (searchParams.max_size / (1024 * 1024)).toFixed(1) : ''}
                    onChange={(e) => {
                      const mb = parseFloat(e.target.value);
                      handleSearch({ max_size: isNaN(mb) ? undefined : Math.round(mb * 1024 * 1024) });
                    }}
                  />
                </div>

                {/* Checksum Filter */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Has Checksum
                  </label>
                  <select
                    className="input text-sm"
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
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Per Page
                  </label>
                  <select
                    className="input text-sm"
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
      )}

      {/* Results */}
      <div className="card">
        <div className="card-header">
          <div className="flex justify-between items-center">
            <div>
              <h3 className="text-lg font-semibold text-gray-900">Search Results</h3>
              {searchResults && (
                <p className="text-sm text-gray-600">
                  Found {searchResults.total_count.toLocaleString()} files
                </p>
              )}
            </div>
            
            {/* Pagination Info */}
            {searchResults && totalPages > 1 && (
              <div className="text-sm text-gray-600">
                Page {currentPage} of {totalPages}
              </div>
            )}
          </div>
        </div>

        <div className="card-content">
          {isLoading ? (
            <div className="text-center py-8">
              <div className="animate-shimmer w-8 h-8 rounded-full mx-auto"></div>
              <p className="mt-4 text-gray-600">Searching files...</p>
            </div>
          ) : error ? (
            <div className="text-center py-8 text-red-600">
              <p>Error loading search results</p>
            </div>
          ) : !searchResults?.files.length ? (
            <div className="text-center py-8 text-gray-500">
              <FileText className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p>No files found matching your criteria</p>
              <p className="text-sm mt-2">Try adjusting your search parameters</p>
            </div>
          ) : (
            <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
              {/* Finder-like header */}
              <div className="bg-gray-50 border-b border-gray-200 px-4 py-2">
                <div className="flex items-center justify-between text-xs font-medium text-gray-500 uppercase tracking-wider">
                  <div className="flex-1">Name</div>
                  <div className="w-20 text-right">Size</div>
                  <div className="w-32 text-right">Modified</div>
                  <div className="w-8"></div>
                </div>
              </div>
              
              {/* File list */}
              <div className="divide-y divide-gray-100">
                {searchResults.files.map((file: FileRecord, index: number) => {
                  const directory = getFileDirectory(file.path);
                  
                  return (
                    <div
                      key={`${file.path}-${file.filename}-${index}`}
                      className="flex items-center px-4 py-2 hover:bg-blue-50 transition-colors group"
                    >
                      {/* File icon and name */}
                      <div className="flex items-center space-x-3 flex-1 min-w-0">
                        <div className="text-2xl flex-shrink-0">
                          {getFileTypeIcon(file.filename)}
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="text-sm font-medium text-gray-900 truncate">
                            {file.filename}
                          </div>
                          <div className="flex items-center space-x-2">
                            <span className="text-xs text-gray-500 truncate" title={file.path}>
                              {truncateText(file.path, 60)}
                            </span>
                            <button
                              onClick={() => browseFolder(directory)}
                              className="text-xs text-blue-600 hover:text-blue-800 flex items-center space-x-1 opacity-0 group-hover:opacity-100 transition-opacity"
                              title="Browse folder"
                            >
                              <FolderOpen className="h-3 w-3" />
                              <span>Show in folder</span>
                            </button>
                          </div>
                        </div>
                      </div>
                      
                      {/* Size */}
                      <div className="w-20 text-right text-sm text-gray-600">
                        {formatFileSize(file.file_size)}
                      </div>
                      
                      {/* Modified date */}
                      <div className="w-32 text-right text-sm text-gray-500">
                        {formatDateTime(file.modification_datetime)}
                      </div>
                      
                      {/* Actions menu */}
                      <div className="w-8 flex justify-end">
                        <div className="relative group/menu">
                          <button className="p-1 text-gray-400 hover:text-gray-600 opacity-0 group-hover:opacity-100 transition-opacity">
                            <MoreVertical className="h-4 w-4" />
                          </button>
                          
                          {/* Dropdown menu */}
                          <div className="absolute right-0 top-8 w-48 bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-10 opacity-0 invisible group-hover/menu:opacity-100 group-hover/menu:visible transition-all">
                            <button
                              onClick={() => copyToClipboard(file.path)}
                              className="flex items-center space-x-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 w-full text-left"
                            >
                              <ClipboardCopy className="h-4 w-4" />
                              <span>Copy path</span>
                            </button>
                            
                            {file.checksum && (
                              <button
                                onClick={() => copyToClipboard(file.checksum!)}
                                className="flex items-center space-x-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 w-full text-left"
                              >
                                <ClipboardCopy className="h-4 w-4" />
                                <span>Copy checksum</span>
                              </button>
                            )}
                            
                            <button
                              onClick={() => browseFolder(directory)}
                              className="flex items-center space-x-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 w-full text-left"
                            >
                              <FolderOpen className="h-4 w-4" />
                              <span>Show in folder</span>
                            </button>
                            
                            {file.checksum && (
                              <div className="border-t border-gray-100 mt-1 pt-1">
                                <div className="px-3 py-2">
                                  <div className="text-xs text-gray-500 mb-1">SHA256:</div>
                                  <div className="text-xs font-mono text-gray-700 bg-gray-50 p-1 rounded break-all">
                                    {file.checksum}
                                  </div>
                                </div>
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
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
                className="btn btn-secondary disabled:opacity-50 disabled:cursor-not-allowed text-sm"
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
                    className={`px-3 py-1 rounded text-sm ${
                      page === currentPage
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                    }`}
                  >
                    {page}
                  </button>
                );
              })}
              
              <button
                onClick={() => handlePageChange(currentPage + 1)}
                disabled={currentPage === totalPages}
                className="btn btn-secondary disabled:opacity-50 disabled:cursor-not-allowed text-sm"
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