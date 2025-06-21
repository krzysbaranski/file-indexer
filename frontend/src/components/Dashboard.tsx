import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { 
  FileText, 
  HardDrive, 
  Copy, 
  FolderOpen, 
  CheckCircle, 
  XCircle,
  TrendingUp,
  Activity,
  BarChart3
} from 'lucide-react';
import FileIndexerAPI from '../lib/api';
import { formatFileSize, formatNumber } from '../lib/utils';

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
  trend?: string;
}

function StatCard({ title, value, subtitle, icon: Icon, color, trend }: StatCardProps) {
  return (
    <div className="card animate-fade-in">
      <div className="card-content">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-slate-600">{title}</p>
            <p className="text-2xl font-bold text-slate-900">{value}</p>
            {subtitle && (
              <p className="text-sm text-slate-500 mt-1">{subtitle}</p>
            )}
            {trend && (
              <div className="flex items-center mt-2 text-xs text-green-600">
                <TrendingUp className="w-3 h-3 mr-1" />
                {trend}
              </div>
            )}
          </div>
          <div className={`w-12 h-12 rounded-lg flex items-center justify-center ${color}`}>
            <Icon className="w-6 h-6 text-white" />
          </div>
        </div>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['stats'],
    queryFn: FileIndexerAPI.getDatabaseStats,
  });

  const { data: vizData, isLoading: vizLoading } = useQuery({
    queryKey: ['visualization'],
    queryFn: FileIndexerAPI.getVisualizationData,
  });

  if (statsLoading || vizLoading) {
    return (
      <div className="space-y-8">
        <div className="text-center py-12">
          <Activity className="w-8 h-8 mx-auto text-primary-500 animate-spin" />
          <p className="mt-4 text-lg text-slate-600">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  if (!stats || !vizData) {
    return (
      <div className="text-center py-12">
        <XCircle className="w-8 h-8 mx-auto text-red-500" />
        <p className="mt-4 text-lg text-slate-600">Failed to load dashboard data</p>
      </div>
    );
  }

  const duplicateSpaceSavings = stats.duplicate_files > 0 
    ? stats.total_size * (stats.duplicate_files / stats.total_files)
    : 0;

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Header */}
      <div className="text-center">
        <h1 className="text-3xl font-bold gradient-text mb-2">File Index Dashboard</h1>
        <p className="text-slate-600">
          Comprehensive overview of your {formatNumber(stats.total_files)} indexed files
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          title="Total Files"
          value={formatNumber(stats.total_files)}
          subtitle={formatFileSize(stats.total_size)}
          icon={FileText}
          color="bg-gradient-to-r from-blue-500 to-blue-600"
          trend="+12% this month"
        />
        
        <StatCard
          title="Storage Used"
          value={formatFileSize(stats.total_size)}
          subtitle={`Avg: ${formatFileSize(stats.average_file_size)}`}
          icon={HardDrive}
          color="bg-gradient-to-r from-cyan-500 to-cyan-600"
        />
        
        <StatCard
          title="Duplicates Found"
          value={formatNumber(stats.duplicate_files)}
          subtitle={`${stats.duplicate_groups} groups`}
          icon={Copy}
          color="bg-gradient-to-r from-amber-500 to-amber-600"
          trend={`${formatFileSize(duplicateSpaceSavings)} savings`}
        />
        
        <StatCard
          title="Directories"
          value={formatNumber(stats.unique_directories)}
          subtitle="Unique paths"
          icon={FolderOpen}
          color="bg-gradient-to-r from-emerald-500 to-emerald-600"
        />
      </div>

      {/* Checksum Status */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <StatCard
          title="With Checksums"
          value={formatNumber(stats.files_with_checksums)}
          subtitle={`${((stats.files_with_checksums / stats.total_files) * 100).toFixed(1)}% of files`}
          icon={CheckCircle}
          color="bg-gradient-to-r from-green-500 to-green-600"
        />
        
        <StatCard
          title="Without Checksums"
          value={formatNumber(stats.files_without_checksums)}
          subtitle={`${((stats.files_without_checksums / stats.total_files) * 100).toFixed(1)}% of files`}
          icon={XCircle}
          color="bg-gradient-to-r from-red-500 to-red-600"
        />
      </div>

      {/* Additional Info Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="card">
          <div className="card-content text-center">
            <div className="text-3xl font-bold text-blue-600 mb-2">
              {formatFileSize(stats.largest_file_size)}
            </div>
            <p className="text-sm text-gray-600">Largest File</p>
          </div>
        </div>
        
        <div className="card">
          <div className="card-content text-center">
            <div className="text-3xl font-bold text-green-600 mb-2">
              {stats.most_recent_modification 
                ? new Date(stats.most_recent_modification).toLocaleDateString()
                : 'N/A'
              }
            </div>
            <p className="text-sm text-gray-600">Most Recent File</p>
          </div>
        </div>
        
        <div className="card">
          <div className="card-content text-center">
            <div className="text-3xl font-bold text-purple-600 mb-2">
              {((stats.files_with_checksums / stats.total_files) * 100).toFixed(0)}%
            </div>
            <p className="text-sm text-gray-600">Checksum Coverage</p>
          </div>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="card">
        <div className="card-header">
          <h3 className="text-lg font-semibold text-slate-900">Quick Actions</h3>
          <p className="text-sm text-slate-600">What would you like to do?</p>
        </div>
        <div className="card-content">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <button className="btn btn-primary flex items-center justify-center space-x-2 py-3">
              <FileText className="w-4 h-4" />
              <span>Search Files</span>
            </button>
            <button className="btn btn-secondary flex items-center justify-center space-x-2 py-3">
              <Copy className="w-4 h-4" />
              <span>Find Duplicates</span>
            </button>
            <button className="btn btn-secondary flex items-center justify-center space-x-2 py-3">
              <BarChart3 className="w-4 h-4" />
              <span>View Analytics</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
} 