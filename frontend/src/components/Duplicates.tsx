import React, { useState, useEffect } from 'react';
import { FileIndexerAPI } from '../lib/api';
import type { DuplicateGroup } from '../types/api';
import { formatFileSize, formatDate, getFileTypeIcon } from '../lib/utils';
import { Search, AlertTriangle, Copy, Trash2, Folder, ChevronDown, ChevronUp } from 'lucide-react';

export const Duplicates: React.FC = () => {
  const [duplicates, setDuplicates] = useState<DuplicateGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [minGroupSize, setMinGroupSize] = useState(2);
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());

  useEffect(() => {
    loadDuplicates();
  }, [minGroupSize]);

  const loadDuplicates = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await FileIndexerAPI.findDuplicates(minGroupSize);
      setDuplicates(response.duplicate_groups || []);
    } catch (err) {
      setError('Failed to load duplicates');
      console.error('Error loading duplicates:', err);
    } finally {
      setLoading(false);
    }
  };

  const filteredDuplicates = duplicates.filter(group =>
    group.files.some(file => 
      file.filename.toLowerCase().includes(searchTerm.toLowerCase()) ||
      file.path.toLowerCase().includes(searchTerm.toLowerCase())
    )
  );

  const toggleGroup = (checksum: string) => {
    const newExpanded = new Set(expandedGroups);
    if (newExpanded.has(checksum)) {
      newExpanded.delete(checksum);
    } else {
      newExpanded.add(checksum);
    }
    setExpandedGroups(newExpanded);
  };

  const calculateWastedSpace = () => {
    return duplicates.reduce((total, group) => {
      const fileSize = group.files[0]?.file_size || 0;
      return total + (fileSize * (group.files.length - 1));
    }, 0);
  };

  const totalDuplicateFiles = duplicates.reduce((sum, group) => sum + group.files.length, 0);
  const wastedSpace = calculateWastedSpace();

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <AlertTriangle className="h-12 w-12 text-red-500 mx-auto mb-4" />
        <p className="text-red-600 text-lg">{error}</p>
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
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold gradient-text">Duplicate Files</h1>
          <p className="text-gray-600 mt-1">
            Find and manage duplicate files to reclaim storage space
          </p>
        </div>
      </div>

      {/* Statistics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="card bg-gradient-to-br from-orange-50 to-orange-100 border-orange-200">
          <div className="flex items-center">
            <div className="p-3 rounded-full bg-orange-500 text-white">
              <Copy className="h-6 w-6" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-orange-800">Duplicate Groups</p>
              <p className="text-2xl font-bold text-orange-900">{filteredDuplicates.length.toLocaleString()}</p>
            </div>
          </div>
        </div>

        <div className="card bg-gradient-to-br from-red-50 to-red-100 border-red-200">
          <div className="flex items-center">
            <div className="p-3 rounded-full bg-red-500 text-white">
              <Trash2 className="h-6 w-6" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-red-800">Total Duplicates</p>
              <p className="text-2xl font-bold text-red-900">{totalDuplicateFiles.toLocaleString()}</p>
            </div>
          </div>
        </div>

        <div className="card bg-gradient-to-br from-purple-50 to-purple-100 border-purple-200">
          <div className="flex items-center">
            <div className="p-3 rounded-full bg-purple-500 text-white">
              <AlertTriangle className="h-6 w-6" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-purple-800">Wasted Space</p>
              <p className="text-2xl font-bold text-purple-900">{formatFileSize(wastedSpace)}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="card">
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-4 w-4" />
              <input
                type="text"
                placeholder="Search duplicate files..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="input pl-10"
              />
            </div>
          </div>
          <div className="flex items-center gap-2">
            <label className="text-sm font-medium text-gray-700">Min Group Size:</label>
            <select
              value={minGroupSize}
              onChange={(e) => setMinGroupSize(parseInt(e.target.value))}
              className="input w-20"
            >
              <option value={2}>2+</option>
              <option value={3}>3+</option>
              <option value={5}>5+</option>
              <option value={10}>10+</option>
            </select>
          </div>
        </div>
      </div>

      {/* Duplicate Groups */}
      <div className="space-y-4">
        {filteredDuplicates.length === 0 ? (
          <div className="text-center py-12">
            <Copy className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <p className="text-gray-500 text-lg">No duplicate files found</p>
            <p className="text-gray-400 text-sm mt-2">
              {searchTerm ? 'Try adjusting your search terms' : 'Try lowering the minimum group size'}
            </p>
          </div>
        ) : (
          filteredDuplicates.map((group) => {
            const isExpanded = expandedGroups.has(group.checksum);
            const sampleFile = group.files[0];
                         const wastedSpaceForGroup = sampleFile.file_size * (group.files.length - 1);

            return (
              <div key={group.checksum} className="card border-l-4 border-l-orange-500">
                <div
                  className="flex items-center justify-between cursor-pointer"
                  onClick={() => toggleGroup(group.checksum)}
                >
                  <div className="flex items-center space-x-4">
                    <div className="flex items-center text-orange-600">
                      {getFileTypeIcon(sampleFile.filename)}
                    </div>
                    <div>
                      <div className="flex items-center space-x-2">
                        <h3 className="font-medium text-gray-900">{sampleFile.filename}</h3>
                        <span className="px-2 py-1 bg-orange-100 text-orange-800 text-xs rounded-full">
                          {group.files.length} copies
                        </span>
                      </div>
                                             <div className="flex items-center space-x-4 text-sm text-gray-500 mt-1">
                         <span>{formatFileSize(sampleFile.file_size)}</span>
                         <span>•</span>
                         <span>Wasting {formatFileSize(wastedSpaceForGroup)}</span>
                         <span>•</span>
                         <span>Checksum: {group.checksum.slice(0, 8)}...</span>
                       </div>
                    </div>
                  </div>
                  <div className="flex items-center space-x-2">
                    {isExpanded ? (
                      <ChevronUp className="h-5 w-5 text-gray-400" />
                    ) : (
                      <ChevronDown className="h-5 w-5 text-gray-400" />
                    )}
                  </div>
                </div>

                {isExpanded && (
                  <div className="mt-4 space-y-2">
                    {group.files.map((file, index) => (
                      <div
                        key={`${file.path}-${index}`}
                        className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                      >
                        <div className="flex items-center space-x-3">
                          <Folder className="h-4 w-4 text-gray-400" />
                          <div>
                            <div className="text-sm font-medium text-gray-900">{file.filename}</div>
                            <div className="text-xs text-gray-500">{file.path}</div>
                          </div>
                        </div>
                                                 <div className="text-right">
                           <div className="text-sm text-gray-600">{formatFileSize(file.file_size)}</div>
                           <div className="text-xs text-gray-400">{formatDate(file.modification_datetime)}</div>
                         </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}; 