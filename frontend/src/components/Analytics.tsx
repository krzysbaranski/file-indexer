import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  LineChart,
  Line,
  Area,
  AreaChart
} from 'recharts';
import { 
  FileText, 
  HardDrive, 
  Database, 
  TrendingUp,
  Calendar,
  Hash
} from 'lucide-react';
import { FileIndexerAPI } from '../lib/api';
import { formatFileSize } from '../lib/utils';

const COLORS = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16'];

export const Analytics: React.FC = () => {
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['database-stats'],
    queryFn: () => FileIndexerAPI.getDatabaseStats(),
  });

  const { data: visualData, isLoading: visualLoading } = useQuery({
    queryKey: ['visualization-data'],
    queryFn: () => FileIndexerAPI.getVisualizationData(),
  });

  const isLoading = statsLoading || visualLoading;

  // Prepare data for charts
  const sizeDistributionData = visualData?.size_distribution?.map(item => ({
    name: item.size_range,
    count: item.count,
    size: item.total_size
  })) || [];

  const extensionData = visualData?.extension_stats?.slice(0, 10).map((item, index) => ({
    name: item.extension || 'No extension',
    count: item.count,
    size: item.total_size,
    fill: COLORS[index % COLORS.length]
  })) || [];

  const monthlyData = visualData?.modification_timeline?.map(item => ({
    month: item.month || 'Unknown',
    count: item.count,
    size: item.total_size
  })) || [];

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-shimmer w-12 h-12 rounded-full"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center">
        <h1 className="text-3xl font-bold gradient-text mb-2">Analytics</h1>
        <p className="text-gray-600">
          Insights and statistics about your file index
        </p>
      </div>

      {/* Key Statistics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="card">
          <div className="flex items-center">
            <div className="p-3 rounded-full bg-gradient-to-r from-blue-500 to-indigo-500 text-white">
              <FileText className="h-6 w-6" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-600">Total Files</p>
              <p className="text-2xl font-bold text-gray-900">
                {stats?.total_files?.toLocaleString() || 0}
              </p>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center">
            <div className="p-3 rounded-full bg-gradient-to-r from-green-500 to-teal-500 text-white">
              <HardDrive className="h-6 w-6" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-600">Total Size</p>
              <p className="text-2xl font-bold text-gray-900">
                {stats?.total_size ? formatFileSize(stats.total_size) : '0 B'}
              </p>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center">
            <div className="p-3 rounded-full bg-gradient-to-r from-purple-500 to-pink-500 text-white">
              <Hash className="h-6 w-6" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-600">With Checksums</p>
              <p className="text-2xl font-bold text-gray-900">
                {stats?.files_with_checksums?.toLocaleString() || 0}
              </p>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center">
            <div className="p-3 rounded-full bg-gradient-to-r from-orange-500 to-red-500 text-white">
              <TrendingUp className="h-6 w-6" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-600">Avg File Size</p>
              <p className="text-2xl font-bold text-gray-900">
                {stats?.average_file_size ? formatFileSize(stats.average_file_size) : '0 B'}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Additional Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="card">
          <div className="card-header">
            <h3 className="text-lg font-semibold text-gray-900 flex items-center">
              <Database className="h-5 w-5 mr-2" />
              Index Statistics
            </h3>
          </div>
          <div className="card-content space-y-3">
            <div className="flex justify-between">
              <span className="text-gray-600">Duplicate Files:</span>
              <span className="font-medium">{stats?.duplicate_files?.toLocaleString() || 0}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Duplicate Groups:</span>
              <span className="font-medium">{stats?.duplicate_groups?.toLocaleString() || 0}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Unique Directories:</span>
              <span className="font-medium">{stats?.unique_directories?.toLocaleString() || 0}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Largest File:</span>
              <span className="font-medium">
                {stats?.largest_file_size ? formatFileSize(stats.largest_file_size) : '0 B'}
              </span>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <h3 className="text-lg font-semibold text-gray-900 flex items-center">
              <Calendar className="h-5 w-5 mr-2" />
              Timeline
            </h3>
          </div>
          <div className="card-content space-y-3">
            <div className="flex justify-between">
              <span className="text-gray-600">Most Recent:</span>
              <span className="font-medium text-sm">
                {stats?.most_recent_modification 
                  ? new Date(stats.most_recent_modification).toLocaleDateString()
                  : 'N/A'
                }
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Oldest:</span>
              <span className="font-medium text-sm">
                {stats?.oldest_modification 
                  ? new Date(stats.oldest_modification).toLocaleDateString()
                  : 'N/A'
                }
              </span>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <h3 className="text-lg font-semibold text-gray-900">Checksum Coverage</h3>
          </div>
          <div className="card-content">
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span>With Checksums</span>
                <span>{stats?.files_with_checksums?.toLocaleString() || 0}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span>Without Checksums</span>
                <span>{stats?.files_without_checksums?.toLocaleString() || 0}</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2 mt-3">
                <div 
                  className="bg-gradient-to-r from-green-500 to-teal-500 h-2 rounded-full"
                  style={{
                    width: stats?.total_files 
                      ? `${(stats.files_with_checksums / stats.total_files) * 100}%`
                      : '0%'
                  }}
                ></div>
              </div>
              <p className="text-xs text-gray-500 text-center">
                {stats?.total_files 
                  ? `${((stats.files_with_checksums / stats.total_files) * 100).toFixed(1)}% coverage`
                  : '0% coverage'
                }
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Charts */}
      <div className="space-y-6">
        {/* Monthly File Activity */}
        <div className="card">
          <div className="card-header">
            <h3 className="text-lg font-semibold text-gray-900">Monthly File Activity</h3>
          </div>
          <div className="card-content">
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={monthlyData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="month" fontSize={12} />
                <YAxis fontSize={12} />
                <Tooltip 
                  formatter={(value, name) => [
                    name === 'count' ? value.toLocaleString() : formatFileSize(value as number),
                    name === 'count' ? 'Files Modified' : 'Total Size'
                  ]}
                />
                <Area 
                  type="monotone" 
                  dataKey="count" 
                  stroke="#3b82f6" 
                  fill="#3b82f6" 
                  fillOpacity={0.3}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* File Size Distribution */}
          <div className="card">
            <div className="card-header">
              <h3 className="text-lg font-semibold text-gray-900">File Size Distribution</h3>
            </div>
            <div className="card-content">
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={sizeDistributionData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" fontSize={12} />
                  <YAxis fontSize={12} />
                  <Tooltip 
                    formatter={(value, name) => [
                      name === 'count' ? value.toLocaleString() : formatFileSize(value as number),
                      name === 'count' ? 'Files' : 'Total Size'
                    ]}
                  />
                  <Bar dataKey="count" fill="#3b82f6" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Top File Extensions */}
          <div className="card">
            <div className="card-header">
              <h3 className="text-lg font-semibold text-gray-900">Top File Extensions</h3>
            </div>
            <div className="card-content">
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={extensionData}
                    cx="50%"
                    cy="50%"
                    outerRadius={80}
                    dataKey="count"
                    label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                    fontSize={12}
                  >
                    {extensionData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.fill} />
                    ))}
                  </Pie>
                  <Tooltip 
                    formatter={(value) => [value.toLocaleString(), 'Files']}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}; 