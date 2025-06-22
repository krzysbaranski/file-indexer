import React, { useState, useEffect, useMemo } from 'react';
import { FileIndexerAPI } from '../lib/api';
import type { DuplicateGroup } from '../types/api';
import { formatFileSize, formatDate, getFileTypeIcon } from '../lib/utils';
import { 
  Search, 
  AlertTriangle, 
  Copy, 
  Trash2, 
  Folder, 
  ChevronDown, 
  ChevronUp, 
  Filter,
  ChevronLeft,
  ChevronRight,
  Settings,
  FileText,
  HardDrive,
  ClipboardCopy,
  Eye
} from 'lucide-react';

export const Duplicates: React.FC = () => {
  const [duplicates, setDuplicates] = useState<DuplicateGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
  const [totalGroups, setTotalGroups] = useState(0);
  const [totalWastedSpace, setTotalWastedSpace] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  
  // Filter states
  const [searchTerm, setSearchTerm] = useState('');
  const [minGroupSize, setMinGroupSize] = useState(2);
  const [minFileSize, setMinFileSize] = useState<number | null>(null);
  const [maxFileSize, setMaxFileSize] = useState<number | null>(null);
  const [filenamePattern, setFilenamePattern] = useState('');
  const [pathPattern, setPathPattern] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  
  // Pagination states
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(20);

  useEffect(() => {
    loadDuplicates();
  }, [minGroupSize, minFileSize, maxFileSize, currentPage, itemsPerPage]);

  const loadDuplicates = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const params = {
        min_group_size: minGroupSize,
        min_file_size: minFileSize || undefined,
        max_file_size: maxFileSize || undefined,
        filename_pattern: filenamePattern || undefined,
        path_pattern: pathPattern || undefined,
        limit: itemsPerPage,
        offset: (currentPage - 1) * itemsPerPage,
      };
      
      const response = await FileIndexerAPI.findDuplicates(params);
      setDuplicates(response.duplicate_groups || []);
      setTotalGroups(response.total_groups);
      setTotalWastedSpace(response.total_wasted_space);
      setHasMore(response.has_more);
    } catch (err) {
      setError('Failed to load duplicates');
      console.error('Error loading duplicates:', err);
    } finally {
      setLoading(false);
    }
  };

  // Client-side search filter for already loaded results
  const filteredDuplicates = useMemo(() => {
    if (!searchTerm) return duplicates;
    
    const searchLower = searchTerm.toLowerCase();
    return duplicates.filter(group => {
      return group.files.some(file => 
        file.filename.toLowerCase().includes(searchLower) ||
        file.path.toLowerCase().includes(searchLower)
      );
    });
  }, [duplicates, searchTerm]);

  // Pagination logic - server-side pagination
  const totalPages = Math.ceil(totalGroups / itemsPerPage);
  const paginatedDuplicates = filteredDuplicates;

  const toggleGroup = (checksum: string) => {
    const newExpanded = new Set(expandedGroups);
    if (newExpanded.has(checksum)) {
      newExpanded.delete(checksum);
    } else {
      newExpanded.add(checksum);
    }
    setExpandedGroups(newExpanded);
  };

  const totalDuplicateFiles = filteredDuplicates.reduce((sum, group) => sum + group.files.length, 0);
  const displayedWastedSpace = filteredDuplicates.reduce((total, group) => total + (group.wasted_space || 0), 0);

  const resetFilters = () => {
    setSearchTerm('');
    setMinFileSize(null);
    setMaxFileSize(null);
    setFilenamePattern('');
    setPathPattern('');
    setCurrentPage(1);
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text).then(() => {
      // Could add a toast notification here
    }).catch(err => {
      console.error('Failed to copy:', err);
    });
  };

  const formatSizeForInput = (bytes: number): string => {
    if (bytes >= 1024 * 1024 * 1024) {
      return (bytes / (1024 * 1024 * 1024)).toFixed(1);
    } else {
      return (bytes / (1024 * 1024)).toFixed(1);
    }
  };

  const parseSizeFromInput = (value: string, unit: string): number => {
    const num = parseFloat(value);
    if (isNaN(num)) return 0;
    return unit === 'GB' ? num * 1024 * 1024 * 1024 : num * 1024 * 1024;
  };

  const applyFilters = () => {
    setCurrentPage(1); // Reset to first page when applying new filters
    loadDuplicates();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-shimmer w-12 h-12 rounded-full"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <AlertTriangle className="h-12 w-12 text-red-500 mx-auto mb-4" />
        <p className="text-red-600 text-lg font-medium">{error}</p>
        <button
          onClick={loadDuplicates}
          className="btn btn-primary mt-4"
        >
          Try Again
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Modern Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold gradient-text">Duplicate Files</h1>
          <p className="text-gray-600 mt-1">
            Find and manage duplicate files to reclaim storage space
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`btn ${showFilters ? 'btn-primary' : 'btn-secondary'} flex items-center space-x-2`}
          >
            <Filter className="h-4 w-4" />
            <span>Filters</span>
          </button>
        </div>
      </div>

      {/* Advanced Filters */}
      {showFilters && (
        <div className="card">
          <div className="card-content space-y-4">
            {/* Search and basic filters row */}
            <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Search Files</label>
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-4 w-4" />
                  <input
                    type="text"
                    placeholder="Search files..."
                    value={searchTerm}
                    onChange={(e) => {
                      setSearchTerm(e.target.value);
                    }}
                    onKeyDown={(e) => e.stopPropagation()}
                    autoComplete="off"
                    spellCheck={false}
                    className="input pl-10 text-sm"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Filename Pattern</label>
                <input
                  type="text"
                  placeholder="%.jpg, %.pdf, report%..."
                  value={filenamePattern}
                  onChange={(e) => {
                    setFilenamePattern(e.target.value);
                  }}
                  onKeyDown={(e) => e.stopPropagation()}
                  autoComplete="off"
                  spellCheck={false}
                  className="input text-sm"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Path Pattern</label>
                <input
                  type="text"
                  placeholder="%/Downloads/%, %/Pictures/%..."
                  value={pathPattern}
                  onChange={(e) => {
                    setPathPattern(e.target.value);
                  }}
                  onKeyDown={(e) => e.stopPropagation()}
                  autoComplete="off"
                  spellCheck={false}
                  className="input text-sm"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Min Group Size</label>
                <select
                  value={minGroupSize}
                  onChange={(e) => setMinGroupSize(parseInt(e.target.value))}
                  className="input text-sm"
                >
                  <option value={2}>2+ copies</option>
                  <option value={3}>3+ copies</option>
                  <option value={5}>5+ copies</option>
                  <option value={10}>10+ copies</option>
                  <option value={20}>20+ copies</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Per Page</label>
                <select
                  value={itemsPerPage}
                  onChange={(e) => {
                    setItemsPerPage(parseInt(e.target.value));
                    setCurrentPage(1);
                  }}
                  className="input text-sm"
                >
                  <option value={10}>10</option>
                  <option value={20}>20</option>
                  <option value={50}>50</option>
                  <option value={100}>100</option>
                </select>
              </div>
            </div>

            {/* Size filters row */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Minimum File Size</label>
                <div className="flex space-x-2">
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    placeholder="No limit"
                    value={minFileSize ? formatSizeForInput(minFileSize) : ''}
                    onChange={(e) => {
                      if (!e.target.value) {
                        setMinFileSize(null);
                      } else {
                        const unit = minFileSize && minFileSize >= 1024 * 1024 * 1024 ? 'GB' : 'MB';
                        const size = parseSizeFromInput(e.target.value, unit);
                        setMinFileSize(size);
                      }
                    }}
                    onKeyDown={(e) => e.stopPropagation()}
                    autoComplete="off"
                    className="input text-sm w-24"
                  />
                  <select
                    value={minFileSize && minFileSize >= 1024 * 1024 * 1024 ? 'GB' : 'MB'}
                    onChange={(e) => {
                      if (minFileSize) {
                        const currentValue = formatSizeForInput(minFileSize);
                        const size = parseSizeFromInput(currentValue, e.target.value);
                        setMinFileSize(size);
                      }
                    }}
                    className="input w-16 text-sm"
                  >
                    <option value="MB">MB</option>
                    <option value="GB">GB</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Maximum File Size (Optional)</label>
                <div className="flex space-x-2">
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    placeholder="No limit"
                    value={maxFileSize ? formatSizeForInput(maxFileSize) : ''}
                    onChange={(e) => {
                      if (!e.target.value) {
                        setMaxFileSize(null);
                      } else {
                        const size = parseSizeFromInput(e.target.value, maxFileSize && maxFileSize >= 1024 * 1024 * 1024 ? 'GB' : 'MB');
                        setMaxFileSize(size);
                      }
                    }}
                    onKeyDown={(e) => e.stopPropagation()}
                    autoComplete="off"
                    className="input text-sm w-24"
                  />
                  <select
                    value={maxFileSize && maxFileSize >= 1024 * 1024 * 1024 ? 'GB' : 'MB'}
                    onChange={(e) => {
                      if (maxFileSize) {
                        const currentValue = formatSizeForInput(maxFileSize);
                        const size = parseSizeFromInput(currentValue, e.target.value);
                        setMaxFileSize(size);
                      }
                    }}
                    className="input w-16 text-sm"
                  >
                    <option value="MB">MB</option>
                    <option value="GB">GB</option>
                  </select>
                </div>
              </div>

              <div className="flex items-end">
                <button
                  onClick={applyFilters}
                  className="btn btn-primary text-sm w-full flex items-center justify-center space-x-2"
                >
                  <Search className="h-4 w-4" />
                  <span>Apply Filters</span>
                </button>
              </div>

              <div className="flex items-end">
                <button
                  onClick={resetFilters}
                  className="btn btn-secondary text-sm w-full"
                >
                  Reset Filters
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Enhanced Statistics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="card">
          <div className="flex items-center">
            <div className="p-3 rounded-full bg-gradient-to-r from-orange-500 to-red-500 text-white">
              <Copy className="h-6 w-6" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-600">Duplicate Groups</p>
              <p className="text-2xl font-bold text-gray-900">{totalGroups.toLocaleString()}</p>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center">
            <div className="p-3 rounded-full bg-gradient-to-r from-red-500 to-pink-500 text-white">
              <FileText className="h-6 w-6" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-600">Total Files</p>
              <p className="text-2xl font-bold text-gray-900">{totalDuplicateFiles.toLocaleString()}</p>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center">
            <div className="p-3 rounded-full bg-gradient-to-r from-purple-500 to-indigo-500 text-white">
              <HardDrive className="h-6 w-6" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-600">Wasted Space</p>
              <p className="text-2xl font-bold text-gray-900">{formatFileSize(totalWastedSpace)}</p>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center">
            <div className="p-3 rounded-full bg-gradient-to-r from-green-500 to-teal-500 text-white">
              <Settings className="h-6 w-6" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-600">Showing</p>
              <p className="text-2xl font-bold text-gray-900">{paginatedDuplicates.length}</p>
            </div>
          </div>
        </div>
      </div>

      

      {/* Pagination Controls (Top) */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <div className="text-sm text-gray-600">
            Showing {((currentPage - 1) * itemsPerPage) + 1} to {Math.min(currentPage * itemsPerPage, (currentPage - 1) * itemsPerPage + paginatedDuplicates.length)} of {totalGroups} groups
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
              disabled={currentPage === 1}
              className="btn btn-secondary disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-1"
            >
              <ChevronLeft className="h-4 w-4" />
              <span>Previous</span>
            </button>
            
            <div className="flex items-center space-x-1">
              {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                const page = currentPage <= 3 ? i + 1 : currentPage - 2 + i;
                if (page <= totalPages) {
                  return (
                    <button
                      key={page}
                      onClick={() => setCurrentPage(page)}
                      className={`btn ${page === currentPage ? 'btn-primary' : 'btn-secondary'} w-10 h-10 p-0`}
                    >
                      {page}
                    </button>
                  );
                }
                return null;
              })}
            </div>

            <button
              onClick={() => setCurrentPage(Math.min(totalPages, currentPage + 1))}
              disabled={currentPage === totalPages}
              className="btn btn-secondary disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-1"
            >
              <span>Next</span>
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {/* Duplicate Groups */}
      <div className="space-y-4">
        {paginatedDuplicates.length === 0 ? (
          <div className="text-center py-12">
            <Copy className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <p className="text-gray-500 text-lg">No duplicate files found</p>
            <p className="text-gray-400 text-sm mt-2">
              Try adjusting your filters or search terms
            </p>
          </div>
        ) : (
          paginatedDuplicates.map((group) => {
            const isExpanded = expandedGroups.has(group.checksum);
            const sampleFile = group.files[0];
            const wastedSpaceForGroup = group.wasted_space || (sampleFile.file_size * (group.files.length - 1));

            return (
              <div key={group.checksum} className="card border-l-4 border-l-gradient-to-b from-orange-500 to-red-500">
                <div className="p-6">
                  {/* Header Row */}
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center space-x-4">
                      <div className="text-2xl text-blue-600">
                        {getFileTypeIcon(sampleFile.filename)}
                      </div>
                      <div>
                        <div className="flex items-center space-x-3">
                          <h3 className="font-bold text-gray-900 text-lg">{sampleFile.filename}</h3>
                          <span className="px-3 py-1 bg-gradient-to-r from-orange-500 to-red-500 text-white text-sm rounded-full font-medium shadow-sm">
                            {group.files.length} copies
                          </span>
                        </div>
                        <div className="flex items-center space-x-6 text-sm text-gray-600 mt-2">
                          <span className="flex items-center space-x-2 bg-blue-50 px-2 py-1 rounded">
                            <HardDrive className="h-4 w-4 text-blue-600" />
                            <span className="font-medium">{formatFileSize(sampleFile.file_size)}</span>
                          </span>
                          <span className="flex items-center space-x-2 bg-red-50 px-2 py-1 rounded">
                            <Trash2 className="h-4 w-4 text-red-600" />
                            <span className="font-medium">Wasting {formatFileSize(wastedSpaceForGroup)}</span>
                          </span>
                        </div>
                      </div>
                    </div>
                    <button
                      onClick={() => toggleGroup(group.checksum)}
                      className="btn btn-secondary flex items-center space-x-2"
                    >
                      <span>{isExpanded ? 'Hide' : 'Show'} Files</span>
                      {isExpanded ? (
                        <ChevronUp className="h-4 w-4" />
                      ) : (
                        <ChevronDown className="h-4 w-4" />
                      )}
                    </button>
                  </div>

                  {/* Checksum Row */}
                  <div className="bg-gray-50 rounded-lg p-3 mb-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <span className="text-xs text-gray-500 uppercase tracking-wide font-medium">SHA256 Checksum</span>
                        <div className="font-mono text-sm text-gray-700 mt-1 break-all">
                          {group.checksum}
                        </div>
                      </div>
                      <button
                        onClick={() => copyToClipboard(group.checksum)}
                        className="btn btn-secondary flex items-center space-x-1 ml-4"
                        title="Copy checksum"
                      >
                        <ClipboardCopy className="h-4 w-4" />
                        <span className="hidden sm:inline">Copy</span>
                      </button>
                    </div>
                  </div>

                  {/* File List */}
                  {isExpanded && (
                    <div className="space-y-2">
                      <h4 className="text-sm font-semibold text-gray-800 mb-3 flex items-center">
                        <Folder className="h-4 w-4 mr-2" />
                        All File Locations:
                      </h4>
                      <div className="grid gap-2">
                        {group.files.map((file, index) => (
                          <div
                            key={`${file.path}-${index}`}
                            className="flex items-center justify-between p-3 bg-white border border-gray-200 rounded-lg hover:shadow-md transition-all"
                          >
                            <div className="flex items-center space-x-3 flex-1 min-w-0">
                              <div className="text-gray-400">
                                {getFileTypeIcon(file.filename)}
                              </div>
                              <div className="min-w-0 flex-1">
                                <div className="text-sm font-medium text-gray-900 truncate">
                                  {file.filename}
                                </div>
                                <div className="text-xs text-gray-500 truncate" title={file.path}>
                                  {file.path}
                                </div>
                              </div>
                            </div>
                            <div className="flex items-center space-x-3">
                              <div className="text-xs text-gray-500">
                                {formatDate(file.modification_datetime)}
                              </div>
                              <button
                                onClick={() => copyToClipboard(file.path)}
                                className="p-1 text-gray-400 hover:text-gray-600 transition-colors"
                                title="Copy file path"
                              >
                                <ClipboardCopy className="h-3 w-3" />
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Pagination Controls (Bottom) */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center">
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
              disabled={currentPage === 1}
              className="btn btn-secondary disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-1"
            >
              <ChevronLeft className="h-4 w-4" />
              <span>Previous</span>
            </button>
            
            <div className="flex items-center space-x-1">
              {Array.from({ length: Math.min(7, totalPages) }, (_, i) => {
                let page;
                if (totalPages <= 7) {
                  page = i + 1;
                } else if (currentPage <= 4) {
                  page = i + 1;
                } else if (currentPage >= totalPages - 3) {
                  page = totalPages - 6 + i;
                } else {
                  page = currentPage - 3 + i;
                }
                
                if (page <= totalPages && page > 0) {
                  return (
                    <button
                      key={page}
                      onClick={() => setCurrentPage(page)}
                      className={`btn ${page === currentPage ? 'btn-primary' : 'btn-secondary'} w-10 h-10 p-0`}
                    >
                      {page}
                    </button>
                  );
                }
                return null;
              })}
            </div>

            <button
              onClick={() => setCurrentPage(Math.min(totalPages, currentPage + 1))}
              disabled={currentPage === totalPages}
              className="btn btn-secondary disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-1"
            >
              <span>Next</span>
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}; 