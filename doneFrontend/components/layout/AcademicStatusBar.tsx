// components/layout/AcademicStatusBar.tsx - Only shows when setup incomplete
'use client'

import { useEffect, useState, useRef } from 'react'
import { academicStatusService, type AcademicStatus } from '@/services/academic-status'
import { AlertCircle, Settings } from 'lucide-react'
import Link from 'next/link'

export default function AcademicStatusBar() {
  const [status, setStatus] = useState<AcademicStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [collapsed, setCollapsed] = useState(false)
  const refreshTimeoutRef = useRef<NodeJS.Timeout>()

  // Initial load and periodic refresh
  useEffect(() => {
    loadStatus()
    
    // Refresh status every 5 minutes
    const interval = setInterval(loadStatus, 5 * 60 * 1000)
    return () => clearInterval(interval)
  }, [])

  // Listen for status updates from other components with debouncing
  useEffect(() => {
    const handleStatusUpdate = () => {
      if (refreshTimeoutRef.current) {
        clearTimeout(refreshTimeoutRef.current)
      }
      
      refreshTimeoutRef.current = setTimeout(() => {
        console.log('AcademicStatusBar: Refreshing after chat activity')
        loadStatus()
      }, 500)
    }

    window.addEventListener('academic-status-updated', handleStatusUpdate)
    
    return () => {
      window.removeEventListener('academic-status-updated', handleStatusUpdate)
      if (refreshTimeoutRef.current) {
        clearTimeout(refreshTimeoutRef.current)
      }
    }
  }, [])

  async function loadStatus() {
    try {
      const data = await academicStatusService.getStatus()
      setStatus(data)
    } catch (error) {
      console.error('Failed to load academic status:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="border-b border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-900/50">
        <div className="px-4 py-2">
          <div className="h-5 w-64 bg-neutral-200 dark:bg-neutral-800 animate-pulse rounded" />
        </div>
      </div>
    )
  }

  if (!status) return null

  const hasWarnings = status.warnings.length > 0
  const isSetupComplete = status.setup_complete

  // HIDE COMPLETELY when setup is complete
  if (isSetupComplete && !hasWarnings) {
    return null
  }

  // WARNING VERSION: Only shows when setup incomplete or has warnings
  return (
    <div className="border-b border-neutral-200 dark:border-neutral-800 bg-amber-50 dark:bg-amber-950/20">
      <div className="px-4 py-2 flex items-center justify-between gap-4">
        {/* Left: Academic Info with Warnings */}
        <div className="flex items-center gap-4 text-sm flex-1 min-w-0">
          {/* Academic Year */}
          <div className="flex items-center gap-2">
            <span className="text-neutral-600 dark:text-neutral-400 font-medium">
              Academic Year:
            </span>
            <span className="font-semibold text-neutral-900 dark:text-neutral-100">
              {status.academic_year?.name || 'Not Set'}
            </span>
            {status.academic_year?.state && status.academic_year.state !== 'ACTIVE' && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400">
                {status.academic_year.state}
              </span>
            )}
          </div>

          {/* Divider */}
          <div className="h-4 w-px bg-neutral-300 dark:bg-neutral-700" />

          {/* Active Term */}
          <div className="flex items-center gap-2">
            <span className="text-neutral-600 dark:text-neutral-400 font-medium">
              Term:
            </span>
            <span className="font-semibold text-neutral-900 dark:text-neutral-100">
              {status.active_term?.name || 'None Active'}
            </span>
            {status.active_term?.state && status.active_term.state !== 'ACTIVE' && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400">
                {status.active_term.state}
              </span>
            )}
          </div>

          {/* Status Indicator */}
          <div className="flex items-center gap-1.5">
            <AlertCircle className="w-4 h-4 text-amber-600 dark:text-amber-400" />
            <span className="text-amber-700 dark:text-amber-400 text-xs font-medium">
              Setup Required
            </span>
          </div>

          {/* Warnings Toggle */}
          {hasWarnings && (
            <button
              onClick={() => setCollapsed(!collapsed)}
              className="text-xs text-amber-700 dark:text-amber-400 hover:underline ml-2"
              aria-label={collapsed ? 'Show issues' : 'Hide issues'}
            >
              {collapsed 
                ? `Show ${status.warnings.length} issue${status.warnings.length !== 1 ? 's' : ''}` 
                : 'Hide issues'
              }
            </button>
          )}
        </div>

        {/* Right: Settings Link */}
        <Link
          href="/settings/academic"
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-amber-100 dark:bg-amber-900/30 hover:bg-amber-200 dark:hover:bg-amber-900/50 transition-colors text-sm font-medium text-amber-900 dark:text-amber-100"
          aria-label="Fix Setup Issues"
        >
          <Settings className="w-4 h-4" />
          <span className="hidden sm:inline">Fix Setup</span>
        </Link>
      </div>

      {/* Warning Messages - Expandable */}
      {hasWarnings && !collapsed && (
        <div className="px-4 pb-2 pt-1 space-y-1 border-t border-amber-200 dark:border-amber-900/30">
          {status.warnings.map((warning, index) => (
            <div key={index} className="text-xs text-amber-700 dark:text-amber-300 flex items-start gap-2">
              <AlertCircle className="w-3 h-3 mt-0.5 flex-shrink-0" />
              <span>{warning}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}