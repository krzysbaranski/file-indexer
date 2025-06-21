import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { format, formatDistanceToNow, parseISO } from 'date-fns';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  
  return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i];
}

export function formatNumber(num: number): string {
  return new Intl.NumberFormat().format(num);
}

export function formatDate(dateString: string): string {
  try {
    const date = parseISO(dateString);
    return format(date, 'MMM d, yyyy');
  } catch {
    return 'Invalid date';
  }
}

export function formatDateTime(dateString: string): string {
  try {
    const date = parseISO(dateString);
    return format(date, 'MMM d, yyyy h:mm a');
  } catch {
    return 'Invalid date';
  }
}

export function formatRelativeTime(dateString: string): string {
  try {
    const date = parseISO(dateString);
    return formatDistanceToNow(date, { addSuffix: true });
  } catch {
    return 'Invalid date';
  }
}

export function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength) + '...';
}

export function getFileExtension(filename: string): string {
  const parts = filename.split('.');
  return parts.length > 1 ? `.${parts[parts.length - 1].toLowerCase()}` : 'No extension';
}

export function calculateSpaceSavings(totalDuplicateSize: number): string {
  // Calculate how much space could be saved by keeping only one copy of each duplicate
  return formatFileSize(totalDuplicateSize);
}

export function getFileTypeIcon(filename: string): string {
  const ext = getFileExtension(filename).toLowerCase();
  
  const icons: Record<string, string> = {
    '.pdf': '📄',
    '.doc': '📝',
    '.docx': '📝',
    '.txt': '📄',
    '.md': '📝',
    '.jpg': '🖼️',
    '.jpeg': '🖼️',
    '.png': '🖼️',
    '.gif': '🖼️',
    '.svg': '🖼️',
    '.mp4': '🎥',
    '.mov': '🎥',
    '.avi': '🎥',
    '.mkv': '🎥',
    '.mp3': '🎵',
    '.wav': '🎵',
    '.flac': '🎵',
    '.zip': '📦',
    '.rar': '📦',
    '.7z': '📦',
    '.tar': '📦',
    '.gz': '📦',
    '.js': '💻',
    '.ts': '💻',
    '.py': '🐍',
    '.java': '☕',
    '.cpp': '💻',
    '.c': '💻',
    '.html': '🌐',
    '.css': '🎨',
    '.json': '📋',
    '.xml': '📋',
    '.csv': '📊',
    '.xlsx': '📊',
    '.xls': '📊',
  };
  
  return icons[ext] || '📄';
} 