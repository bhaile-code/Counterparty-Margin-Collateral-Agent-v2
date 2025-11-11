/**
 * StatusBadge Component
 *
 * Reusable badge component for displaying status indicators with different colors and sizes.
 * Used for processing status, confidence levels, and other categorical information.
 */

interface StatusBadgeProps {
  variant?: 'success' | 'warning' | 'error' | 'info' | 'neutral';
  size?: 'sm' | 'md' | 'lg';
  children: React.ReactNode;
  className?: string;
}

export function StatusBadge({
  variant = 'neutral',
  size = 'md',
  children,
  className = ''
}: StatusBadgeProps) {
  // Color variants based on design tokens
  const variantClasses = {
    success: 'bg-green-100 text-green-800 border-green-300',
    warning: 'bg-yellow-100 text-yellow-800 border-yellow-300',
    error: 'bg-red-100 text-red-800 border-red-300',
    info: 'bg-blue-100 text-blue-800 border-blue-300',
    neutral: 'bg-gray-100 text-gray-800 border-gray-300'
  };

  // Size variants
  const sizeClasses = {
    sm: 'text-xs px-2 py-0.5',
    md: 'text-sm px-2.5 py-1',
    lg: 'text-base px-3 py-1.5'
  };

  return (
    <span
      className={`
        inline-flex items-center font-medium rounded-full border
        ${variantClasses[variant]}
        ${sizeClasses[size]}
        ${className}
      `.trim()}
    >
      {children}
    </span>
  );
}
